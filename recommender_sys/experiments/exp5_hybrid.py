"""
Experiment 5 — Hybrid Recommender (Content + Popularity Weighted)
=================================================================

⚠ STATUS: DOCUMENTED STUB — algorithm structure and rationale only.
   Skeleton code provided for reference; metrics are illustrative.

PURPOSE
-------
Combine the strengths of content-based filtering (personalisation) with
popularity-based ranking (robustness) using a tunable weighting parameter α.

    hybrid_score = α × content_score + (1-α) × popularity_score

This approach is the **most common in industry** and addresses weaknesses
of both pure approaches.

METHOD
------
1. Compute **content-based scores** using our existing `score_workout()`
   function (goal alignment + feedback + rating).
2. Compute **popularity scores** — normalised completion counts across
   all users (or rating as proxy).
3. Combine with weighting parameter α:
   - α = 1.0 → pure content-based (Exp 3)
   - α = 0.0 → pure popularity (Exp 2)
   - α = 0.7 → 70% content + 30% popularity (balanced)
4. Sort by hybrid score and return top-K.

ALGORITHM SKETCH
----------------
```python
def hybrid_recommend(user, workouts, interaction_history, alpha=0.7, n=10):
    # Step 1: Content-based scores (normalised to 0-1)
    candidates = hard_filter_workouts(workouts, user)
    content = {w.id: score_workout(w, user) for w in candidates}
    max_c = max(content.values()) or 1
    content_norm = {wid: s / max_c for wid, s in content.items()}

    # Step 2: Popularity scores (normalised to 0-1)
    popularity = compute_popularity(interaction_history)
    max_p = max(popularity.values()) or 1
    pop_norm = {wid: popularity.get(wid, 0) / max_p for wid in content}

    # Step 3: Combine
    hybrid = {}
    for wid in content:
        hybrid[wid] = alpha * content_norm[wid] + (1-alpha) * pop_norm.get(wid, 0)

    # Step 4: Sort and return
    ranked = sorted(hybrid, key=hybrid.get, reverse=True)
    return ranked[:n]
```

α-TUNING EXPERIMENTS
--------------------
| α    | Content Weight | Popularity Weight | Expected Behaviour           |
|------|----------------|-------------------|------------------------------|
| 1.0  | 100%           | 0%                | Pure content-based (Exp 3)   |
| 0.7  | 70%            | 30%               | Personalised with pop boost  |
| 0.5  | 50%            | 50%               | Equal blend                  |
| 0.3  | 30%            | 70%               | Popularity-heavy             |
| 0.0  | 0%             | 100%              | Pure popularity (Exp 2)      |

WHY WE INCLUDED IT
------------------
1. **Industry relevance** — most production recommender systems (Netflix,
   Spotify, Amazon) use hybrid approaches.
2. **Tunable parameter** — α provides a knob to control the
   exploration-exploitation trade-off.
3. **Cold-start handling** — new users with no feedback get reasonable
   recommendations from the popularity component.
4. **Robustness** — combining signals reduces the risk of poor
   recommendations from any single approach.

EXPECTED RESULTS
----------------
- Precision / Recall: best or near-best (combines two informative signals)
- Diversity: moderate (α controls the trade-off)
- Coverage: moderate (popularity component creates some bias)
- Novelty: moderate (less than content-only because popularity pushes
  toward common items)

WHAT WE LEARNED
---------------
The hybrid approach shows that **combining signals is almost always
better than any single signal**.  The α parameter lets us tune:
- α → 1: maximum personalisation (good for established users)
- α → 0: maximum safety (good for new users / cold start)

In a production system, α could be adaptive:
- Start low for new users (rely on popularity)
- Increase as the system learns more about the user

WHY WE MOVED TO EXPERIMENT 6
-----------------------------
While the hybrid approach improves robustness, both the content and
popularity components use **fixed feature weights**.  Experiment 6
explores whether we can **learn** which features matter most to each
user, potentially improving personalisation further.
"""

# --------------------------------------------------------------------------- #
#  Skeleton implementation                                                    #
# --------------------------------------------------------------------------- #

from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile
from filters import hard_filter_workouts, score_workout
from experiments.experiment_base import ExperimentBase


class HybridRecommender(ExperimentBase):
    """
    Hybrid recommender combining content-based scores with popularity.

    STUB — demonstrates the algorithm structure.  The popularity
    component requires interaction data (synthetic or real).
    """

    name = "Exp 5: Hybrid"
    description = "α × content_score + (1-α) × popularity_score. (STUB)"

    def __init__(self, alpha: float = 0.7):
        """
        Parameters
        ----------
        alpha : float
            Blending weight.  1.0 = pure content-based, 0.0 = pure popularity.
        """
        self.alpha = alpha

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        popularity: Dict[str, int] = None,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        ⚠ STUB — falls back to content-based if no popularity data.

        Full implementation normalises both score distributions to [0,1]
        and blends them with α.
        """
        candidates = hard_filter_workouts(workouts, user)

        if not popularity:
            # No popularity data → degrade to content-based
            scored = [(w, score_workout(w, user)) for w in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [w for w, _ in scored[:top_k]]

        # Content scores
        content_scores = {w.workout_id: score_workout(w, user) for w in candidates}
        max_c = max(content_scores.values()) if content_scores else 1.0
        if max_c == 0:
            max_c = 1.0

        # Popularity scores
        max_p = max(popularity.values()) if popularity else 1
        if max_p == 0:
            max_p = 1

        # Hybrid blend
        hybrid = []
        for w in candidates:
            c_norm = content_scores[w.workout_id] / max_c
            p_norm = popularity.get(w.workout_id, 0) / max_p
            score = self.alpha * c_norm + (1 - self.alpha) * p_norm
            hybrid.append((w, score))

        hybrid.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in hybrid[:top_k]]
