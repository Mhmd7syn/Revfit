"""
routers/pose.py — Pose-analysis endpoints.

POST /pose/analyze/{session_id}        → upload video, run analysis, return results
POST /pose/classify/{session_id}       → upload video, classify exercise via ensemble
POST /pose/upload/{session_id}         → upload video for streaming analysis
GET  /pose/history/{session_id}        → retrieve past analysis results
GET  /pose/exercises                   → list supported exercise names
WS   /pose/live/{session_id}           → real-time pose estimation via WebSocket
WS   /pose/stream-analyze/{session_id} → stream annotated frames from uploaded video
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect

from schemas import PoseAnalysisResponse, ExerciseClassificationResponse, VideoUploadResponse
from pose_analysis import (
    analyze_video,
    list_supported_exercises,
    stream_analyze_video,
    PoseResult,
    StreamFrame,
    POSE_OUTPUT_DIR,
)
from exercise_classifier import classify_exercise, EXERCISE_CLASSES
from live_pose import LivePoseProcessor
from video_upload import save_upload, get_upload_path, cleanup_upload
import state

router = APIRouter()


@router.get("/exercises", response_model=List[str])
def exercises():
    """Return the list of exercise names that the Pose module supports."""
    return list_supported_exercises()


@router.get("/classifier/classes", response_model=List[str])
def classifier_classes():
    """Return the 20-class taxonomy used by the exercise classifier."""
    return EXERCISE_CLASSES


@router.post("/classify/{session_id}", response_model=ExerciseClassificationResponse)
async def classify(
    session_id: str,
    video: UploadFile = File(..., description="Short video clip for exercise detection"),
):
    """
    Upload a short video clip and receive the predicted exercise class.

    Uses a 50/50 weighted ensemble of VideoMAE (ViT) and X3D-M (3D CNN).
    The response contains the predicted exercise name and the ensemble
    confidence score.  This is Phase 1 classification only — no form
    evaluation or skeletal analysis is performed.
    """
    # Validate session
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Save the upload to a temp file
    suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(video.file, tmp)
        tmp.close()

        # Run ensemble classification
        predicted_exercise, confidence = classify_exercise(tmp.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        # Clean up temp upload
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    return ExerciseClassificationResponse(
        predicted_exercise=predicted_exercise,
        confidence=confidence,
    )


@router.post("/analyze/{session_id}", response_model=PoseAnalysisResponse)
async def analyze(
    session_id: str,
    exercise_name: str = Form(..., description="Exercise name (e.g. 'barbell biceps curl')"),
    video: UploadFile = File(..., description="Video file (.mp4, .avi, .mov)"),
):
    """
    Upload an exercise video and receive form-correction results.

    The response includes a ``video_url`` pointing to the annotated correction
    video, which can be downloaded from ``/pose-outputs/<filename>``.
    """
    # Validate session
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Save the upload to a temp file
    suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(video.file, tmp)
        tmp.close()

        # Run the analysis
        result = analyze_video(
            video_path=tmp.name,
            exercise_name=exercise_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        # Clean up temp upload (keep the output video)
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    # Build the relative URL for the correction video
    video_filename = os.path.basename(result.output_video_path)
    video_url = f"/pose-outputs/{video_filename}"

    response = PoseAnalysisResponse(
        exercise_name=result.exercise_name,
        form_score=result.form_score,
        rep_count=result.rep_count,
        total_frames=result.total_frames,
        bad_frame_count=result.bad_frame_count,
        feedback_summary=result.feedback_summary,
        video_url=video_url,
    )

    # Persist so the recommender / chatbot can access later
    state.store_pose_result(session_id, response.model_dump())

    return response


@router.post("/upload/{session_id}", response_model=VideoUploadResponse)
async def upload_video(
    session_id: str,
    video: UploadFile = File(..., description="Video file (.mp4, .avi, .mov)"),
):
    """
    Upload a video file for subsequent streaming analysis.

    Returns a ``video_id`` that can be passed to the
    ``/pose/stream-analyze/{session_id}`` WebSocket endpoint.
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    video_id = save_upload(video)
    return VideoUploadResponse(video_id=video_id)


@router.websocket("/stream-analyze/{session_id}")
async def stream_analyze(
    websocket: WebSocket,
    session_id: str,
    exercise_name: str = Query(..., description="Exercise name for form evaluation"),
    video_id: str = Query(..., description="video_id from POST /pose/upload"),
):
    """
    Stream annotated frames from a previously uploaded video.

    Processing runs in a background thread, pushing frames into a queue.
    This handler reads from the queue and sends each frame to the client
    **as soon as it's ready** — so the frontend plays chunks while the
    backend is still processing the next ones.

    Message protocol (server → client):

    - **Text** JSON ``{"type": "frame", ...}``  then immediately
    - **Binary** JPEG annotated frame
    - **Text** JSON ``{"type": "form_correction", "message": "..."}``
    - **Text** JSON ``{"type": "complete", "result": {...}}``
    """
    import queue as thread_queue_mod

    # ── Validate inputs ──────────────────────────────────────────────
    user = state.get_user(session_id)
    if not user:
        await websocket.close(code=4004, reason=f"Session '{session_id}' not found")
        return

    exercise_lower = exercise_name.lower()
    from exercise_config import EXERCISE_TO_CONFIG
    if exercise_lower not in EXERCISE_TO_CONFIG:
        await websocket.close(
            code=4000,
            reason=f"Unsupported exercise '{exercise_name}'. See GET /pose/exercises",
        )
        return

    video_path = get_upload_path(video_id)
    if not video_path:
        await websocket.close(code=4001, reason=f"Video '{video_id}' not found")
        return

    await websocket.accept()

    loop = asyncio.get_event_loop()

    # Thread-safe queue: background thread pushes items here
    t_queue: thread_queue_mod.Queue = thread_queue_mod.Queue()

    # Asyncio queue: the relay task bridges t_queue → a_queue
    a_queue: asyncio.Queue = asyncio.Queue()

    # Track recently-sent corrections for deduplication (3-sec cooldown)
    _correction_cooldowns: dict[str, float] = {}
    _CORRECTION_COOLDOWN_SECS = 3.0

    async def _relay():
        """Relay items from thread-safe queue to asyncio queue."""
        while True:
            item = await loop.run_in_executor(None, t_queue.get)
            await a_queue.put(item)
            if item is None:
                break  # sentinel received

    def _run_processing():
        """Run blocking video processing in a thread."""
        try:
            stream_analyze_video(
                video_path=video_path,
                exercise_name=exercise_lower,
                frame_queue=t_queue,
            )
        except Exception as exc:
            # Push error string then sentinel so the consumer unblocks
            t_queue.put(exc)
            t_queue.put(None)

    try:
        # Start processing in a background thread
        proc_future = loop.run_in_executor(None, _run_processing)

        # Start the relay task
        relay_task = asyncio.create_task(_relay())

        # ── Read from the async queue and send over WebSocket ────────
        while True:
            item = await a_queue.get()

            if item is None:
                # Sentinel: processing complete
                break

            if isinstance(item, Exception):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(item),
                }))
                break

            if isinstance(item, StreamFrame):
                # Send JSON metadata
                frame_msg = {
                    "type": "frame",
                    "index": item.index,
                    "total": item.total,
                    "is_good_form": item.is_good_form,
                    "feedback": item.feedback_messages,
                    "rep_count": item.rep_count,
                    "form_score": item.form_score,
                }
                await websocket.send_text(json.dumps(frame_msg))

                # Send binary annotated JPEG
                await websocket.send_bytes(item.annotated_jpeg)

                # Send form correction alerts (deduplicated)
                if not item.is_good_form and item.feedback_messages:
                    now = time.time()
                    for msg in item.feedback_messages:
                        last_sent = _correction_cooldowns.get(msg, 0)
                        if now - last_sent >= _CORRECTION_COOLDOWN_SECS:
                            await websocket.send_text(json.dumps({
                                "type": "form_correction",
                                "message": msg,
                            }))
                            _correction_cooldowns[msg] = now

            elif isinstance(item, PoseResult):
                # Final report
                video_filename = os.path.basename(item.output_video_path)
                video_url = f"/pose-outputs/{video_filename}"

                response = PoseAnalysisResponse(
                    exercise_name=item.exercise_name,
                    form_score=item.form_score,
                    rep_count=item.rep_count,
                    total_frames=item.total_frames,
                    bad_frame_count=item.bad_frame_count,
                    feedback_summary=item.feedback_summary,
                    video_url=video_url,
                )

                state.store_pose_result(session_id, response.model_dump())

                await websocket.send_text(json.dumps({
                    "type": "complete",
                    "result": response.model_dump(),
                }))

        # Wait for background thread to finish
        await proc_future
        relay_task.cancel()

        # Gracefully close
        await websocket.close()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(exc),
            }))
            await websocket.close(code=1011, reason=str(exc)[:120])
        except Exception:
            pass
    finally:
        cleanup_upload(video_id)


@router.get("/history/{session_id}", response_model=List[PoseAnalysisResponse])
def history(session_id: str):
    """Return all past pose-analysis results for a session."""
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return state.get_pose_results(session_id)


@router.websocket("/live/{session_id}")
async def live_pose(
    websocket: WebSocket,
    session_id: str,
    exercise: str = Query(..., description="Exercise name for form evaluation"),
):
    """
    Real-time pose estimation over WebSocket.

    The client sends raw JPEG frame bytes as binary messages.
    The server responds with a JSON text message per frame containing::

        {
            "is_good_form": true,
            "feedback_messages": [...],
            "rep_count": 3,
            "form_score": 87.5,
            "landmarks": [[x, y, vis], ...]
        }

    On disconnect, a final summary is stored in the session history.
    """
    # Validate session
    user = state.get_user(session_id)
    if not user:
        await websocket.close(code=4004, reason=f"Session '{session_id}' not found")
        return

    # Validate exercise
    exercise_lower = exercise.lower()
    from exercise_config import EXERCISE_TO_CONFIG
    if exercise_lower not in EXERCISE_TO_CONFIG:
        await websocket.close(
            code=4000,
            reason=f"Unsupported exercise '{exercise}'. See GET /pose/exercises",
        )
        return

    await websocket.accept()

    # Create processor
    processor = LivePoseProcessor(exercise_lower)
    loop = asyncio.get_event_loop()

    try:
        while True:
            # Receive binary JPEG data from the client
            data = await websocket.receive_bytes()

            # Run CPU-heavy inference off the event loop
            result = await loop.run_in_executor(
                None, processor.process_frame, data
            )

            # Send JSON response
            await websocket.send_text(json.dumps(result))

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Build and store session summary
        summary = processor.get_summary()
        state.store_pose_result(session_id, summary)
        processor.close()
