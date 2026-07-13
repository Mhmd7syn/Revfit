"""
meal_exp_base.py — Shared base class and evaluation metrics for meal experiments.

Every meal experiment inherits from MealExperimentBase and implements:
    recommend(user, recipes, top_k) -> List[RecipeItem]

Evaluation metrics are analogous to workout experiments:
    - Precision / Recall  (relevance against held-out liked meals)
    - Diversity           (variety of cuisines and nutrient profiles)
    - Coverage            (catalogue utilisation)
    - Novelty             (how non-obvious the recommendations are)
"""

import random
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Set, Tuple
from collections import Counter

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from recipe_Item import RecipeItem
from user_profile import UserProfile


# ================================================================== #
#  Base class                                                         #
# ================================================================== #

class MealExperimentBase(ABC):
    """Abstract base for all meal recommendation experiments."""

    name: str = "MealBaseExperiment"
    description: str = ""

    @abstractmethod
    def recommend(
        self,
        user: UserProfile,
        recipes: List[RecipeItem],
        top_k: int = 5,
        **kwargs,
    ) -> List[RecipeItem]:
        """Return top-K meal recommendations for the given user."""
        ...

    def __repr__(self):
        return f"<{self.name}>"


# ================================================================== #
#  Evaluation metrics                                                 #
# ================================================================== #

def meal_precision_at_k(recommended: List[RecipeItem], relevant: Set[str]) -> float:
    """Precision@K = |recommended intersect relevant| / |recommended|."""
    if not recommended:
        return 0.0
    hits = sum(1 for r in recommended if r.recipe_id in relevant)
    return hits / len(recommended)


def meal_recall_at_k(recommended: List[RecipeItem], relevant: Set[str]) -> float:
    """Recall@K = |recommended intersect relevant| / |relevant|."""
    if not relevant:
        return 0.0
    hits = sum(1 for r in recommended if r.recipe_id in relevant)
    return hits / len(relevant)


def meal_diversity(recommended: List[RecipeItem]) -> float:
    """
    Intra-list diversity: fraction of distinct cuisines among recommendations.
    Higher = more diverse set of meals.
    """
    if len(recommended) <= 1:
        return 0.0
    cuisines = [r.cuisine for r in recommended]
    unique = len(set(cuisines))
    return unique / len(cuisines)


def meal_coverage(
    all_recommendations: List[List[RecipeItem]],
    catalogue_size: int,
) -> float:
    """Catalogue coverage across all users."""
    if catalogue_size == 0:
        return 0.0
    unique_ids = set()
    for recs in all_recommendations:
        for r in recs:
            unique_ids.add(r.recipe_id)
    return len(unique_ids) / catalogue_size


def meal_novelty(
    recommended: List[RecipeItem],
    popularity: Dict[str, int],
    total_interactions: int,
) -> float:
    """Average self-information of recommended meals."""
    if not recommended or total_interactions == 0:
        return 0.0
    total = 0.0
    for r in recommended:
        pop = popularity.get(r.recipe_id, 0)
        prob = (pop + 1) / (total_interactions + 1)
        total += -math.log2(prob)
    return total / len(recommended)


# ================================================================== #
#  Synthetic meal interaction data generator                          #
# ================================================================== #

def generate_synthetic_meal_interactions(
    recipes: List[RecipeItem],
    n_users: int = 50,
    interactions_per_user: int = 8,
    seed: int = 42,
) -> Dict[int, List[str]]:
    """
    Generate synthetic user -> liked-recipe-ids mapping.
    Popularity follows a power-law distribution.
    """
    rng = random.Random(seed)
    weights = [(1.0 / (i + 1)) for i in range(len(recipes))]
    total_w = sum(weights)
    probs = [w / total_w for w in weights]

    shuffled = list(recipes)
    rng.shuffle(shuffled)

    interactions: Dict[int, List[str]] = {}
    for uid in range(n_users):
        k = min(interactions_per_user, len(shuffled))
        chosen = rng.choices(shuffled, weights=probs, k=k)
        seen: set = set()
        unique: List[str] = []
        for r in chosen:
            if r.recipe_id not in seen:
                seen.add(r.recipe_id)
                unique.append(r.recipe_id)
        interactions[uid] = unique

    return interactions


def compute_meal_popularity(interactions: Dict[int, List[str]]) -> Tuple[Dict[str, int], int]:
    """Compute popularity dict and total interaction count."""
    counter: Counter = Counter()
    total = 0
    for recipe_ids in interactions.values():
        for rid in recipe_ids:
            counter[rid] += 1
            total += 1
    return dict(counter), total


# ================================================================== #
#  Results formatting                                                 #
# ================================================================== #

def format_meal_results_table(results: List[Dict]) -> str:
    """Format meal experiment results into an ASCII table."""
    header = (
        f"{'Approach':<35} {'Prec':>6} {'Recall':>6} "
        f"{'Divers':>6} {'Cover':>6} {'Novel':>6}  Best For"
    )
    sep = "-" * len(header)

    lines = [sep, header, sep]
    for r in results:
        lines.append(
            f"{r['name']:<35} {r['precision']:>6.3f} {r['recall']:>6.3f} "
            f"{r['diversity']:>6.3f} {r['coverage']:>6.3f} {r['novelty']:>6.3f}  "
            f"{r.get('best_for', '')}"
        )
    lines.append(sep)
    return "\n".join(lines)
