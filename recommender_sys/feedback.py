"""
feedback.py — Persistent meal & workout feedback store with decay.

Feedback is saved to a JSON file (default: feedback_store.json).

Workout feedback uses **exponential decay**: signals from the past
lose influence over time according to DECAY_HALF_LIFE_DAYS (constants.py).

  decayed_score = sum(delta_i × 0.5 ^ (days_elapsed_i / half_life))

Usage
-----
from feedback import FeedbackStore

store = FeedbackStore()
store.record_workout(workout, liked=True)
store.record_meal("recipe_42", liked=True)
store.load_into_user(user)          # apply decayed scores to user
store.save()                        # persist to disk
"""

import json
import os
import math
from datetime import datetime, timezone
from typing import Dict, List

from constants import GOAL_DECAY_DAYS, DECAY_HALF_LIFE_DEFAULT

DEFAULT_PATH = "feedback_store.json"


# ================================================================== #
#  Internal helpers                                                   #
# ================================================================== #

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _days_since(iso_ts: str) -> float:
    """Return how many days have elapsed since an ISO-8601 timestamp."""
    then = datetime.fromisoformat(iso_ts)
    # Make timezone-aware if naive
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - then
    return delta.total_seconds() / 86_400.0


def _decay_factor(days: float, half_life: float) -> float:
    """Exponential decay: 1.0 at day 0, 0.5 at day=half_life."""
    return math.pow(0.5, days / half_life)


# ================================================================== #
#  FeedbackStore                                                      #
# ================================================================== #

class FeedbackStore:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._data: Dict = self._load()
        self._migrate_legacy()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self) -> Dict:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._default_schema()

    @staticmethod
    def _default_schema() -> Dict:
        return {
            "liked_meals":              [],
            "disliked_meals":           [],
            "liked_workouts":           [],
            "disliked_workouts":        [],
            # NEW: timestamped events (replaces flat workout_preferences)
            "workout_events":           [],
            # Legacy flat dicts (kept for backward compat, migrated on load)
            "workout_preferences":      {},
            "workout_type_preferences": {},
        }

    def _migrate_legacy(self):
        """
        One-time migration: if the store has the old flat workout_preferences
        dict but no events yet, convert each entry to a timestamped event
        stamped as 'now' so decay starts from today.
        """
        if "workout_events" not in self._data:
            self._data["workout_events"] = []

        legacy_prefs = self._data.get("workout_preferences", {})
        if legacy_prefs and not self._data["workout_events"]:
            ts = _now_iso()
            for wid, score in legacy_prefs.items():
                # Treat the existing score as a single event with delta=score
                self._data["workout_events"].append({
                    "workout_id":   wid,
                    "workout_type": None,   # unknown from old format
                    "delta":        score,
                    "ts":           ts,
                })
            # Clear the legacy flat dict so we don't migrate twice
            self._data["workout_preferences"] = {}
            self.save()

    def save(self):
        """Write feedback to disk."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    # ------------------------------------------------------------------ #
    #  Meal feedback                                                       #
    # ------------------------------------------------------------------ #

    def record_meal(self, recipe_id: str, liked: bool):
        """Record a meal like/dislike and persist immediately."""
        if liked:
            if recipe_id not in self._data["liked_meals"]:
                self._data["liked_meals"].append(recipe_id)
            if recipe_id in self._data["disliked_meals"]:
                self._data["disliked_meals"].remove(recipe_id)
        else:
            if recipe_id not in self._data["disliked_meals"]:
                self._data["disliked_meals"].append(recipe_id)
            if recipe_id in self._data["liked_meals"]:
                self._data["liked_meals"].remove(recipe_id)
        self.save()

    # ------------------------------------------------------------------ #
    #  Workout feedback (timestamped)                                      #
    # ------------------------------------------------------------------ #

    def record_workout(self, workout, liked: bool):
        """
        Record a workout like/dislike as a timestamped event.

        Each call appends one event:
          { workout_id, workout_type, delta (+1 or -1), ts (ISO UTC) }

        The running score used by the recommender is computed from all
        events on load, with exponential decay applied per event.
        """
        delta = 1 if liked else -1

        self._data["workout_events"].append({
            "workout_id":   workout.workout_id,
            "workout_type": workout.workout_type,
            "delta":        delta,
            "ts":           _now_iso(),
        })

        # Also maintain the liked/disliked id lists for summary display
        if liked:
            if workout.workout_id not in self._data["liked_workouts"]:
                self._data["liked_workouts"].append(workout.workout_id)
        else:
            if workout.workout_id not in self._data["disliked_workouts"]:
                self._data["disliked_workouts"].append(workout.workout_id)

        self.save()

    # ------------------------------------------------------------------ #
    #  Apply saved (decayed) feedback to a UserProfile                   #
    # ------------------------------------------------------------------ #

    def load_into_user(self, user):
        """
        Populate user feedback fields from the persisted store.
        Workout scores are decayed using the half-life for user.goal_type.
        Call this right after creating a UserProfile.
        """
        from collections import defaultdict

        user.liked_meals       = list(self._data.get("liked_meals", []))
        user.disliked_meals    = list(self._data.get("disliked_meals", []))
        user.liked_workouts    = list(self._data.get("liked_workouts", []))
        user.disliked_workouts = list(self._data.get("disliked_workouts", []))

        # ---- Decayed workout_preferences (goal-aware half-life) ----
        half_life = GOAL_DECAY_DAYS.get(user.goal_type, DECAY_HALF_LIFE_DEFAULT)
        prefs: Dict[str, float] = {}
        type_prefs: Dict[str, float] = defaultdict(float)

        for event in self._data.get("workout_events", []):
            wid   = event["workout_id"]
            wtype = event.get("workout_type")
            delta = event["delta"]
            ts    = event["ts"]

            days   = _days_since(ts)
            factor = _decay_factor(days, half_life)

            prefs[wid] = prefs.get(wid, 0.0) + delta * factor
            if wtype:
                type_prefs[wtype] += 0.3 * delta * factor

        user.workout_preferences      = prefs
        user.workout_type_preferences = type_prefs

    # ------------------------------------------------------------------ #
    #  Decay info                                                          #
    # ------------------------------------------------------------------ #

    def decay_summary(self, user=None) -> str:
        """Return a short string describing decay state of workout events."""
        events = self._data.get("workout_events", [])
        if not events:
            return "  No workout feedback events recorded yet."

        half_life = (
            GOAL_DECAY_DAYS.get(user.goal_type, DECAY_HALF_LIFE_DEFAULT)
            if user else DECAY_HALF_LIFE_DEFAULT
        )
        goal_label = f"goal={user.goal_type}" if user else "default"
        lines = [f"  Feedback decay  (half-life = {half_life}d  [{goal_label}]):"]
        for ev in events:
            days   = _days_since(ev["ts"])
            factor = _decay_factor(days, half_life) if half_life else 1.0
            sign   = "+" if ev["delta"] > 0 else "-"
            lines.append(
                f"    {sign}1  {ev['workout_id']:<20}  "
                f"{days:.1f}d ago  →  weight {factor:.3f}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Summary                                                             #
    # ------------------------------------------------------------------ #

    def summary(self) -> str:
        liked_m    = len(self._data["liked_meals"])
        disliked_m = len(self._data["disliked_meals"])
        liked_w    = len(self._data["liked_workouts"])
        disliked_w = len(self._data["disliked_workouts"])
        n_events   = len(self._data.get("workout_events", []))
        return (
            f"Feedback store ({self.path}):\n"
            f"  Meals    → {liked_m} liked, {disliked_m} disliked\n"
            f"  Workouts → {liked_w} liked, {disliked_w} disliked"
            f"  ({n_events} timestamped events)"
        )
