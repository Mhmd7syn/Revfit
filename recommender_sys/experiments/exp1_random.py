"""
Experiment 1 — Random Recommender
=================================

PURPOSE
-------
Establishes the **worst-case lower bound** for recommendation quality.
Any intelligent recommender should comfortably beat random selection.

METHOD
------
After applying the same hard filters (equipment availability, fitness level)
as our content-based system, we randomly sample K workouts from the
remaining candidates.  No user preference, history, or item feature
information is used.

WHY WE INCLUDED IT
------------------
1. **Statistical baseline** — without a random baseline, we can't demonstrate
   that our content-based scores are meaningfully better than chance.
2. **Diversity benchmark** — random selection maximises diversity, so it sets
   the upper bound for that metric.
3. **Cold-start analogy** — in production, a random recommender is essentially
   what happens when you have *zero* information about a user.

EXPECTED RESULTS
----------------
- Precision / Recall: very low (essentially guessing)
- Diversity: maximum (highest of all experiments)
- Coverage: highest (no popularity bias)
- Novelty: highest (equally likely to recommend rare items)

WHAT WE LEARNED
---------------
Random performs terribly on relevance metrics but scores highest on diversity
and novelty.  This confirms that naive randomness explores the catalogue fully
but provides no personalisation.  It demonstrates that our content-based system
adds real value by focusing on the user's goals and constraints.

WHY WE MOVED TO EXPERIMENT 2
-----------------------------
Random lacks any intelligence.  The next step is to test whether even a simple
non-personalised signal (global popularity) can do better, which motivates
Experiment 2: Most Popular Recommender.
"""

import random as _random
from typing import List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile
from filters import hard_filter_workouts
from experiments.experiment_base import ExperimentBase


class RandomRecommender(ExperimentBase):
    """Return random workouts after hard-filtering by equipment and level."""

    name = "Exp 1: Random"
    description = "Random selection from hard-filtered candidates."

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        seed: int = None,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        Parameters
        ----------
        user      : UserProfile with equipment and fitness_level set.
        workouts  : Full workout catalogue.
        top_k     : Number of results to return.
        seed      : Optional random seed for reproducibility.

        Returns
        -------
        List[WorkoutItem] — random sample (size ≤ top_k).
        """
        # Apply the same hard filters as the content-based system
        candidates = hard_filter_workouts(workouts, user)

        if seed is not None:
            _random.seed(seed)

        k = min(top_k, len(candidates))
        return _random.sample(candidates, k)
