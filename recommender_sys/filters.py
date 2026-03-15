from constants import LEVEL_ORDER, GOAL_TYPES

# ================================================================== #
#  Workout scoring weights per goal                                   #
# ================================================================== #

GOAL_TYPE_WEIGHTS = {
    "fat_loss": {
        "Cardio": 3.0,
        "Strength": 2.0,
        "Plyometrics": 2.5,
        "Stretching": 1.0
    },
    "muscle_gain": {
        "Strength": 3.0,
        "Powerlifting": 3.0,
        "Olympic Weightlifting": 2.5,
        "Cardio": 0.5
    },
    "maintenance": {
        "Strength": 2.0,
        "Cardio": 2.0,
        "Stretching": 1.5
    },
    "endurance": {
        "Cardio": 3.0,
        "Plyometrics": 2.0,
        "Strength": 1.5
    }
}

FEEDBACK_WEIGHT = 0.3

# ================================================================== #
#  Cooking-time budget (minutes)                                      #
# ================================================================== #

COOKING_TIME_MAX = {
    "quick":    30,
    "flexible": 9999,  # no limit
}

# Protein target ranges (g per serving)
PROTEIN_TARGETS = {
    "low":    (0,  15),
    "medium": (15, 30),
    "high":   (30, 9999),
}


# ================================================================== #
#  Workout filtering & scoring                                        #
# ================================================================== #

def hard_filter_workouts(workouts, user):
    filtered = []
    for w in workouts:
        if w.equipment not in user.available_equipment and w.equipment != "Body Only":
            continue
        if LEVEL_ORDER[w.level] > LEVEL_ORDER[user.fitness_level.capitalize()]:
            continue
        filtered.append(w)
    return filtered


def score_workout(workout, user):
    score = 0.0

    goal_weights = GOAL_TYPE_WEIGHTS.get(user.goal_type, {})
    score += goal_weights.get(workout.workout_type, 0.5)

    # Workout-specific feedback (strong signal)
    score += user.workout_preferences.get(workout.workout_id, 0) * 0.7

    # Workout-type preference (weak signal)
    score += user.workout_type_preferences.get(workout.workout_type, 0)

    # Rating bonus
    if workout.rating is not None:
        score += 0.2 * workout.rating

    return score


def recommend_workouts(workouts, user, top_k=5):
    valid = hard_filter_workouts(workouts, user)
    scored = [(w, score_workout(w, user)) for w in valid]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [w for w, _ in scored[:top_k]]


# ================================================================== #
#  Meal filtering & scoring                                           #
# ================================================================== #

def hard_filter_meals(recipes, user):
    """
    Remove meals that violate hard constraints:
      - diet_type mismatch (if user is vegan/vegetarian)
      - contains an allergen/intolerance the user has
      - too high in calories (> 120% of per-meal budget)
      - prep time exceeds cooking_time_preference limit
    """
    filtered = []
    time_limit = COOKING_TIME_MAX.get(user.cooking_time_preference, 9999)

    # Per-meal calorie ceiling (120% tolerance)
    per_meal_ceiling = None
    if user.target_calories:
        meals = max(user.meals_per_day, 1)
        per_meal_ceiling = (user.target_calories / meals) * 1.2

    # Diet requirements mapping
    DIET_REQUIREMENTS = {
        "vegan":       "vegan",
        "vegetarian":  "vegetarian",
        "ketogenic":   "ketogenic",
        "paleo":       "paleo",
    }

    for r in recipes:
        # 1. Diet check
        required_label = DIET_REQUIREMENTS.get(user.diet_type)
        if required_label and required_label not in r.diet_labels:
            continue

        # 2. Intolerance / allergy check
        user_restrictions = set(
            [a.lower() for a in user.allergies] +
            [i.lower() for i in user.intolerances]
        )
        if user_restrictions & set(r.intolerances):
            continue

        # 3. Calorie ceiling
        if per_meal_ceiling and r.calories > per_meal_ceiling:
            continue

        # 4. Prep time
        if r.prep_time_min > time_limit:
            continue

        filtered.append(r)

    return filtered


def score_meal(recipe, user):
    """
    Score a recipe based on user preferences.
    Higher score = better match.
    """
    score = 0.0

    # Cuisine match
    if user.preferred_cuisine and recipe.cuisine == user.preferred_cuisine.lower():
        score += 2.0

    # Protein focus match
    lo, hi = PROTEIN_TARGETS.get(user.protein_focus, (0, 9999))
    if lo <= recipe.protein_g <= hi:
        score += 1.5

    # Feedback memory
    if recipe.recipe_id in user.liked_meals:
        score += 2.0
    if recipe.recipe_id in user.disliked_meals:
        score -= 3.0

    # Calorie proximity bonus (closer to per-meal target = better)
    if user.target_calories:
        meals = max(user.meals_per_day, 1)
        per_meal_target = user.target_calories / meals
        deviation = abs(recipe.calories - per_meal_target)
        # Max bonus 1.0 at 0 deviation, decays linearly
        score += max(0.0, 1.0 - deviation / per_meal_target)

    # Rating bonus
    if recipe.rating is not None:
        score += 0.2 * recipe.rating

    return score


def recommend_meals(recipes, user, top_k=5):
    """Hard filter → score → sort → top K."""
    valid = hard_filter_meals(recipes, user)
    scored = [(r, score_meal(r, user)) for r in valid]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scored[:top_k]]
