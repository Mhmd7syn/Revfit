"""
pose_analysis.py — Server-side wrapper for the Pose Estimation module.

Runs inference headless, computes a form score, and writes an annotated
correction video with green/red skeleton overlays.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Make the Pose/Code package importable
# ---------------------------------------------------------------------------
_POSE_CODE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Pose", "Code")
)
if _POSE_CODE_DIR not in sys.path:
    sys.path.insert(0, _POSE_CODE_DIR)

import cv2
import numpy as np

# Pose module imports (now resolvable via sys.path)
from inference import (
    get_inference,
    evaluate_metrics,
    draw_skeleton,
    create_info_bar,
    draw_overlays,
    get_active_sides,
)
from repetition_counter import RepetitionCounter
from exercise_config import EXERCISE_TO_CONFIG, JOINT_DEFINITIONS
import process_video as pv

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
POSE_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "pose_outputs")
os.makedirs(POSE_OUTPUT_DIR, exist_ok=True)


@dataclass
class PoseResult:
    """Container for pose-analysis results."""

    exercise_name: str
    form_score: float  # 0–100
    rep_count: int
    total_frames: int
    bad_frame_count: int
    feedback_summary: Dict[str, int]  # feedback message → occurrence count
    output_video_path: str  # absolute path to the annotated video


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_supported_exercises() -> List[str]:
    """Return exercise names the Pose module knows about."""
    return sorted(EXERCISE_TO_CONFIG.keys())


def analyze_video(
    video_path: str,
    exercise_name: str,
    frame_skip: int = 2,
    output_dir: Optional[str] = None,
) -> PoseResult:
    """
    Run full pose analysis on *video_path* for the given *exercise_name*.

    1.  First pass — headless inference to collect metrics.
    2.  Second pass — write an annotated correction video.
    3.  Compute form score and return a ``PoseResult``.
    """
    exercise_name_lower = exercise_name.lower()
    if exercise_name_lower not in EXERCISE_TO_CONFIG:
        raise ValueError(
            f"Unsupported exercise '{exercise_name}'. "
            f"Supported: {list_supported_exercises()}"
        )

    # ---- Pass 1: headless inference ----
    total_frames, bad_frame_count, frame_details, rep_count = get_inference(
        video_path, exercise_name_lower, headless=True, frame_skip=frame_skip
    )

    if total_frames == 0:
        raise RuntimeError(f"Could not process video: {video_path}")

    form_score = round(((total_frames - bad_frame_count) / total_frames) * 100, 2)

    # Build a compact feedback summary  {message: count}
    feedback_summary: Dict[str, int] = {}
    for frame_msgs in frame_details.values():
        for msg in frame_msgs:
            feedback_summary[msg] = feedback_summary.get(msg, 0) + 1

    # ---- Pass 2: write annotated correction video ----
    out_dir = output_dir or POSE_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_filename = f"{uuid.uuid4().hex}.mp4"
    out_path = os.path.join(out_dir, out_filename)

    _write_correction_video(
        video_path,
        exercise_name_lower,
        out_path,
        frame_skip=frame_skip,
    )

    return PoseResult(
        exercise_name=exercise_name_lower,
        form_score=form_score,
        rep_count=rep_count,
        total_frames=total_frames,
        bad_frame_count=bad_frame_count,
        feedback_summary=feedback_summary,
        output_video_path=out_path,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_correction_video(
    video_path: str,
    exercise_name: str,
    output_path: str,
    frame_skip: int = 2,
) -> None:
    """Re-process the video and write each annotated frame to *output_path*."""
    ex_config = EXERCISE_TO_CONFIG[exercise_name]
    metric_keys = ex_config.get("metrics", [])
    ref = ex_config.get("thresholds", {})
    metric_configs = {
        m: JOINT_DEFINITIONS[m] for m in metric_keys if m in JOINT_DEFINITIONS
    }

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video for correction pass: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    # Initialize the new RepetitionCounter
    rep_counter = RepetitionCounter(exercise_name, metric_configs, ref)

    # State for rep counting and feedback collection
    state = {
        "paused": False,
        "frame_count": 0,
        "quit": False,
        "headless": True,
        "feedbacks": {},
        "bar_width": None,
        "window_created": False,
        "rep_count": 0,
        "rep_counter": rep_counter,
    }

    # Collect annotated frames
    annotated_frames: list = []
    first_frame_size = None

    def frame_callback(frame, current_metrics, results):
        nonlocal first_frame_size

        state["frame_count"] += frame_skip + 1
        if state["frame_count"] > total_frames:
            state["frame_count"] = total_frames

        active_sides = get_active_sides(results)
        is_good_form, feedback_messages, bad_joints = evaluate_metrics(
            current_metrics, metric_configs, ref, state, active_sides
        )
        if current_metrics:
            state['rep_counter'].add_frame(current_metrics, active_sides)
            state['rep_count'] = state['rep_counter'].get_rep_count()

        # Draw skeleton overlay on a copy
        display = frame.copy()
        h, w = display.shape[:2]
        min_height = 360
        if h < min_height:
            scale = min_height / h
            display = cv2.resize(display, (int(w * scale), int(h * scale)))
            h, w = display.shape[:2]

        draw_skeleton(display, results, metric_configs, bad_joints, active_sides)

        composite, bar_h, state["bar_width"] = create_info_bar(
            display, w, h, feedback_messages, fixed_width=state["bar_width"]
        )
        draw_overlays(
            composite,
            exercise_name,
            is_good_form,
            state["frame_count"],
            total_frames,
            fps,
            feedback_messages,
            bar_h=bar_h,
            rep_count=state["rep_count"],
        )

        if first_frame_size is None:
            first_frame_size = (composite.shape[1], composite.shape[0])

        # Resize to consistent dimensions if needed
        target_w, target_h = first_frame_size
        if composite.shape[1] != target_w or composite.shape[0] != target_h:
            composite = cv2.resize(composite, (target_w, target_h))

        annotated_frames.append(composite)
        return True

    pv.process_video(
        (video_path, exercise_name, metric_configs),
        frame_skip=frame_skip,
        frame_callback=frame_callback,
    )

    if not annotated_frames or first_frame_size is None:
        raise RuntimeError("No frames were produced for the correction video.")

    # Write the video — try H.264 first (browser-compatible), fall back to
    # mp4v + ffmpeg re-encode if the H.264 encoder is unavailable.
    out_fps = fps / (frame_skip + 1) if frame_skip else fps

    def _try_write(path: str, fourcc_str: str) -> bool:
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(path, fourcc, out_fps, first_frame_size)
        if not writer.isOpened():
            return False
        for fr in annotated_frames:
            writer.write(fr)
        writer.release()
        return os.path.getsize(path) > 0

    # Attempt 1: H.264 (avc1) — plays natively in all browsers
    if _try_write(output_path, "avc1"):
        return

    # Attempt 2: write mp4v then re-encode to H.264 via ffmpeg
    import shutil
    import subprocess

    tmp_path = output_path + ".tmp.mp4"
    _try_write(tmp_path, "mp4v")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [ffmpeg, "-y", "-i", tmp_path, "-c:v", "libx264",
             "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
             output_path],
            capture_output=True,
        )
        os.unlink(tmp_path)
    else:
        # No ffmpeg available — serve mp4v as-is (may not play in browser)
        os.rename(tmp_path, output_path)

