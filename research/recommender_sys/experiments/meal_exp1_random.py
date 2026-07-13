"""
Meal Experiment 1 — Random Meal Recommender
============================================

PURPOSE
-------
Establishes the **worst-case lower bound** for meal recommendation quality.

METHOD
------
After applying the same hard filters (diet type, intolerances, calorie
ceiling, prep time) as our content-based system, we randomly sample K
recipes from the remaining candidates.  No nutritional matching, cuisine
preference, or feedback is used.

WHY WE INCLUDED IT
------------------
1. **Statistical baseline** — proves our scoring system beats chance.
2. **Diversity benchmark** — random selection maximises cuisine diversity.
3. **Cold-start analogy** — a new user with zero preferences gets random.

EXPECTED RESULTS
----------------
- Precision / Recall: very low
- Diversity: maximum (highest cuisine variety)
- Coverage: highest (no popularity bias)
- Novelty: highest

WHAT WE LEARNED
---------------
Random meals pass the hard filters (so they're safe for the user's diet)
but completely ignore nutritional goals, cuisine preferences, and macro
targets.  Demonstrates that personalisation adds real value.

WHY WE MOVED TO EXPERIMENT 2
-----------------------------
Random lacks any intelligence.  Next: does global popularity alone help?
"""

import random as _random
from typing import List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile
from filters import hard_filter_meals
from experiments.meal_exp_base import MealExperimentBase


class RandomMealRecommender(MealExperimentBase):
    """Return random meals after hard-filtering."""

    name = "Meal Exp 1: Random"
    description = "Random selection from hard-filtered recipes."

    def recommend(
        self,
        user: UserProfile,
        recipes: List[RecipeItem],
        top_k: int = 5,
        seed: int = None,
        **kwargs,
    ) -> List[RecipeItem]:
        candidates = hard_filter_meals(recipes, user)
        if seed is not None:
            _random.seed(seed)
        k = min(top_k, len(candidates))
        return _random.sample(candidates, k) if candidates else []
