from dataclasses import dataclass, field
from typing import List, Optional
from collections import defaultdict
from constants import (
    LEVEL_ORDER, GOAL_TYPES, FITNESS_LEVELS, DIET_TYPES, LOCATION_TYPES,
    LOCATION_TO_CUISINE, ACTIVITY_MULTIPLIERS, GOAL_CALORIE_DELTA
)


# ---------- User Profile ----------

@dataclass
class UserProfile:
    # ---- Body & context ----
    age: int
    height_cm: float
    weight_kg: float
    sex: Optional[str] = None           # "male" / "female" / None

    # ---- Core goal ----
    goal_type: str = "maintenance"
    fitness_level: str = "beginner"

    # ---- Activity ----
    activity_level: str = "light"       # sedentary / light / moderate / active / very_active

    # ---- Workout constraints ----
    workout_location: str = "both"
    available_equipment: List[str] = field(default_factory=list)

    # ---- Meal constraints ----
    diet_type: str = "omnivore"
    allergies: List[str] = field(default_factory=list)
    intolerances: List[str] = field(default_factory=list)

    # ---- Soft preferences ----
    country: Optional[str] = None
    preferred_cuisine: Optional[str] = field(default=None, init=False)
    preferred_workout_duration: str = "medium"   # short / medium / long
    cardio_strength_bias: str = "balanced"       # cardio / balanced / strength
    meals_per_day: int = 3
    cooking_time_preference: str = "flexible"    # quick / flexible
    protein_focus: str = "medium"                # low / medium / high

    # ---- Auto-computed nutrition targets ----
    target_calories: Optional[int] = field(default=None, init=False)

    # ---- Feedback memory ----
    liked_workouts: List[str] = field(default_factory=list)
    disliked_workouts: List[str] = field(default_factory=list)
    workout_preferences: dict = field(default_factory=dict)
    workout_type_preferences: dict = field(
        default_factory=lambda: defaultdict(float)
    )
    liked_meals: List[str] = field(default_factory=list)
    disliked_meals: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Derive cuisine from country
        self.preferred_cuisine = LOCATION_TO_CUISINE.get(self.country, None)

        # Auto-compute calorie target (Mifflin-St Jeor)
        self.target_calories = self._compute_target_calories()

    # ---- Calorie calculation ---- #

    def _compute_target_calories(self) -> int:
        """
        Mifflin-St Jeor BMR → TDEE (activity multiplier) → goal adjustment.
        Falls back to a neutral 2000 kcal if sex is unknown.
        """
        w, h, a = self.weight_kg, self.height_cm, self.age

        if self.sex and self.sex.lower() == "male":
            bmr = 10 * w + 6.25 * h - 5 * a + 5
        elif self.sex and self.sex.lower() == "female":
            bmr = 10 * w + 6.25 * h - 5 * a - 161
        else:
            # Average of male/female formulas when sex is unknown
            bmr = 10 * w + 6.25 * h - 5 * a - 78

        multiplier = ACTIVITY_MULTIPLIERS.get(self.activity_level, 1.375)
        tdee = bmr * multiplier
        delta = GOAL_CALORIE_DELTA.get(self.goal_type, 0)

        return max(1200, round(tdee + delta))   # never go below 1200 kcal

    # ---- Update methods ---- #

    def update_goal(self, new_goal: str):
        if new_goal not in GOAL_TYPES:
            raise ValueError(f"Invalid goal type: {new_goal}")
        self.goal_type = new_goal
        self.target_calories = self._compute_target_calories()  # recalculate

    def add_workout_feedback(self, workout, liked: bool):
        delta = 1 if liked else -1
        self.workout_preferences[workout.workout_id] = (
            self.workout_preferences.get(workout.workout_id, 0) + delta
        )
        self.workout_type_preferences[workout.workout_type] += 0.3 * delta

    def add_meal_feedback(self, meal_id: str, liked: bool):
        if liked:
            self.liked_meals.append(meal_id)
        else:
            self.disliked_meals.append(meal_id)
