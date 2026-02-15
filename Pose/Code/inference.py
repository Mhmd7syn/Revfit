import os
import json
import cv2
import numpy as np
import mediapipe as mp
import process_video_for_reference as pvr

def load_references(json_path):
    if not os.path.exists(json_path):
        print(f"Reference file not found at: {json_path}")
        return None
    with open(json_path, 'r') as f:
        return json.load(f)

def test_exercise(video_path, exercise_name, references):
    if not references or exercise_name not in references:
        print(f"No reference data for {exercise_name}")
        return

    ref = references[exercise_name]
    metric_configs = ref.get('angle_configs', {})
    
    print(f"Testing {exercise_name}...")
    
    # Run the video processing
    result = pvr.process_video_for_reference((video_path, exercise_name, metric_configs))
    
    if not result:
        print("Could not process video.")
        return

    print("\n--- Analysis Results ---")

    feedback_set = set()
    for metric_name, config in metric_configs.items():
        metric_type = config.get('type', 'angle')
        
        if metric_type == 'angle':
            tolerance = 15.0 # Degrees
        else:
            tolerance = 0.05 # Units
            
        msg_high = config.get('message_high')
        msg_low = config.get('message_low')

        for side in ['left', 'right']:
            # Get Measured Values
            meas_min = result.get(f"{metric_name}_{side.lower()}_min")
            meas_max = result.get(f"{metric_name}_{side.lower()}_max")
            
            # Get Reference Values
            ref_min = ref.get(f"{metric_name}_min")
            ref_max = ref.get(f"{metric_name}_max")

            if meas_min is None or ref_min is None:
                continue

            # Compare Ranges
            
            # Check 1: Min Comparison
            if meas_min > (ref_min + tolerance):
                if msg_high: feedback_set.add(f"[{side.upper()}] {msg_high} (Min val {meas_min:.2f} > {ref_min:.2f})")
            
            elif meas_min < (ref_min - tolerance):
                if msg_low: feedback_set.add(f"[{side.upper()}] {msg_low} (Min val {meas_min:.2f} < {ref_min:.2f})")

            # Check 2: Max Comparison
            if meas_max > (ref_max + tolerance):
                if msg_high: feedback_set.add(f"[{side.upper()}] {msg_high} (Max val {meas_max:.2f} > {ref_max:.2f})")
            
            elif meas_max < (ref_max - tolerance):
                if msg_low: feedback_set.add(f"[{side.upper()}] {msg_low} (Max val {meas_max:.2f} < {ref_max:.2f})")

    if feedback_set:
        print("\n[Form Feedback]")
        for item in sorted(list(feedback_set)):
            print(f"- {item}")
    else:
        print("\n[Form Feedback] Good form! No significant deviations detected.")

def test_exercise_frame_by_frame(video_path, exercise_name, references):
    """
    Process video frame-by-frame, check form quality, and display with visual feedback.
    Highlights the pose skeleton on the body - green for good form, red for bad form.
    """
    if not references or exercise_name not in references:
        print(f"No reference data for {exercise_name}")
        return
    
    ref = references[exercise_name]
    metric_configs = ref.get('angle_configs', {})
    
    # Initialize the pose model
    pvr.init_worker()
    
    # MediaPipe drawing utilities
    mp_drawing = mp.solutions.drawing_utils
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return
    
    # Get video properties for display
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_delay = int(1000 / fps) if fps > 0 else 33  # ms between frames
    
    print(f"\nTesting {exercise_name} frame by frame...")
    print(f"Total frames: {total_frames}")
    print("Press 'q' to quit, 'p' to pause/resume")
    print("=" * 50)
    
    paused = False
    frame_count = 0
    
    while cap.isOpened():
        if not paused:
            ret, frame = cap.read()
            if not ret:
                # End of video - stop instead of looping
                print("\nEnd of video reached.")
                break
            frame_count += 1
        
        # Get current metrics and pose results in one call (optimized to avoid duplicate processing)
        result_tuple = pvr.process_frame(frame, metric_configs, return_results=True)
        
        if result_tuple:
            current_metrics, results = result_tuple
        else:
            current_metrics, results = None, None
        
        # Determine form quality
        is_good_form = True
        feedback_messages = []
        
        if current_metrics:
            for metric_name, config in metric_configs.items():
                metric_type = config.get('type', 'angle')
                
                if metric_type == 'angle':
                    tolerance = 15.0  # Degrees
                else:
                    tolerance = 0.05  # Units for distance metrics
                
                msg_high = config.get('message_high', '')
                msg_low = config.get('message_low', '')
                
                # Get reference values
                ref_min = ref.get(f"{metric_name}_min")
                ref_max = ref.get(f"{metric_name}_max")
                
                if ref_min is None or ref_max is None:
                    continue
                
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
                            feedback_messages.append(f"[{side.upper()}] {msg_low}")
                    elif current_val > upper_bound:
                        is_good_form = False
                        if msg_high:
                            feedback_messages.append(f"[{side.upper()}] {msg_high}")
        else:
            feedback_messages.append("No pose detected")
        
        # Create visualization
        display_frame = frame.copy()
        h, w = display_frame.shape[:2]
        
        # Set colors based on form quality
        if is_good_form:
            # Green for good form
            skeleton_color = (0, 255, 0)  # BGR Green
            joint_color = (0, 200, 0)
            status_text = "GOOD FORM"
        else:
            # Red for bad form
            skeleton_color = (0, 0, 255)  # BGR Red
            joint_color = (0, 0, 200)
            status_text = "FIX FORM"
        
        # Draw only the relevant joints/muscles being trained
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Map joint names to MediaPipe landmark indices (for both sides)
            joint_to_landmarks = {
                'shoulder': (pvr.MP_POSE.PoseLandmark.LEFT_SHOULDER, pvr.MP_POSE.PoseLandmark.RIGHT_SHOULDER),
                'elbow': (pvr.MP_POSE.PoseLandmark.LEFT_ELBOW, pvr.MP_POSE.PoseLandmark.RIGHT_ELBOW),
                'wrist': (pvr.MP_POSE.PoseLandmark.LEFT_WRIST, pvr.MP_POSE.PoseLandmark.RIGHT_WRIST),
                'hip': (pvr.MP_POSE.PoseLandmark.LEFT_HIP, pvr.MP_POSE.PoseLandmark.RIGHT_HIP),
                'knee': (pvr.MP_POSE.PoseLandmark.LEFT_KNEE, pvr.MP_POSE.PoseLandmark.RIGHT_KNEE),
                'ankle': (pvr.MP_POSE.PoseLandmark.LEFT_ANKLE, pvr.MP_POSE.PoseLandmark.RIGHT_ANKLE),
                'nose': (pvr.MP_POSE.PoseLandmark.NOSE, pvr.MP_POSE.PoseLandmark.NOSE),
            }
            
            # Extract relevant joints from metric configs
            relevant_joints = set()
            for config in metric_configs.values():
                joints = config.get('joints', [])
                for j in joints:
                    if j in joint_to_landmarks:
                        relevant_joints.add(j)
            
            # Define connections between adjacent joints
            joint_connections = [
                ('shoulder', 'elbow'),
                ('elbow', 'wrist'),
                ('shoulder', 'hip'),
                ('hip', 'knee'),
                ('knee', 'ankle'),
            ]
            
            # Filter to only relevant connections
            relevant_connections = []
            for j1, j2 in joint_connections:
                if j1 in relevant_joints and j2 in relevant_joints:
                    relevant_connections.append((j1, j2))
            
            # Draw connections for both sides
            for j1, j2 in relevant_connections:
                for side_idx in [0, 1]:  # 0=left, 1=right
                    lm1 = landmarks[joint_to_landmarks[j1][side_idx]]
                    lm2 = landmarks[joint_to_landmarks[j2][side_idx]]
                    
                    if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                        pt1 = (int(lm1.x * w), int(lm1.y * h))
                        pt2 = (int(lm2.x * w), int(lm2.y * h))
                        cv2.line(display_frame, pt1, pt2, skeleton_color, 4)
            
            # Draw joint circles for relevant joints
            for joint_name in relevant_joints:
                for side_idx in [0, 1]:
                    lm = landmarks[joint_to_landmarks[joint_name][side_idx]]
                    if lm.visibility > 0.5:
                        pt = (int(lm.x * w), int(lm.y * h))
                        cv2.circle(display_frame, pt, 8, joint_color, -1)
                        cv2.circle(display_frame, pt, 8, skeleton_color, 2)
        
        # Add semi-transparent overlay at the top for text
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
        
        # Draw status text
        cv2.putText(display_frame, status_text, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, skeleton_color, 3)
        
        # Draw exercise name
        cv2.putText(display_frame, exercise_name.upper(), (w - 350, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw frame counter and progress
        progress_text = f"Frame: {frame_count}/{total_frames}"
        cv2.putText(display_frame, progress_text, (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Draw feedback messages at the bottom
        if feedback_messages:
            feedback_y_start = h - 30 * min(len(feedback_messages), 4) - 20
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (0, feedback_y_start - 10), (w, h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
            
            for i, msg in enumerate(feedback_messages[:4]):
                y_pos = feedback_y_start + (i * 30)
                cv2.putText(display_frame, msg, (20, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, skeleton_color, 2)
        
        # Display the frame
        cv2.imshow(f'Exercise Form Check - {exercise_name}', display_frame)
        
        # Handle keyboard input
        key = cv2.waitKey(frame_delay) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('p'):
            paused = not paused
            if paused:
                print("Paused. Press 'p' to resume.")
    
    cap.release()
    cv2.destroyAllWindows()
    print("\nVisualization complete.")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REF_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_reference_angles.json'))
    references = load_references(REF_PATH)
    
    if references:
        VIDEO_PATH = '../TestData/barbell biceps curl/barbell biceps curl_1.mp4'
        VIDEO_ABS_PATH = os.path.abspath(os.path.join(BASE_DIR, VIDEO_PATH))
        if os.path.exists(VIDEO_ABS_PATH):
            test_exercise_frame_by_frame(VIDEO_ABS_PATH, 'barbell biceps curl', references)
            # test_exercise(VIDEO_ABS_PATH, 'barbell biceps curl', references)
        else:
            print("Video not found. Please check paths.")
    else:
        print("No references loaded. Run analysis.py first.")
