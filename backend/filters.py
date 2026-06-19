"""
filters.py — Content-Based Filtering scoring engine (Experiment 3).

This module is the canonical implementation of the Revfit content-based
recommender system, validated in experiments/exp3_content_based.py (workouts)
and experiments/meal_exp3_content_based.py (meals).

Workout Scoring Signals
-----------------------
  - Goal-alignment weight: 0.5 – 3.0 per workout_type
  - Workout-specific feedback: +0.7 × preference per like/dislike
  - Workout-type preference: accumulated via feedback (weak signal)
  - Rating bonus: +0.2 × rating
  Hard filters: equipment match + fitness level ≤ user's level

Meal Scoring Signals
--------------------
  - Cuisine match:       +2.0 (if recipe.cuisine == user.preferred_cuisine)
  - Protein focus match: +1.5 (if protein_g falls in user's target range)
  - Feedback memory:     +2.0 (liked) / -3.0 (disliked)
  - Calorie proximity:   +0.0 to +1.0 (linear decay from per-meal target)
  - Rating bonus:        +0.2 × rating
  Hard filters: diet type, allergens, calorie ceiling (120%), prep time
"""

from constants import LEVEL_ORDER, GOAL_TYPES
from plan_type import build_workout_plan, WorkoutPlan

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


def recommend_workout_plan(workouts, user) -> WorkoutPlan:
    """
    Build a structured day-by-day WorkoutPlan using user.plan_type.

    Steps
    -----
    1. Hard-filter workouts by equipment and fitness level.
    2. Score every remaining workout (goal alignment + feedback + rating).
    3. Pass the sorted candidates to build_workout_plan(), which groups
       exercises by training day according to SPLIT_BODY_MAP.

    Parameters
    ----------
    workouts : List[WorkoutItem]
        Full catalogue loaded from CSV.
    user : UserProfile
        Provides plan_type, goal_type, fitness_level, equipment, etc.

    Returns
    -------
    WorkoutPlan
        Structured plan with .days dict (day_name → List[WorkoutItem]).
    """
    valid = hard_filter_workouts(workouts, user)
    # Sort by score so _pick_exercises gets the best candidates first
    scored = sorted(valid, key=lambda w: score_workout(w, user), reverse=True)
    return build_workout_plan(scored, user)


# ================================================================== #
#  Muscle-specific recommendations                                    #
# ================================================================== #

def recommend_by_muscle(workouts, user, muscle: str, top_k: int = 5):
    """
    Return the top-K exercises that target a specific muscle group.

    The function first applies the same hard filters (equipment, level)
    as the main recommender, then narrows to the requested body part
    and scores/ranks the remaining candidates normally.

    Parameters
    ----------
    workouts : List[WorkoutItem]
        Full catalogue loaded from CSV.
    user     : UserProfile
        Provides goal_type, fitness_level, equipment, feedback, etc.
    muscle   : str
        Body part name — must match a value in BODY_PARTS exactly
        (e.g. "Chest", "Lats", "Quadriceps").  Case-insensitive.
    top_k    : int
        Maximum number of exercises to return.

    Returns
    -------
    List[WorkoutItem]
        Best exercises for the requested muscle, ranked by score.

    Raises
    ------
    ValueError
        If muscle doesn't match any known body part.
    """
    from workouts import BODY_PARTS

    # Normalise: find the canonical casing used in the dataset
    muscle_canonical = next(
        (bp for bp in BODY_PARTS if bp.lower() == muscle.strip().lower()),
        None,
    )
    if muscle_canonical is None:
        valid_list = ", ".join(sorted(BODY_PARTS))
        raise ValueError(
            f"Unknown muscle '{muscle}'. Valid options: {valid_list}"
        )

    # 1. Hard filter (equipment + level)
    valid = hard_filter_workouts(workouts, user)

    # 2. Keep only exercises targeting the requested body part
    targeted = [w for w in valid if w.body_part == muscle_canonical]

    if not targeted:
        return []

    # 3. Score + rank
    scored = sorted(targeted, key=lambda w: score_workout(w, user), reverse=True)
    return scored[:top_k]

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
