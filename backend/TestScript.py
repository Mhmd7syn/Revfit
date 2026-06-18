"""
TestScript.py — Full test for the Revfit recommender system.

Uses the Spoonacular API to fetch real recipes.
Make sure your API key is set in Request_Api.py before running.

Tests:
  1. User profile (auto-computed calories & macros)
  2. Workout recommender (loaded from megaGymDataset.csv, before & after feedback)
  3. Diet recommender via Spoonacular API
  4. Meal feedback persistence (FeedbackStore)
"""

import os
from filters import recommend_workout_plan, recommend_meals, recommend_by_muscle
from plan_type import print_workout_plan
from workouts import WorkoutItem, load_workouts_csv
from user_profile import UserProfile
from meal_plan import generate_meal_plan, plan_summary, compute_macro_targets
from feedback import FeedbackStore
from Request_Api import fetch_recipes


# ═══════════════════════════════════════════════════════════════════ #
#  Load workouts from CSV                                             #
# ═══════════════════════════════════════════════════════════════════ #

_csv_path = os.path.join(os.path.dirname(__file__), "megaGymDataset.csv")
workouts = load_workouts_csv(_csv_path)
print(f"  Loaded {len(workouts)} workouts from megaGymDataset.csv")


# ═══════════════════════════════════════════════════════════════════ #
#  User                                                               #
# ═══════════════════════════════════════════════════════════════════ #

user = UserProfile(
    age=25, height_cm=175, weight_kg=75, sex="male",
    goal_type="muscle_gain",
    activity_level="moderate",
    fitness_level="beginner",
    available_equipment=["Body Only"],
    country="Egypt",               # → preferred_cuisine = "middle eastern"
    diet_type="omnivore",
    protein_focus="high",
    meals_per_day=3,
    cooking_time_preference="flexible",
    plan_type="upper_lower",               # full_body / ppl / upper_lower
)

# Load any persisted feedback from previous runs
store = FeedbackStore()
store.load_into_user(user)


# ═══════════════════════════════════════════════════════════════════ #
#  Section 1 — User profile summary                                   #
# ═══════════════════════════════════════════════════════════════════ #

print("=" * 52)
print("  USER PROFILE")
print("=" * 52)
print(f"  Goal:              {user.goal_type}")
print(f"  Target calories:   {user.target_calories} kcal/day")
print(f"  Preferred cuisine: {user.preferred_cuisine}")

macros = compute_macro_targets(user)
print(f"  Daily macro targets:")
print(f"    Protein: {macros['protein_g']}g")
print(f"    Carbs:   {macros['carbs_g']}g")
print(f"    Fat:     {macros['fat_g']}g")
print(f"\n{store.summary()}")
print(store.decay_summary(user))
print()


# ═══════════════════════════════════════════════════════════════════ #
#  Section 2 — Structured workout plan (driven by user.plan_type)     #
# ═══════════════════════════════════════════════════════════════════ #

# plan_type is read directly from the UserProfile — no override needed.
# Change user.plan_type above to switch between full_body / ppl / upper_lower.

print("=" * 52)
print(f"  WORKOUT PLAN  (plan_type = '{user.plan_type}')")
print("=" * 52)

workout_plan = recommend_workout_plan(workouts, user)
print_workout_plan(workout_plan)
print(f"  {workout_plan.summary()}")

# ── Feedback loop (uses the first two exercises from the plan) ───── #
all_plan_exercises = [
    w for exercises in workout_plan.days.values() for w in exercises
]
if len(all_plan_exercises) >= 2:
    disliked_w = all_plan_exercises[0]
    liked_w    = all_plan_exercises[1]
    print(f"\n  [Feedback] Disliking '{disliked_w.name}' x3, Liking '{liked_w.name}'")
    for _ in range(3):
        user.add_workout_feedback(disliked_w, liked=False)
    user.add_workout_feedback(liked_w, liked=True)
    store.record_workout(disliked_w, liked=False)
    store.record_workout(liked_w, liked=True)

    print(f"\n  WORKOUT PLAN after feedback (plan_type = '{user.plan_type}')")
    print("=" * 52)
    updated_plan = recommend_workout_plan(workouts, user)
    print_workout_plan(updated_plan)
else:
    print("\n  [Feedback] Not enough exercises in plan to test feedback.")


# ═══════════════════════════════════════════════════════════════════ #
#  Section 2c — Muscle-specific query                                 #
# ═══════════════════════════════════════════════════════════════════ #

# Ask for specific muscles — just change the list below.
# Available: Chest, Lats, Quadriceps, Hamstrings, Glutes,
#            Shoulders, Triceps, Biceps, Abdominals, Lower Back,
#            Middle Back, Traps, Calves, Forearms, Abductors, Adductors

MUSCLE_QUERIES = ["Chest", "Lats", "Quadriceps"]

for muscle in MUSCLE_QUERIES:
    print("=" * 52)
    print(f"  MUSCLE QUERY — {muscle} (top 5)")
    print("=" * 52)
    try:
        muscle_recs = recommend_by_muscle(workouts, user, muscle=muscle, top_k=5)
        if not muscle_recs:
            print(f"  ⚠️  No {muscle} exercises found for your equipment/level.")
        else:
            for i, w in enumerate(muscle_recs, start=1):
                rating_str = f"  ★ {w.rating:.1f}" if w.rating else ""
                print(
                    f"  {i}. {w.name}"
                    f"  [{w.workout_type} | {w.equipment} | {w.level}]"
                    f"{rating_str}"
                )
    except ValueError as e:
        print(f"  ❌ {e}")
    print()


# ═══════════════════════════════════════════════════════════════════ #
#  Section 3 — Diet recommender via Spoonacular API                   #
# ═══════════════════════════════════════════════════════════════════ #

print("\n" + "=" * 52)
print("  FETCHING RECIPES FROM SPOONACULAR API ...")
print("=" * 52)

try:
    all_recipes = fetch_recipes(user, num_results=20)
    print(f"  Fetched {len(all_recipes)} recipes from API.")
except Exception as e:
    print(f"  ❌ API error: {e}")
    print("  Check your API key in Request_Api.py (line 12).")
    raise SystemExit(1)

print("\n  MEAL RECOMMENDATIONS (before feedback)")
print("=" * 52)
top_meals = recommend_meals(all_recipes, user, top_k=5)

if not top_meals:
    print("  ⚠️  No meals passed the hard filter. Try relaxing diet_type or intolerances.")
else:
    for r in top_meals:
        print(f"  • {r.title} [{r.cuisine}]  {r.calories:.0f} kcal")

    # Display full daily plan with macro breakdown
    plan = generate_meal_plan(top_meals, user)
    print("\n" + plan_summary(plan, user))


# ═══════════════════════════════════════════════════════════════════ #
#  Section 4 — Meal feedback persistence                              #
# ═══════════════════════════════════════════════════════════════════ #

if top_meals:
    print("=" * 52)
    print("  MEAL FEEDBACK")
    print("=" * 52)

    disliked = top_meals[0]
    liked    = top_meals[2] if len(top_meals) > 2 else None

    print(f"  [Disliking] {disliked.title} ({disliked.recipe_id})")
    user.add_meal_feedback(disliked.recipe_id, liked=False)
    store.record_meal(disliked.recipe_id, liked=False)

    if liked:
        print(f"  [Liking]    {liked.title} ({liked.recipe_id})")
        user.add_meal_feedback(liked.recipe_id, liked=True)
        store.record_meal(liked.recipe_id, liked=True)

    print("\n  MEAL RECOMMENDATIONS (after feedback)")
    print("=" * 52)
    top_meals_after = recommend_meals(all_recipes, user, top_k=5)
    for r in top_meals_after:
        print(f"  • {r.title} [{r.cuisine}]  {r.calories:.0f} kcal")

    plan_after = generate_meal_plan(top_meals_after, user)
    print("\n" + plan_summary(plan_after, user))

print(f"\nFeedback saved → feedback_store.json")
print(store.summary())