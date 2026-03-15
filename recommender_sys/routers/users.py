"""
routers/users.py — User profile endpoints.

POST   /users/                       → create session + user profile
GET    /users/{session_id}           → get user profile
PUT    /users/{session_id}/goal      → update goal type (recalculates calories)
DELETE /users/{session_id}           → delete session
GET    /users/{session_id}/macros    → get daily macro targets
GET    /users/                       → list all active session IDs
"""

from fastapi import APIRouter, HTTPException
from schemas import (
    UserCreateRequest, UserResponse, UpdateGoalRequest, MacroTargetsResponse
)
from user_profile import UserProfile
from meal_plan import compute_macro_targets
import state

router = APIRouter()


def _user_to_response(user: UserProfile) -> UserResponse:
    return UserResponse(
        age=user.age,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        sex=user.sex,
        goal_type=user.goal_type,
        fitness_level=user.fitness_level,
        activity_level=user.activity_level,
        workout_location=user.workout_location,
        available_equipment=user.available_equipment,
        diet_type=user.diet_type,
        allergies=user.allergies,
        intolerances=user.intolerances,
        country=user.country,
        preferred_cuisine=user.preferred_cuisine,
        meals_per_day=user.meals_per_day,
        cooking_time_preference=user.cooking_time_preference,
        protein_focus=user.protein_focus,
        target_calories=user.target_calories,
    )


def _get_or_404(session_id: str) -> UserProfile:
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return user


# ------------------------------------------------------------------ #

@router.post("/", response_model=dict, status_code=201)
def create_user(body: UserCreateRequest):
    """
    Create a new user profile and return a session_id.
    All subsequent requests must include this session_id.
    """
    user = UserProfile(
        age=body.age,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        sex=body.sex,
        goal_type=body.goal_type,
        fitness_level=body.fitness_level,
        activity_level=body.activity_level,
        workout_location=body.workout_location,
        available_equipment=body.available_equipment,
        diet_type=body.diet_type,
        allergies=body.allergies,
        intolerances=body.intolerances,
        country=body.country,
        preferred_workout_duration=body.preferred_workout_duration,
        cardio_strength_bias=body.cardio_strength_bias,
        meals_per_day=body.meals_per_day,
        cooking_time_preference=body.cooking_time_preference,
        protein_focus=body.protein_focus,
    )
    session_id = state.create_session(user)
    return {"session_id": session_id, "target_calories": user.target_calories}


@router.get("/", response_model=dict)
def list_sessions():
    """List all active session IDs."""
    return {"sessions": state.list_sessions()}


@router.get("/{session_id}", response_model=UserResponse)
def get_user(session_id: str):
    """Get user profile for a session."""
    return _user_to_response(_get_or_404(session_id))


@router.put("/{session_id}/goal", response_model=UserResponse)
def update_goal(session_id: str, body: UpdateGoalRequest):
    """Update goal type — recalculates target_calories automatically."""
    user = _get_or_404(session_id)
    user.update_goal(body.goal_type)
    return _user_to_response(user)


@router.delete("/{session_id}", response_model=dict)
def delete_session(session_id: str):
    """Delete a session."""
    if not state.delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"deleted": session_id}


@router.get("/{session_id}/macros", response_model=MacroTargetsResponse)
def get_macros(session_id: str):
    """Return daily macro targets based on user's goal and calorie target."""
    user = _get_or_404(session_id)
    macros = compute_macro_targets(user)
    return MacroTargetsResponse(
        **macros,
        target_calories=user.target_calories,
        goal_type=user.goal_type,
    )
