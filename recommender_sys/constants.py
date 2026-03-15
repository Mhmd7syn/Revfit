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
