"""
routers/workouts.py — Workout endpoints.

GET  /workouts/                              → list all workouts (with filters)
GET  /workouts/{workout_id}                  → get single workout
POST /workouts/recommend/{session_id}        → get personalised recommendations
GET  /workouts/filter                        → hard-filter workouts for a session
"""

import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from workouts import WorkoutItem, load_workouts_csv
from filters import recommend_workouts, hard_filter_workouts, score_workout
from schemas import WorkoutResponse, WorkoutRecommendRequest
import state

router = APIRouter()

# Load once at startup
_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "megaGymDataset.csv")
try:
    _ALL_WORKOUTS: List[WorkoutItem] = load_workouts_csv(_CSV_PATH)
except FileNotFoundError:
    _ALL_WORKOUTS = []


def _w_to_response(w: WorkoutItem, score: float = None) -> WorkoutResponse:
    return WorkoutResponse(
        workout_id=w.workout_id,
        name=w.name,
        workout_type=w.workout_type,
        body_part=w.body_part,
        equipment=w.equipment,
        level=w.level,
        rating=w.rating,
        score=round(score, 4) if score is not None else None,
    )


# ------------------------------------------------------------------ #

@router.get("/", response_model=dict)
def list_workouts(
    workout_type: Optional[str] = Query(None),
    body_part: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List all workouts from the dataset with optional filters and pagination.
    """
    results = _ALL_WORKOUTS
    if workout_type:
        results = [w for w in results if w.workout_type.lower() == workout_type.lower()]
    if body_part:
        results = [w for w in results if w.body_part.lower() == body_part.lower()]
    if equipment:
        results = [w for w in results if w.equipment.lower() == equipment.lower()]
    if level:
        results = [w for w in results if w.level.lower() == level.lower()]

    total = len(results)
    page = results[offset: offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "workouts": [_w_to_response(w) for w in page],
    }


@router.get("/meta", response_model=dict)
def workout_metadata():
    """Return all unique values for filters (types, body parts, equipment, levels)."""
    return {
        "workout_types": sorted({w.workout_type for w in _ALL_WORKOUTS}),
        "body_parts":    sorted({w.body_part    for w in _ALL_WORKOUTS}),
        "equipment":     sorted({w.equipment    for w in _ALL_WORKOUTS}),
        "levels":        sorted({w.level        for w in _ALL_WORKOUTS}),
        "total_workouts": len(_ALL_WORKOUTS),
    }


@router.get("/{workout_id}", response_model=WorkoutResponse)
def get_workout(workout_id: str):
    """Get a single workout by its ID."""
    for w in _ALL_WORKOUTS:
        if w.workout_id == workout_id:
            return _w_to_response(w)
    raise HTTPException(status_code=404, detail=f"Workout '{workout_id}' not found")


@router.post("/recommend/{session_id}", response_model=List[WorkoutResponse])
def recommend(session_id: str, body: WorkoutRecommendRequest):
    """
    Return top-K personalised workout recommendations for a user session.
    Applies hard filters (equipment, level) then scores by goal + feedback.
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    if not _ALL_WORKOUTS:
        raise HTTPException(status_code=503, detail="Workout dataset not loaded. Check megaGymDataset.csv path.")

    top = recommend_workouts(_ALL_WORKOUTS, user, top_k=body.top_k)
    return [_w_to_response(w, score_workout(w, user)) for w in top]


@router.get("/filter/{session_id}", response_model=List[WorkoutResponse])
def filter_workouts(session_id: str):
    """
    Return all workouts that pass the hard filter for a session
    (equipment match + level constraint), without scoring.
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    valid = hard_filter_workouts(_ALL_WORKOUTS, user)
    return [_w_to_response(w) for w in valid]
