"""
Meal Experiment 2 — Most Popular Meal Recommender
==================================================

PURPOSE
-------
Tests whether **global meal popularity** alone is a useful signal.

METHOD
------
Rank all recipes by their popularity (simulated completion count or rating
proxy).  After hard-filtering, return the top-K most popular meals.

WHY WE INCLUDED IT
------------------
1. **Popularity baseline** — shows whether personalisation adds value.
2. **Industry standard** — most papers include popularity comparison.
3. **Cold-start solution** — what to show a brand-new user.

EXPECTED RESULTS
----------------
- Precision / Recall: moderate (popular meals are popular for a reason)
- Diversity: low (everyone gets the same recommendations)
- Coverage: very low (only top-rated meals)
- Novelty: lowest

WHAT WE LEARNED
---------------
Popular meals achieve decent relevance but zero personalisation.  A user
with specific macro needs (high protein for muscle_gain) or cuisine
preferences (middle eastern) gets generic popular Western meals.

WHY WE MOVED TO EXPERIMENT 3
-----------------------------
Popularity ignores individual nutritional needs.  Content-Based (Exp 3)
uses the user's calorie target, cuisine preference, protein focus, and
feedback history for personalisation.
"""

from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile
from filters import hard_filter_meals
from experiments.meal_exp_base import MealExperimentBase
from Request_Api import fetch_recipes


class MostPopularMealRecommender(MealExperimentBase):
    """Recommend globally most popular meals (rating as proxy)."""

    name = "Meal Exp 2: Most Popular"
    description = "Rank by global popularity, no personalisation."

    def recommend(
        self,
        user: UserProfile,
        recipes: List[RecipeItem],
        top_k: int = 5,
        popularity: Dict[str, int] = None,
        **kwargs,
    ) -> List[RecipeItem]:
        
        try:
            # Fetch directly from Spoonacular API sorted by popularity
            popular_recipes = fetch_recipes(user, num_results=top_k, sort="popularity")
            if popular_recipes:
                return popular_recipes
        except Exception as e:
            print(f"    [Warning] API fetch for popular meals failed: {e}. Falling back to interaction-based popularity.")

        candidates = hard_filter_meals(recipes, user)

        if popularity:
            scored = sorted(
                candidates,
                key=lambda r: popularity.get(r.recipe_id, 0),
                reverse=True,
            )
        else:
            scored = sorted(
                candidates,
                key=lambda r: (r.rating or 0),
                reverse=True,
            )
        return scored[:top_k]
