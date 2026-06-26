"""
live_pose.py — Real-time frame-by-frame pose estimation processor.

Each WebSocket connection creates a ``LivePoseProcessor`` instance that
maintains per-session state (TCN buffer, rep counter, running score) and
exposes ``process_frame(jpeg_bytes) → dict`` for each incoming camera frame.

Reuses the same inference pipeline as the batch ``pose_analysis.py`` module
(MediaPipe PoseLandmarker → TCN refinement → metric evaluation).
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Make the Pose/Code package importable (same as pose_analysis.py)
# ---------------------------------------------------------------------------
_POSE_CODE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Pose", "Code")
)
if _POSE_CODE_DIR not in sys.path:
    sys.path.insert(0, _POSE_CODE_DIR)

import torch
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from process_video import (
    load_tcn_model,
    get_landmark_coords_from_fit3d,
    TCN_MODEL,
    TCN_WINDOW_SIZE,
    MP_POSE,
)
from evaluation import get_active_sides, evaluate_metrics
from exercise_config import EXERCISE_TO_CONFIG, JOINT_DEFINITIONS
from repetition_counter import RepetitionCounter


# ---------------------------------------------------------------------------
# MediaPipe model path (resolved once)
# ---------------------------------------------------------------------------
_MP_MODEL_PATH = os.path.abspath(
    os.path.join(_POSE_CODE_DIR, "..", "Models", "pose_landmarker_full.task")
)


class LivePoseProcessor:
    """Processes camera frames one-by-one for a single live session.

    Lifecycle
    ---------
    1.  Construct with the exercise name.
    2.  Call ``process_frame(jpeg_bytes)`` for every incoming JPEG frame.
    3.  Call ``get_summary()`` when the session ends.
    """

    def __init__(self, exercise_name: str) -> None:
        exercise_name = exercise_name.lower()
        if exercise_name not in EXERCISE_TO_CONFIG:
            raise ValueError(
                f"Unsupported exercise '{exercise_name}'. "
                f"Supported: {sorted(EXERCISE_TO_CONFIG.keys())}"
            )
        self.exercise_name = exercise_name

        # ── Exercise config ──────────────────────────────────────────────
        ex_config = EXERCISE_TO_CONFIG[exercise_name]
        metric_keys = ex_config.get("metrics", [])
        self.ref = ex_config.get("thresholds", {})
        self.metric_configs = {
            m: JOINT_DEFINITIONS[m] for m in metric_keys if m in JOINT_DEFINITIONS
        }

        # ── MediaPipe PoseLandmarker ─────────────────────────────────────
        base_options = mp_python.BaseOptions(model_asset_path=_MP_MODEL_PATH)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
        )
        self.mp_pose = vision.PoseLandmarker.create_from_options(options)

        # ── TCN model (lazy-loaded global singleton) ─────────────────────
        global TCN_MODEL
        if TCN_MODEL is None:
            load_tcn_model()
        self.tcn_model = TCN_MODEL
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # ── Per-session tracking state ───────────────────────────────────
        self.landmark_buffer: list = []  # sliding window for TCN
        self.rep_counter = RepetitionCounter(
            exercise_name, self.metric_configs, self.ref
        )
        self.frame_count = 0
        self.bad_frame_count = 0
        self.feedbacks: Dict[str, list] = {}

        # Internal state dict expected by evaluate_metrics
        self._eval_state = {
            "paused": False,
            "frame_count": 0,
            "quit": False,
            "headless": True,
            "feedbacks": self.feedbacks,
            "bar_width": None,
            "window_created": False,
            "rep_count": 0,
            "rep_counter": self.rep_counter,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, jpeg_bytes: bytes) -> dict:
        """Decode a JPEG frame and run the full inference pipeline.

        Returns a dict suitable for JSON serialisation::

            {
                "is_good_form": True,
                "feedback_messages": ["[LEFT] Keep elbows tucked"],
                "rep_count": 3,
                "form_score": 87.5,
                "landmarks": [[0.52, 0.31, 0.99], ...],   # 33 × [x, y, vis]
            }
        """
        # Decode JPEG → OpenCV BGR frame
        buf = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if frame is None:
            return self._empty_response()

        self.frame_count += 1
        self._eval_state["frame_count"] = self.frame_count

        # ── MediaPipe detection ──────────────────────────────────────────
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self.mp_pose.detect(mp_image)

        # Extract 2D landmarks for the overlay (normalised 0-1)
        landmarks_2d: List[List[float]] = []
        if results.pose_landmarks and len(results.pose_landmarks) > 0:
            landmarks_2d = [
                [lm.x, lm.y, lm.visibility]
                for lm in results.pose_landmarks[0]
            ]

        # Extract 3D world landmarks for TCN
        if results.pose_world_landmarks and len(results.pose_world_landmarks) > 0:
            current_raw = np.array(
                [[lm.x, lm.y, lm.z] for lm in results.pose_world_landmarks[0]]
            )
            self.landmark_buffer.append(current_raw)
        else:
            last = (
                self.landmark_buffer[-1]
                if self.landmark_buffer
                else np.zeros((33, 3))
            )
            self.landmark_buffer.append(last)

        # Trim buffer
        if len(self.landmark_buffer) > TCN_WINDOW_SIZE:
            self.landmark_buffer.pop(0)

        # ── TCN refinement & metric computation ──────────────────────────
        frame_metrics: dict = {}
        if self.tcn_model and len(self.landmark_buffer) > 0:
            frame_metrics = self._run_tcn_and_metrics()

        # ── Evaluate form ────────────────────────────────────────────────
        valid_results = (
            results
            if (
                hasattr(results, "pose_world_landmarks")
                and results.pose_world_landmarks
                and len(results.pose_world_landmarks) > 0
            )
            else None
        )
        active_sides = get_active_sides(valid_results)
        is_good_form, feedback_messages, bad_joints = evaluate_metrics(
            frame_metrics if frame_metrics else None,
            self.metric_configs,
            self.ref,
            self._eval_state,
            active_sides,
        )

        if not is_good_form and feedback_messages:
            self.bad_frame_count += 1

        # ── Rep counting ─────────────────────────────────────────────────
        if frame_metrics:
            self.rep_counter.add_frame(frame_metrics, active_sides)
            self._eval_state["rep_count"] = self.rep_counter.get_rep_count()

        # ── Running form score ───────────────────────────────────────────
        form_score = 100.0
        if self.frame_count > 0:
            form_score = round(
                ((self.frame_count - self.bad_frame_count) / self.frame_count)
                * 100,
                2,
            )

        return {
            "is_good_form": is_good_form,
            "feedback_messages": feedback_messages,
            "rep_count": self._eval_state["rep_count"],
            "form_score": form_score,
            "landmarks": landmarks_2d,
        }

    def get_summary(self) -> dict:
        """Return an end-of-session summary matching LivePoseSessionSummary."""
        feedback_summary: Dict[str, int] = {}
        for msg, instances in self.feedbacks.items():
            feedback_summary[msg] = len(instances)

        form_score = 100.0
        if self.frame_count > 0:
            form_score = round(
                ((self.frame_count - self.bad_frame_count) / self.frame_count)
                * 100,
                2,
            )

        return {
            "exercise_name": self.exercise_name,
            "total_frames": self.frame_count,
            "rep_count": self._eval_state["rep_count"],
            "form_score": form_score,
            "feedback_summary": feedback_summary,
        }

    def close(self) -> None:
        """Release resources."""
        try:
            self.mp_pose.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_tcn_and_metrics(self) -> dict:
        """Run TCN refinement on the current buffer and compute metrics."""
        mid_idx = TCN_WINDOW_SIZE // 2

        if len(self.landmark_buffer) < TCN_WINDOW_SIZE:
            pad_left = TCN_WINDOW_SIZE - len(self.landmark_buffer)
            window = np.pad(
                self.landmark_buffer, ((pad_left, 0), (0, 0), (0, 0)), mode="edge"
            )
        else:
            window = np.array(self.landmark_buffer)

        with torch.no_grad():
            # Root-relative normalisation (hips midpoint)
            mp_root = (window[:, 23, :] + window[:, 24, :]) / 2.0
            norm_window = window - mp_root[:, np.newaxis, :]

            # Scale normalisation (median spine length)
            mp_shoulders = (norm_window[:, 11, :] + norm_window[:, 12, :]) / 2.0
            mp_spine_len_all = np.linalg.norm(mp_shoulders, axis=-1)
            mp_spine_len_median = max(1e-5, float(np.median(mp_spine_len_all)))
            norm_window = norm_window / mp_spine_len_median

            tens = (
                torch.from_numpy(norm_window)
                .float()
                .unsqueeze(0)
                .to(self.device)
            )
            refined_full = self.tcn_model(tens).squeeze(0).cpu().numpy()
            refined_full = refined_full * mp_spine_len_median

            idx = (
                mid_idx
                if len(self.landmark_buffer) >= TCN_WINDOW_SIZE
                else -1
            )
            refined_pose = refined_full[idx]

        # Compute metrics from refined pose
        frame_metrics: dict = {}
        for metric_name, config in self.metric_configs.items():
            joints = config.get("joints", [])
            metric_type = config.get("type", "angle")

            for side in ["LEFT", "RIGHT"]:
                points = []
                valid = True
                for j in joints:
                    p = get_landmark_coords_from_fit3d(refined_pose, j, side)
                    if p is None:
                        valid = False
                        break
                    points.append(p)

                if not valid:
                    continue

                value = None
                if metric_type == "angle" and len(points) == 3:
                    a, b, c = points[0], points[1], points[2]
                    if isinstance(a, str):
                        a = (
                            np.array([b[0], b[1] - 0.5, b[2]])
                            if a == "vertical"
                            else np.array([b[0] + 0.5, b[1], b[2]])
                        )
                    if isinstance(c, str):
                        c = (
                            np.array([b[0], b[1] - 0.5, b[2]])
                            if c == "vertical"
                            else np.array([b[0] + 0.5, b[1], b[2]])
                        )
                    ba = a - b
                    bc = c - b
                    n1, n2 = np.linalg.norm(ba), np.linalg.norm(bc)
                    if n1 > 1e-6 and n2 > 1e-6:
                        cos_a = np.dot(ba, bc) / (n1 * n2)
                        value = np.degrees(
                            np.arccos(np.clip(cos_a, -1.0, 1.0))
                        )
                elif metric_type == "horizontal_distance" and len(points) >= 2:
                    value = np.abs(points[0][0] - points[1][0]) / 0.5
                elif metric_type == "vertical_distance" and len(points) >= 2:
                    value = np.abs(points[0][1] - points[1][1]) / 0.5
                elif metric_type == "distance_from_line" and len(points) == 3:
                    p0, p1, p2 = points[0], points[1], points[2]
                    value = np.linalg.norm(
                        np.cross(p1 - p0, p0 - p2)
                    ) / np.linalg.norm(p1 - p0)

                if value is not None:
                    frame_metrics[f"{metric_name}_{side.lower()}"] = value

        return frame_metrics

    def _empty_response(self) -> dict:
        """Return a safe empty response for undecodable frames."""
        return {
            "is_good_form": True,
            "feedback_messages": ["No frame data"],
            "rep_count": self._eval_state.get("rep_count", 0),
            "form_score": 100.0,
            "landmarks": [],
        }
