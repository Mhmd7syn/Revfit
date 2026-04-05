"""
experiment_base.py — Shared base class and evaluation metrics for experiments.

Every experiment inherits from ExperimentBase and implements:
    recommend(user, workouts, top_k) → List[WorkoutItem]

Evaluation metrics (computed without real users via held-out simulation):
    - Precision / Recall  (relevance of recommendations)
    - Diversity           (variety among recommended items)
    - Coverage            (catalogue utilisation)
    - Novelty             (how non-obvious the recommendations are)
"""

import random
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Set
from collections import Counter

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile


# ================================================================== #
#  Base class                                                         #
# ================================================================== #

class ExperimentBase(ABC):
    """Abstract base for all recommendation experiments."""

    name: str = "BaseExperiment"
    description: str = ""

    @abstractmethod
    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        **kwargs,
    ) -> List[WorkoutItem]:
        """Return top-K workout recommendations for the given user."""
        ...

    def __repr__(self):
        return f"<{self.name}>"


# ================================================================== #
#  Evaluation metrics                                                 #
# ================================================================== #

def precision_at_k(recommended: List[WorkoutItem], relevant: Set[str]) -> float:
    """
    Precision@K = |recommended ∩ relevant| / |recommended|

    Parameters
    ----------
    recommended : List[WorkoutItem]
        The workouts returned by the recommender.
    relevant : Set[str]
        Set of workout_ids considered relevant (e.g. held-out completions).

    Returns
    -------
    float   0.0 – 1.0
    """
    if not recommended:
        return 0.0
    hits = sum(1 for w in recommended if w.workout_id in relevant)
    return hits / len(recommended)


def recall_at_k(recommended: List[WorkoutItem], relevant: Set[str]) -> float:
    """
    Recall@K = |recommended ∩ relevant| / |relevant|
    """
    if not relevant:
        return 0.0
    hits = sum(1 for w in recommended if w.workout_id in relevant)
    return hits / len(relevant)


def diversity(recommended: List[WorkoutItem]) -> float:
    """
    Intra-list diversity: fraction of distinct (body_part, workout_type)
    pairs among the recommendations.

    Higher = more diverse set of exercises.
    """
    if len(recommended) <= 1:
        return 0.0
    features = [(w.body_part, w.workout_type) for w in recommended]
    unique = len(set(features))
    return unique / len(features)


def coverage(
    all_recommendations: List[List[WorkoutItem]],
    catalogue_size: int,
) -> float:
    """
    Catalogue coverage = |unique items recommended across all users| / |catalogue|.
    """
    if catalogue_size == 0:
        return 0.0
    unique_ids = set()
    for recs in all_recommendations:
        for w in recs:
            unique_ids.add(w.workout_id)
    return len(unique_ids) / catalogue_size


def novelty(
    recommended: List[WorkoutItem],
    popularity: Dict[str, int],
    total_interactions: int,
) -> float:
    """
    Average self-information of recommended items:
        novelty = mean( -log2(popularity(i) / N) )

    Rare items have higher novelty.
    """
    if not recommended or total_interactions == 0:
        return 0.0
    total = 0.0
    for w in recommended:
        pop = popularity.get(w.workout_id, 0)
        prob = (pop + 1) / (total_interactions + 1)   # Laplace smoothing
        total += -math.log2(prob)
    return total / len(recommended)


# ================================================================== #
#  Synthetic interaction data generator                               #
# ================================================================== #

def generate_synthetic_interactions(
    workouts: List[WorkoutItem],
    n_users: int = 50,
    interactions_per_user: int = 15,
    seed: int = 42,
) -> Dict[int, List[str]]:
    """
    Generate synthetic user → completed-workout-ids mapping.

    This simulates interaction data so experiments can be evaluated
    offline without real users.  Popularity follows a power-law-like
    distribution: a few workouts are completed by many users, most
    by very few.

    Returns
    -------
    Dict[int, List[str]]
        user_id → list of completed workout_ids
    """
    rng = random.Random(seed)

    # Create power-law-ish popularity weights
    weights = [(1.0 / (i + 1)) for i in range(len(workouts))]
    total_w = sum(weights)
    probs = [w / total_w for w in weights]

    # Shuffle workouts to randomise which ones are "popular"
    shuffled = list(workouts)
    rng.shuffle(shuffled)

    interactions: Dict[int, List[str]] = {}
    for uid in range(n_users):
        # Weighted sample without replacement
        k = min(interactions_per_user, len(shuffled))
        chosen = rng.choices(shuffled, weights=probs, k=k)
        # Remove duplicates while keeping order
        seen: Set[str] = set()
        unique: List[str] = []
        for w in chosen:
            if w.workout_id not in seen:
                seen.add(w.workout_id)
                unique.append(w.workout_id)
        interactions[uid] = unique

    return interactions


def compute_popularity(interactions: Dict[int, List[str]]) -> Tuple[Dict[str, int], int]:
    """
    From synthetic interactions, compute:
        - popularity dict: workout_id → total completions
        - total_interactions: sum of all completions
    """
    counter: Counter = Counter()
    total = 0
    for workout_ids in interactions.values():
        for wid in workout_ids:
            counter[wid] += 1
            total += 1
    return dict(counter), total


# ================================================================== #
#  Results formatting                                                 #
# ================================================================== #

def format_results_table(results: List[Dict]) -> str:
    """
    Format a list of experiment result dicts into a pretty ASCII table.

    Each dict should have keys:
        name, precision, recall, diversity, coverage, novelty, best_for
    """
    header = (
        f"{'Approach':<30} {'Prec':>6} {'Recall':>6} "
        f"{'Divers':>6} {'Cover':>6} {'Novel':>6}  Best For"
    )
    sep = "-" * len(header)

    lines = [sep, header, sep]
    for r in results:
        lines.append(
            f"{r['name']:<30} {r['precision']:>6.3f} {r['recall']:>6.3f} "
            f"{r['diversity']:>6.3f} {r['coverage']:>6.3f} {r['novelty']:>6.3f}  "
            f"{r.get('best_for', '')}"
        )
    lines.append(sep)
    return "\n".join(lines)
