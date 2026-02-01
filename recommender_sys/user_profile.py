from dataclasses import dataclass, field
from typing import List, Optional
from collections import defaultdict
LEVEL_ORDER = {
    "Beginner": 0,
    "Intermediate": 1,
    "Expert": 2
}



# ---------- Controlled vocabularies ----------

GOAL_TYPES = {"fat_loss", "muscle_gain", "maintenance", "endurance"}
FITNESS_LEVELS = {"beginner", "intermediate", "advanced"}
DIET_TYPES = {"omnivore", "vegetarian", "vegan"}
LOCATION_TYPES = {"home", "gym", "both"}



# ---------- User Profile ----------

@dataclass
class UserProfile:
    # ---- Body & context ----
    age: int
    height_cm: float
    weight_kg: float
    sex: Optional[str] = None  # optional

    # ---- Core goal ----
    goal_type: str = "maintenance"
    fitness_level: str = "beginner"

    # ---- Workout constraints ----
    workout_location: str = "both"
    available_equipment: List[str] = field(default_factory=list)

    # ---- Meal constraints ----
    diet_type: str = "omnivore"
    allergies: List[str] = field(default_factory=list)

    # ---- Soft preferences ----
    preferred_workout_duration: str = "medium"   # short / medium / long
    cardio_strength_bias: str = "balanced"       # cardio / balanced / strength
    meals_per_day: int = 3
    cooking_time_preference: str = "flexible"    # quick / flexible
    protein_focus: str = "medium"                # low / medium / high

    # ---- Feedback memory ----
    liked_workouts: List[str] = field(default_factory=list)
    disliked_workouts: List[str] = field(default_factory=list)
    # inside UserProfile
    workout_preferences: dict = field(default_factory=dict)
    workout_type_preferences: dict = field(
    default_factory=lambda: defaultdict(float)
)

    liked_meals: List[str] = field(default_factory=list)
    disliked_meals: List[str] = field(default_factory=list)
    

    # ---- Update methods ----
    def update_goal(self, new_goal: str):
        if new_goal not in GOAL_TYPES:
            raise ValueError(f"Invalid goal type: {new_goal}")
        self.goal_type = new_goal

    def add_workout_feedback(self, workout, liked: bool):
        delta = 1 if liked else -1

        # workout-specific preference (strong)
        self.workout_preferences[workout.workout_id] = (
            self.workout_preferences.get(workout.workout_id, 0) + delta
        )

        # workout-type preference (weak)
        self.workout_type_preferences[workout.workout_type] += 0.3 * delta


    def add_meal_feedback(self, meal_id: str, liked: bool):
        if liked:
            self.liked_meals.append(meal_id)
        else:
            self.disliked_meals.append(meal_id)
