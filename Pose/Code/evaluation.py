import process_video as pv

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
