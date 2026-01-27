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
    angle_configs = ref['angle_configs']
    
    print(f"Testing {exercise_name}...")
    
    result = process_video_for_reference((video_path, exercise_name, angle_configs))
    
    if not result:
        print("Could not process video.")
        return

    print("\n--- Analysis Results ---")
    
    # 1. Geometric Form Feedback (from rules)
    if 'feedback' in result and result['feedback']:
        print("\n[Form Feedback]")
        for item in result['feedback']:
            print(f"- {item}")
    else:
        print("\n[Form Feedback] No specific form faults detected.")

    # 2. Angle Range Feedback (ROM)
    print("\n[Range of Motion Check]")
    if 'angle_configs' in ref:
        for angle_name in ref['angle_configs']:
            for side in ['left', 'right']:
                min_key = f"{angle_name}_{side}_min"
                max_key = f"{angle_name}_{side}_max"
                
                measured_min = result.get(min_key)
                measured_max = result.get(max_key)
                
                if measured_min is None:
                    continue
                    
                # Get Reference Values
                ref_min = ref.get(f"{angle_name}_min")
                ref_max = ref.get(f"{angle_name}_max")
                
                if ref_min is not None and ref_max is not None:
                    tolerance = 15.0 # Degrees
                    
                    # Check Min (Deepest point / Flexion usually)
                    if measured_min > (ref_min + tolerance):
                        print(f"[{side.upper()} {angle_name}] Issue: Value too high (Min: {measured_min:.1f}, Target: ~{ref_min:.1f}) -> Try to go deeper/flex more.")
                    
                    # Check Max (Extension usually)
                    elif measured_max < (ref_max - tolerance):
                         print(f"[{side.upper()} {angle_name}] Issue: Value too low (Max: {measured_max:.1f}, Target: ~{ref_max:.1f}) -> Extend more.")
                    else:
                        pass

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REF_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_reference_angles.json'))
    references = load_references(REF_PATH)
    
    if references:
        VIDEO_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Data/lat pulldown/lat pulldown_2.mp4'))
        test_exercise(VIDEO_PATH, 'lat pulldown', references)
        print("Inference script ready.")
