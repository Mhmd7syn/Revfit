"""
Meal Experiment 5 — Hybrid Meal Recommender (Content + Popularity)
==================================================================

STATUS: DOCUMENTED STUB — algorithm structure and rationale only.

PURPOSE
-------
Combine content-based (nutritional matching) with popularity signals:

    hybrid_score = alpha x content_score + (1-alpha) x popularity_score

METHOD
------
1. Compute content-based scores using existing `score_meal()`.
2. Compute popularity scores (normalised selection count or rating).
3. Blend with alpha weighting parameter.
4. Sort and return top-K.

ALPHA-TUNING FOR MEALS
----------------------
| alpha | Content | Popularity | Scenario                      |
|-------|---------|------------|-------------------------------|
| 1.0   | 100%    | 0%         | Pure content-based (Exp 3)    |
| 0.7   | 70%     | 30%        | Personalised + pop boost      |
| 0.5   | 50%     | 50%        | Balanced blend                |
| 0.3   | 30%     | 70%        | Popularity-heavy (new users)  |
| 0.0   | 0%      | 100%       | Pure popularity (Exp 2)       |

WHY WE INCLUDED IT
------------------
1. **Industry standard** — meal delivery apps (Uber Eats, DoorDash) use
   hybrid approaches combining personal taste with trending meals.
2. **Cold-start handling** — new users get popular meals while the system
   learns their nutritional preferences.
3. **Tunable** — alpha controls exploration vs exploitation.

EXPECTED RESULTS
----------------
- Precision: best or near-best (two informative signals)
- Diversity: moderate (alpha-controlled)
- Robustness: highest (graceful degradation for new users)

WHAT WE LEARNED
---------------
Hybrid is the most robust approach for meal recommendation because:
- Popular meals tend to be well-rated and broadly appealing
- Content-based scoring adds personalised nutritional matching
- Alpha can adapt: low for new users → high for established users

WHY WE MOVED TO EXPERIMENT 6
-----------------------------
Both signals use fixed scoring weights.  Experiment 6 explores whether
we can learn which nutritional features matter most per user.
"""

from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile
from filters import hard_filter_meals, score_meal
from experiments.meal_exp_base import MealExperimentBase


class HybridMealRecommender(MealExperimentBase):
    """Hybrid meal recommender (STUB)."""

    name = "Meal Exp 5: Hybrid"
    description = "alpha x content + (1-alpha) x popularity. (STUB)"

    def __init__(self, alpha=0.7):
        self.alpha = alpha

    def recommend(self, user, recipes, top_k=5, popularity=None, **kwargs):
        """STUB — falls back to content-based without popularity data."""
        candidates = hard_filter_meals(recipes, user)
        if not popularity:
            scored = [(r, score_meal(r, user)) for r in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [r for r, _ in scored[:top_k]]

        content_scores = {r.recipe_id: score_meal(r, user) for r in candidates}
        max_c = max(content_scores.values()) if content_scores else 1.0
        if max_c == 0: max_c = 1.0
        max_p = max(popularity.values()) if popularity else 1
        if max_p == 0: max_p = 1

        hybrid = []
        for r in candidates:
            c_norm = content_scores[r.recipe_id] / max_c
            p_norm = popularity.get(r.recipe_id, 0) / max_p
            score = self.alpha * c_norm + (1 - self.alpha) * p_norm
            hybrid.append((r, score))
        hybrid.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in hybrid[:top_k]]
