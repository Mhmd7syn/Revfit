"""
plan_type.py — Structured multi-day workout plan builder.

Builds a day-by-day plan from a flat list of WorkoutItem objects,
respecting the user's chosen plan_type (full_body / ppl / upper_lower).

Public API
----------
build_workout_plan(workouts, user) -> WorkoutPlan
    Returns a WorkoutPlan dataclass with a .days dict and helper methods.

print_workout_plan(plan)
    Pretty-prints the plan to stdout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from constants import SPLIT_BODY_MAP, EXERCISES_PER_BODYPART, PLAN_TYPES
from workouts import WorkoutItem


# ================================================================== #
#  WorkoutPlan dataclass                                              #
# ================================================================== #

@dataclass
class WorkoutPlan:
    """
    Holds a structured workout split.

    Attributes
    ----------
    plan_type : str
        One of "full_body", "ppl", "upper_lower".
    days : Dict[str, List[WorkoutItem]]
        Mapping of day-name → list of exercises for that day.
        e.g. {"Push": [...], "Pull": [...], "Legs": [...]}
    """

    plan_type: str
    days: Dict[str, List[WorkoutItem]] = field(default_factory=dict)

    # ---- Convenience helpers ---- #

    @property
    def total_exercises(self) -> int:
        return sum(len(exs) for exs in self.days.values())

    @property
    def day_names(self) -> List[str]:
        return list(self.days.keys())

    def summary(self) -> str:
        """Return a compact one-line summary."""
        counts = ", ".join(
            f"{day}: {len(exs)} exercises"
            for day, exs in self.days.items()
        )
        return f"[{self.plan_type.upper()}] {counts}"


# ================================================================== #
#  Internal helpers                                                   #
# ================================================================== #

def _index_by_body_part(workouts: List[WorkoutItem]) -> Dict[str, List[WorkoutItem]]:
    """Group a flat workout list by body_part."""
    index: Dict[str, List[WorkoutItem]] = {}
    for w in workouts:
        index.setdefault(w.body_part, []).append(w)
    return index


def _pick_exercises(
    body_part_index: Dict[str, List[WorkoutItem]],
    target_parts: List[str],
    n_per_part: int,
) -> List[WorkoutItem]:
    """
    For each body part in target_parts, pick up to n_per_part exercises
    from the index (highest-rated first; random tie-break).
    """
    picked: List[WorkoutItem] = []
    for part in target_parts:
        candidates = body_part_index.get(part, [])
        if not candidates:
            continue
        # Sort: rated exercises first (desc), unrated last
        candidates_sorted = sorted(
            candidates,
            key=lambda w: (w.rating is not None, w.rating or 0),
            reverse=True,
        )
        picked.extend(candidates_sorted[:n_per_part])
    return picked


# ================================================================== #
#  Public builder                                                     #
# ================================================================== #

def build_workout_plan(workouts: List[WorkoutItem], user) -> WorkoutPlan:
    """
    Build a structured WorkoutPlan from a filtered/scored workout list.

    Parameters
    ----------
    workouts : List[WorkoutItem]
        Pre-filtered (and optionally pre-scored) workout candidates.
    user : UserProfile
        Provides user.plan_type.

    Returns
    -------
    WorkoutPlan
        A day-by-day grouped plan.

    Raises
    ------
    ValueError
        If user.plan_type is not one of the valid PLAN_TYPES.
    """
    plan_type = user.plan_type
    if plan_type not in PLAN_TYPES:
        raise ValueError(
            f"Invalid plan_type '{plan_type}'. Must be one of: {PLAN_TYPES}"
        )

    day_map: Dict[str, List[str]] = SPLIT_BODY_MAP[plan_type]
    n_per_part: int = EXERCISES_PER_BODYPART[plan_type]

    body_part_index = _index_by_body_part(workouts)

    days: Dict[str, List[WorkoutItem]] = {}
    for day_name, target_parts in day_map.items():
        days[day_name] = _pick_exercises(body_part_index, target_parts, n_per_part)

    return WorkoutPlan(plan_type=plan_type, days=days)


# ================================================================== #
#  Pretty-printer                                                     #
# ================================================================== #

def print_workout_plan(plan: WorkoutPlan) -> None:
    """Print the full structured workout plan to stdout."""
    width = 60
    border = "═" * width

    plan_labels = {
        "full_body":    "Full Body",
        "ppl":          "Push / Pull / Legs (PPL)",
        "upper_lower":  "Upper / Lower Split",
    }
    label = plan_labels.get(plan.plan_type, plan.plan_type.upper())

    print(f"\n{'═' * width}")
    print(f"  WORKOUT PLAN — {label}")
    print(f"  Total exercises: {plan.total_exercises}")
    print(f"{'═' * width}")

    for day_name, exercises in plan.days.items():
        print(f"\n  ── {day_name.upper()} DAY ──")
        if not exercises:
            print("    (no exercises found for this day)")
            continue
        for i, w in enumerate(exercises, start=1):
            rating_str = f"  ★ {w.rating:.1f}" if w.rating else ""
            print(
                f"    {i:>2}. {w.name}"
                f"\n        [{w.workout_type} | {w.body_part} | {w.equipment} | {w.level}]"
                f"{rating_str}"
            )
    print(f"\n{'═' * width}\n")
