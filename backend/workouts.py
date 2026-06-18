from dataclasses import dataclass
from typing import List, Optional
import csv
import os
from constants import LEVEL_ORDER


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


# ================================================================== #
#  CSV loader                                                         #
# ================================================================== #

def load_workouts_csv(csv_path: str) -> List[WorkoutItem]:
    """
    Load workouts from megaGymDataset.csv.

    CSV columns (0-indexed):
      0: row index, 1: Title, 2: Desc, 3: Type, 4: BodyPart,
      5: Equipment, 6: Level, 7: Rating, 8: RatingDesc

    Rows with invalid / unknown category values are silently skipped.
    """
    workouts: List[WorkoutItem] = []

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            workout_type = row.get("Type", "").strip()
            body_part    = row.get("BodyPart", "").strip()
            equipment    = row.get("Equipment", "").strip()
            level        = row.get("Level", "").strip()
            title        = row.get("Title", "").strip()
            row_id       = row.get("", "").strip()   # the unnamed index column

            # Skip rows with empty required fields
            if not all([title, workout_type, body_part, equipment, level]):
                continue

            # Skip rows whose values don't match the known enums
            if workout_type not in WORKOUT_TYPES:
                continue
            if body_part not in BODY_PARTS:
                continue
            if equipment not in EQUIPMENT_TYPES:
                continue
            if level not in LEVELS:
                continue

            # Parse optional rating
            raw_rating = row.get("Rating", "").strip()
            try:
                rating = float(raw_rating) if raw_rating else None
                # Treat 0.0 as no rating (dataset uses 0.0 as sentinel)
                if rating == 0.0:
                    rating = None
            except ValueError:
                rating = None

            workout_id = f"csv_{row_id}" if row_id else f"csv_{len(workouts)}"

            try:
                workouts.append(
                    WorkoutItem(
                        workout_id=workout_id,
                        name=title,
                        workout_type=workout_type,
                        body_part=body_part,
                        equipment=equipment,
                        level=level,
                        rating=rating,
                    )
                )
            except ValueError:
                # Catches any edge-case validation error from __post_init__
                continue

    return workouts