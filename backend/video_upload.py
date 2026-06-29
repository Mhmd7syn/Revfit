"""
video_upload.py — Temporary video upload manager.

Saves uploaded video files to ``pose_outputs/uploads/<uuid>.<ext>`` and
provides lookup / cleanup helpers so the WebSocket streaming endpoint
can reference a previously-uploaded file by its video_id.
"""

from __future__ import annotations

import os
import shutil
import uuid
from typing import Optional

from fastapi import UploadFile

# ---------------------------------------------------------------------------
# Upload directory (sibling of pose_outputs/)
# ---------------------------------------------------------------------------
_UPLOAD_DIR = os.path.join(
    os.path.dirname(__file__), "pose_outputs", "uploads"
)
os.makedirs(_UPLOAD_DIR, exist_ok=True)

# In-memory registry:  video_id → absolute file path
_uploads: dict[str, str] = {}


def save_upload(file: UploadFile) -> str:
    """Persist *file* to disk and return a unique ``video_id``."""
    ext = os.path.splitext(file.filename or "upload.mp4")[1] or ".mp4"
    video_id = uuid.uuid4().hex
    dest = os.path.join(_UPLOAD_DIR, f"{video_id}{ext}")

    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    _uploads[video_id] = dest
    return video_id


def get_upload_path(video_id: str) -> Optional[str]:
    """Return the absolute file path for *video_id*, or ``None``."""
    path = _uploads.get(video_id)
    if path and os.path.exists(path):
        return path
    return None


def cleanup_upload(video_id: str) -> None:
    """Delete the temp file and remove the registry entry."""
    path = _uploads.pop(video_id, None)
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass
