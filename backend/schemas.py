"""
schemas.py — Pydantic request / response models for the RevFit API.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from constants import GOAL_TYPES, FITNESS_LEVELS, DIET_TYPES, ACTIVITY_MULTIPLIERS


# ================================================================== #
#  User                                                               #
# ================================================================== #

class UserCreateRequest(BaseModel):
    age: int = Field(..., ge=10, le=120)
    height_cm: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    sex: Optional[str] = Field(None, pattern="^(male|female)$")

    goal_type: str = "maintenance"
    fitness_level: str = "beginner"
    activity_level: str = "light"

    workout_location: str = "both"
    available_equipment: List[str] = []

    diet_type: str = "omnivore"
    allergies: List[str] = []
    intolerances: List[str] = []

    country: Optional[str] = None
    preferred_workout_duration: str = "medium"
    cardio_strength_bias: str = "balanced"
    meals_per_day: int = Field(3, ge=1, le=5)
    cooking_time_preference: str = "flexible"
    protein_focus: str = "medium"

    @field_validator("goal_type")
    @classmethod
    def validate_goal(cls, v):
        if v not in GOAL_TYPES:
            raise ValueError(f"goal_type must be one of {GOAL_TYPES}")
        return v

    @field_validator("fitness_level")
    @classmethod
    def validate_fitness(cls, v):
        if v not in FITNESS_LEVELS:
            raise ValueError(f"fitness_level must be one of {FITNESS_LEVELS}")
        return v

    @field_validator("diet_type")
    @classmethod
    def validate_diet(cls, v):
        if v not in DIET_TYPES:
            raise ValueError(f"diet_type must be one of {DIET_TYPES}")
        return v

    @field_validator("activity_level")
    @classmethod
    def validate_activity(cls, v):
        if v not in ACTIVITY_MULTIPLIERS:
            raise ValueError(f"activity_level must be one of {list(ACTIVITY_MULTIPLIERS.keys())}")
        return v


class UserResponse(BaseModel):
    age: int
    height_cm: float
    weight_kg: float
    sex: Optional[str]
    goal_type: str
    fitness_level: str
    activity_level: str
    workout_location: str
    available_equipment: List[str]
    diet_type: str
    allergies: List[str]
    intolerances: List[str]
    country: Optional[str]
    preferred_cuisine: Optional[str]
    meals_per_day: int
    cooking_time_preference: str
    protein_focus: str
    target_calories: Optional[int]


class UpdateGoalRequest(BaseModel):
    goal_type: str

    @field_validator("goal_type")
    @classmethod
    def validate_goal(cls, v):
        if v not in GOAL_TYPES:
            raise ValueError(f"goal_type must be one of {GOAL_TYPES}")
        return v


class MacroTargetsResponse(BaseModel):
    protein_g: float
    carbs_g: float
    fat_g: float
    target_calories: int
    goal_type: str


# ================================================================== #
#  Workouts                                                           #
# ================================================================== #

class WorkoutResponse(BaseModel):
    workout_id: str
    name: str
    workout_type: str
    body_part: str
    equipment: str
    level: str
    rating: Optional[float]
    score: Optional[float] = None


class WorkoutRecommendRequest(BaseModel):
    top_k: int = Field(5, ge=1, le=50)


class WorkoutFeedbackRequest(BaseModel):
    workout_id: str
    liked: bool


class WorkoutPlanDayResponse(BaseModel):
    day_name: str
    exercises: List[WorkoutResponse]


class WorkoutPlanResponse(BaseModel):
    plan_type: str
    total_exercises: int
    days: List[WorkoutPlanDayResponse]
    summary: str


# ================================================================== #
#  Meals / Recipes                                                    #
# ================================================================== #

class RecipeResponse(BaseModel):
    recipe_id: str
    title: str
    cuisine: str
    diet_labels: List[str]
    intolerances: List[str]
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    prep_time_min: int
    rating: Optional[float]
    image_url: Optional[str]
    source_url: Optional[str]
    score: Optional[float] = None


class MealRecommendRequest(BaseModel):
    top_k: int = Field(5, ge=1, le=50)
    num_fetch: int = Field(20, ge=5, le=100)


class MealFeedbackRequest(BaseModel):
    recipe_id: str
    liked: bool


# ================================================================== #
#  Meal Plan                                                          #
# ================================================================== #

class SlotMacros(BaseModel):
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


class MealPlanSlot(BaseModel):
    slot: str
    target: SlotMacros
    recipes: List[RecipeResponse]


class MealPlanResponse(BaseModel):
    goal_type: str
    target_calories: int
    daily_macros: MacroTargetsResponse
    slots: List[MealPlanSlot]
    summary: str


# ================================================================== #
#  Feedback                                                           #
# ================================================================== #

class FeedbackSummaryResponse(BaseModel):
    liked_meals: List[str]
    disliked_meals: List[str]
    liked_workouts: List[str]
    disliked_workouts: List[str]
    workout_preferences: Dict[str, float]
    workout_type_preferences: Dict[str, float]


# ================================================================== #
#  Pose Analysis                                                      #
# ================================================================== #

class PoseAnalysisResponse(BaseModel):
    exercise_name: str
    form_score: float          # 0–100
    rep_count: int
    total_frames: int
    bad_frame_count: int
    feedback_summary: Dict[str, int]  # feedback message → occurrence count
    video_url: str             # relative URL to download correction video
