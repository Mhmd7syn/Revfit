import os

# Suppress TensorFlow and MediaPipe logging before importing libraries that trigger them
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['GLOG_minloglevel'] = '2' 

import json
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
from process_video import process_video, init_worker
from exercise_config import JOINT_DEFINITIONS, EXERCISE_TO_CONFIG

def analyze_dataset(dataset_path, output_json='exercise_reference_angles.json', output_csv='exercise_analysis_details.csv'):
    tasks = []
    print(f"Scanning dataset at: {dataset_path}")
    
    # Walk through directories
    for root, dirs, files in os.walk(dataset_path):
        folder_name = os.path.basename(root).lower()
        
        matched_exercise = None
        for ex_key in EXERCISE_TO_CONFIG.keys():
            if ex_key in folder_name:
                matched_exercise = ex_key
                break
        
        if matched_exercise:
            config_list = EXERCISE_TO_CONFIG[matched_exercise] 
            angle_configs = {}
            for def_name in config_list:
                angle_configs[def_name] = JOINT_DEFINITIONS[def_name]

            for file in files:
                if file.lower().endswith(('.mp4', '.avi', '.mov')):
                    video_path = os.path.join(root, file)
                    tasks.append((video_path, matched_exercise, angle_configs))

    if not tasks:
        print("No videos found matching the exercise list.")
        return None

    print(f"Starting analysis of {len(tasks)} videos using multiprocessing...")

    final_data = []
    
    # Use ProcessPoolExecutor for parallelism, with initializer to share model instance
    with ProcessPoolExecutor(initializer=init_worker) as executor:
        future_to_info = {executor.submit(process_video, task): task[1] for task in tasks}
        
        for future in tqdm(future_to_info):
            exercise_name = future_to_info[future]
            try:
                data = future.result()
                if data:
                    final_data.append(data)
            except Exception as e:
                print(f"Error processing video for {exercise_name}: {e}")

    # Aggregation
    df = pd.DataFrame(final_data)
    if not df.empty:
        df.to_csv(output_csv, index=False)
        print(f"Detailed analysis saved to {output_csv}")
        
        references = {}
        grouped = df.groupby('exercise')
        
        for name, group in grouped:
            # Reconstruct the reference config for saving
            config_list = EXERCISE_TO_CONFIG[name]
            reconstructed_config = {}
            for def_name in config_list:
                reconstructed_config[def_name] = JOINT_DEFINITIONS[def_name]
            ref_data = {'angle_configs': reconstructed_config}
            
            # Calculate stats for min, max
            for def_name in config_list:
                for stat in ['min', 'max']:
                    target_cols = [f"{def_name}_left_{stat}", f"{def_name}_right_{stat}"]
                    valid_cols = [c for c in target_cols if c in group.columns]
                    
                    if valid_cols:
                        mean_val = group[valid_cols].stack().mean()
                        ref_data[f"{def_name}_{stat}"] = float(mean_val)
                        
                        # Store SD to help with thresholding
                        std_val = group[valid_cols].stack().std()
                        if pd.notna(std_val):
                             ref_data[f"{def_name}_std"] = float(std_val)

            references[name] = ref_data
            
        with open(output_json, 'w') as f:
            json.dump(references, f, indent=4)
        print(f"Reference angles saved to {output_json}")
        
        return references
    else:
        print("No valid data extracted.")
        return None

if __name__ == "__main__":
    # Base paths relative to this script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATASET_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Data'))
    OUTPUT_CSV = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_analysis_details.csv'))
    OUTPUT_JSON = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_reference_angles.json'))

    print(f"Using dataset path: {DATASET_PATH}")
    references = analyze_dataset(DATASET_PATH, OUTPUT_JSON, OUTPUT_CSV)
