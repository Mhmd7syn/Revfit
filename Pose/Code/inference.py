import os
import json
from process_video_for_reference import process_video_for_reference

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
    result = process_video_for_reference((video_path, exercise_name, metric_configs))
    
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

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REF_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_reference_angles.json'))
    references = load_references(REF_PATH)
    
    if references:
        VIDEO_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Data/lat pulldown/lat pulldown_2.mp4'))
        if os.path.exists(VIDEO_PATH):
            test_exercise(VIDEO_PATH, 'lat pulldown', references)
        else:
            print("Video not found. Please check paths.")
    else:
        print("No references loaded. Run analysis.py first.")
