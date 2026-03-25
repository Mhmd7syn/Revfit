"""
routers/pose.py — Pose-analysis endpoints.

POST /pose/analyze/{session_id}   → upload video, run analysis, return results
GET  /pose/history/{session_id}   → retrieve past analysis results
GET  /pose/exercises              → list supported exercise names
"""

import os
import shutil
import tempfile
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas import PoseAnalysisResponse
from pose_analysis import analyze_video, list_supported_exercises, POSE_OUTPUT_DIR
import state

router = APIRouter()


@router.get("/exercises", response_model=List[str])
def exercises():
    """Return the list of exercise names that the Pose module supports."""
    return list_supported_exercises()


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


@router.get("/history/{session_id}", response_model=List[PoseAnalysisResponse])
def history(session_id: str):
    """Return all past pose-analysis results for a session."""
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return state.get_pose_results(session_id)
