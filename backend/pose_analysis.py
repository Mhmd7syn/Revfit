"""
pose_analysis.py — Server-side wrapper for the Pose Estimation module.

Runs inference headless, computes a form score, and writes an annotated
correction video with green/red skeleton overlays.

Also provides ``stream_analyze_video()`` — a generator that yields
annotated frames one-by-one for real-time WebSocket streaming.
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


@dataclass
class StreamFrame:
    """A single annotated frame yielded during streaming analysis."""

    index: int               # 1-based frame index (processed frames)
    total: int               # total frame count in the video
    annotated_jpeg: bytes    # JPEG-encoded annotated frame
    is_good_form: bool
    feedback_messages: List[str]
    rep_count: int
    form_score: float        # running form score 0–100


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


def stream_analyze_video(
    video_path: str,
    exercise_name: str,
    frame_skip: int = 2,
    max_width: int = 640,
    output_dir: Optional[str] = None,
    frame_queue: Optional["queue.Queue[StreamFrame | PoseResult | None]"] = None,
) -> None:
    """
    Single-pass streaming analysis that pushes ``StreamFrame`` objects into
    *frame_queue* **as each frame is processed** (not after all frames are
    done).  When processing finishes, it compiles the output video, pushes
    a final ``PoseResult``, then pushes ``None`` as a sentinel.

    This function is **blocking** — call it from a background thread while
    the WebSocket handler reads from *frame_queue* concurrently.

    If *frame_queue* is ``None``, one is created internally and the function
    returns it (useful for testing).
    """
    import queue as _queue_mod

    if frame_queue is None:
        frame_queue = _queue_mod.Queue()

    exercise_name_lower = exercise_name.lower()
    if exercise_name_lower not in EXERCISE_TO_CONFIG:
        frame_queue.put(None)  # sentinel
        raise ValueError(
            f"Unsupported exercise '{exercise_name}'. "
            f"Supported: {list_supported_exercises()}"
        )

    ex_config = EXERCISE_TO_CONFIG[exercise_name_lower]
    metric_keys = ex_config.get("metrics", [])
    ref = ex_config.get("thresholds", {})
    metric_configs = {
        m: JOINT_DEFINITIONS[m] for m in metric_keys if m in JOINT_DEFINITIONS
    }

    # ── Open video to read metadata ──────────────────────────────────
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        frame_queue.put(None)
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    # ── Initialize repetition counter ────────────────────────────────
    rep_counter = RepetitionCounter(exercise_name_lower, metric_configs, ref)

    proc_state = {
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

    # Collect annotated frames for final video compilation
    annotated_frames: list = []
    first_frame_size = None
    min_height = 360
    estimated_total = total_frames // (frame_skip + 1) if frame_skip else total_frames

    def frame_callback(frame, current_metrics, results):
        """Called by pv.process_video for each frame — pushes to queue immediately."""
        nonlocal first_frame_size

        proc_state["frame_count"] += frame_skip + 1
        if proc_state["frame_count"] > total_frames:
            proc_state["frame_count"] = total_frames

        active_sides = get_active_sides(results)
        is_good_form, feedback_messages, bad_joints = evaluate_metrics(
            current_metrics, metric_configs, ref, proc_state, active_sides
        )
        if current_metrics:
            proc_state["rep_counter"].add_frame(current_metrics, active_sides)
            proc_state["rep_count"] = proc_state["rep_counter"].get_rep_count()

        # ── Draw annotated frame ─────────────────────────────────────
        display = frame.copy()
        h, w = display.shape[:2]
        if h < min_height:
            scale = min_height / h
            display = cv2.resize(display, (int(w * scale), int(h * scale)))
            h, w = display.shape[:2]

        draw_skeleton(display, results, metric_configs, bad_joints, active_sides)

        composite, bar_h, proc_state["bar_width"] = create_info_bar(
            display, w, h, feedback_messages, fixed_width=proc_state["bar_width"]
        )
        draw_overlays(
            composite,
            exercise_name_lower,
            is_good_form,
            proc_state["frame_count"],
            total_frames,
            fps,
            feedback_messages,
            bar_h=bar_h,
            rep_count=proc_state["rep_count"],
        )

        if first_frame_size is None:
            first_frame_size = (composite.shape[1], composite.shape[0])

        # Resize to consistent dimensions
        target_w, target_h = first_frame_size
        if composite.shape[1] != target_w or composite.shape[0] != target_h:
            composite = cv2.resize(composite, (target_w, target_h))

        # Keep full-res copy for final video compilation
        annotated_frames.append(composite)

        # ── Encode JPEG for streaming (optionally downscaled) ────────
        stream_img = composite
        sf_h, sf_w = stream_img.shape[:2]
        if max_width and sf_w > max_width:
            scale_factor = max_width / sf_w
            stream_img = cv2.resize(
                stream_img,
                (max_width, int(sf_h * scale_factor)),
            )

        _, jpeg_buf = cv2.imencode(".jpg", stream_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
        jpeg_bytes = jpeg_buf.tobytes()

        # Running form score
        fc = proc_state["frame_count"]
        bad_count = len({
            f for msg_instances in proc_state["feedbacks"].values()
            for inst in msg_instances
            for f in [inst["frame"]]
        })
        form_score = round(((fc - bad_count) / fc) * 100, 2) if fc > 0 else 100.0

        # ── Push to queue IMMEDIATELY (real-time) ────────────────────
        frame_queue.put(StreamFrame(
            index=len(annotated_frames),
            total=estimated_total,
            annotated_jpeg=jpeg_bytes,
            is_good_form=is_good_form,
            feedback_messages=feedback_messages,
            rep_count=proc_state["rep_count"],
            form_score=form_score,
        ))

        return True

    # ── Run the blocking processing loop ─────────────────────────────
    # pv.process_video iterates every frame; our callback pushes each
    # StreamFrame to the queue in real-time as it's produced.
    pv.process_video(
        (video_path, exercise_name_lower, metric_configs),
        frame_skip=frame_skip,
        frame_callback=frame_callback,
    )

    # ── Compile final video ──────────────────────────────────────────
    out_dir = output_dir or POSE_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_filename = f"{uuid.uuid4().hex}.mp4"
    out_path = os.path.join(out_dir, out_filename)

    if annotated_frames and first_frame_size:
        out_fps = fps / (frame_skip + 1) if frame_skip else fps
        _compile_video(annotated_frames, out_path, out_fps, first_frame_size)

    # ── Build and push final result ──────────────────────────────────
    bad_frames_set = set()
    feedback_summary: Dict[str, int] = {}
    for msg, instances in proc_state["feedbacks"].items():
        feedback_summary[msg] = len(instances)
        for inst in instances:
            bad_frames_set.add(inst["frame"])

    processed_count = proc_state["frame_count"]
    bad_count = len(bad_frames_set)
    form_score = round(((processed_count - bad_count) / processed_count) * 100, 2) if processed_count > 0 else 100.0

    frame_queue.put(PoseResult(
        exercise_name=exercise_name_lower,
        form_score=form_score,
        rep_count=proc_state["rep_count"],
        total_frames=processed_count,
        bad_frame_count=bad_count,
        feedback_summary=feedback_summary,
        output_video_path=out_path,
    ))

    # Sentinel: signals the consumer that no more items will come
    frame_queue.put(None)


def _compile_video(
    frames: list,
    output_path: str,
    fps: float,
    frame_size: tuple,
) -> None:
    """Write a list of annotated frames to a video file."""

    def _try_write(path: str, fourcc_str: str) -> bool:
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(path, fourcc, fps, frame_size)
        if not writer.isOpened():
            return False
        for fr in frames:
            writer.write(fr)
        writer.release()
        return os.path.getsize(path) > 0

    # Attempt 1: H.264 (avc1)
    if _try_write(output_path, "avc1"):
        return

    # Attempt 2: mp4v then re-encode via ffmpeg
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
        os.rename(tmp_path, output_path)


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

