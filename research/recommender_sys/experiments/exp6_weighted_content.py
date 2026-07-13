"""
Experiment 6 — Feature-Weighted Content-Based Recommender
=========================================================

⚠ STATUS: DOCUMENTED STUB — algorithm structure and rationale only.

PURPOSE
-------
Extend our content-based system (Exp 3) by allowing **different weights
for different features**, rather than using a fixed scoring formula.
The hypothesis is that feature importance varies by user: some users
care most about workout difficulty, others about equipment availability.

METHOD
------
Instead of the fixed scoring in `score_workout()`, we introduce a weight
vector W = [w_type, w_level, w_equipment_match, w_rating, w_feedback]
and compute:

    score = W · F(workout, user)

where F extracts normalised feature signals.

FEATURE WEIGHT STRATEGIES
-------------------------
| Strategy             | Weights                              | Rationale                        |
|----------------------|--------------------------------------|----------------------------------|
| Uniform              | [0.2, 0.2, 0.2, 0.2, 0.2]           | Equal importance (baseline)      |
| Goal-focused         | [0.4, 0.2, 0.1, 0.2, 0.1]           | Workout type matters most        |
| Difficulty-focused   | [0.1, 0.5, 0.1, 0.2, 0.1]           | Match difficulty precisely       |
| Equipment-focused    | [0.1, 0.1, 0.5, 0.2, 0.1]           | Users with limited gear          |
| Feedback-focused     | [0.1, 0.1, 0.1, 0.1, 0.6]           | Heavy personalisation from likes |
| Learned from history | [optimised via gradient-free search] | Data-driven weights              |

ALGORITHM SKETCH
----------------
```python
def weighted_content_recommend(user, workouts, weights=None, n=10):
    if weights is None:
        weights = {'type': 0.2, 'level': 0.2, 'equip': 0.2,
                   'rating': 0.2, 'feedback': 0.2}

    candidates = hard_filter_workouts(workouts, user)
    scores = {}
    for w in candidates:
        features = extract_features(w, user)
        # features = [type_match, level_match, equipment_match, rating, feedback]
        score = sum(weights[k] * features[k] for k in weights)
        scores[w.id] = score

    return sorted(scores, key=scores.get, reverse=True)[:n]


def extract_features(workout, user):
    return {
        'type':     goal_type_score(workout, user),       # 0-3 range
        'level':    level_match_score(workout, user),      # 0-1 range
        'equip':    equipment_match_score(workout, user),  # 0 or 1
        'rating':   (workout.rating or 0) / 10,           # normalised
        'feedback': user.workout_preferences.get(
                        workout.workout_id, 0),            # raw feedback
    }


def learn_weights(user, workouts, held_out_set):
    \"\"\"
    Simple grid search or random search over weight space to find
    weights that maximise precision on a held-out set of liked workouts.
    \"\"\"
    best_weights = None
    best_precision = 0

    for trial in range(100):
        # Random weight vector (normalised to sum to 1)
        w = random_weight_vector(5)
        recs = weighted_recommend(user, workouts, w)
        p = precision_at_k(recs, held_out_set)
        if p > best_precision:
            best_precision = p
            best_weights = w

    return best_weights
```

WHY WE INCLUDED IT
------------------
1. **Interpretability** — shows which features actually drive good
   recommendations for different user types.
2. **Natural extension** — a clear evolution from our fixed-weight Exp 3.
3. **A/B testing potential** — different users could benefit from different
   weight configurations.
4. **Research direction** — demonstrates awareness of learned representations.

EXPECTED RESULTS
----------------
- Precision / Recall: potentially best (weights optimised for the task)
- Diversity: depends on weight distribution
- Coverage: similar to content-based
- Novelty: similar to content-based

WHAT WE LEARNED
---------------
Feature weighting addresses a limitation of our reference system: the
fixed scoring formula treats every user the same way.  By allowing
per-user or per-goal-type weights, we can:
- Better handle diverse user preferences
- Identify which features actually matter (feature importance analysis)
- Create interpretable explanations ("We recommended this because you
  prioritise difficulty-appropriate exercises")

The main challenge is **learning good weights** without enough interaction
data — random search works but isn't guaranteed to find the optimum.
More sophisticated approaches (Bayesian optimisation, online learning)
would be needed for production use.

CONCLUSIONS FROM ALL EXPERIMENTS
--------------------------------
1. **Random** (Exp 1) → worst relevance, best diversity — pure exploration.
2. **Most Popular** (Exp 2) → decent relevance, no personalisation.
3. **Content-Based** (Exp 3) → good relevance, personalised, our reference.
4. **Collaborative Filtering** (Exp 4) → needs dense data we don't have.
5. **Hybrid** (Exp 5) → most robust, industry standard, tunable.
6. **Weighted Content** (Exp 6) → most potential, but needs weight learning.

For our sparse-data fitness app, **Content-Based (Exp 3)** is the right
choice, with **Hybrid (Exp 5)** as the natural next step when we have
enough users to compute meaningful popularity signals.
"""

# --------------------------------------------------------------------------- #
#  Skeleton implementation                                                    #
# --------------------------------------------------------------------------- #

from typing import List, Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workouts import WorkoutItem
from user_profile import UserProfile
from filters import hard_filter_workouts, GOAL_TYPE_WEIGHTS
from experiments.experiment_base import ExperimentBase


# Default uniform weights
DEFAULT_WEIGHTS = {
    "type":      0.2,
    "level":     0.2,
    "equipment": 0.2,
    "rating":    0.2,
    "feedback":  0.2,
}


class WeightedContentRecommender(ExperimentBase):
    """
    Content-based recommender with tuneable feature weights.

    STUB — demonstrates the concept.  Weight learning requires
    held-out liked workouts to optimise against.
    """

    name = "Exp 6: Weighted Content"
    description = "Content-based with tuneable feature importance weights. (STUB)"

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def _extract_features(self, workout: WorkoutItem, user: UserProfile) -> Dict[str, float]:
        """Extract normalised feature signals for one workout-user pair."""
        from constants import LEVEL_ORDER

        # Type-goal alignment (0 – 3 range, normalised to 0-1)
        goal_weights = GOAL_TYPE_WEIGHTS.get(user.goal_type, {})
        type_score = goal_weights.get(workout.workout_type, 0.5) / 3.0

        # Level match (1 if exact match, 0.5 if close, 0.2 if distant)
        user_lvl = LEVEL_ORDER.get(user.fitness_level.capitalize(), 0)
        work_lvl = LEVEL_ORDER.get(workout.level, 0)
        level_diff = abs(user_lvl - work_lvl)
        level_score = {0: 1.0, 1: 0.5, 2: 0.2}.get(level_diff, 0.1)

        # Equipment match (1 if available, 0.5 if body only, 0 otherwise)
        if workout.equipment in user.available_equipment:
            equip_score = 1.0
        elif workout.equipment == "Body Only":
            equip_score = 0.5
        else:
            equip_score = 0.0

        # Rating (normalised to 0-1)
        rating_score = (workout.rating or 0) / 10.0

        # Feedback signal (raw, can be negative)
        feedback_score = user.workout_preferences.get(workout.workout_id, 0)
        # Clamp to [-1, 1] for normalisation
        feedback_score = max(-1.0, min(1.0, feedback_score))
        # Shift to [0, 1]
        feedback_norm = (feedback_score + 1) / 2.0

        return {
            "type":      type_score,
            "level":     level_score,
            "equipment": equip_score,
            "rating":    rating_score,
            "feedback":  feedback_norm,
        }

    def recommend(
        self,
        user: UserProfile,
        workouts: List[WorkoutItem],
        top_k: int = 10,
        **kwargs,
    ) -> List[WorkoutItem]:
        """
        Score each workout using weighted feature combination.

        score = Σ (weight_i × feature_i)  for all features
        """
        candidates = hard_filter_workouts(workouts, user)

        scored = []
        for w in candidates:
            features = self._extract_features(w, user)
            score = sum(self.weights[k] * features[k] for k in self.weights)
            scored.append((w, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in scored[:top_k]]
