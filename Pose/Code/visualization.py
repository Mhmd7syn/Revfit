import cv2
import numpy as np
import process_video as pv

def draw_skeleton(display_frame, results, metric_configs, bad_joints, active_sides=None):
    """Draws the pose skeleton on the frame, highlighting bad joints in red."""
    if active_sides is None:
        active_sides = ['left', 'right']

    has_landmarks = False
    landmarks = None
    if results:
        if hasattr(results, 'pose_landmarks') and results.pose_landmarks:
            if hasattr(results.pose_landmarks, 'landmark'):
                landmarks = results.pose_landmarks.landmark
                has_landmarks = True
            elif isinstance(results.pose_landmarks, list) and len(results.pose_landmarks) > 0:
                landmarks = results.pose_landmarks[0]
                has_landmarks = True

    if not has_landmarks or landmarks is None:
        return

    h, w = display_frame.shape[:2]

    good_skeleton_color = (0, 255, 0)
    good_joint_color = (0, 200, 0)
    bad_skeleton_color = (0, 0, 255)
    bad_joint_color = (0, 0, 200)

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
