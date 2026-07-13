"""
Experiment 4 — Simplified User-Based Collaborative Filtering
=============================================================

⚠ STATUS: DOCUMENTED STUB — algorithm structure and rationale only.
   Not fully runnable because we lack real multi-user interaction data.

PURPOSE
-------
Test whether **user-user similarity** can produce better recommendations
than content features alone.  In collaborative filtering (CF), we find
users with similar workout histories and recommend what *they* enjoyed
but the current user hasn't tried yet.

METHOD
------
1. Build a user-item interaction matrix (users × workouts), where each
   cell is 1 (completed) or 0 (not completed).
2. For the target user, compute similarity to all other users using
   cosine similarity on their interaction vectors.
3. Identify the K-nearest neighbours (most similar users).
4. Aggregate the neighbours' completed workouts, weighted by similarity.
5. Exclude workouts the target user already completed.
6. Return the top-N by aggregated weighted score.

ALGORITHM SKETCH
----------------
```python
def user_based_cf(target_user, all_users, interaction_matrix, k=5, n=10):
    # Step 1: Compute similarity between target and all others
    similarities = {}
    for other_user in all_users:
        if other_user == target_user:
            continue
        sim = cosine_similarity(
            interaction_matrix[target_user],
            interaction_matrix[other_user]
        )
        similarities[other_user] = sim

    # Step 2: Find K nearest neighbours
    neighbours = sorted(similarities, key=similarities.get, reverse=True)[:k]

    # Step 3: Aggregate neighbour preferences
    scores = defaultdict(float)
    for neighbour in neighbours:
        sim = similarities[neighbour]
        for workout_id in interaction_matrix[neighbour]:
            if interaction_matrix[neighbour][workout_id] == 1:
                if workout_id not in interaction_matrix[target_user]:
                    scores[workout_id] += sim  # weighted by similarity

    # Step 4: Sort and return
    ranked = sorted(scores, key=scores.get, reverse=True)
    return ranked[:n]
```

WHY WE INCLUDED IT
------------------
1. **Paradigm comparison** — CF is the most common alternative to content-based
   filtering.  Including it demonstrates understanding of both paradigms.
2. **Sparsity discussion** — in our low-data scenario (few users, sparse
   interactions), CF is expected to struggle.  This is a key insight.
3. **Cold-start problem** — CF cannot handle new users who have no history,
   unlike content-based which uses profile features.

EXPECTED RESULTS
----------------
- Precision / Recall: poor (sparse interaction matrix → unreliable similarities)
- Diversity: moderate to good (draws from diverse neighbour histories)
- Coverage: low (many workouts have zero interactions → never recommended)
- Novelty: moderate (depends on neighbour diversity)

WHAT WE LEARNED
---------------
CF requires **dense interaction data** to compute meaningful similarities.
In our scenario:
- Few simulated users → too few neighbours to learn from
- Sparse completions → most user-pairs have near-zero overlap
- Cold-start users get no recommendations at all

This confirms that **content-based filtering is the right choice** for our
low-data fitness application.  CF would only become viable with hundreds
of active users generating rich interaction histories.

KEY DISCUSSION POINTS FOR SEMINAR
----------------------------------
1. **Data requirements**: CF needs O(users × items) interactions; content-based
   needs only item features + user profile.
2. **Sparsity**: With 50 users and 800+ workouts, the interaction matrix is
   >98% empty — cosine similarities become unreliable.
3. **Cold-start**: New users have empty rows → CF produces nothing.
   Content-based can immediately recommend based on stated preferences.
4. **Serendipity**: CF's one advantage is discovering items that are *different*
   from what the user has tried but *similar* users enjoyed.

WHY WE MOVED TO EXPERIMENT 5
-----------------------------
Since pure CF fails in sparse settings, we explore whether a **hybrid**
approach (combining content scores with popularity) can get the best of
both worlds — personalisation from content + robustness from popularity.
"""

# --------------------------------------------------------------------------- #
#  Skeleton implementation (not runnable without multi-user interaction data)  #
# --------------------------------------------------------------------------- #

from typing import List, Dict
from collections import defaultdict
import math

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile
from experiments.experiment_base import ExperimentBase


class CollaborativeFilteringRecommender(ExperimentBase):
    """
    User-based collaborative filtering (STUB).

    This class documents the algorithm structure but is not fully
    functional — it requires real multi-user interaction data that
    our current system does not collect.
    """

    name = "Exp 4: Collaborative Filtering"
    description = "User-based CF using cosine similarity on interaction vectors. (STUB)"

    def __init__(self, interaction_matrix: Dict[int, Dict[str, int]] = None, k: int = 5):
        """
        Parameters
        ----------
        interaction_matrix : Dict[int, Dict[str, int]]
            user_id → {workout_id: 1/0} interaction data.
        k : int
            Number of nearest neighbours to consider.
        """
        self.interaction_matrix = interaction_matrix or {}
        self.k = k

    @staticmethod
    def _cosine_similarity(vec_a: Dict[str, int], vec_b: Dict[str, int]) -> float:
        """Cosine similarity between two sparse interaction vectors."""
        # Union of keys
        all_keys = set(vec_a.keys()) | set(vec_b.keys())
        if not all_keys:
            return 0.0

        dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in all_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        target_user_id: int = 0,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        ⚠ STUB — returns empty list if no interaction data is provided.

        In a full implementation:
        1. Compute similarity to all other users
        2. Find K nearest neighbours
        3. Aggregate their preferred workouts
        4. Return top-N unseen workouts
        """
        if not self.interaction_matrix:
            # No data available — CF cannot function
            return []

        target_vec = self.interaction_matrix.get(target_user_id, {})
        if not target_vec:
            return []  # Cold-start case

        # Find neighbours
        similarities: Dict[int, float] = {}
        for uid, vec in self.interaction_matrix.items():
            if uid == target_user_id:
                continue
            sim = self._cosine_similarity(target_vec, vec)
            if sim > 0:
                similarities[uid] = sim

        neighbours = sorted(similarities, key=similarities.get, reverse=True)[:self.k]

        # Aggregate
        scores: Dict[str, float] = defaultdict(float)
        for nid in neighbours:
            sim = similarities[nid]
            for wid, completed in self.interaction_matrix[nid].items():
                if completed and wid not in target_vec:
                    scores[wid] += sim

        # Map back to WorkoutItem objects
        workout_lookup = {w.workout_id: w for w in workouts}
        ranked = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [workout_lookup[wid] for wid in ranked if wid in workout_lookup]
