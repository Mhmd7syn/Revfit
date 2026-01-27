import os

# Suppress TensorFlow and MediaPipe logging before importing libraries that trigger them
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['GLOG_minloglevel'] = '2' 

import json
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
from process_video_for_reference import process_video_for_reference, init_worker

# Format: { 'names': [...], 'type': 'angle'|'horizontal_distance'|'vertical_distance'|'distance_from_line', 'joints': [...] }
_JOINT_GROUPS = {
    # --- ANGLES ---
    ('ELBOW_ANGLE', 'ELBOW_BEND', 'ARM_BEND'): {
        'type': 'angle',
        'joints': ['shoulder', 'elbow', 'wrist'],
        'message_high': 'Elbows too straight.',
        'message_low': 'Elbows bent too much.'
    },
    ('KNEE_ANGLE', 'LEG_STRAIGHTNESS', 'SOFT_KNEES'): {
        'type': 'angle',
        'joints': ['hip', 'knee', 'ankle'],
        'message_high': 'Legs too straight (Lockout?).',
        'message_low': 'Bend knees less.'
    },
    ('HIP_EXTENSION', 'TORSO_STABILITY'): {
        'type': 'angle',
        'joints': ['shoulder', 'hip', 'knee'],
        'message_high': 'Hips extended too much.',
        'message_low': 'Hips flexed too much (sitting back?).'
    },
    ('SHOULDER_ABDUCTION', 'ELBOW_FLARE'): {
        'type': 'angle',
        'joints': ['hip', 'shoulder', 'elbow'],
        'message_high': 'Elbows flaring out too much.'
    },
    ('SHIN_ANGLE',): {
        'type': 'angle',
        'joints': ['vertical', 'ankle', 'knee'],
        'message_high': 'Knees tracking too far forward.'
    },
    ('TORSO_SWING', 'TORSO_LEAN', 'TORSO_ARCH', 'BACK_ANGLE_VERTICAL'): {
        'type': 'angle',
        'joints': ['vertical', 'hip', 'shoulder'],
        'message_high': 'Leaning back too far.',
        'message_low': 'Leaning forward too much.'
    },
    ('BACK_ANGLE_HORIZONTAL',): {
        'type': 'angle',
        'joints': ['horizontal', 'hip', 'shoulder'],
        'message_high': 'Torso too upright.',
        'message_low': 'Torso too low.'
    },
    ('BODY_SWING',): {
        'type': 'angle',
        'joints': ['vertical', 'shoulder', 'hip'],
        'message_high': 'Excessive body swing.'
    },

    # --- HORIZONTAL DISTANCES ---
    ('SHOULDER_SWING', 'ELBOW_PIN', 'ELBOW_STABILITY'): {
        'type': 'horizontal_distance',
        'joints': ['shoulder', 'elbow'],
        'message_high': 'Keep elbows pinned to your sides (Horizontal Drift)!'
    },
    ('WRIST_ELBOW_STACK',): {
        'type': 'horizontal_distance',
        'joints': ['wrist', 'elbow'],
        'message_high': 'Stack wrists over elbows (Horizontal Drift).'
    },

    # --- VERTICAL DISTANCES ---
    ('SHOULDER_ELBOW_DEPTH',): {
        'type': 'vertical_distance',
        'joints': ['shoulder', 'elbow'],
        'message_high': 'Too deep! Shoulders dropping below elbows.'
    },
    ('IMPINGEMENT_RISK',): {
         'type': 'vertical_distance',
         'joints': ['elbow', 'shoulder'],
         'message_low': 'Lower elbows slightly to protect shoulders.'
    },
    ('WRIST_ELBOW_HEIGHT',): {
        'type': 'vertical_distance',
        'joints': ['wrist', 'elbow'],
        'message_low': 'Lead with elbows, not wrists.'
    },
    ('CHIN_BAR_HEIGHT',): {
        'type': 'vertical_distance',
        'joints': ['nose', 'wrist'],
        'message_high': 'Get your chin over the bar!' 
    },
    ('HIP_SHOULDER_HEIGHT',): {
        'type': 'vertical_distance',
        'joints': ['hip', 'shoulder'],
        'message_low': 'Hips too high! Lower hips.'
    },
    ('HIP_KNEE_HEIGHT_DEADLIFT',): {
        'type': 'vertical_distance',
        'joints': ['hip', 'knee'],
        'message_high': 'Hips too low! Don\'t squat the deadlift.' 
    },
    ('SQUAT_DEPTH_CHECK',): {
        'type': 'vertical_distance',
        'joints': ['hip', 'knee'],
        'message_low': 'Squat deeper!'
    },

    # --- DISTANCE FROM LINE ---
    ('BODY_LINE', 'HIP_SAG', 'HIP_HIKE'): {
        'type': 'distance_from_line',
        'joints': ['hip', 'shoulder', 'ankle'],
        'message_high': 'Body not straight (Sagging or Piking).'
    },
    ('NECK_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['nose', 'shoulder', 'hip'],
        'message_high': 'Keep neck neutral with spine.'
    },
    ('HIP_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['hip', 'shoulder', 'ankle'],
        'message_high': 'Align hips with body.'
    }
}

# Flatten into the lookup dictionary
JOINT_DEFINITIONS = {name: config for names, config in _JOINT_GROUPS.items() for name in names}

# Group exercises with identical configurations
_EXERCISE_GROUPS = {
    ('barbell biceps curl', 'hammer curl'): ['ELBOW_ANGLE', 'ELBOW_PIN'],
    ('deadlift',): ['HIP_EXTENSION', 'HIP_SHOULDER_HEIGHT', 'HIP_KNEE_HEIGHT_DEADLIFT'],
    ('romanian deadlift',): ['HIP_EXTENSION', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
    ('bench press',): ['ELBOW_ANGLE', 'ELBOW_FLARE', 'WRIST_ELBOW_STACK'],
    ('chest fly machine',): ['ELBOW_BEND'],
    ('hip thrust',): ['HIP_EXTENSION', 'SHIN_ANGLE'],
    ('lat pulldown',): ['ELBOW_ANGLE', 'TORSO_SWING'],
    ('lateral raise',): ['SHOULDER_ABDUCTION', 'ELBOW_BEND', 'IMPINGEMENT_RISK', 'WRIST_ELBOW_HEIGHT'],
    ('leg extension',): ['KNEE_ANGLE', 'TORSO_STABILITY'],
    ('leg raises',): ['HIP_EXTENSION', 'LEG_STRAIGHTNESS'],
    ('plank',): ['BODY_LINE', 'HIP_HIKE'],
    ('pull up',): ['ELBOW_ANGLE', 'BODY_SWING', 'CHIN_BAR_HEIGHT'],
    ('push-up',): ['ELBOW_ANGLE', 'BODY_LINE'],
    ('russian twist',): ['HIP_EXTENSION', 'TORSO_LEAN'],
    ('shoulder press',): ['ELBOW_ANGLE', 'TORSO_ARCH', 'WRIST_ELBOW_STACK'],
    ('squat',): ['KNEE_ANGLE', 'BACK_ANGLE_VERTICAL', 'SQUAT_DEPTH_CHECK'],
    ('t bar row',): ['ELBOW_ANGLE', 'BACK_ANGLE_HORIZONTAL', 'NECK_ALIGNMENT'],
    ('tricep dips',): ['ELBOW_ANGLE', 'TORSO_LEAN', 'SHOULDER_ELBOW_DEPTH'],
    ('tricep pushdown',): ['ELBOW_ANGLE', 'ELBOW_PIN']
}

# Flatten into map
EXERCISE_TO_CONFIG = {ex: conf for exercises, conf in _EXERCISE_GROUPS.items() for ex in exercises}

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
        future_to_info = {executor.submit(process_video_for_reference, task): task[1] for task in tasks}
        
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
