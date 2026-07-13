import os
import json
import argparse
import numpy as np
import cv2
from pathlib import Path
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

SUBJECTS: list  = []   # empty = auto-discover all subjects in the split folder
PADDING_ALPHA   = 0.15
PERSON_CLASS_ID = 0
SPLIT           = "train"


def project_3d_to_2d_batch(points3d: np.ndarray, cam_params: dict) -> np.ndarray:
    f = cam_params["f"]
    c = cam_params["c"]
    cam_matrix = np.array([[f[0], 0, c[0]], [0, f[1], c[1]], [0, 0, 1]], dtype=np.float64)
    if "k" in cam_params and "p" in cam_params:
        k = cam_params["k"]
        p = cam_params["p"]
        dist_coeffs = np.array([k[0], k[1], p[0], p[1], k[2]], dtype=np.float64)  # k1,k2,p1,p2,k3
    else:
        dist_coeffs = np.zeros(5, dtype=np.float64)
    rvec = np.zeros((3, 1), dtype=np.float64)
    tvec = np.zeros((3, 1), dtype=np.float64)
    pts2d, _ = cv2.projectPoints(points3d.reshape(-1, 3).astype(np.float64), rvec, tvec, cam_matrix, dist_coeffs)
    return pts2d.reshape(points3d.shape[:-1] + (2,))


def joints2d_to_yolo(joints2d: np.ndarray, img_w: int, img_h: int, alpha: float = PADDING_ALPHA) -> dict:
    u, v = joints2d[:, 0], joints2d[:, 1]
    x_min, x_max = float(np.min(u)), float(np.max(u))
    y_min, y_max = float(np.min(v)), float(np.max(v))
    dx, dy = x_max - x_min, y_max - y_min
    x_min_p = max(0.0,         x_min - dx * alpha)
    x_max_p = min(float(img_w), x_max + dx * alpha)
    y_min_p = max(0.0,         y_min - dy * alpha)
    y_max_p = min(float(img_h), y_max + dy * alpha)
    box_w, box_h = x_max_p - x_min_p, y_max_p - y_min_p
    if box_w <= 0 or box_h <= 0:
        return None
    return {
        "x_center": round((x_min_p + x_max_p) / 2.0 / img_w, 6),
        "y_center": round((y_min_p + y_max_p) / 2.0 / img_h, 6),
        "width":    round(box_w / img_w, 6),
        "height":   round(box_h / img_h, 6),
    }


def get_image_size(cam_params: dict, video_path: str):
    for key in ("res", "resolution", "image_size"):
        if key in cam_params:
            v = cam_params[key]
            return int(v[0]), int(v[1])
    cap = cv2.VideoCapture(video_path)
    if cap.isOpened():
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if w > 0 and h > 0:
            return w, h
    return 900, 900  # Fit3D default fallback


def safe_write(path: str, content: str = ""):
    import time
    for _ in range(5):
        try:
            with open(path, "w") as f:
                f.write(content)
            return
        except OSError:
            time.sleep(0.1)
    with open(path, "w") as f:
        f.write(content)

def process_action_camera(dataset_root: str, subj: str, action: str, cam_id: str, out_dir: Path):
    base = Path(dataset_root) / SPLIT / subj

    j3d_path = base / "joints3d_25" / f"{action}.json"
    if not j3d_path.exists():
        return f"  [SKIP] {j3d_path.name} not found"
    
    with open(j3d_path) as f:
        j3d_data = json.load(f)
    j3ds = np.array(j3d_data.get("joints3d_25", list(j3d_data.values())[0]) if isinstance(j3d_data, dict) else j3d_data)

    cam_path = base / "camera_parameters" / str(cam_id) / f"{action}.json"
    if not cam_path.exists():
        return f"  [SKIP] camera params not found for {action}/{cam_id}"
    
    with open(cam_path) as f:
        cam_raw = json.load(f)
    cam_params = (cam_raw.get("intrinsics_wo_distortion")
                  or cam_raw.get("intrinsics_w_distortion")
                  or cam_raw)

    video_path = str(base / "videos" / str(cam_id) / f"{action}.mp4")
    img_w, img_h = get_image_size(cam_params, video_path)

    T = j3ds.shape[0]
    action_out_dir = out_dir / str(cam_id) / action
    action_out_dir.mkdir(parents=True, exist_ok=True)

    valid_count: int = 0
    existing_files = set(os.listdir(action_out_dir))
    action_out_dir_str = str(action_out_dir)

    # Fast skip if already fully processed
    if len(existing_files) >= T:
        if all(f"frame_{idx:06d}.txt" in existing_files for idx in range(T)):
            return f"  [SKIP]  {subj}/{action} cam={cam_id}  (already done)"

    pts2d_all = project_3d_to_2d_batch(j3ds, cam_params)

    for frame_idx in range(T):
        txt_name = f"frame_{frame_idx:06d}.txt"
        if txt_name in existing_files:
            continue
            
        txt_file_path = os.path.join(action_out_dir_str, txt_name)
        
        joints_3d = j3ds[frame_idx]
        valid_mask = joints_3d[:, 2] != 0  # drop Z=0 (occluded) joints

        if valid_mask.sum() < 2:
            safe_write(txt_file_path, "")
            continue

        valid_joints_2d = pts2d_all[frame_idx][valid_mask]
        yolo_box = joints2d_to_yolo(valid_joints_2d, img_w, img_h)
        
        if yolo_box is None:
            safe_write(txt_file_path, "")
        else:
            safe_write(txt_file_path, f"{PERSON_CLASS_ID} {yolo_box['x_center']} {yolo_box['y_center']} "
                                      f"{yolo_box['width']} {yolo_box['height']}")
            valid_count += 1

    return f"  [OK]  {subj}/{action} cam={cam_id}  {T} frames  ({valid_count} labelled)"


def main(dataset_root: str, out_root: str):
    base_path = Path(dataset_root) / SPLIT
    out_base_path = Path(out_root) / SPLIT
    subjects  = SUBJECTS if SUBJECTS else sorted(d.name for d in base_path.iterdir() if d.is_dir())

    print(f"Root: {dataset_root}  |  Out: {out_root}  |  Split: {SPLIT}  |  Subjects: {subjects}  |  α={PADDING_ALPHA}")
    print("=" * 60)

    tasks: list[tuple[str, str, str, str, Path]] = []
    for subj in subjects:
        subj_path = base_path / subj
        if not subj_path.exists():
            print(f"[WARN] {subj_path} not found, skipping.")
            continue

        out_dir  = out_base_path / subj / "BB (Not Original)"
        j3d_dir  = subj_path / "joints3d_25"
        if not j3d_dir.exists():
            print(f"[WARN] joints3d_25 missing for {subj}, skipping.")
            continue

        action_files = sorted(j3d_dir.glob("*.json"))
        print(f"\n{subj}: {len(action_files)} action(s)")

        cam_params_dir = subj_path / "camera_parameters"
        if not cam_params_dir.exists():
            print(f"  [SKIP] No camera_parameters dir for {subj}")
            continue

        for j3d_file in action_files:
            action  = j3d_file.stem
            cam_ids = sorted(d.name for d in cam_params_dir.iterdir()
                             if d.is_dir() and (d / f"{action}.json").exists())
            if not cam_ids:
                print(f"  [SKIP] No cameras for {action}")
                continue
            for cam_id in cam_ids:
                tasks.append((dataset_root, subj, action, cam_id, out_dir))

    print(f"\nCollected {len(tasks)} tasks.")
    print("Starting parallel processing...")
    
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_action_camera, task[0], task[1], task[2], task[3], task[4]): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Actions/Cameras"):
            try:
                future.result()
            except Exception as e:
                import traceback
                task = futures[future]
                tqdm.write(f"[ERROR] Task failed for {task[1]}/{task[2]} cam={task[3]}:\n{traceback.format_exc()}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fit3D joints3d_25 → YOLO .txt labels")
    parser.add_argument("--dataset_root", default="G:/My Drive/GP Datasets/fit3d_data",
                        help="Folder containing train/, test/, etc.")
    parser.add_argument("--out_dir", default="d:/GP/Pose/YOLO_Labels_Temp",
                        help="Fast local folder to write the output BB labels before moving to GDrive")
    parser.add_argument("--subjects", nargs="+", default=[],
                        help="Subjects to process (default: all in split folder).")
    parser.add_argument("--alpha", type=float, default=PADDING_ALPHA,
                        help="Bounding-box padding factor (default: 0.15).")
    args = parser.parse_args()
    SUBJECTS[:] = args.subjects
    PADDING_ALPHA = args.alpha
    main(args.dataset_root, args.out_dir)
