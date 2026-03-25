import os
import cv2
import numpy as np
import mediapipe as mp
import process_video as pv
from exercise_config import EXERCISE_TO_CONFIG, JOINT_DEFINITIONS


def get_inference(video_path, exercise_name, headless=False, frame_skip=2):
    if exercise_name not in EXERCISE_TO_CONFIG:
        print(f"No configuration data for {exercise_name}")
        return 0, 0, {}, 0

    ex_config = EXERCISE_TO_CONFIG[exercise_name]
    metric_keys = ex_config.get('metrics', [])
    ref = ex_config.get('thresholds', {})
    metric_configs = {m: JOINT_DEFINITIONS[m] for m in metric_keys if m in JOINT_DEFINITIONS}

    if not headless:
        print(f"Testing {exercise_name}...")
        print(f"Source: {ex_config.get('source', 'Unknown')}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return 0, 0, {}, 0
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_delay = int(1000 / fps) if fps > 0 else 33
    cap.release()

    if not headless:
        print(f"Total frames: {total_frames}")
        print("Press 'q' to quit, 'p' to pause/resume")
        print("=" * 50)

    min_height = 360
    scaled_w, scaled_h = orig_w, orig_h
    if orig_h > 0 and orig_h < min_height:
        scale = min_height / orig_h
        scaled_w = int(orig_w * scale)
        scaled_h = int(orig_h * scale)

    # Pre-compute bar width to keep it fixed from frame 1
    _all_possible_msgs = []
    for mc in metric_configs.values():
        for side in ['LEFT', 'RIGHT']:
            if mc.get('message_high'):
                _all_possible_msgs.append(f"[{side}] {mc['message_high']}")
            if mc.get('message_low'):
                _all_possible_msgs.append(f"[{side}] {mc['message_low']}")

    _scale_factor = max(scaled_w / 800.0, scaled_h / 720.0) if scaled_h > 0 and scaled_w > 0 else 1.0
    _pre_font_scale = max(0.4, 0.7 * _scale_factor)
    _pre_thick = max(1, int(2 * _scale_factor))
    _pre_width = scaled_w

    _status_font_scale = max(0.5, 1.2 * _scale_factor)
    _status_thick = max(1, int(3 * _scale_factor))
    _status_w = max(
        cv2.getTextSize("GOOD FORM", cv2.FONT_HERSHEY_SIMPLEX, _status_font_scale, _status_thick)[0][0],
        cv2.getTextSize("FIX FORM", cv2.FONT_HERSHEY_SIMPLEX, _status_font_scale, _status_thick)[0][0]
    )

    _ex_font_scale = max(0.4, 0.7 * _scale_factor)
    _ex_thick = max(1, int(2 * _scale_factor))
    _ex_w = cv2.getTextSize(exercise_name.upper(), cv2.FONT_HERSHEY_SIMPLEX, _ex_font_scale, _ex_thick)[0][0]

    _prog_font_scale = max(0.45, 0.6 * _scale_factor)
    _prog_thick = max(1, int(1 * _scale_factor))
    _prog_w = cv2.getTextSize("Time: 999.9s / 999.9s", cv2.FONT_HERSHEY_SIMPLEX, _prog_font_scale, _prog_thick)[0][0]

    _rep_font_scale = max(0.5, 1.2 * _scale_factor)
    _rep_thick = max(1, int(3 * _scale_factor))
    _rep_w = cv2.getTextSize("REPS: 999", cv2.FONT_HERSHEY_SIMPLEX, _rep_font_scale, _rep_thick)[0][0]

    _pre_width = max(_pre_width, _status_w + _ex_w + 60, _prog_w + 40, _rep_w + 40)

    for _msg in _all_possible_msgs:
        _tw = cv2.getTextSize(_msg, cv2.FONT_HERSHEY_SIMPLEX, _pre_font_scale, _pre_thick)[0][0]
        _pre_width = max(_pre_width, _tw + 40)

    # Rep counting: the first angle metric in the config is the primary rep metric
    _rep_metric = None
    _rep_low_thresh = None
    _rep_high_thresh = None
    for _m, _mdef in metric_configs.items():
        if _mdef.get('type', 'angle') == 'angle' and ref.get(f"{_m}_min") is not None:
            _r_min = ref[f"{_m}_min"]
            _r_max = ref[f"{_m}_max"]
            _span = _r_max - _r_min
            if _span > 0:
                _rep_metric = _m
                _rep_low_thresh = _r_min + 0.4 * _span
                _rep_high_thresh = _r_max - 0.4 * _span
            break

    state = {
        'paused': False,
        'frame_count': 0,
        'quit': False,
        'headless': headless,
        'feedbacks': {},
        'bar_width': _pre_width if _pre_width > 0 else None,
        'window_created': False,
        'rep_count': 0,
        'rep_phase': {'left': 'extended', 'right': 'extended'},
        'rep_side_counts': {'left': 0, 'right': 0},
        'rep_metric': _rep_metric,
        'rep_low_thresh': _rep_low_thresh,
        'rep_high_thresh': _rep_high_thresh,
    }

    def frame_callback(frame, current_metrics, results):
        if state['quit']:
            return False

        state['frame_count'] += (frame_skip + 1)
        if state['frame_count'] > total_frames:
            state['frame_count'] = total_frames

        active_sides = get_active_sides(results)

        is_good_form, feedback_messages, bad_joints = evaluate_metrics(
            current_metrics, metric_configs, ref, state, active_sides
        )

        if current_metrics:
            update_rep_count(current_metrics, state, active_sides)

        if state['headless']:
            return True

        display_frame = frame.copy()

        h, w = display_frame.shape[:2]
        if h < min_height:
            scale = min_height / h
            display_frame = cv2.resize(display_frame, (int(w * scale), int(h * scale)))

        h, w = display_frame.shape[:2]
        draw_skeleton(display_frame, results, metric_configs, bad_joints, active_sides)

        composite, bar_h, state['bar_width'] = create_info_bar(display_frame, w, h, feedback_messages, fixed_width=state['bar_width'])

        draw_overlays(
            composite,
            exercise_name,
            is_good_form,
            state['frame_count'],
            total_frames,
            fps,
            feedback_messages,
            bar_h=bar_h,
            rep_count=state['rep_count']
        )

        try:
            window_name = f'Exercise Form Check - {exercise_name}'
            if not state['window_created']:
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                ch, cw = composite.shape[:2]
                target_height = min(ch, 700)
                target_width = int(cw * (target_height / ch))
                cv2.resizeWindow(window_name, target_width, target_height)
                state['window_created'] = True

            cv2.imshow(window_name, composite)

            while True:
                key = cv2.waitKey(frame_delay) & 0xFF
                if key == ord('q'):
                    state['quit'] = True
                    return False
                elif key == ord('p'):
                    state['paused'] = not state['paused']
                    if state['paused']:
                        print("Paused. Press 'p' to resume.")

                if not state['paused']:
                    break
        except cv2.error:
            if state['frame_count'] <= (frame_skip + 1):
                print("Note: Graphical display not supported. Running analysis silently...")
            state['headless'] = True

        return True

    result = pv.process_video((video_path, exercise_name, metric_configs), frame_skip=frame_skip, frame_callback=frame_callback)
    cv2.destroyAllWindows()

    if not result:
        if not headless:
            print("Could not process video or processing stopped early.")
        return 0, 0, {}, 0

    if not headless:
        print("\n--- Overall Analysis Results ---")
        format_feedback_summary(state['feedbacks'], fps, frame_skip=frame_skip)

    bad_frames = set()
    frame_details = {}
    for msg, instances in state['feedbacks'].items():
        for inst in instances:
            f = inst['frame']
            bad_frames.add(f)
            frame_details.setdefault(f, []).append(msg)

    return state['frame_count'], len(bad_frames), frame_details, state['rep_count']


def get_active_sides(results):
    if not (results and hasattr(results, 'pose_landmarks') and results.pose_landmarks):
        return ['left', 'right']

    vis_landmarks = results.pose_landmarks.landmark

    # Use world landmarks for metric depth if available; else fall back to image landmarks
    if results.pose_world_landmarks:
        depth_landmarks = results.pose_world_landmarks.landmark
    else:
        depth_landmarks = vis_landmarks

    left_z = (depth_landmarks[pv.MP_POSE.PoseLandmark.LEFT_SHOULDER].z +
               depth_landmarks[pv.MP_POSE.PoseLandmark.LEFT_HIP].z) / 2.0

    right_z = (depth_landmarks[pv.MP_POSE.PoseLandmark.RIGHT_SHOULDER].z +
                depth_landmarks[pv.MP_POSE.PoseLandmark.RIGHT_HIP].z) / 2.0

    left_vis = (vis_landmarks[pv.MP_POSE.PoseLandmark.LEFT_SHOULDER].visibility +
                vis_landmarks[pv.MP_POSE.PoseLandmark.LEFT_HIP].visibility +
                vis_landmarks[pv.MP_POSE.PoseLandmark.LEFT_ELBOW].visibility +
                vis_landmarks[pv.MP_POSE.PoseLandmark.LEFT_KNEE].visibility) / 4.0

    right_vis = (vis_landmarks[pv.MP_POSE.PoseLandmark.RIGHT_SHOULDER].visibility +
                 vis_landmarks[pv.MP_POSE.PoseLandmark.RIGHT_HIP].visibility +
                 vis_landmarks[pv.MP_POSE.PoseLandmark.RIGHT_ELBOW].visibility +
                 vis_landmarks[pv.MP_POSE.PoseLandmark.RIGHT_KNEE].visibility) / 4.0

    if left_vis > 0.6 and right_vis > 0.6:
        return ['left', 'right']

    if left_z < right_z - 0.1:
        return ['left']
    elif right_z < left_z - 0.1:
        return ['right']

    if left_vis > right_vis + 0.2:
        return ['left']
    elif right_vis > left_vis + 0.2:
        return ['right']

    return ['left', 'right']


def update_rep_count(current_metrics, state, active_sides):
    """State-machine rep counter driven by the primary angle metric."""
    metric = state['rep_metric']
    if not metric:
        return
    low = state['rep_low_thresh']
    high = state['rep_high_thresh']
    for side in active_sides:
        val = current_metrics.get(f"{metric}_{side}")
        if val is None:
            continue
            
        phase = state['rep_phase'][side]
        if phase == 'extended' and val < low:
            state['rep_phase'][side] = 'contracted'
        elif phase == 'contracted' and val > high:
            state['rep_phase'][side] = 'extended'
            state['rep_side_counts'][side] += 1
            state['rep_count'] = max(state['rep_side_counts'].values())


def evaluate_metrics(current_metrics, metric_configs, ref, state, active_sides=None):
    """Evaluates current frame metrics against reference ranges."""
    if active_sides is None:
        active_sides = ['left', 'right']

    is_good_form = True
    feedback_messages = []
    bad_joints = set()

    if not current_metrics:
        return is_good_form, ["No pose detected"], bad_joints

    for metric_name, config in metric_configs.items():
        metric_type = config.get('type', 'angle')
        joints_involved = config.get('joints', [])

        ref_min = ref.get(f"{metric_name}_min")
        ref_max = ref.get(f"{metric_name}_max")

        if ref_min is None or ref_max is None:
            continue

        if metric_type == 'angle':
            # ±10° matches the "strict form" tolerance reported by Mercadal-Baudart et al.
            # (2024) and Sim et al. (2024) for single-camera pose-based exercise evaluation.
            base_tol = config.get('tolerance', 10.0)
            min_tolerance = base_tol
            max_tolerance = base_tol
        else:
            # Distances are normalised ratios; ±0.10 retained (no published standard).
            base_tol = config.get('tolerance', 0.10)
            min_tolerance = base_tol
            max_tolerance = base_tol

        msg_high = config.get('message_high', '')
        msg_low = config.get('message_low', '')

        for side in active_sides:
            key = f"{metric_name}_{side}"
            current_val = current_metrics.get(key)

            if current_val is None:
                continue

            lower_bound = ref_min - min_tolerance
            upper_bound = ref_max + max_tolerance

            hard_max = config.get('hard_max')
            if hard_max is not None:
                upper_bound = min(upper_bound, hard_max)

            hard_min = config.get('hard_min')
            if hard_min is not None:
                lower_bound = max(lower_bound, hard_min)

            if current_val < lower_bound:
                is_good_form = False
                bad_joints.update(f"{j}_{side}" for j in joints_involved)
                if msg_low:
                    msg = f"[{side.upper()}] {msg_low}"
                    feedback_messages.append(msg)
                    state['feedbacks'].setdefault(msg, []).append({
                        'frame': state['frame_count'],
                        'current_val': current_val,
                        'required_range': (lower_bound, upper_bound),
                        'metric_type': metric_type
                    })
            elif current_val > upper_bound:
                is_good_form = False
                bad_joints.update(f"{j}_{side}" for j in joints_involved)
                if msg_high:
                    msg = f"[{side.upper()}] {msg_high}"
                    feedback_messages.append(msg)
                    state['feedbacks'].setdefault(msg, []).append({
                        'frame': state['frame_count'],
                        'current_val': current_val,
                        'required_range': (lower_bound, upper_bound),
                        'metric_type': metric_type
                    })

    return is_good_form, feedback_messages, bad_joints


def draw_skeleton(display_frame, results, metric_configs, bad_joints, active_sides=None):
    """Draws the pose skeleton on the frame, highlighting bad joints in red."""
    if active_sides is None:
        active_sides = ['left', 'right']

    if not (results and hasattr(results, 'pose_landmarks') and results.pose_landmarks):
        return

    h, w = display_frame.shape[:2]

    good_skeleton_color = (0, 255, 0)
    good_joint_color = (0, 200, 0)
    bad_skeleton_color = (0, 0, 255)
    bad_joint_color = (0, 0, 200)

    landmarks = results.pose_landmarks.landmark

    joint_to_landmarks = {
        'shoulder': (pv.MP_POSE.PoseLandmark.LEFT_SHOULDER, pv.MP_POSE.PoseLandmark.RIGHT_SHOULDER),
        'elbow':    (pv.MP_POSE.PoseLandmark.LEFT_ELBOW,    pv.MP_POSE.PoseLandmark.RIGHT_ELBOW),
        'wrist':    (pv.MP_POSE.PoseLandmark.LEFT_WRIST,    pv.MP_POSE.PoseLandmark.RIGHT_WRIST),
        'index':    (pv.MP_POSE.PoseLandmark.LEFT_INDEX,    pv.MP_POSE.PoseLandmark.RIGHT_INDEX),
        'hip':      (pv.MP_POSE.PoseLandmark.LEFT_HIP,      pv.MP_POSE.PoseLandmark.RIGHT_HIP),
        'knee':     (pv.MP_POSE.PoseLandmark.LEFT_KNEE,     pv.MP_POSE.PoseLandmark.RIGHT_KNEE),
        'ankle':    (pv.MP_POSE.PoseLandmark.LEFT_ANKLE,    pv.MP_POSE.PoseLandmark.RIGHT_ANKLE),
    }

    joint_connections = [
        ('shoulder', 'elbow'),
        ('elbow', 'wrist'),
        ('wrist', 'index'),
        ('shoulder', 'hip'),
        ('hip', 'knee'),
        ('knee', 'ankle'),
    ]

    for j1, j2 in joint_connections:
        for side_idx, side_name in [(0, 'left'), (1, 'right')]:
            if side_name not in active_sides:
                continue
            is_bad = (f"{j1}_{side_name}" in bad_joints and f"{j2}_{side_name}" in bad_joints)
            s_col = bad_skeleton_color if is_bad else good_skeleton_color
            lm1 = landmarks[joint_to_landmarks[j1][side_idx]]
            lm2 = landmarks[joint_to_landmarks[j2][side_idx]]
            if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                pt1 = (int(lm1.x * w), int(lm1.y * h))
                pt2 = (int(lm2.x * w), int(lm2.y * h))
                cv2.line(display_frame, pt1, pt2, s_col, 4)

    for joint_name in joint_to_landmarks:
        for side_idx, side_name in [(0, 'left'), (1, 'right')]:
            if side_name not in active_sides:
                continue
            is_bad = f"{joint_name}_{side_name}" in bad_joints
            j_col = bad_joint_color if is_bad else good_joint_color
            s_col = bad_skeleton_color if is_bad else good_skeleton_color
            lm = landmarks[joint_to_landmarks[joint_name][side_idx]]
            if lm.visibility > 0.5:
                pt = (int(lm.x * w), int(lm.y * h))
                cv2.circle(display_frame, pt, 8, j_col, -1)
                cv2.circle(display_frame, pt, 8, s_col, 2)


def create_info_bar(display_frame, w, h, feedback_messages, fixed_width=None):
    """Creates a dark info panel above the video. Returns (composite, bar_height, bar_width)."""
    scale_factor = min(w / 800.0, h / 720.0)
    font_scale_medium = max(0.4, 0.7 * scale_factor)
    thick_medium = max(1, int(2 * scale_factor))
    line_spacing = int(32 * scale_factor)

    # 5 rows: status | reps | progress | feedback×2
    num_lines = 5
    bar_h = int(line_spacing * num_lines + int(24 * scale_factor))

    needed_width = w
    for msg in feedback_messages:
        tw = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, font_scale_medium, thick_medium)[0][0]
        needed_width = max(needed_width, tw + 40)

    bar_width = max(needed_width, fixed_width or 0)

    padded_video = display_frame
    if bar_width > w:
        pad_left_w = (bar_width - w) // 2
        pad_right_w = bar_width - w - pad_left_w
        bar_color = (25, 25, 25)
        pad_left = np.full((h, pad_left_w, 3), bar_color, dtype=np.uint8)
        pad_right = np.full((h, pad_right_w, 3), bar_color, dtype=np.uint8)
        padded_video = np.hstack([pad_left, display_frame, pad_right])

    bar = np.full((bar_h, bar_width, 3), (25, 25, 25), dtype=np.uint8)
    composite = np.vstack([bar, padded_video])
    return composite, bar_h, bar_width


def draw_overlays(display_frame, exercise_name, is_good_form, frame_count, total_frames, fps, feedback_messages, bar_h=None, bar_y=None, video_width=None, rep_count=None):
    """Draws status text, rep count, progress, and feedback into the info bar area."""
    h, w = display_frame.shape[:2]

    if bar_h is not None:
        bar_start = 0
        video_h = h - bar_h
    elif bar_y is not None:
        bar_start = bar_y
        video_h = bar_y
    else:
        bar_start = 0
        video_h = h

    scale_factor = min(w / 800.0, video_h / 720.0)
    font_scale_large  = max(0.5, 1.2 * scale_factor)
    font_scale_medium = max(0.4, 0.7 * scale_factor)
    font_scale_small  = max(0.45, 0.6 * scale_factor)
    thick_large  = max(1, int(3 * scale_factor))
    thick_medium = max(1, int(2 * scale_factor))
    thick_small  = max(1, int(1 * scale_factor))
    line_spacing = int(30 * scale_factor)

    status_color = (0, 255, 0) if is_good_form else (0, 0, 255)
    status_text = "GOOD FORM" if is_good_form else "FIX FORM"

    # Row 1: status (left) + exercise name (right)
    y_row1 = bar_start + max(30, int(35 * scale_factor))
    cv2.putText(display_frame, status_text, (20, y_row1),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale_large, status_color, thick_large, cv2.LINE_AA)

    ex_size = cv2.getTextSize(exercise_name.upper(), cv2.FONT_HERSHEY_SIMPLEX, font_scale_medium, thick_medium)[0]
    cv2.putText(display_frame, exercise_name.upper(), (w - ex_size[0] - 20, y_row1),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale_medium, (200, 200, 200), thick_medium, cv2.LINE_AA)

    # Row 2: rep count (centered)
    y_row2 = y_row1 + line_spacing
    if rep_count is not None:
        rep_text = f"REPS: {rep_count}"
        rep_size = cv2.getTextSize(rep_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale_large, thick_large)[0]
        cv2.putText(display_frame, rep_text, ((w - rep_size[0]) // 2, y_row2),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale_large, (255, 200, 0), thick_large, cv2.LINE_AA)

    # Row 3: progress timer
    current_time_sec = frame_count / fps if fps > 0 else 0
    total_time_sec = total_frames / fps if fps > 0 else 0
    progress_text = f"Time: {current_time_sec:.1f}s / {total_time_sec:.1f}s"
    y_row3 = y_row2 + line_spacing
    cv2.putText(display_frame, progress_text, (20, y_row3),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale_small, (200, 200, 200), thick_small, cv2.LINE_AA)

    # Rows 4-5: feedback messages
    if feedback_messages:
        y_fb_start = y_row3 + line_spacing
        for i, msg in enumerate(feedback_messages[:2]):
            y_pos = y_fb_start + (i * line_spacing)
            cv2.putText(display_frame, msg, (20, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale_medium, status_color, thick_medium, cv2.LINE_AA)


def format_feedback_summary(feedbacks, fps, frame_skip=0):
    """Prints a formatted summary of form feedback grouped into contiguous time ranges."""
    if not feedbacks:
        print("\n[Form Feedback] Good form! No significant deviations detected.")
        return

    print("\n[Form Feedback]")
    for msg, instances in sorted(feedbacks.items()):
        if not instances:
            continue

        ranges = []
        start_inst = instances[0]
        prev_inst = instances[0]
        current_range_instances = [start_inst]

        def format_range(instances_list):
            s_inst = instances_list[0]
            e_inst = instances_list[-1]
            s = s_inst['frame']
            e = e_inst['frame']
            metric_type = s_inst['metric_type']
            unit = " deg" if metric_type == 'angle' else ""
            avg_val = sum(x['current_val'] for x in instances_list) / len(instances_list)
            req_min, req_max = s_inst['required_range']

            if metric_type == 'angle':
                val_str = f" measured ~{avg_val:.1f}{unit} (needed {req_min:.1f}{unit}–{req_max:.1f}{unit})"
            else:
                val_str = f" measured ~{avg_val:.3f}{unit} (needed {req_min:.3f}{unit}–{req_max:.3f}{unit})"

            if s == e:
                time_str = f"frame {s} ({s/fps:.1f}s)" if fps > 0 else f"frame {s}"
            else:
                time_str = f"frames {s}-{e} ({s/fps:.1f}-{e/fps:.1f}s)" if fps > 0 else f"frames {s}-{e}"

            return f"{time_str}{val_str}"

        for inst in instances[1:]:
            if inst['frame'] <= prev_inst['frame'] + (frame_skip + 1):
                prev_inst = inst
                current_range_instances.append(inst)
            else:
                ranges.append(format_range(current_range_instances))
                start_inst = inst
                prev_inst = inst
                current_range_instances = [inst]

        ranges.append(format_range(current_range_instances))

        print(f"- {msg}")
        for r in ranges:
            print(f"  -> {r}")


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    VIDEO_PATH = "../TestData/barbell biceps curl/ELBOW_PIN4.mp4"
    VIDEO_ABS_PATH = os.path.abspath(os.path.join(BASE_DIR, VIDEO_PATH))
    if os.path.exists(VIDEO_ABS_PATH):
        get_inference(VIDEO_ABS_PATH, 'barbell biceps curl')
    else:
        print("Video not found. Please check paths.")