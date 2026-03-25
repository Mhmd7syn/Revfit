import os
import sys
from contextlib import contextmanager

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

import cv2
import mediapipe as mp
import mediapipe.solutions.pose as mp_pose
import numpy as np
from geometry_checks import GeometryChecks


class EMAFilter:
    """Exponential Moving Average filter for per-metric noise reduction.

    Smooths frame-level metric values before heuristic evaluation to reduce
    MediaPipe landmark jitter (alpha=0.6 per Sim et al., 2024).
    Formula: smoothed = alpha * current + (1 - alpha) * previous
    """
    def __init__(self, alpha=0.6):
        self.alpha = alpha
        self._state = {}  # key -> last smoothed value

    def smooth(self, metrics: dict) -> dict:
        out = {}
        for k, v in metrics.items():
            if k not in self._state:
                self._state[k] = v   # first observation: pass through unchanged
            else:
                v = self.alpha * v + (1.0 - self.alpha) * self._state[k]
                self._state[k] = v
            out[k] = v
        return out

MP_POSE = mp_pose


def get_landmark_coords(world_landmarks, vis_landmarks, joint_name, side):
    """Returns (x, y, z) from world_landmarks for the given joint/side,
    using vis_landmarks (pose_landmarks) for the visibility gate.
    Returns the string 'vertical'/'horizontal' for virtual reference points."""
    if joint_name.lower() in ['vertical', 'horizontal']:
        return joint_name.lower()

    attr_name = f"{side}_{joint_name.upper()}"
    if hasattr(MP_POSE.PoseLandmark, attr_name):
        idx = getattr(MP_POSE.PoseLandmark, attr_name)
        if vis_landmarks[idx].visibility < 0.5:
            return None
        lm = world_landmarks[idx]
        return np.array([lm.x, lm.y, lm.z])
    return None


POSE_MODEL = None


def init_worker():
    """Initializes the MediaPipe Pose model once per worker process."""
    global POSE_MODEL
    POSE_MODEL = MP_POSE.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=2,
        static_image_mode=False
    )


def process_video(args, frame_skip=0, frame_callback=None):
    """
    Process a single video to extract per-metric min/max values.

    args: (video_path, exercise_name, metric_configs)
    frame_skip: skip N frames between each processed frame (0 = every frame, 2 = every 3rd)
    frame_callback: optional callback(frame, frame_metrics, results) called per processed frame.
                    Return False to stop early.
    """
    global POSE_MODEL
    if POSE_MODEL is None:
        init_worker()

    pose = POSE_MODEL

    if len(args) == 4:
        video_path, exercise_name, metric_configs, fs = args
        if frame_skip == 0:
            frame_skip = fs
    else:
        video_path, exercise_name, metric_configs = args

    if not os.path.exists(video_path):
        return None

    cap = cv2.VideoCapture(video_path)
    collected_values = {name: {'left': [], 'right': []} for name in metric_configs}

    # EMA smoother: only active in inference mode (when a frame_callback is provided).
    # The analysis/data-collection path uses percentile-based noise rejection instead.
    ema = EMAFilter(alpha=0.6) if frame_callback is not None else None

    raw_frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        raw_frame_idx += 1
        if frame_skip > 0 and raw_frame_idx % (frame_skip + 1) != 0:
            continue

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        results = pose.process(image)

        frame_metrics = {}
        if results.pose_world_landmarks and results.pose_landmarks:
            world_lms = results.pose_world_landmarks.landmark
            vis_lms = results.pose_landmarks.landmark
            frame_keypoints = {'LEFT': {}, 'RIGHT': {}}

            nose_idx = MP_POSE.PoseLandmark.NOSE
            nose_coords = None
            if vis_lms[nose_idx].visibility > 0.5:
                lm_nose = world_lms[nose_idx]
                nose_coords = np.array([lm_nose.x, lm_nose.y, lm_nose.z])

            target_joints = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle', 'index']

            for side in ['LEFT', 'RIGHT']:
                for name in target_joints:
                    coords = get_landmark_coords(world_lms, vis_lms, name, side)
                    if coords is not None:
                        frame_keypoints[side][name] = coords
                if nose_coords is not None:
                    frame_keypoints[side]['nose'] = nose_coords

            # Pre-compute torso length per side for distance normalization
            torso_lengths = {}
            for side in ['LEFT', 'RIGHT']:
                sh = frame_keypoints[side].get('shoulder')
                hp = frame_keypoints[side].get('hip')
                if sh is not None and hp is not None:
                    torso_lengths[side] = float(np.linalg.norm(sh - hp))
                else:
                    torso_lengths[side] = 1.0  # fallback: no normalization

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

                    value = None
                    if metric_type == 'angle':
                        if len(points) == 3:
                            p0, p1, p2 = points[0], points[1], points[2]

                            if isinstance(p0, str):
                                p0 = np.array([p1[0], p1[1] - 0.5, p1[2]]) if p0 == 'vertical' else np.array([p1[0] + 0.5, p1[1], p1[2]])
                            if isinstance(p2, str):
                                p2 = np.array([p1[0], p1[1] - 0.5, p1[2]]) if p2 == 'vertical' else np.array([p1[0] + 0.5, p1[1], p1[2]])

                            if not any(type(p) is str for p in (p0, p1, p2)):
                                value = GeometryChecks.calculate_angle(p0, p1, p2)

                    elif metric_type == 'horizontal_distance':
                        if len(points) >= 2:
                            raw = GeometryChecks.calculate_horizontal_distance(points[0], points[1])
                            torso = max(torso_lengths[side], 1e-6)
                            value = raw / torso

                    elif metric_type == 'vertical_distance':
                        if len(points) >= 2:
                            raw = GeometryChecks.calculate_vertical_distance(points[0], points[1])
                            torso = max(torso_lengths[side], 1e-6)
                            value = raw / torso

                    elif metric_type == 'distance_from_line':
                        if len(points) == 3:
                            raw = GeometryChecks.distance_from_line(points[0], points[1], points[2])
                            torso = max(torso_lengths[side], 1e-6)
                            value = raw / torso

                    if value is not None:
                        frame_metrics[f"{metric_name}_{side.lower()}"] = value

        if frame_metrics:
            for key, value in frame_metrics.items():
                parts = key.rsplit('_', 1)
                if len(parts) == 2:
                    metric_name, side = parts
                    if metric_name in collected_values and side in collected_values[metric_name]:
                        collected_values[metric_name][side].append(value)

        if frame_callback:
            # Apply EMA smoothing before passing metrics to the inference callback.
            smoothed_metrics = ema.smooth(frame_metrics) if (ema and frame_metrics) else frame_metrics
            if frame_callback(frame, smoothed_metrics if smoothed_metrics else None, results if results.pose_world_landmarks else None) is False:
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
                arr = np.array(values)
                # Use robust percentile-based min/max to ignore 1-frame glitches
                result[f"{metric_name}_{side}_min"] = float(np.percentile(arr, 5))
                result[f"{metric_name}_{side}_max"] = float(np.percentile(arr, 95))
            else:
                result[f"{metric_name}_{side}_min"] = None
                result[f"{metric_name}_{side}_max"] = None

    return result if has_data else None