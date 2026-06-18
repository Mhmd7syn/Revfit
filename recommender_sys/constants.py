# ---------- Shared constants ----------
# Single source of truth — imported by user_profile.py, workouts.py, filters.py

LEVEL_ORDER = {
    "Beginner": 0,
    "Intermediate": 1,
    "Expert": 2
}

GOAL_TYPES = {"fat_loss", "muscle_gain", "maintenance", "endurance"}
FITNESS_LEVELS = {"beginner", "intermediate", "advanced"}
DIET_TYPES = {"omnivore", "vegetarian", "vegan", "paleo", "ketogenic", "gluten free"}
LOCATION_TYPES = {"home", "gym", "both"}

LOCATION_TO_CUISINE = {
    "Egypt": "middle eastern",
    "Italy": "italian",
    "Japan": "japanese",
    "Mexico": "mexican",
    "India": "indian",
    "France": "french",
    "China": "chinese",
    "USA": "american",
    "Greece": "mediterranean",
    "Spain": "spanish",
    "Thailand": "thai",
    # expand as needed
}


# Activity level multipliers (Harris-Benedict / Mifflin-St Jeor)
ACTIVITY_MULTIPLIERS = {
    "sedentary":    1.2,    # little or no exercise
    "light":        1.375,  # light exercise 1-3 days/week
    "moderate":     1.55,   # moderate exercise 3-5 days/week
    "active":       1.725,  # hard exercise 6-7 days/week
    "very_active":  1.9,    # very hard exercise / physical job
}

# Goal calorie adjustments (delta on top of TDEE)
GOAL_CALORIE_DELTA = {
    "fat_loss":    -500,
    "muscle_gain": +300,
    "maintenance":    0,
    "endurance":   +200,
}


# ================================================================== #
#  Workout Plan Types                                                 #
# ================================================================== #

PLAN_TYPES = {"full_body", "ppl", "upper_lower"}

# Feedback decay — scores halve every N days (per goal type).
# A shorter half-life means the recommender forgets old feedback faster.
# Falls back to DECAY_HALF_LIFE_DEFAULT if goal_type is unknown.
DECAY_HALF_LIFE_DEFAULT = 30   # days

GOAL_DECAY_DAYS = {
    "muscle_gain":  14,   # adapts fast — training blocks change quickly
    "fat_loss":     21,   # moderate memory
    "maintenance":  45,   # slow change — stable preferences
    "endurance":    30,   # balanced
}


# Body parts that belong to each training day for every split style.
# Keys = day names shown in output.  Values = list of BodyPart strings
# that match the CSV (case-sensitive).
SPLIT_BODY_MAP = {
    # Push / Pull / Legs  (3-day split)
    "ppl": {
        "Push": [
            "Chest", "Shoulders", "Triceps",
        ],
        "Pull": [
            "Lats", "Middle Back", "Lower Back",
            "Traps", "Biceps", "Forearms",
        ],
        "Legs": [
            "Quadriceps", "Hamstrings", "Glutes",
            "Calves", "Abductors", "Adductors", "Abdominals",
        ],
    },

    # Upper / Lower  (2-day split)
    "upper_lower": {
        "Upper": [
            "Chest", "Shoulders", "Triceps", "Biceps",
            "Lats", "Middle Back", "Traps", "Forearms",
        ],
        "Lower": [
            "Quadriceps", "Hamstrings", "Glutes", "Calves",
            "Abductors", "Adductors", "Lower Back", "Abdominals",
        ],
    },

    # Full Body  (1-day template, repeated every session)
    "full_body": {
        "Full Body": [
            "Chest", "Shoulders", "Triceps", "Biceps",
            "Lats", "Middle Back", "Quadriceps", "Hamstrings",
            "Glutes", "Calves", "Abdominals", "Lower Back",
            "Traps", "Forearms", "Abductors", "Adductors",
        ],
    },
}

# Max exercises to pick per body-part group per training day
EXERCISES_PER_BODYPART = {
    "full_body":    1,   # 1 per muscle → ~10-12 total per session
    "ppl":          2,   # 2 per muscle → ~6-10 per day
    "upper_lower":  2,   # 2 per muscle → ~8-10 per day
}
