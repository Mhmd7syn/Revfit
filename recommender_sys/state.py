"""
state.py — Simple in-memory session store.

In production, replace with Redis or a database-backed session.
Each "session" is keyed by a session_id (UUID string).
"""

from __future__ import annotations
from typing import Dict
from uuid import uuid4

from user_profile import UserProfile
from feedback import FeedbackStore


# ---- Singleton stores ---- #

_sessions: Dict[str, UserProfile] = {}
_feedback_store = FeedbackStore()          # single shared store (file-backed)


def create_session(user: UserProfile) -> str:
    session_id = str(uuid4())
    _sessions[session_id] = user
    _feedback_store.load_into_user(user)
    return session_id


def get_user(session_id: str) -> UserProfile | None:
    return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


def list_sessions() -> list[str]:
    return list(_sessions.keys())


def get_feedback_store() -> FeedbackStore:
    return _feedback_store


# ---- Pose analysis results ---- #

_pose_results: Dict[str, list] = {}  # session_id → [result_dict, …]


def store_pose_result(session_id: str, result: dict) -> None:
    """Append a pose-analysis result dict for the given session."""
    _pose_results.setdefault(session_id, []).append(result)


def get_pose_results(session_id: str) -> list:
    """Return all pose-analysis results for the given session."""
    return _pose_results.get(session_id, [])
