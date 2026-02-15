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
        
        # Open null device
        devnull = os.open(null_device, os.O_WRONLY)
        
        # Redirect both to null
        os.dup2(devnull, sys.stdout.fileno())
        os.dup2(devnull, sys.stderr.fileno())
        
        yield
        
    except Exception:
        yield
    finally:
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
            model_complexity=0,  # Optimized: 0 is ~3x faster than 1, sufficient for clear videos
            static_image_mode=False 
        )


def process_video_for_reference(args, frame_skip=0):
    """
    Process a single video to extract min/max/std for multiple target metrics.
    args: (video_path, exercise_name, metric_configs) or (video_path, exercise_name, metric_configs, frame_skip)
    metric_configs: dict of {metric_name: {'type': '...', 'joints': [...]}}}
    frame_skip: Process every (frame_skip + 1)th frame. 0 = all frames, 1 = every 2nd, 2 = every 3rd, etc.
    """
    # Handle both old and new call signatures
    if len(args) == 4:
        video_path, exercise_name, metric_configs, frame_skip = args
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
        
        # Process the frame using process_frame
        frame_metrics = process_frame(frame, metric_configs)
        
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

def process_frame(frame, metric_configs, return_results=False):
    """
    Process a single frame to extract current metric values for real-time inference.
    Unlike process_video_for_reference which returns min/max, this returns current values.
    
    Args:
        frame: A single BGR image frame (numpy array from cv2)
        metric_configs: dict of {metric_name: {'type': '...', 'joints': [...]}}
        return_results: If True, return tuple of (metrics, results), otherwise just metrics
    
    Returns:
        dict with current values for each metric and side, e.g.:
        {'elbow_angle_left': 45.2, 'elbow_angle_right': 47.8, ...}
        Returns None if no pose detected or no data extracted.
        If return_results=True, returns (metrics_dict, results) tuple.
    """
    global POSE_MODEL
    if POSE_MODEL is None:
        init_worker()
        
    pose = POSE_MODEL
    
    # Convert to RGB
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    
    with suppress_c_logging():
        results = pose.process(image)
    
    if not results.pose_landmarks:
        return (None, results) if return_results else None
    
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
    result = {}
    
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
                result[f"{metric_name}_{side.lower()}"] = value

    if return_results:
        return (result if result else None, results)
    else:
        return result if result else None