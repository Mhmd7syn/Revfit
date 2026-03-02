import os
import json
import cv2
import numpy as np
import mediapipe as mp
import process_video as pv

def load_references(json_path):
    if not os.path.exists(json_path):
        print(f"Reference file not found at: {json_path}")
        return None
    with open(json_path, 'r') as f:
        return json.load(f)

def get_inference(video_path, exercise_name, references, headless=False):
    if not references or exercise_name not in references:
        print(f"No reference data for {exercise_name}")
        return 0, 0, {}

    ref = references[exercise_name]
    metric_configs = ref.get('angle_configs', {})
    
    if not headless:
        print(f"Testing {exercise_name}...")
    
    # Setup for frame-by-frame visualization
    # MediaPipe drawing utilities
    mp_drawing = mp.solutions.drawing_utils
    
    # To get total frames for progress mapping  
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return 0, 0, {}
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_delay = int(1000 / fps) if fps > 0 else 33
    cap.release()
    
    if not headless:
        print(f"\nTesting {exercise_name} frame by frame...")
        print(f"Total frames: {total_frames}")
        print("Press 'q' to quit, 'p' to pause/resume")
        print("=" * 50)
    
    state = {
        'paused': False,
        'frame_count': 0,
        'quit': False,
        'headless': headless,
        'feedbacks': {}
    }

    def frame_callback(frame, current_metrics, results):
        if state['quit']:
            return False
            
        state['frame_count'] += 1
        
        # Determine form quality
        is_good_form = True
        feedback_messages = []
        
        if current_metrics:
            for metric_name, config in metric_configs.items():
                metric_type = config.get('type', 'angle')
                
                # Get reference mean and standard deviation
                ref_min = ref.get(f"{metric_name}_min")
                ref_max = ref.get(f"{metric_name}_max")
                ref_std = ref.get(f"{metric_name}_std", 0) # Default to 0 if missing
                
                if ref_min is None or ref_max is None:
                    continue
                
                # Calculate dynamic tolerance based on Standard Deviation (Z-score approach)
                z_score = 2.0 # Allow 2 standard deviations of variance
                dynamic_tolerance = z_score * ref_std
                
                # Enforce a minimum tolerance to prevent impossibly strict bounds on low-variance joints
                if metric_type == 'angle':
                    min_allowed_tolerance = 15.0  # Degrees
                else:
                    min_allowed_tolerance = 0.05  # Units for distance metrics
                    
                tolerance = max(dynamic_tolerance, min_allowed_tolerance)
                
                msg_high = config.get('message_high', '')
                msg_low = config.get('message_low', '')
                
                for side in ['left', 'right']:
                    key = f"{metric_name}_{side}"
                    current_val = current_metrics.get(key)
                    
                    if current_val is None:
                        continue
                    
                    # Check if current value is within acceptable range
                    lower_bound = ref_min - tolerance
                    upper_bound = ref_max + tolerance
                    
                    if current_val < lower_bound:
                        is_good_form = False
                        if msg_low:
                            msg = f"[{side.upper()}] {msg_low}"
                            feedback_messages.append(msg)
                            state['feedbacks'].setdefault(msg, []).append(state['frame_count'])
                    elif current_val > upper_bound:
                        is_good_form = False
                        if msg_high:
                            msg = f"[{side.upper()}] {msg_high}"
                            feedback_messages.append(msg)
                            state['feedbacks'].setdefault(msg, []).append(state['frame_count'])
        else:
            feedback_messages.append("No pose detected")
        
        # If headless, we can skip drawing to save time
        if state['headless']:
            return True
            
        # Create visualization
        display_frame = frame.copy()
        h, w = display_frame.shape[:2]
        
        if is_good_form:
            skeleton_color = (0, 255, 0)
            joint_color = (0, 200, 0)
            status_text = "GOOD FORM"
        else:
            skeleton_color = (0, 0, 255)
            joint_color = (0, 0, 200)
            status_text = "FIX FORM"
            
        if results and results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            joint_to_landmarks = {
                'shoulder': (pv.MP_POSE.PoseLandmark.LEFT_SHOULDER, pv.MP_POSE.PoseLandmark.RIGHT_SHOULDER),
                'elbow': (pv.MP_POSE.PoseLandmark.LEFT_ELBOW, pv.MP_POSE.PoseLandmark.RIGHT_ELBOW),
                'wrist': (pv.MP_POSE.PoseLandmark.LEFT_WRIST, pv.MP_POSE.PoseLandmark.RIGHT_WRIST),
                'hip': (pv.MP_POSE.PoseLandmark.LEFT_HIP, pv.MP_POSE.PoseLandmark.RIGHT_HIP),
                'knee': (pv.MP_POSE.PoseLandmark.LEFT_KNEE, pv.MP_POSE.PoseLandmark.RIGHT_KNEE),
                'ankle': (pv.MP_POSE.PoseLandmark.LEFT_ANKLE, pv.MP_POSE.PoseLandmark.RIGHT_ANKLE),
                'nose': (pv.MP_POSE.PoseLandmark.NOSE, pv.MP_POSE.PoseLandmark.NOSE),
            }
            
            relevant_joints = set()
            for config in metric_configs.values():
                joints = config.get('joints', [])
                for j in joints:
                    if j in joint_to_landmarks:
                        relevant_joints.add(j)
            
            joint_connections = [
                ('shoulder', 'elbow'),
                ('elbow', 'wrist'),
                ('shoulder', 'hip'),
                ('hip', 'knee'),
                ('knee', 'ankle'),
            ]
            
            relevant_connections = []
            for j1, j2 in joint_connections:
                if j1 in relevant_joints and j2 in relevant_joints:
                    relevant_connections.append((j1, j2))
            
            for j1, j2 in relevant_connections:
                for side_idx in [0, 1]:
                    lm1 = landmarks[joint_to_landmarks[j1][side_idx]]
                    lm2 = landmarks[joint_to_landmarks[j2][side_idx]]
                    if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                        pt1 = (int(lm1.x * w), int(lm1.y * h))
                        pt2 = (int(lm2.x * w), int(lm2.y * h))
                        cv2.line(display_frame, pt1, pt2, skeleton_color, 4)
            
            for joint_name in relevant_joints:
                for side_idx in [0, 1]:
                    lm = landmarks[joint_to_landmarks[joint_name][side_idx]]
                    if lm.visibility > 0.5:
                        pt = (int(lm.x * w), int(lm.y * h))
                        cv2.circle(display_frame, pt, 8, joint_color, -1)
                        cv2.circle(display_frame, pt, 8, skeleton_color, 2)
                        
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
        
        cv2.putText(display_frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, skeleton_color, 3)
        cv2.putText(display_frame, exercise_name.upper(), (w - 350, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        progress_text = f"Frame: {state['frame_count']}/{total_frames}"
        cv2.putText(display_frame, progress_text, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        if feedback_messages:
            feedback_y_start = h - 30 * min(len(feedback_messages), 4) - 20
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (0, feedback_y_start - 10), (w, h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
            
            for i, msg in enumerate(feedback_messages[:4]):
                y_pos = feedback_y_start + (i * 30)
                cv2.putText(display_frame, msg, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, skeleton_color, 2)
                
        try:
            cv2.imshow(f'Exercise Form Check - {exercise_name}', display_frame)
            
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
            if state['frame_count'] == 1:
                print("Note: Graphical display not supported (OpenCV headless mode). Running analysis silently...")
            state['headless'] = True
                
        return True

    # Run the video processing with the callback
    result = pv.process_video((video_path, exercise_name, metric_configs), frame_callback=frame_callback)
    cv2.destroyAllWindows()
    
    if not result:
        if not headless:
            print("Could not process video or processing stopped early.")
        return 0, 0, {}

    if not headless:
        print("\n--- Overall Analysis Results ---")

        if not state['feedbacks']:
            print("\n[Form Feedback] Good form! No significant deviations detected.")
        else:
            print("\n[Form Feedback]")
            for msg, frames in sorted(state['feedbacks'].items()):
                ranges = []
                start = frames[0]
                prev = frames[0]
                
                def format_range(s, e):
                    if s == e:
                        if fps > 0: return f"frame {s} ({s/fps:.1f}s)"
                        return f"frame {s}"
                    else:
                        if fps > 0: return f"frames {s}-{e} ({s/fps:.1f}-{e/fps:.1f}s)"
                        return f"frames {s}-{e}"
                
                for f in frames[1:]:
                    if f == prev + 1:
                        prev = f
                    else:
                        ranges.append(format_range(start, prev))
                        start = f
                        prev = f
                
                ranges.append(format_range(start, prev))
                
                range_str = ", ".join(ranges)
                print(f"- {msg}")
                print(f"  -> Occurred at: {range_str}")
            
    bad_frames = set()
    frame_details = {}
    for msg, frames in state['feedbacks'].items():
        bad_frames.update(frames)
        for f in frames:
            if f not in frame_details:
                frame_details[f] = []
            frame_details[f].append(msg)
        
    return state['frame_count'], len(bad_frames), frame_details

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REF_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_reference_angles.json'))
    references = load_references(REF_PATH)
    
    if references:
        VIDEO_PATH = "../TestData/barbell biceps curl/barbell biceps curl_1.mp4"
        VIDEO_ABS_PATH = os.path.abspath(os.path.join(BASE_DIR, VIDEO_PATH))
        if os.path.exists(VIDEO_ABS_PATH):
            get_inference(VIDEO_ABS_PATH, 'barbell biceps curl', references)
        else:
            print("Video not found. Please check paths.")
    else:
        print("No references loaded. Run analysis.py first.")
