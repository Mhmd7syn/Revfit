import os
import cv2
import numpy as np
import mediapipe as mp
import process_video as pv
from exercise_config import EXERCISE_TO_CONFIG, JOINT_DEFINITIONS
from repetition_counter import RepetitionCounter
from evaluation import get_active_sides, evaluate_metrics
from visualization import draw_skeleton, create_info_bar, draw_overlays, format_feedback_summary


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
        high_msg = mc.get('message_high')
        low_msg = mc.get('message_low')
        for side in ['LEFT', 'RIGHT']:
            if high_msg: _all_possible_msgs.append(f"[{side}] {high_msg}")
            if low_msg: _all_possible_msgs.append(f"[{side}] {low_msg}")

    _scale_factor = max(scaled_w / 800.0, scaled_h / 720.0) if scaled_h > 0 and scaled_w > 0 else 1.0
    _pre_font_scale = max(0.4, 0.7 * _scale_factor)
    _pre_thick = max(1, int(2 * _scale_factor))
    _pre_width = scaled_w

    # Ensure status, ex name, etc fit
    for _msg in _all_possible_msgs + ["GOOD FORM", "FIX FORM", exercise_name.upper(), "REPS: 999", "Time: 999.9s / 999.9s"]:
        _tw = cv2.getTextSize(_msg, cv2.FONT_HERSHEY_SIMPLEX, _pre_font_scale if "Time" not in _msg else 0.5, _pre_thick)[0][0]
        _pre_width = max(_pre_width, _tw + 100)

    # Initialize the new RepetitionCounter
    rep_counter = RepetitionCounter(exercise_name, metric_configs, ref)

    state = {
        'paused': False,
        'frame_count': 0,
        'quit': False,
        'headless': headless,
        'feedbacks': {},
        'bar_width': _pre_width,
        'window_created': False,
        'rep_count': 0,
        'rep_counter': rep_counter,
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
            state['rep_counter'].add_frame(current_metrics, active_sides)
            state['rep_count'] = state['rep_counter'].get_rep_count()

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





if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # ✅ Good form:
    #   ../TestData/deadlift/deadlift_1.mp4            -> 'deadlift'
    #   ../TestData/push-up/video15.mp4                -> 'push-up'
    #   ../TestData/lateral raise/video10.mp4          -> 'lateral raise'
    #
    # ❌ Bad form:
    #   ../TestData/lateral raise/lateral raise_1.mp4  -> 'lateral raise'        (elbows too bent at top)
    #   ../TestData/deadlift/video4.mp4               -> 'deadlift'             (legs too straight)
    #   ../TestData/push-up/push-up_1.mp4             -> 'push-up'              (body sag + elbow flare)

    VIDEO_PATH = "../TestData/deadlift/deadlift_1.mp4"
    VIDEO_ABS_PATH = os.path.abspath(os.path.join(BASE_DIR, VIDEO_PATH))
    if os.path.exists(VIDEO_ABS_PATH):
        get_inference(VIDEO_ABS_PATH, 'deadlift')
    else:
        print("Video not found. Please check paths.")