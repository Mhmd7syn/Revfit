"""
endpoints/pose.py  – all /api/pose/* routes
"""
import os
import sys
import shutil
import tempfile
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

# Make Pose/Code importable
_POSE_CODE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'Code')
)
if _POSE_CODE_DIR not in sys.path:
    sys.path.insert(0, _POSE_CODE_DIR)

from exercise_config import EXERCISE_TO_CONFIG  # noqa: E402

router = APIRouter(prefix="/api/pose", tags=["Pose Analysis"])

# In-memory session store  {session_id: AnalysisResult dict}
_sessions: Dict[str, Any] = {}


def _get_output_dir() -> str:
    """Returns (and creates) the outputs directory next to this package."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))
    os.makedirs(base, exist_ok=True)
    return base


# ── GET /api/pose/exercises ────────────────────────────────────────────────
@router.get("/exercises")
async def list_exercises():
    """Return all supported exercise names, sorted alphabetically."""
    exercises = sorted(EXERCISE_TO_CONFIG.keys())
    return {"exercises": exercises, "total": len(exercises)}


# ── POST /api/pose/analyze ─────────────────────────────────────────────────
@router.post("/analyze")
async def analyze_video(
    exercise_name: str = Form(..., description="Exercise name, e.g. 'squat'"),
    video: UploadFile = File(..., description="Video file (.mp4 / .mov / .avi)"),
):
    """
    Upload a video + exercise name.
    Returns analysis JSON with session_id for follow-up download.
    Processing is synchronous (runs in the request).
    """
    if exercise_name not in EXERCISE_TO_CONFIG:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported exercise '{exercise_name}'. "
                   f"Call GET /api/pose/exercises for the full list.",
        )

    # Save upload to a temp file
    suffix = os.path.splitext(video.filename or "video.mp4")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video.file, tmp)
        tmp_path = tmp.name

    try:
        from video_processor import process_and_annotate  # lazy import (heavy)

        output_dir = _get_output_dir()
        result = process_and_annotate(
            video_path=tmp_path,
            exercise_name=exercise_name,
            output_dir=output_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[API] ERROR in /analyze: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")
    finally:
        os.unlink(tmp_path)

    total = max(result['total_frames'], 1)
    bad = result['bad_frames']
    good_pct = round(max(0.0, (total - bad) / total) * 100, 1)

    payload = {
        "session_id": result['session_id'],
        "exercise_name": exercise_name,
        "total_frames": result['total_frames'],
        "bad_frames": bad,
        "rep_count": result['rep_count'],
        "good_form_percent": good_pct,
        "feedbacks": result['feedbacks'],
        "annotated_video_url": f"/api/pose/download/{result['session_id']}",
        "status": "completed",
    }
    _sessions[result['session_id']] = payload
    # Also store the output path for the download endpoint
    _sessions[result['session_id']]['_output_path'] = result['output_path']

    # Return without the internal key
    return {k: v for k, v in payload.items() if not k.startswith('_')}


# ── GET /api/pose/result/{session_id} ─────────────────────────────────────
@router.get("/result/{session_id}")
async def get_result(session_id: str):
    """Retrieve the stored analysis JSON for a previous session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {k: v for k, v in session.items() if not k.startswith('_')}


# ── GET /api/pose/download/{session_id} ───────────────────────────────────
@router.get("/download/{session_id}")
async def download_video(session_id: str):
    """Stream the annotated output video for download."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    output_path = session.get('_output_path', '')
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Annotated video file not found.")

    filename = f"analyzed_{session.get('exercise_name', 'video').replace(' ', '_')}.mp4"
    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=filename,
    )
