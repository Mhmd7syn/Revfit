from dataclasses import dataclass
from typing import Optional


WORKOUT_TYPES = {
    "Strength", "Plyometrics", "Stretching", "Powerlifting",
    "Strongman", "Cardio", "Olympic Weightlifting"
}

BODY_PARTS = {
    "Abdominals", "Abductors", "Adductors", "Biceps", "Calves",
    "Chest", "Forearms", "Glutes", "Hamstrings", "Lats",
    "Lower Back", "Middle Back", "Traps", "Quadriceps",
    "Shoulders", "Triceps"
}

EQUIPMENT_TYPES = {
    "Barbell", "Kettlebells", "Dumbbell", "Other", "Cable",
    "Machine", "Body Only", "Medicine Ball", "Exercise Ball",
    "Foam Roll", "E-Z Curl Bar", "Bands"
}

LEVELS = {"Beginner", "Intermediate", "Expert"}

@dataclass
class WorkoutItem:
    # ---- Identity ----
    workout_id: str
    name: str

    # ---- Core dataset features ----
    workout_type: str          # from WORKOUT_TYPES
    body_part: str             # from BODY_PARTS
    equipment: str             # from EQUIPMENT_TYPES
    level: str                 # Beginner / Intermediate / Expert

    # ---- Optional quality signal ----
    rating: Optional[float] = None

    # ---- Validation ----
    def __post_init__(self):
        if self.workout_type not in WORKOUT_TYPES:
            raise ValueError(f"Invalid workout type: {self.workout_type}")

        if self.body_part not in BODY_PARTS:
            raise ValueError(f"Invalid body part: {self.body_part}")

        if self.equipment not in EQUIPMENT_TYPES:
            raise ValueError(f"Invalid equipment: {self.equipment}")

        if self.level not in LEVELS:
            raise ValueError(f"Invalid level: {self.level}")