"""
recommender.py — Unified entry point for the Revfit recommender system.

Usage
-----
from recommender import recommend, recommend_muscle

result = recommend(user)
# result["workouts"]      → List[WorkoutItem]  (flat top-K)
# result["workout_plan"]  → WorkoutPlan        (split-aware, from user.plan_type)
# result["meal_plan"]     → dict  (slot → List[RecipeItem])
# result["plan_summary"]  → str

muscle_recs = recommend_muscle(user, muscle="Chest")
# → List[WorkoutItem] — best Chest exercises for this user
"""

import pandas as pd
from typing import List, Dict, Any

from user_profile import UserProfile
from workouts import WorkoutItem
from recipe_Item import RecipeItem
from filters import recommend_workouts, recommend_meals, recommend_workout_plan, recommend_by_muscle
from plan_type import WorkoutPlan, print_workout_plan
from meal_plan import generate_meal_plan, plan_summary
from Request_Api import fetch_recipes


# ------------------------------------------------------------------ #
#  Workouts — load from CSV                                           #
# ------------------------------------------------------------------ #

def load_workouts(csv_path: str = "megaGymDataset.csv") -> List[WorkoutItem]:
    """Load the gym dataset CSV into a list of WorkoutItem objects."""
    df = pd.read_csv(csv_path)
    workouts = []

    for _, row in df.iterrows():
        try:
            w = WorkoutItem(
                workout_id=str(row.get("id", row.name)),
                name=str(row.get("Title", "")),
                workout_type=str(row.get("Type", "")),
                body_part=str(row.get("BodyPart", "")),
                equipment=str(row.get("Equipment", "")),
                level=str(row.get("Level", "Beginner")),
                rating=float(row["Rating"]) if pd.notna(row.get("Rating")) else None,
            )
            workouts.append(w)
        except (ValueError, KeyError):
            # Skip rows with invalid data
            continue

    return workouts


# ------------------------------------------------------------------ #
#  Main recommend() function                                          #
# ------------------------------------------------------------------ #

def recommend(
    user: UserProfile,
    csv_path: str = "megaGymDataset.csv",
    top_k_workouts: int = 5,
    top_k_meals: int = 5,
    offline_recipes: List[RecipeItem] = None,
) -> Dict[str, Any]:
    """
    Full recommendation pipeline.

    Parameters
    ----------
    user            : UserProfile
    csv_path        : Path to the gym CSV dataset
    top_k_workouts  : Number of workouts to return
    top_k_meals     : Number of meals to return per day
    offline_recipes : Optional pre-loaded recipes (skips API call if provided)

    Returns
    -------
    {
        "workouts":      List[WorkoutItem],      # flat top-K for backwards compat
        "workout_plan":  WorkoutPlan,            # structured split (new)
        "meal_plan":     Dict[str, List[RecipeItem]],
        "plan_summary":  str,
    }
    """
    # 1. Workouts — flat list (backwards compat) + structured split
    all_workouts = load_workouts(csv_path)
    workouts = recommend_workouts(all_workouts, user, top_k=top_k_workouts)
    workout_plan = recommend_workout_plan(all_workouts, user)

    # 2. Meals — use offline list or fetch from API
    if offline_recipes is not None:
        all_recipes = offline_recipes
    else:
        all_recipes = fetch_recipes(user)

    meals = recommend_meals(all_recipes, user, top_k=top_k_meals)

    # 3. Daily meal plan
    plan = generate_meal_plan(meals, user)
    summary = plan_summary(plan, user)

    return {
        "workouts":     workouts,
        "workout_plan": workout_plan,
        "meal_plan":    plan,
        "plan_summary": summary,
    }


# ------------------------------------------------------------------ #
#  Muscle-specific query                                              #
# ------------------------------------------------------------------ #

def recommend_muscle(
    user,
    muscle: str,
    csv_path: str = "megaGymDataset.csv",
    top_k: int = 5,
):
    """
    Return top-K exercises that target a specific muscle, filtered and
    scored according to the user's equipment, level, goal, and feedback.

    Parameters
    ----------
    user    : UserProfile
    muscle  : str   e.g. "Chest", "Lats", "Quadriceps" (case-insensitive)
    top_k   : int   max results to return

    Returns
    -------
    List[WorkoutItem]
    """
    all_workouts = load_workouts(csv_path)
    return recommend_by_muscle(all_workouts, user, muscle=muscle, top_k=top_k)
