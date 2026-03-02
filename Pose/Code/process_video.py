import os
import sys
from contextlib import contextmanager

# Suppress TensorFlow logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

import cv2
import mediapipe as mp
import numpy as np
from geometry_checks import GeometryChecks

# Standard MediaPipe Landmarks
try:
    MP_POSE = mp.solutions.pose
except AttributeError:
    # Fallback for some environments
    import mediapipe.python.solutions.pose as MP_POSE

@contextmanager
def suppress_c_logging():
    """
    Redirects C-level stdout and stderr to NUL to suppress persistent MediaPipe warnings 
    and TFLite INFO logs that defy environment variable suppression on Windows.
    """
    if os.name == 'nt':
        null_device = 'NUL'
    else:
        null_device = '/dev/null'
    
    try:
        # Save original fds
        original_stdout_fd = os.dup(sys.stdout.fileno())
        original_stderr_fd = os.dup(sys.stderr.fileno())
        
        # Save Python sys streams
        orig_sys_stdout = sys.stdout
        orig_sys_stderr = sys.stderr
        
        # Open null device
        devnull = os.open(null_device, os.O_WRONLY)
        
        # Redirect C-level file descriptors to null
        os.dup2(devnull, sys.stdout.fileno())
        os.dup2(devnull, sys.stderr.fileno())
        
        # Redirect Python level to avoid WinError 1 on print
        null_file_out = open(null_device, 'w')
        null_file_err = open(null_device, 'w')
        sys.stdout = null_file_out
        sys.stderr = null_file_err
        
        yield
        
    except Exception:
        yield
    finally:
        # Restore Python sys streams
        if 'orig_sys_stdout' in locals():
            sys.stdout = orig_sys_stdout
            sys.stderr = orig_sys_stderr
            if 'null_file_out' in locals():
                try: null_file_out.close()
                except: pass
            if 'null_file_err' in locals():
                try: null_file_err.close()
                except: pass
                
        # Restore C-level file descriptors
        if 'original_stdout_fd' in locals():
            os.dup2(original_stdout_fd, sys.stdout.fileno())
            os.close(original_stdout_fd)
        if 'original_stderr_fd' in locals():
            os.dup2(original_stderr_fd, sys.stderr.fileno())
            os.close(original_stderr_fd)
        if 'devnull' in locals():
            os.close(devnull)

def get_landmark_coords(landmarks, joint_name, side):
    """
    Helper to get (x, y) coordinates for a specific joint and side.
    Handles 'vertical' and 'horizontal' virtual points.
    """
    if joint_name.lower() in ['vertical', 'horizontal']:
        return joint_name.lower()

    attr_name = f"{side}_{joint_name.upper()}"
    if hasattr(MP_POSE.PoseLandmark, attr_name):
        lm = landmarks[getattr(MP_POSE.PoseLandmark, attr_name)]
        if lm.visibility < 0.5:
            return None
        return np.array([lm.x, lm.y])
    return None


POSE_MODEL = None
def init_worker():
    """Initializer for the worker process to create the Pose model once."""
    global POSE_MODEL
    # Suppress TFLite initialization logs
    with suppress_c_logging():
        POSE_MODEL = MP_POSE.Pose(
            min_detection_confidence=0.5, 
            min_tracking_confidence=0.5, 
            model_complexity=0,
            static_image_mode=False 
        )


def process_video(args, frame_skip=0, frame_callback=None):
    """
    Process a single video to extract min/max/std for multiple target metrics.
    args: (video_path, exercise_name, metric_configs) or (video_path, exercise_name, metric_configs, frame_skip)
    metric_configs: dict of {metric_name: {'type': '...', 'joints': [...]}}}
    frame_skip: Process every (frame_skip + 1)th frame. 0 = all frames, 1 = every 2nd, etc.
    frame_callback: Optional function(frame, frame_metrics, results) called per frame.
                    If it returns False, video processing stops early.
    """
    global POSE_MODEL
    if POSE_MODEL is None:
        init_worker()
        
    pose = POSE_MODEL

    # Handle both old and new call signatures
    if len(args) == 4:
        video_path, exercise_name, metric_configs, fs = args
        if frame_skip == 0:
            frame_skip = fs
    else:
        video_path, exercise_name, metric_configs = args
    
    if not os.path.exists(video_path):
        return None

    cap = cv2.VideoCapture(video_path)
    
    # Storage for collected values
    collected_values = {name: {'left': [], 'right': []} for name in metric_configs}
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Skip frames if frame_skip is set
        if frame_skip > 0 and frame_count % (frame_skip + 1) != 0:
            frame_count += 1
            continue
        
        frame_count += 1
        
        # --- Frame Processing Logic ---
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        
        with suppress_c_logging():
            results = pose.process(image)
        
        frame_metrics = {}
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            frame_keypoints = {'LEFT': {}, 'RIGHT': {}}
            
            # Global/Central points
            nose_idx = MP_POSE.PoseLandmark.NOSE
            nose_coords = None
            if landmarks[nose_idx].visibility > 0.5:
                nose_coords = np.array([landmarks[nose_idx].x, landmarks[nose_idx].y])

            target_joints = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle']
            
            for side in ['LEFT', 'RIGHT']:
                for name in target_joints:
                    coords = get_landmark_coords(landmarks, name, side)
                    if coords is not None:
                        frame_keypoints[side][name] = coords
                # Add nose to each side for convenience in checks
                if nose_coords is not None:
                    frame_keypoints[side]['nose'] = nose_coords

            # Calculate Metrics from Config  
            for metric_name, config in metric_configs.items():
                metric_type = config.get('type', 'angle')
                joints = config.get('joints', [])
                
                for side in ['LEFT', 'RIGHT']:
                    points = []
                    valid_side = True
                    
                    for j in joints:
                        if j in ['vertical', 'horizontal']:
                            points.append(j)
                        elif j in frame_keypoints[side]:
                            points.append(frame_keypoints[side][j])
                        else:
                            valid_side = False
                            break
                    
                    if not valid_side:
                        continue
                        
                    # Perform Calculation based on Type
                    value = None
                    if metric_type == 'angle':
                        if len(points) == 3:
                            p0, p1, p2 = points[0], points[1], points[2]
                            
                            if isinstance(p0, str):
                                if p0 == 'vertical': p0 = np.array([p1[0], p1[1] - 0.5])
                                elif p0 == 'horizontal': p0 = np.array([p1[0] + 0.5, p1[1]])
                            
                            if isinstance(p2, str):
                                if p2 == 'vertical': p2 = np.array([p1[0], p1[1] - 0.5])
                                elif p2 == 'horizontal': p2 = np.array([p1[0] + 0.5, p1[1]])
                                
                            if not isinstance(p0, str) and not isinstance(p1, str) and not isinstance(p2, str):
                                value = GeometryChecks.calculate_angle(p0, p1, p2)

                    elif metric_type == 'horizontal_distance':
                        if len(points) >= 2:
                            value = GeometryChecks.calculate_horizontal_distance(points[0], points[1])
                             
                    elif metric_type == 'vertical_distance':
                        if len(points) >= 2:
                            value = GeometryChecks.calculate_vertical_distance(points[0], points[1])

                    elif metric_type == 'distance_from_line':
                        if len(points) == 3:
                            value = GeometryChecks.distance_from_line(points[0], points[1], points[2])
                    
                    if value is not None:
                        frame_metrics[f"{metric_name}_{side.lower()}"] = value

        # --- end frame processing logic ---
        
        if frame_metrics:
            # Parse the flattened results and accumulate
            for key, value in frame_metrics.items():
                # key format: "metric_name_side" (e.g., "elbow_angle_left")
                # Split to get metric_name and side
                parts = key.rsplit('_', 1)  # Split from right to get last underscore
                if len(parts) == 2:
                    metric_name = parts[0]
                    side = parts[1]
                    if metric_name in collected_values and side in collected_values[metric_name]:
                        collected_values[metric_name][side].append(value)

        if frame_callback:
            # Allow the callback to stop processing (e.g. user pressed 'q')
            if frame_callback(frame, frame_metrics if frame_metrics else None, results if 'results' in locals() and results.pose_landmarks else None) is False:
                break

    cap.release()
    
    result = {
        'video': os.path.basename(video_path),
        'exercise': exercise_name,
    }
    
    has_data = False
    for metric_name, sides in collected_values.items():
        for side, values in sides.items():
            if values:
                has_data = True
                result[f"{metric_name}_{side}_min"] = float(np.min(values))
                result[f"{metric_name}_{side}_max"] = float(np.max(values))
            else:
                result[f"{metric_name}_{side}_min"] = None
                result[f"{metric_name}_{side}_max"] = None

    if has_data:
        return result
    return None