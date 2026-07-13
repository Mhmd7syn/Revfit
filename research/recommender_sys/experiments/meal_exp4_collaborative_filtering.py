"""
Meal Experiment 4 — User-Based Collaborative Filtering for Meals
================================================================

STATUS: DOCUMENTED STUB — algorithm structure and rationale only.

PURPOSE
-------
Test whether **user-user taste similarity** can produce better meal
recommendations than nutritional feature matching alone.

METHOD
------
1. Build user-item interaction matrix (users x recipes).
2. Compute cosine similarity between users based on their liked meals.
3. Find K-nearest neighbours.
4. Aggregate their preferred recipes weighted by similarity.
5. Return top-N unseen recipes.

ALGORITHM SKETCH
----------------
```python
def meal_cf(target_user, all_users, interaction_matrix, k=5, n=5):
    similarities = {}
    for other in all_users:
        sim = cosine_similarity(
            interaction_matrix[target_user],
            interaction_matrix[other]
        )
        similarities[other] = sim

    neighbours = sorted(similarities, key=similarities.get, reverse=True)[:k]

    scores = defaultdict(float)
    for neighbour in neighbours:
        for recipe_id in interaction_matrix[neighbour]:
            if recipe_id not in interaction_matrix[target_user]:
                scores[recipe_id] += similarities[neighbour]

    return sorted(scores, key=scores.get, reverse=True)[:n]
```

WHY WE INCLUDED IT
------------------
1. **Paradigm comparison** — CF discovers meals that *similar users* enjoyed,
   potentially introducing new cuisines the user hasn't tried.
2. **Serendipity** — CF's strength is surprising recommendations.
3. **Sparsity demonstration** — shows CF fails with few users.

EXPECTED RESULTS
----------------
- Precision: poor (sparse interactions, few users)
- Diversity: moderate (draws from diverse neighbour tastes)
- Coverage: low (many recipes have zero interactions)
- Key problem: cold-start (new users get nothing)

WHAT WE LEARNED
---------------
CF requires dense interaction data. With Spoonacular's 380K+ recipes and
only simulated users, the matrix is extremely sparse.  Content-based
filtering using nutritional metadata is far more reliable.

KEY DISCUSSION POINTS
---------------------
1. CF can discover new cuisines, but needs hundreds of active users.
2. Dietary safety is not guaranteed — CF might recommend meals that
   violate a user's allergies if only based on similar user preferences.
3. Content-based can enforce hard constraints (allergies, diet type)
   which CF cannot without a filtering layer.

WHY WE MOVED TO EXPERIMENT 5
-----------------------------
Since pure CF fails in sparse settings, we explore Hybrid (combining
content scores with popularity) for robustness.
"""

from typing import List, Dict
from collections import defaultdict
import math

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile
from experiments.meal_exp_base import MealExperimentBase


class CollaborativeFilteringMealRecommender(MealExperimentBase):
    """User-based CF for meals (STUB)."""

    name = "Meal Exp 4: Collaborative Filtering"
    description = "User-based CF on meal interaction vectors. (STUB)"

    def __init__(self, interaction_matrix=None, k=5):
        self.interaction_matrix = interaction_matrix or {}
        self.k = k

    def recommend(self, user, recipes, top_k=5, **kwargs):
        """STUB — returns empty list without interaction data."""
        if not self.interaction_matrix:
            return []
        return []
