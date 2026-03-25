"""
video_processor.py
Headless video processor: runs pose inference and writes an annotated output video.
"""
import os
import sys
import uuid
import cv2
import numpy as np

# Make sure Pose/Code is on the path
_POSE_CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Code'))
if _POSE_CODE_DIR not in sys.path:
    sys.path.insert(0, _POSE_CODE_DIR)

import process_video as pv
from exercise_config import EXERCISE_TO_CONFIG, JOINT_DEFINITIONS
from inference import (
    get_active_sides,
    evaluate_metrics,
    update_rep_count,
    draw_skeleton,
    create_info_bar,
    draw_overlays,
)


def process_and_annotate(
    video_path: str,
    exercise_name: str,
    output_dir: str,
    frame_skip: int = 2,
) -> dict:
    """
    Runs pose analysis on *video_path* and writes an annotated MP4 to *output_dir*.

    Returns a dict with:
      session_id, output_path, total_frames, bad_frames, feedbacks, rep_count
    """
    if exercise_name not in EXERCISE_TO_CONFIG:
        raise ValueError(f"Unsupported exercise: '{exercise_name}'")

    session_id = str(uuid.uuid4())
    output_path = os.path.join(output_dir, f"{session_id}.mp4")

    ex_config = EXERCISE_TO_CONFIG[exercise_name]
    metric_keys = ex_config.get('metrics', [])
    ref = ex_config.get('thresholds', {})
    metric_configs = {m: JOINT_DEFINITIONS[m] for m in metric_keys if m in JOINT_DEFINITIONS}

    # ── Open source video ──────────────────────────────────────────────────
    cap_info = cv2.VideoCapture(video_path)
    if not cap_info.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap_info.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap_info.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap_info.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap_info.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap_info.release()

    # Scale up tiny videos
    min_h = 360
    if orig_h > 0 and orig_h < min_h:
        scale = min_h / orig_h
        out_w = int(orig_w * scale)
        out_h = int(orig_h * scale)
    else:
        out_w, out_h = orig_w, orig_h

    # Ensure out_w and out_h are even for codec compatibility
    if out_w % 2 != 0: out_w += 1
    if out_h % 2 != 0: out_h += 1

    # Info-bar height estimate (5 rows, ~32px each at scale 1)
    bar_rows = 5
    scale_factor = min(out_w / 800.0, out_h / 720.0) if out_h > 0 and out_w > 0 else 1.0
    bar_h_estimate = int(32 * scale_factor * bar_rows + 24 * scale_factor)
    composite_h = out_h + bar_h_estimate
    
    # Ensure composite_h is even
    if composite_h % 2 != 0:
        composite_h += 1

    # Try H.264 then XVID
    print(f"[Processor] Creating output video: {out_w}x{composite_h} @ {fps}fps")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (out_w, composite_h))
    if not writer.isOpened():
        print(f"[Processor] ERROR: FAILED to open VideoWriter with mp4v")
        raise RuntimeError(f"Cannot create output video: {output_path}")

    # ── Shared state ───────────────────────────────────────────────────────
    _rep_metric = None
    _rep_low_thresh = None
    _rep_high_thresh = None
    for _m, _mdef in metric_configs.items():
        if _mdef.get('type', 'angle') == 'angle' and ref.get(f"{_m}_min") is not None:
            _r_min = ref[f"{_m}_min"]
            _r_max = ref[f"{_m}_max"]
            _span = _r_max - _r_min
            if _span > 0:
                _rep_metric = _m
                _rep_low_thresh = _r_min + 0.25 * _span
                _rep_high_thresh = _r_max - 0.25 * _span
            break

    state = {
        'frame_count': 0,
        'feedbacks': {},
        'bar_width': None,
        'rep_count': 0,
        'rep_phase': {'left': 'extended', 'right': 'extended'},
        'rep_side_counts': {'left': 0, 'right': 0},
        'rep_metric': _rep_metric,
        'rep_low_thresh': _rep_low_thresh,
        'rep_high_thresh': _rep_high_thresh,
    }

    def frame_callback(frame, current_metrics, results):
        state['frame_count'] += (frame_skip + 1)
        if state['frame_count'] > total_frames:
            state['frame_count'] = total_frames

        active_sides = get_active_sides(results)
        is_good_form, feedback_messages, bad_joints = evaluate_metrics(
            current_metrics, metric_configs, ref, state, active_sides
        )
        if current_metrics:
            update_rep_count(current_metrics, state, active_sides)

        display_frame = frame.copy()
        h, w = display_frame.shape[:2]
        if h < min_h:
            s = min_h / h
            display_frame = cv2.resize(display_frame, (int(w * s), int(h * s)))

        h, w = display_frame.shape[:2]
        draw_skeleton(display_frame, results, metric_configs, bad_joints, active_sides)

        composite, bar_h, state['bar_width'] = create_info_bar(
            display_frame, w, h, feedback_messages, fixed_width=state['bar_width']
        )
        draw_overlays(
            composite,
            exercise_name,
            is_good_form,
            state['frame_count'],
            total_frames,
            fps,
            feedback_messages,
            bar_h=bar_h,
            rep_count=state['rep_count'],
        )

        # Resize composite to (out_w, composite_h) so VideoWriter stays happy
        comp_h, comp_w = composite.shape[:2]
        if comp_w != out_w or comp_h != composite_h:
            composite = cv2.resize(composite, (out_w, composite_h))

        writer.write(composite)
        if state['frame_count'] % 50 == 0:
            print(f"[Processor] Progress: {state['frame_count']}/{total_frames} frames")
        return True

    pv.process_video(
        (video_path, exercise_name, metric_configs),
        frame_skip=frame_skip,
        frame_callback=frame_callback,
    )
    writer.release()

    # ── Summarise feedbacks ────────────────────────────────────────────────
    bad_frame_set = set()
    feedback_summary = []
    for msg, instances in state['feedbacks'].items():
        for inst in instances:
            bad_frame_set.add(inst['frame'])
        avg_val = sum(i['current_val'] for i in instances) / len(instances)
        feedback_summary.append({
            'message': msg,
            'occurrence_count': len(instances),
            'metric_type': instances[0]['metric_type'],
            'avg_value': round(avg_val, 3),
        })

    return {
        'session_id': session_id,
        'output_path': output_path,
        'total_frames': state['frame_count'],
        'bad_frames': len(bad_frame_set),
        'feedbacks': feedback_summary,
        'rep_count': state['rep_count'],
    }
