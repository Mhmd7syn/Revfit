"""
Meal Experiment 3 — Content-Based Meal Recommender (Our Reference System)
=========================================================================

PURPOSE
-------
This is our **reference meal recommender** — the actual system deployed in
Revfit.  All other meal experiments are compared against this.

METHOD
------
Content-based filtering that matches recipe features to the user profile:

1. **Hard filters** — remove recipes violating diet constraints:
   - Diet type mismatch (vegan/vegetarian/keto/paleo)
   - Contains user's allergens or intolerances
   - Calories exceed 120% of per-meal budget
   - Prep time exceeds user's cooking time preference

2. **Soft scoring** — multi-signal scoring function:
   - Cuisine match:         +2.0 (if recipe.cuisine == user.preferred_cuisine)
   - Protein focus match:   +1.5 (if protein_g falls in user's target range)
   - Feedback memory:       +2.0 (liked) / -3.0 (disliked)
   - Calorie proximity:     +0.0 to +1.0 (linear decay from target)
   - Rating bonus:          +0.2 x rating

3. **Sort and return top-K**.

DATA SOURCE
-----------
Recipes are fetched from the **Spoonacular API** which provides:
- Nutritional data (calories, protein, carbs, fat per serving)
- Cuisine labels, diet labels, prep time
- 380,000+ recipes in their database

This approach aligns with recent academic research:
> Yusoff et al. (2024), "KAWANKULINER: Personalised Food Recommendation App
> Using BMR and TDEE for Optimal Daily Nutrition", JMSI.
Their system also uses Spoonacular API + caloric/macro matching.

FEATURES USED
-------------
| Feature         | Role in Scoring                           |
|-----------------|-------------------------------------------|
| cuisine         | Soft match to user's country (+2.0)       |
| calories        | Proximity to per-meal target (0-1.0)      |
| protein_g       | Protein focus range match (+1.5)          |
| diet_labels     | Hard filter (vegan/vegetarian/keto/paleo) |
| intolerances    | Hard filter (allergens)                   |
| prep_time_min   | Hard filter (cooking_time_preference)     |
| rating          | Bonus signal (+0.2 x rating)              |
| feedback        | Like/dislike memory (+2.0 / -3.0)         |

EXPECTED RESULTS
----------------
- Precision / Recall: good (personalised to nutritional goals)
- Diversity: moderate (cuisine preference creates some bias)
- Coverage: good (different users with different diets see different sets)
- Novelty: moderate

WHAT WE LEARNED
---------------
Content-based meal filtering works well because:
1. Spoonacular provides rich nutritional metadata for scoring
2. User preferences (cuisine, diet, macros) map directly to recipe features
3. Hard filters ensure safety (allergies, diet restrictions)
4. Feedback memory prevents repeated recommendations of disliked meals

Limitations:
- Can't discover meals outside user's stated cuisine preference
- Calorie/macro matching is approximate (per-serving vs per-meal)
- No social signal (what similar users enjoyed)

WHY WE EXPLORED FURTHER
------------------------
While our system works well, we explored:
- Exp 4 (CF): Can user-user similarity discover new cuisines?
- Exp 5 (Hybrid): Can combining popularity with content improve robustness?
- Exp 6 (Weighted): Can we learn which features matter most per user?
"""

from typing import List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile
from filters import hard_filter_meals, score_meal
from experiments.meal_exp_base import MealExperimentBase


class ContentBasedMealRecommender(MealExperimentBase):
    """
    Content-based meal recommender — wraps the existing Revfit
    scoring logic from filters.py (score_meal + hard_filter_meals).

    This is the REFERENCE SYSTEM for meal experiments.
    """

    name = "Meal Exp 3: Content-Based"
    description = "Content-based with cuisine + macros + feedback + rating."

    def recommend(
        self,
        user: UserProfile,
        recipes: List[RecipeItem],
        top_k: int = 5,
        **kwargs,
    ) -> List[RecipeItem]:
        valid = hard_filter_meals(recipes, user)
        scored = [(r, score_meal(r, user)) for r in valid]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]
