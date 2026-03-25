"""
routers/feedback.py — Feedback persistence endpoints.

POST /feedback/meal/{session_id}      → like/dislike a meal
POST /feedback/workout/{session_id}   → like/dislike a workout
GET  /feedback/{session_id}           → get full feedback summary for session
GET  /feedback/store/summary          → global feedback store summary
DELETE /feedback/{session_id}/reset   → clear all feedback for a session
"""

from fastapi import APIRouter, HTTPException

from schemas import MealFeedbackRequest, WorkoutFeedbackRequest, FeedbackSummaryResponse
import state

router = APIRouter()


def _get_or_404(session_id: str):
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return user


def _find_workout(workout_id: str):
    """Look up a WorkoutItem from the dataset loaded in the workouts router."""
    from routers.workouts import _ALL_WORKOUTS
    for w in _ALL_WORKOUTS:
        if w.workout_id == workout_id:
            return w
    return None


# ------------------------------------------------------------------ #

@router.post("/meal/{session_id}", response_model=dict)
def meal_feedback(session_id: str, body: MealFeedbackRequest):
    """Record a like / dislike for a meal recipe."""
    user = _get_or_404(session_id)
    user.add_meal_feedback(body.recipe_id, liked=body.liked)

    store = state.get_feedback_store()
    store.record_meal(body.recipe_id, liked=body.liked)

    action = "liked" if body.liked else "disliked"
    return {"status": "ok", "recipe_id": body.recipe_id, "action": action}


@router.post("/workout/{session_id}", response_model=dict)
def workout_feedback(session_id: str, body: WorkoutFeedbackRequest):
    """Record a like / dislike for a workout."""
    user = _get_or_404(session_id)

    workout = _find_workout(body.workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail=f"Workout '{body.workout_id}' not found in dataset")

    user.add_workout_feedback(workout, liked=body.liked)

    store = state.get_feedback_store()
    store.record_workout(workout, liked=body.liked)

    action = "liked" if body.liked else "disliked"
    return {"status": "ok", "workout_id": body.workout_id, "action": action}


@router.get("/{session_id}", response_model=FeedbackSummaryResponse)
def get_feedback(session_id: str):
    """Get all feedback recorded for a user session."""
    user = _get_or_404(session_id)
    return FeedbackSummaryResponse(
        liked_meals=user.liked_meals,
        disliked_meals=user.disliked_meals,
        liked_workouts=user.liked_workouts,
        disliked_workouts=user.disliked_workouts,
        workout_preferences=user.workout_preferences,
        workout_type_preferences=dict(user.workout_type_preferences),
    )


@router.get("/store/summary", response_model=dict)
def store_summary():
    """Return a summary of the global on-disk feedback store."""
    store = state.get_feedback_store()
    return {"summary": store.summary()}


@router.delete("/{session_id}/reset", response_model=dict)
def reset_feedback(session_id: str):
    """Clear all feedback for a session (in-memory only; does not affect disk store)."""
    user = _get_or_404(session_id)
    user.liked_meals.clear()
    user.disliked_meals.clear()
    user.liked_workouts.clear()
    user.disliked_workouts.clear()
    user.workout_preferences.clear()
    user.workout_type_preferences.clear()
    return {"status": "reset", "session_id": session_id}
