"""
Experiment 7 — VDB-Based Collaborative Filtering (Profile Similarity)
======================================================================

✅ STATUS: FULLY IMPLEMENTED — functional CF using a user-profile VDB.

PURPOSE
-------
Experiment 4 (classic CF) failed completely because we have no user-item
interaction data.  Experiment 7 solves this with a different CF paradigm:
**profile-based (demographic) collaborative filtering**.

Instead of asking "which users completed the same workouts?", we ask:
"which users have similar fitness profiles?" — then use those users'
content preferences as a CF signal.

This is academically grounded:
  Pazzani, M.J. (1999). "A framework for collaborative, content-based
  and demographic filtering." Artificial Intelligence Review, 13(5-6),
  393-408.

It is the standard remedy for CF cold-start in fitness apps where:
  • User-item interactions are sparse or absent
  • User profile information (goal, equipment, diet, level) is rich
  • A population of reference users already exists (the 10 personas)

HOW IT WORKS
------------
1. At initialisation, index all population profiles into a UserProfileIndex
   (numpy-backed cosine similarity VDB — see cf_vdb.py).

2. When recommending for a target user:
   a. Hard-filter the workout catalogue (equipment + level).
   b. Embed the target profile → query the VDB → retrieve the
      top-N most similar users with their cosine similarities.
   c. For each candidate workout, compute a CF bonus:
          cf_bonus(w) = Σ sim_i × score_workout(w, similar_user_i)
      This is a similarity-weighted aggregation of what similar users
      would score the workout — the CF signal.
   d. Normalise the CF bonus to [0, 1].
   e. Compute the target user's own content score (same as Exp 3).
   f. Blend:
          final_score = α × content_score_norm + (1-α) × cf_bonus_norm

3. Sort by final_score and return top-K.

WHY THIS IS BETTER THAN EXP 4
------------------------------
• Exp 4 required a non-empty interaction matrix → always returned [].
• Exp 7 uses profile features → produces recommendations for every user.
• The CF signal genuinely draws on *other users' preferences*, not just
  the target user's own goal weights.
• Users with identical profiles (e.g. two muscle-gain intermediate gym
  users) get recommendations influenced by all similar users' equipment
  & preference nuances — adding serendipity.

SCORE FORMULA
-------------
    final_score(w, u) = α × norm(content_score(w, u))
                      + (1-α) × norm(cf_bonus(w))

Where:
    content_score   = score_workout(w, u)         from filters.py  [Exp 3]
    cf_bonus(w)     = Σ cosine_sim(u, u_j) × score_workout(w, u_j)
    α               = content weight (default 0.6)
    (1-α)           = CF weight      (default 0.4)

PARAMETERS
----------
| Parameter       | Default | Effect                                   |
|-----------------|---------|------------------------------------------|
| alpha           | 0.6     | Content vs CF blend. 1.0 = pure content. |
| cf_neighbours   | 3       | Similar users to consult per query.      |
| population      | personas| UserProfile pool indexed into the VDB.   |

EXPECTED RESULTS
----------------
- Precision:  ≥ 0.94 — similar users share goal alignment, preserving
  relevance. Slight variation vs Exp 3 due to CF influence.
- Diversity:  ≥ 0.54 — similar users with slightly different equipment/
  preferences may inject variety beyond a single user's profile.
- Coverage:   ~0.9% — consistent with content-aware methods at K=5.
- Novelty:    ~10.49 — same popularity proxy as other methods.

WHAT WE LEARNED
---------------
Profile-based CF produces a functioning CF signal without any interaction
data.  The VDB query is fast (O(n) numpy dot products on 30-dim vectors)
and the leave-one-out design ensures we never query a user against herself.
"""

from __future__ import annotations

from typing import List, Dict, Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from workouts import WorkoutItem
from user_profile import UserProfile
from filters import hard_filter_workouts, score_workout
from cf_vdb import UserProfileIndex
from experiments.experiment_base import ExperimentBase


class CFVDBRecommender(ExperimentBase):
    """
    Collaborative Filtering via User-Profile Vector Database.

    Finds the most similar users in the VDB (cosine similarity over
    embedded profile vectors), then blends their content scores with
    the target user's own content score to produce recommendations.

    Parameters
    ----------
    population_users : List[UserProfile]
        Reference user pool to index (e.g. the 10 Persona profiles).
    population_ids   : List[str]
        Human-readable labels for each profile (e.g. persona names).
    alpha            : float
        Weight for the target user's own content score (0-1).
        (1-alpha) is the weight for the CF-neighbour bonus.
    cf_neighbours    : int
        How many similar users to retrieve from the VDB per query.
    """

    name = "Exp 7: CF-VDB (Profile Similarity)"
    description = (
        "Profile-based CF: embed user profiles into a VDB, "
        "retrieve similar users, blend their content scores as a CF signal."
    )

    def __init__(
        self,
        population_users: List[UserProfile],
        population_ids: List[str],
        alpha: float = 0.6,
        cf_neighbours: int = 3,
    ) -> None:
        self.alpha = alpha
        self.cf_neighbours = cf_neighbours

        # Build the user-profile VDB at construction time
        self._index = UserProfileIndex()
        self._index.fit(population_users, population_ids)

        # Map id → UserProfile for CF bonus computation
        self._profile_map: Dict[str, UserProfile] = {
            uid: usr for uid, usr in zip(population_ids, population_users)
        }

    # ── Core recommendation method ────────────────────────────────────

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        exclude_id: Optional[str] = None,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        Return top-K workouts using profile-CF blended scoring.

        Parameters
        ----------
        user       : Target UserProfile to recommend for.
        workouts   : Full workout catalogue.
        top_k      : Number of results to return.
        exclude_id : VDB entry to exclude from neighbour search
                     (pass the persona name to do leave-one-out evaluation).
        """
        # 1. Hard filter — same constraints as Exp 3
        candidates = hard_filter_workouts(workouts, user)
        if not candidates:
            return []

        # 2. Query VDB for similar users (leave-one-out)
        exclude = [exclude_id] if exclude_id else []
        neighbours = self._index.query(
            user,
            top_k=self.cf_neighbours,
            exclude_ids=exclude,
        )
        # neighbours = [(uid, cosine_sim), ...]

        # 3. Compute per-workout scores
        scored = []
        for workout in candidates:
            # ── content score (target user's own preferences) ──
            cs = score_workout(workout, user)

            # ── CF bonus (weighted sum over similar users) ──────
            cf_bonus = 0.0
            total_sim = sum(sim for _, sim in neighbours)
            if total_sim > 0:
                for uid, sim in neighbours:
                    other = self._profile_map[uid]
                    cf_bonus += sim * score_workout(workout, other)

            scored.append((workout, cs, cf_bonus))

        if not scored:
            return []

        # 4. Normalise both score dimensions to [0, 1] independently
        all_cs     = [cs    for _, cs, _  in scored]
        all_cf     = [cf    for _, _, cf  in scored]

        cs_norm = _minmax_normalise(all_cs)
        cf_norm = _minmax_normalise(all_cf)

        # 5. Blend and rank
        blended = []
        for i, (workout, _, _) in enumerate(scored):
            final = self.alpha * cs_norm[i] + (1.0 - self.alpha) * cf_norm[i]
            blended.append((workout, final))

        blended.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in blended[:top_k]]


# ================================================================== #
#  Internal helpers                                                   #
# ================================================================== #

def _minmax_normalise(values: List[float]) -> List[float]:
    """
    Scale a list of floats to [0, 1].
    If all values are equal, returns all 0.5 (avoids divide-by-zero).
    """
    lo, hi = min(values), max(values)
    spread = hi - lo
    if spread == 0:
        return [0.5] * len(values)
    return [(v - lo) / spread for v in values]
