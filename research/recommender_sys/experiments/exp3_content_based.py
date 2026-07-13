"""
Experiment 3 — Content-Based Filtering (Our Reference System)
=============================================================

PURPOSE
-------
This is our **reference baseline** — the actual recommender system we built
for Revfit.  All other experiments are compared against this.

METHOD
------
Content-based filtering matches *item features* to a *user profile*:

1. **Hard filters** — remove workouts that don't match the user's equipment
   or are above their fitness level.
2. **Goal-weighted scoring** — each workout_type receives a weight based on the
   user's goal (e.g. `Strength: 3.0` for `muscle_gain`, `Cardio: 3.0` for
   `fat_loss`).
3. **Feedback signals** — user likes/dislikes modify scores:
   - Workout-specific preference (+0.7 per like/dislike)
   - Workout-type preference (+0.3 per like/dislike)
   Both use exponential decay over time.
4. **Rating bonus** — global rating adds +0.2 × rating.
5. **Sort and return top-K**.

FEATURES USED
-------------
| Feature        | Role in Scoring                          |
|----------------|------------------------------------------|
| workout_type   | Goal-alignment weight (0.5 – 3.0)       |
| body_part      | Hard filter (via plan_type split mapping)|
| equipment      | Hard filter (must match user's equipment)|
| level          | Hard filter (must ≤ user's fitness_level)|
| rating         | Bonus signal (+0.2 × rating)             |
| feedback       | Personalisation via like/dislike memory  |

WHY IT'S THE REFERENCE
----------------------
This is the system we actually deployed and the most complete implementation.
It demonstrates understanding of:
- Feature engineering for recommendations
- Multi-signal scoring (goal + feedback + quality)
- Hard vs. soft constraints
- Feedback decay for temporal relevance

EXPECTED RESULTS
----------------
- Precision / Recall: good (personalised to user's goals and constraints)
- Diversity: moderate (goal weights create some bias toward certain types)
- Coverage: good (hard filters depend on user, so different users see
  different subsets)
- Novelty: moderate (rating bonus slightly favours well-known exercises)

WHAT WE LEARNED
---------------
Content-based filtering works well for our use case because:
1. Rich item features exist (type, body part, equipment, level, rating)
2. User preferences can be encoded as feature preferences
3. No user-user interaction data is needed (solves cold-start for new users)
4. Feedback decay keeps recommendations fresh over time

Limitations:
- Can't discover items outside the user's existing feature preferences
  (the "filter bubble" problem)
- Feature weights are fixed per goal, not learned from data
- No serendipity — won't surprise users with unexpected but good matches

WHY WE EXPLORED FURTHER
------------------------
While content-based works well, we wanted to explore:
- Exp 4 (Collaborative Filtering): Can user-user similarity beat feature matching?
- Exp 5 (Hybrid): Can combining popularity with content scores improve robustness?
- Exp 6 (Weighted Content): Can we learn better feature weights from data?
"""

from typing import List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile
from filters import hard_filter_workouts, score_workout
from experiments.experiment_base import ExperimentBase


class ContentBasedRecommender(ExperimentBase):
    """
    Content-based recommender — wraps the existing Revfit scoring logic
    from filters.py.

    This is the REFERENCE SYSTEM that all experiments are compared against.
    """

    name = "Exp 3: Content-Based"
    description = "Content-based filtering with goal weights + feedback + rating."

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        Delegates to the existing filters.py pipeline:
            hard_filter_workouts → score_workout → sort → top-K

        Parameters
        ----------
        user     : UserProfile with goal_type, equipment, fitness_level,
                   workout_preferences, etc.
        workouts : Full workout catalogue.
        top_k    : Number of results.

        Returns
        -------
        List[WorkoutItem] — top-K scored by content-based relevance.
        """
        valid = hard_filter_workouts(workouts, user)
        scored = [(w, score_workout(w, user)) for w in valid]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in scored[:top_k]]
