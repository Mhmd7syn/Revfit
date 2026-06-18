"""
Meal Experiment 6 — Feature-Weighted Meal Recommender
=====================================================

STATUS: DOCUMENTED STUB — algorithm structure and rationale only.

PURPOSE
-------
Extend content-based meal scoring by allowing **different weights for
different nutritional features** per user, rather than a fixed formula.

METHOD
------
score = W . F(recipe, user) where:

W = [w_cuisine, w_protein, w_calorie_proximity, w_rating, w_feedback]
F = normalised feature signals per recipe-user pair

WEIGHT STRATEGIES
-----------------
| Strategy          | Weights                       | Rationale                   |
|-------------------|-------------------------------|-----------------------------|
| Uniform           | [0.2, 0.2, 0.2, 0.2, 0.2]    | Equal importance (baseline) |
| Macro-focused     | [0.1, 0.4, 0.3, 0.1, 0.1]    | Prioritise nutritional fit  |
| Cuisine-focused   | [0.5, 0.1, 0.1, 0.2, 0.1]    | Cultural preference heavy   |
| Feedback-focused  | [0.1, 0.1, 0.1, 0.1, 0.6]    | Heavy personalisation       |
| Learned           | [optimised via search]        | Data-driven (best)          |

WHY WE INCLUDED IT
------------------
1. **Interpretability** — shows which nutritional features actually matter.
2. **Natural extension** — evolution from fixed-weight Exp 3.
3. **Per-user tuning** — a bodybuilder cares most about protein; a dieter
   cares most about calorie precision.

EXPECTED RESULTS
----------------
- Precision: potentially highest (optimised weights)
- Interpretability: can explain "why" a meal was recommended

WHAT WE LEARNED
---------------
Feature weighting addresses the one-size-fits-all limitation.  Different
users should have different priorities:
- muscle_gain → protein weight high
- fat_loss → calorie proximity weight high
- cultural preference → cuisine weight high

CONCLUSIONS FROM ALL MEAL EXPERIMENTS
-------------------------------------
1. Random (Exp 1) → worst relevance, best diversity
2. Most Popular (Exp 2) → decent relevance, no personalisation
3. Content-Based (Exp 3) → good relevance, personalised, our reference
4. Collaborative Filtering (Exp 4) → needs dense data we don't have
5. Hybrid (Exp 5) → most robust, industry standard
6. Weighted Content (Exp 6) → most potential, needs weight learning

For our Spoonacular-powered system, **Content-Based (Exp 3)** is the
right choice, with **Hybrid (Exp 5)** as the natural next step.
"""

from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile
from filters import hard_filter_meals, PROTEIN_TARGETS
from experiments.meal_exp_base import MealExperimentBase


DEFAULT_MEAL_WEIGHTS = {
    "cuisine":   0.2,
    "protein":   0.2,
    "calories":  0.2,
    "rating":    0.2,
    "feedback":  0.2,
}


class WeightedContentMealRecommender(MealExperimentBase):
    """Content-based meal recommender with tuneable weights (STUB)."""

    name = "Meal Exp 6: Weighted Content"
    description = "Content-based with tuneable feature weights. (STUB)"

    def __init__(self, weights=None):
        self.weights = weights or DEFAULT_MEAL_WEIGHTS.copy()

    def _extract_features(self, recipe, user):
        # Cuisine match
        cuisine_score = 1.0 if (
            user.preferred_cuisine and
            recipe.cuisine == user.preferred_cuisine.lower()
        ) else 0.0

        # Protein focus
        lo, hi = PROTEIN_TARGETS.get(user.protein_focus, (0, 9999))
        protein_score = 1.0 if lo <= recipe.protein_g <= hi else 0.0

        # Calorie proximity
        cal_score = 0.0
        if user.target_calories:
            meals = max(user.meals_per_day, 1)
            target = user.target_calories / meals
            if target > 0:
                cal_score = max(0.0, 1.0 - abs(recipe.calories - target) / target)

        # Rating
        rating_score = (recipe.rating or 0) / 5.0

        # Feedback
        if recipe.recipe_id in user.liked_meals:
            feedback_score = 1.0
        elif recipe.recipe_id in user.disliked_meals:
            feedback_score = 0.0
        else:
            feedback_score = 0.5

        return {
            "cuisine":  cuisine_score,
            "protein":  protein_score,
            "calories": cal_score,
            "rating":   rating_score,
            "feedback": feedback_score,
        }

    def recommend(self, user, recipes, top_k=5, **kwargs):
        candidates = hard_filter_meals(recipes, user)
        scored = []
        for r in candidates:
            features = self._extract_features(r, user)
            score = sum(self.weights[k] * features[k] for k in self.weights)
            scored.append((r, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]
