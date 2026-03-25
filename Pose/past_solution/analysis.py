import os

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

import json
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from process_video import process_video, init_worker
from exercise_config import JOINT_DEFINITIONS, EXERCISE_TO_CONFIG


def analyze_dataset(dataset_path, output_json='exercise_reference_angles.json', output_csv='exercise_analysis_details.csv', frame_skip=2):
    tasks = []
    print(f"Scanning dataset at: {dataset_path}")

    for root, dirs, files in os.walk(dataset_path):
        folder_name = os.path.basename(root).lower()

        matched_exercise = None
        for ex_key in EXERCISE_TO_CONFIG.keys():
            if ex_key in folder_name:
                matched_exercise = ex_key
                break

        if matched_exercise:
            config_list = EXERCISE_TO_CONFIG[matched_exercise]
            angle_configs = {def_name: JOINT_DEFINITIONS[def_name] for def_name in config_list}

            for file in files:
                if file.lower().endswith(('.mp4', '.avi', '.mov')):
                    video_path = os.path.join(root, file)
                    tasks.append((video_path, matched_exercise, angle_configs))

    if not tasks:
        print("No videos found matching the exercise list.")
        return None

    print(f"Starting analysis of {len(tasks)} videos using multiprocessing...")

    final_data = []

    with ProcessPoolExecutor(initializer=init_worker) as executor:
        future_to_info = {executor.submit(process_video, task, frame_skip=frame_skip): task[1] for task in tasks}

        for future in tqdm(as_completed(future_to_info), total=len(future_to_info)):
            exercise_name = future_to_info[future]
            try:
                data = future.result()
                if data:
                    final_data.append(data)
            except Exception as e:
                print(f"Error processing video for {exercise_name}: {e}")

    df = pd.DataFrame(final_data)
    if not df.empty:
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        df.to_csv(output_csv, index=False)
        print(f"Detailed analysis saved to {output_csv}")

        references = {}
        grouped = df.groupby('exercise')

        for name, group in grouped:
            config_list = EXERCISE_TO_CONFIG[name]
            reconstructed_config = {def_name: JOINT_DEFINITIONS[def_name] for def_name in config_list}
            ref_data = {'angle_configs': reconstructed_config}

            for def_name in config_list:
                for stat in ['min', 'max']:
                    target_cols = [f"{def_name}_left_{stat}", f"{def_name}_right_{stat}"]
                    valid_cols = [c for c in target_cols if c in group.columns]

                    if valid_cols:
                        raw_vals = group[valid_cols].stack().dropna().values

                        # Two-pass outlier rejection:
                        # Pass 1: clip to 5th–95th percentile
                        if len(raw_vals) >= 4:
                            lo, hi = np.percentile(raw_vals, [5, 95])
                            filtered = raw_vals[(raw_vals >= lo) & (raw_vals <= hi)]
                        else:
                            filtered = raw_vals

                        # Pass 2: remove points with |Z-score| > 2
                        if len(filtered) > 1:
                            mean_f = np.mean(filtered)
                            std_f = np.std(filtered, ddof=1)
                            if std_f > 1e-9:
                                z_scores = np.abs((filtered - mean_f) / std_f)
                                filtered = filtered[z_scores <= 2.0]

                        if len(filtered) == 0:
                            filtered = raw_vals  # fallback: keep all if everything filtered

                        mean_val = float(np.mean(filtered))
                        ref_data[f"{def_name}_{stat}"] = mean_val

                        if len(filtered) > 1:
                            ref_data[f"{def_name}_{stat}_std"] = float(np.std(filtered, ddof=1))

            references[name] = ref_data

        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        with open(output_json, 'w') as f:
            json.dump(references, f, indent=4)
        print(f"Reference angles saved to {output_json}")

        return references
    else:
        print("No valid data extracted.")
        return None


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATASET_PATH = os.path.abspath(os.path.join(BASE_DIR, '../Temp_data'))
    OUTPUT_CSV = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_analysis_details.csv'))
    OUTPUT_JSON = os.path.abspath(os.path.join(BASE_DIR, '../Outputs/exercise_reference_angles.json'))

    print(f"Using dataset path: {DATASET_PATH}")
    references = analyze_dataset(DATASET_PATH, OUTPUT_JSON, OUTPUT_CSV)
