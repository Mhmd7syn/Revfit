import os
import glob
import csv
from inference import load_references, get_inference

def test_all_accuracy():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ref_path = os.path.abspath(os.path.join(base_dir, '../Outputs/exercise_reference_angles.json'))
    test_data_dir = os.path.abspath(os.path.join(base_dir, '../TestData'))
    output_csv_path = os.path.abspath(os.path.join(base_dir, '../Outputs/inference_accuracy_report.csv'))
    
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    
    references = load_references(ref_path)
    if not references:
        print("No references found. Ensure analysis.py has been run.")
        return

    exercises = [d for d in os.listdir(test_data_dir) if os.path.isdir(os.path.join(test_data_dir, d))]
    
    total_frames_overall = 0
    bad_frames_overall = 0
    
    print("=========================================")
    print("   Evaluating Form Checker Accuracy      ")
    print("=========================================")
    
    exercise_accuracies = {}
    csv_rows = []
    failed_videos = []
    
    valid_exercises = [ex for ex in sorted(exercises) if ex.lower() in references]
    total_exercises = len(valid_exercises)
    
    for ex_idx, exercise_name in enumerate(valid_exercises, 1):
        ex_dir = os.path.join(test_data_dir, exercise_name)
        videos = glob.glob(os.path.join(ex_dir, "*.mp4")) + glob.glob(os.path.join(ex_dir, "*.mov")) + glob.glob(os.path.join(ex_dir, "*.MOV"))
        
        if not videos:
            continue
            
        print(f"\n--- Testing Exercise {ex_idx}/{total_exercises}: {exercise_name} ---")
        ex_total = 0
        ex_bad = 0
        
        total_videos = len(videos)
        
        for vid_idx, video_path in enumerate(sorted(videos), 1):
            video_name = os.path.basename(video_path)
            # Run inference in headless mode quietly
            frames, bad_frames, frame_details = get_inference(video_path, exercise_name, references, headless=True)
            
            ex_total += frames
            ex_bad += bad_frames
            
            # Record per-frame details for CSV
            for frame_idx in range(1, frames + 1):
                is_good = frame_idx not in frame_details
                status = "good" if is_good else "bad"
                feedback = "None" if is_good else " | ".join(frame_details[frame_idx])
                
                csv_rows.append({
                    "exercise": exercise_name,
                    "videoName": video_name,
                    "frame": frame_idx,
                    "good/bad": status,
                    "feedback": feedback
                })
            
            if frames > 0:
                acc = ((frames - bad_frames) / frames) * 100
                print(f"  [{vid_idx}/{total_videos}] {video_name}: Accuracy = {acc:.2f}%")
            else:
                failed_videos.append(os.path.join(exercise_name, video_name))
                print(f"  [{vid_idx}/{total_videos}] {video_name}: Failed to process or 0 frames")
                
        total_frames_overall += ex_total
        bad_frames_overall += ex_bad
        
        if ex_total > 0:
            ex_acc = ((ex_total - ex_bad) / ex_total) * 100
            exercise_accuracies[exercise_name] = ex_acc
            print(f"> {exercise_name} Overall Accuracy = {ex_acc:.2f}%")
            
    print("\n=========================================")
    print("          FINAL OVERALL ACCURACY         ")
    print("=========================================")
    if total_frames_overall > 0:
        overall_acc = ((total_frames_overall - bad_frames_overall) / total_frames_overall) * 100
        print(f"Total Frames Processed : {total_frames_overall}")
        print(f"Total Correct Frames   : {total_frames_overall - bad_frames_overall}")
        print(f"Total Bad Frames       : {bad_frames_overall}")
        print(f"OVERALL ACCURACY       : {overall_acc:.2f}%\n")
        
        print("--- Accuracy Breakdown by Exercise ---")
        for ex, acc in exercise_accuracies.items():
            print(f"  {ex}: {acc:.2f}%")
            
        # Write CSV report
        headers = ["exercise", "videoName", "frame", "good/bad", "feedback"]
        with open(output_csv_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(csv_rows)
            
        print(f"\nDetailed report saved to: {output_csv_path}")
        
        if failed_videos:
            print("\n--- Videos that failed to process ---")
            for fv in failed_videos:
                print(f"  - {fv}")
    else:
        print("No frames were processed.")
    print("=========================================")

if __name__ == "__main__":
    test_all_accuracy()
