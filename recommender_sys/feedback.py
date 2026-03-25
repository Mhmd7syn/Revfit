"""
feedback.py — Persistent meal & workout feedback store.

Feedback is saved to a JSON file (default: feedback_store.json) so that
liked/disliked signals survive across sessions.

Usage
-----
from feedback import FeedbackStore

store = FeedbackStore()                      # loads from disk
store.record_meal(user, "recipe_42", liked=True)
store.load_into_user(user)                   # apply saved feedback to user
store.save()                                 # persist to disk
"""

import json
import os
from typing import Dict

DEFAULT_PATH = "feedback_store.json"


class FeedbackStore:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._data: Dict = self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self) -> Dict:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        # Default schema
        return {
            "liked_meals": [],
            "disliked_meals": [],
            "liked_workouts": [],
            "disliked_workouts": [],
            "workout_preferences": {},
            "workout_type_preferences": {},
        }

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
            # Remove from disliked if previously disliked
            if recipe_id in self._data["disliked_meals"]:
                self._data["disliked_meals"].remove(recipe_id)
        else:
            if recipe_id not in self._data["disliked_meals"]:
                self._data["disliked_meals"].append(recipe_id)
            if recipe_id in self._data["liked_meals"]:
                self._data["liked_meals"].remove(recipe_id)
        self.save()

    # ------------------------------------------------------------------ #
    #  Workout feedback                                                    #
    # ------------------------------------------------------------------ #

    def record_workout(self, workout, liked: bool):
        """Record a workout like/dislike and persist immediately."""
        delta = 1 if liked else -1
        prefs = self._data["workout_preferences"]
        prefs[workout.workout_id] = prefs.get(workout.workout_id, 0) + delta

        type_prefs = self._data["workout_type_preferences"]
        type_prefs[workout.workout_type] = (
            type_prefs.get(workout.workout_type, 0.0) + 0.3 * delta
        )

        if liked:
            if workout.workout_id not in self._data["liked_workouts"]:
                self._data["liked_workouts"].append(workout.workout_id)
        else:
            if workout.workout_id not in self._data["disliked_workouts"]:
                self._data["disliked_workouts"].append(workout.workout_id)

        self.save()

    # ------------------------------------------------------------------ #
    #  Apply saved feedback to a UserProfile                              #
    # ------------------------------------------------------------------ #

    def load_into_user(self, user):
        """
        Populate user.liked_meals, disliked_meals, workout_preferences, etc.
        from the persisted store.  Call this right after creating a UserProfile.
        """
        from collections import defaultdict

        user.liked_meals    = list(self._data.get("liked_meals", []))
        user.disliked_meals = list(self._data.get("disliked_meals", []))
        user.liked_workouts    = list(self._data.get("liked_workouts", []))
        user.disliked_workouts = list(self._data.get("disliked_workouts", []))
        user.workout_preferences = dict(self._data.get("workout_preferences", {}))
        raw_type_prefs = self._data.get("workout_type_preferences", {})
        user.workout_type_preferences = defaultdict(float, raw_type_prefs)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def summary(self) -> str:
        liked_m   = len(self._data["liked_meals"])
        disliked_m = len(self._data["disliked_meals"])
        liked_w   = len(self._data["liked_workouts"])
        disliked_w = len(self._data["disliked_workouts"])
        return (
            f"Feedback store ({self.path}):\n"
            f"  Meals    → {liked_m} liked, {disliked_m} disliked\n"
            f"  Workouts → {liked_w} liked, {disliked_w} disliked"
        )
