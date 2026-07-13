import os
import sys
import torch
import cv2
import mediapipe as mp
import numpy as np
from model_tcn import Temporal3DRefinementNet
from exercise_config import FIT3D_JOINT_MAP

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

class MP_POSE_ENUM:
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

class MP_POSE:
    PoseLandmark = MP_POSE_ENUM

TCN_MODEL = None
TCN_WINDOW_SIZE = 81

def load_tcn_model(model_path=None):
    global TCN_MODEL
    if model_path is None:
        _here = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(_here, "..", "Models", "best_tcn_model.pt")
    model_path = os.path.abspath(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = Temporal3DRefinementNet(num_joints_in=33, num_joints_out=25)
    
    # Handle both full state_dict and jit or path issues
    if os.path.exists(model_path):
        state_dict = torch.load(model_path, map_location=device)
        # Handle "compiled" models or different state_dict structures
        new_state_dict = {}
        for k, v in state_dict.items():
            name = k.replace('_orig_mod.', '') # Remove torch.compile prefix if present
            new_state_dict[name] = v
        model.load_state_dict(new_state_dict)
        model.to(device)
        model.eval()
        TCN_MODEL = model
        print(f"TCN model loaded from {model_path}")
    else:
        print(f"Warning: TCN model not found at {model_path}. Performance will be degraded.")

def get_landmark_coords_from_fit3d(refined_pose, joint_name, side):
    """Returns (x, y, z) from refined 25-joint pose."""
    if joint_name.lower() in ['vertical', 'horizontal']:
        return joint_name.lower()
    
    indices = FIT3D_JOINT_MAP.get(joint_name.lower())
    if indices is None:
        return None
    
    idx = indices[0] if side.upper() == 'LEFT' else indices[1]
    if idx is None:
        return None
        
    return refined_pose[idx]

def process_video(args, frame_skip=0, frame_callback=None):
    global TCN_MODEL
    if TCN_MODEL is None:
        load_tcn_model()

    if len(args) == 4:
        video_path, exercise_name, metric_configs, fs = args
        if frame_skip == 0:
            frame_skip = fs
    else:
        video_path, exercise_name, metric_configs = args

    if not os.path.exists(video_path):
        return None

    cap = cv2.VideoCapture(video_path)
    base_options = mp_python.BaseOptions(model_asset_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Models', 'pose_landmarker_full.task')))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        output_segmentation_masks=False)
    mp_pose = vision.PoseLandmarker.create_from_options(options)
    
    collected_values = {name: {'left': [], 'right': []} for name in metric_configs}
    
    # Buffer for TCN: stores (33, 3) raw world landmarks
    landmark_buffer = []
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    mid_idx = TCN_WINDOW_SIZE // 2

    raw_frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        raw_frame_idx += 1
        if frame_skip > 0 and raw_frame_idx % (frame_skip + 1) != 0:
            continue

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        results = mp_pose.detect(mp_image)

        if results.pose_world_landmarks and len(results.pose_world_landmarks) > 0:
            current_raw = np.array([[lm.x, lm.y, lm.z] for lm in results.pose_world_landmarks[0]])
            landmark_buffer.append(current_raw)
        else:
            # Pad with last valid or zeros
            last = landmark_buffer[-1] if landmark_buffer else np.zeros((33, 3))
            landmark_buffer.append(last)

        # Maintain buffer size
        if len(landmark_buffer) > TCN_WINDOW_SIZE:
            landmark_buffer.pop(0)

        # We need a full window for TCN, or we pad for initial frames
        if TCN_MODEL and len(landmark_buffer) > 0:
            # Padding for short/start sequences
            if len(landmark_buffer) < TCN_WINDOW_SIZE:
                pad_left = TCN_WINDOW_SIZE - len(landmark_buffer)
                window = np.pad(landmark_buffer, ((pad_left, 0), (0, 0), (0, 0)), mode='edge')
            else:
                window = np.array(landmark_buffer)

            # Pre-feed to TCN
            with torch.no_grad():
                # 1. Normalization: Root-relative (centered on hips)
                # MP Joints 23 (L Hip), 24 (R Hip)
                mp_root = (window[:, 23, :] + window[:, 24, :]) / 2.0
                norm_window = window - mp_root[:, np.newaxis, :]
                
                # 2. Sequence-level scale normalization (median spine length)
                # MP Joints 11 (L Shoulder), 12 (R Shoulder)
                mp_shoulders = (norm_window[:, 11, :] + norm_window[:, 12, :]) / 2.0
                mp_spine_len_all = np.linalg.norm(mp_shoulders, axis=-1)
                mp_spine_len_median = max(1e-5, float(np.median(mp_spine_len_all)))
                
                norm_window = norm_window / mp_spine_len_median
                
                tens = torch.from_numpy(norm_window).float().unsqueeze(0).to(device)
                refined_full = TCN_MODEL(tens).squeeze(0).cpu().numpy() # (T, 25, 3)
                
                # 3. Unscale to restore original metric space
                refined_full = refined_full * mp_spine_len_median
                
                refined_pose = refined_full[mid_idx if len(landmark_buffer) >= TCN_WINDOW_SIZE else -1]
                
            frame_metrics = {}
            # Compute metrics using the refined Pose (25 joints)
            for metric_name, config in metric_configs.items():
                joints = config.get('joints', [])
                metric_type = config.get('type', 'angle')
                
                for side in ['LEFT', 'RIGHT']:
                    points = []
                    valid = True
                    for j in joints:
                        p = get_landmark_coords_from_fit3d(refined_pose, j, side)
                        if p is None:
                            valid = False; break
                        points.append(p)
                    
                    if not valid: continue
                    
                    value = None
                    if metric_type == 'angle' and len(points) == 3:
                        # Follow notebook calculate_angle_3d logic
                        a, b, c = points[0], points[1], points[2]
                        if isinstance(a, str): # vertical/horizontal
                            a = np.array([b[0], b[1] - 0.5, b[2]]) if a == 'vertical' else np.array([b[0] + 0.5, b[1], b[2]])
                        if isinstance(c, str):
                            c = np.array([b[0], b[1] - 0.5, b[2]]) if c == 'vertical' else np.array([b[0] + 0.5, b[1], b[2]])
                        
                        ba = a - b
                        bc = c - b
                        n1, n2 = np.linalg.norm(ba), np.linalg.norm(bc)
                        if n1 > 1e-6 and n2 > 1e-6:
                            cos_a = np.dot(ba, bc) / (n1 * n2)
                            value = np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0)))
                            
                    elif metric_type == 'horizontal_distance' and len(points) >= 2:
                        value = np.abs(points[0][0] - points[1][0]) / 0.5 # Normalization placeholder
                    elif metric_type == 'vertical_distance' and len(points) >= 2:
                        value = np.abs(points[0][1] - points[1][1]) / 0.5
                    elif metric_type == 'distance_from_line' and len(points) == 3:
                        p0, p1, p2 = points[0], points[1], points[2]
                        value = np.linalg.norm(np.cross(p1 - p0, p0 - p2)) / np.linalg.norm(p1 - p0)
                    
                    if value is not None:
                        frame_metrics[f"{metric_name}_{side.lower()}"] = value

            if frame_metrics:
                for k, v in frame_metrics.items():
                    name, side = k.rsplit('_', 1)
                    if name in collected_values:
                        collected_values[name][side].append(v)

            if frame_callback:
                valid_results = results if (hasattr(results, 'pose_world_landmarks') and results.pose_world_landmarks and len(results.pose_world_landmarks) > 0) else None
                if frame_callback(frame, frame_metrics if frame_metrics else None, valid_results) is False:
                    break

    cap.release()
    has_data = any(any(s) for m in collected_values.values() for s in m.values())
    
    if not has_data: return None
    
    result = {'video': os.path.basename(video_path), 'exercise': exercise_name}
    for m, sides in collected_values.items():
        for side, vals in sides.items():
            if vals:
                result[f"{m}_{side}_min"] = float(np.percentile(vals, 5))
                result[f"{m}_{side}_max"] = float(np.percentile(vals, 95))
    return result