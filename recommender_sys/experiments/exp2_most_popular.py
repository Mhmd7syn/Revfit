"""
Experiment 2 — Most Popular Recommender
=======================================

PURPOSE
-------
Tests whether **global popularity** alone is a useful recommendation signal.
This is the "naive" baseline that most academic papers include.

METHOD
------
Rank all workouts by their popularity (number of completions across all
simulated users).  After hard-filtering, return the top-K most popular
workouts that the current user hasn't completed yet.

Since we don't have real user interaction data, we use the **rating** field
from the megaGymDataset as a proxy for popularity: higher-rated workouts
are assumed to be more widely completed.

WHY WE INCLUDED IT
------------------
1. **Popularity baseline** — shows whether personalisation adds value over
   simply recommending what everyone else likes.
2. **Industry standard** — most recommendation papers compare against a
   popularity baseline.
3. **Cold-start solution** — in production, this is what you'd show a brand-new
   user before you learn their preferences.

EXPECTED RESULTS
----------------
- Precision / Recall: moderate (popular items are popular for a reason)
- Diversity: low (everyone gets the same recommendations)
- Coverage: very low (only recommends a small slice of the catalogue)
- Novelty: lowest (by definition, it recommends the most common items)

WHAT WE LEARNED
---------------
Most-Popular achieves decent relevance metrics because high-quality workouts
tend to be popular.  However, it provides zero personalisation — every user
gets the exact same list.  This shows that popularity is a useful signal but
is insufficient on its own.

WHY WE MOVED TO EXPERIMENT 3
-----------------------------
Popularity misses the user entirely.  Content-Based Filtering (Exp 3) uses
the user's specific goals, equipment, and level to personalise recommendations,
which should beat popularity for users whose preferences diverge from the
average.
"""

from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile
from filters import hard_filter_workouts
from experiments.experiment_base import ExperimentBase


class MostPopularRecommender(ExperimentBase):
    """Recommend the globally most popular workouts (rating as proxy)."""

    name = "Exp 2: Most Popular"
    description = "Rank by global popularity (rating proxy), no personalisation."

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        popularity: Dict[str, int] = None,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        Parameters
        ----------
        user       : UserProfile — only used for hard-filter constraints.
        workouts   : Full workout catalogue.
        top_k      : Number of results.
        popularity : Optional dict workout_id → completion count from
                     synthetic interactions.  If None, falls back to rating.

        Returns
        -------
        List[WorkoutItem] — top-K by popularity.
        """
        candidates = hard_filter_workouts(workouts, user)

        if popularity:
            # Sort by interaction count (descending)
            scored = sorted(
                candidates,
                key=lambda w: popularity.get(w.workout_id, 0),
                reverse=True,
            )
        else:
            # Fallback: use the dataset's rating as a popularity proxy
            scored = sorted(
                candidates,
                key=lambda w: (w.rating or 0),
                reverse=True,
            )

        return scored[:top_k]
