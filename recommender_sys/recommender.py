"""
recommender.py — Unified entry point for the Revfit recommender system.

Usage
-----
from recommender import recommend

result = recommend(user)
# result["workouts"]  → List[WorkoutItem]
# result["meal_plan"] → dict  (slot → List[RecipeItem])
# result["plan_summary"] → str
"""

import pandas as pd
from typing import List, Dict, Any

from user_profile import UserProfile
from workouts import WorkoutItem
from recipe_Item import RecipeItem
from filters import recommend_workouts, recommend_meals
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
        "workouts":     List[WorkoutItem],
        "meal_plan":    Dict[str, List[RecipeItem]],
        "plan_summary": str,
    }
    """
    # 1. Workouts
    all_workouts = load_workouts(csv_path)
    workouts = recommend_workouts(all_workouts, user, top_k=top_k_workouts)

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
        "workouts": workouts,
        "meal_plan": plan,
        "plan_summary": summary,
    }
