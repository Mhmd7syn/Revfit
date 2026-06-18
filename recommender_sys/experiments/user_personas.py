"""
user_personas.py — 10 predefined user personas for offline evaluation.

Each persona is a dataclass that bundles:
  - user                    : UserProfile
  - name                    : str  (human-readable label)
  - preferred_workout_types : Set[str]
      Workout types this persona considers "relevant".
      Aligned with GOAL_TYPE_WEIGHTS so the content-based scorer
      naturally recommends items that fall into these types.
  - preferred_diet_labels   : Set[str]
      Diet labels a meal must carry to be considered relevant.
      Empty = accept any diet.
  - max_calories_per_meal   : float
      Upper calorie bound for a meal to be considered relevant.

RELEVANCE SETS (built at runtime in run_persona_experiments.py)
───────────────────────────────────────────────────────────────
Workout:
  hard_filter_workouts(workouts, persona.user)
  → keep items whose workout_type ∈ preferred_workout_types
  (aligned with GOAL_TYPE_WEIGHTS — exactly what content-based
   scoring rewards most highly)

Meal:
  hard_filter_meals(recipes, persona.user)      ← passes diet/allergy/cal
  → additionally keep only items whose calories ≤ max_calories_per_meal
    AND (diet_labels ∩ preferred_diet_labels ≠ ∅  OR  no diet preference)
  (mirrors what score_meal() actually rewards: macros + diet fit)
"""

from dataclasses import dataclass, field
from typing import Set

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from user_profile import UserProfile


# ================================================================== #
#  Persona dataclass                                                  #
# ================================================================== #

@dataclass
class Persona:
    name: str
    user: UserProfile

    # Workout-side relevance (aligned with GOAL_TYPE_WEIGHTS)
    preferred_workout_types: Set[str] = field(default_factory=set)

    # Meal-side relevance
    preferred_diet_labels: Set[str] = field(default_factory=set)   # lower-case
    max_calories_per_meal: float = 9999.0


# ================================================================== #
#  Goal → high-weight workout types                                   #
# (mirrors GOAL_TYPE_WEIGHTS keys with weight ≥ 2.0)                 #
# ================================================================== #

GOAL_RELEVANT_TYPES = {
    "muscle_gain": {"Strength", "Powerlifting", "Olympic Weightlifting"},
    "fat_loss":    {"Cardio", "Plyometrics", "Strength"},
    "maintenance": {"Strength", "Cardio", "Stretching"},
    "endurance":   {"Cardio", "Plyometrics", "Strength"},
}


# ================================================================== #
#  The 10 Personas                                                    #
# ================================================================== #

def build_personas():
    """Return the list of 10 pre-defined Persona objects."""

    return [

        # ── 1  Ahmed — muscle gain, gym barbell ──────────────────────
        Persona(
            name="Ahmed",
            user=UserProfile(
                age=24, height_cm=178, weight_kg=80, sex="male",
                goal_type="muscle_gain", activity_level="active",
                fitness_level="intermediate",
                available_equipment=["Barbell", "Dumbbell", "Body Only"],
                country="Egypt", diet_type="omnivore",
                protein_focus="high", meals_per_day=3,
                cooking_time_preference="flexible", plan_type="ppl",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["muscle_gain"],
            preferred_diet_labels=set(),
            max_calories_per_meal=900.0,
        ),

        # ── 2  Sara — fat loss, bodyweight only ──────────────────────
        Persona(
            name="Sara",
            user=UserProfile(
                age=22, height_cm=163, weight_kg=65, sex="female",
                goal_type="fat_loss", activity_level="light",
                fitness_level="beginner",
                available_equipment=["Body Only"],
                country="Egypt", diet_type="omnivore",
                protein_focus="medium", meals_per_day=3,
                cooking_time_preference="quick", plan_type="full_body",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["fat_loss"],
            preferred_diet_labels=set(),
            max_calories_per_meal=550.0,
        ),

        # ── 3  Youssef — endurance, vegan, bands ─────────────────────
        Persona(
            name="Youssef",
            user=UserProfile(
                age=28, height_cm=182, weight_kg=73, sex="male",
                goal_type="endurance", activity_level="very_active",
                fitness_level="intermediate",
                available_equipment=["Body Only", "Bands"],
                country=None, diet_type="vegan",
                protein_focus="medium", meals_per_day=4,
                cooking_time_preference="flexible", plan_type="full_body",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["endurance"],
            preferred_diet_labels={"vegan"},
            max_calories_per_meal=750.0,
        ),

        # ── 4  Layla — muscle gain, dumbbell + cable ─────────────────
        Persona(
            name="Layla",
            user=UserProfile(
                age=26, height_cm=166, weight_kg=58, sex="female",
                goal_type="muscle_gain", activity_level="moderate",
                fitness_level="intermediate",
                available_equipment=["Dumbbell", "Cable", "Body Only"],
                country=None, diet_type="omnivore",
                protein_focus="high", meals_per_day=3,
                cooking_time_preference="flexible", plan_type="upper_lower",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["muscle_gain"],
            preferred_diet_labels=set(),
            max_calories_per_meal=750.0,
        ),

        # ── 5  Omar — maintenance, full machine gym ───────────────────
        Persona(
            name="Omar",
            user=UserProfile(
                age=35, height_cm=176, weight_kg=82, sex="male",
                goal_type="maintenance", activity_level="moderate",
                fitness_level="beginner",
                available_equipment=["Machine", "Dumbbell", "Body Only"],
                country=None, diet_type="omnivore",
                protein_focus="medium", meals_per_day=3,
                cooking_time_preference="flexible", plan_type="full_body",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["maintenance"],
            preferred_diet_labels=set(),
            max_calories_per_meal=800.0,
        ),

        # ── 6  Nour — fat loss, kettlebells, vegetarian ───────────────
        Persona(
            name="Nour",
            user=UserProfile(
                age=30, height_cm=168, weight_kg=62, sex="female",
                goal_type="fat_loss", activity_level="active",
                fitness_level="intermediate",
                available_equipment=["Kettlebells", "Body Only", "Bands"],
                country=None, diet_type="vegetarian",
                protein_focus="medium", meals_per_day=3,
                cooking_time_preference="quick", plan_type="full_body",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["fat_loss"],
            preferred_diet_labels={"vegetarian"},
            max_calories_per_meal=550.0,
        ),

        # ── 7  Khalid — muscle gain, full powerlifting gym ────────────
        Persona(
            name="Khalid",
            user=UserProfile(
                age=27, height_cm=185, weight_kg=100, sex="male",
                goal_type="muscle_gain", activity_level="very_active",
                fitness_level="intermediate",
                available_equipment=["Barbell", "Machine", "Dumbbell", "Body Only", "Cable"],
                country=None, diet_type="omnivore",
                protein_focus="high", meals_per_day=4,
                cooking_time_preference="flexible", plan_type="ppl",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["muscle_gain"],
            preferred_diet_labels=set(),
            max_calories_per_meal=1200.0,
        ),

        # ── 8  Hana — maintenance, bodyweight, vegan ─────────────────
        Persona(
            name="Hana",
            user=UserProfile(
                age=20, height_cm=160, weight_kg=55, sex="female",
                goal_type="maintenance", activity_level="sedentary",
                fitness_level="beginner",
                available_equipment=["Body Only"],
                country=None, diet_type="vegan",
                protein_focus="low", meals_per_day=3,
                cooking_time_preference="quick", plan_type="full_body",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["maintenance"],
            preferred_diet_labels={"vegan"},
            max_calories_per_meal=550.0,
        ),

        # ── 9  Ziad — endurance, bands + exercise ball ────────────────
        Persona(
            name="Ziad",
            user=UserProfile(
                age=32, height_cm=179, weight_kg=76, sex="male",
                goal_type="endurance", activity_level="active",
                fitness_level="intermediate",
                available_equipment=["Body Only", "Bands", "Exercise Ball"],
                country=None, diet_type="omnivore",
                protein_focus="medium", meals_per_day=3,
                cooking_time_preference="flexible", plan_type="full_body",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["endurance"],
            preferred_diet_labels=set(),
            max_calories_per_meal=700.0,
        ),

        # ── 10 Dina — fat loss, dumbbell + cable, ketogenic ──────────
        Persona(
            name="Dina",
            user=UserProfile(
                age=29, height_cm=165, weight_kg=68, sex="female",
                goal_type="fat_loss", activity_level="moderate",
                fitness_level="intermediate",
                available_equipment=["Dumbbell", "Cable", "Body Only"],
                country=None, diet_type="ketogenic",
                protein_focus="high", meals_per_day=2,
                cooking_time_preference="flexible", plan_type="upper_lower",
            ),
            preferred_workout_types=GOAL_RELEVANT_TYPES["fat_loss"],
            preferred_diet_labels={"ketogenic"},
            max_calories_per_meal=750.0,
        ),
    ]
