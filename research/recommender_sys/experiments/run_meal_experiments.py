"""
run_meal_experiments.py — Execute and compare meal recommendation experiments.

Runs Meal Experiments 1-3 (Random, Most Popular, Content-Based) using
recipes fetched from the Spoonacular API, then prints a comparison table.

NOTE: This script calls the Spoonacular API (150 free requests/day).
      If you've already fetched recipes via TestScript.py, the API
      call count applies to your daily quota.

Usage
-----
    cd a:\\Collage\\Gp Project\\Revfit\\recommender_sys
    python experiments/run_meal_experiments.py
"""

import sys
import os
import io

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from user_profile import UserProfile
from feedback import FeedbackStore
from Request_Api import fetch_recipes

from experiments.meal_exp_base import (
    generate_synthetic_meal_interactions,
    compute_meal_popularity,
    meal_precision_at_k,
    meal_recall_at_k,
    meal_diversity,
    meal_coverage,
    meal_novelty,
    format_meal_results_table,
)
from experiments.meal_exp1_random import RandomMealRecommender
from experiments.meal_exp2_most_popular import MostPopularMealRecommender
from experiments.meal_exp3_content_based import ContentBasedMealRecommender


def main():
    # -- Create test user ------------------------------------------------
    user = UserProfile(
        age=25, height_cm=175, weight_kg=75, sex="male",
        goal_type="muscle_gain",
        activity_level="moderate",
        fitness_level="beginner",
        available_equipment=["Body Only"],
        country="Egypt",
        diet_type="omnivore",
        protein_focus="high",
        meals_per_day=3,
        cooking_time_preference="flexible",
        plan_type="upper_lower",
    )

    # Load persisted feedback
    store_path = os.path.join(os.path.dirname(__file__), "..", "feedback_store.json")
    if os.path.exists(store_path):
        store = FeedbackStore(store_path)
        store.load_into_user(user)

    # -- Fetch recipes from Spoonacular API ------------------------------
    print("=" * 60)
    print("  FETCHING RECIPES FROM SPOONACULAR API ...")
    print("=" * 60)

    try:
        all_recipes = fetch_recipes(user, num_results=20)
        print(f"  Fetched {len(all_recipes)} recipes from API.\n")
    except Exception as e:
        print(f"  ERROR: API call failed: {e}")
        print("  Check your API key in Request_Api.py (line 12).")
        print("  Exiting.")
        return

    if not all_recipes:
        print("  No recipes returned. Try changing diet_type or country.")
        return

    # -- Generate synthetic interactions for evaluation ------------------
    interactions = generate_synthetic_meal_interactions(all_recipes, n_users=50, interactions_per_user=8)
    pop, total_int = compute_meal_popularity(interactions)
    held_out_ids = set(interactions.get(0, []))

    # -- Run experiments -------------------------------------------------
    experiments = [
        RandomMealRecommender(),
        MostPopularMealRecommender(),
        ContentBasedMealRecommender(),
    ]

    TOP_K = 5
    all_results = []
    all_recs_for_coverage = []

    print("=" * 60)
    print("  MEAL EXPERIMENT RESULTS")
    print("=" * 60)

    for exp in experiments:
        print(f"\n  -- {exp.name} --")
        print(f"  {exp.description}")

        recs = exp.recommend(
            user, all_recipes, top_k=TOP_K,
            popularity=pop, seed=42,
        )
        all_recs_for_coverage.append(recs)

        for i, r in enumerate(recs, start=1):
            print(f"    {i}. {r.title}  [{r.cuisine}]  {r.calories:.0f} kcal  P:{r.protein_g:.0f}g")

        p = meal_precision_at_k(recs, held_out_ids)
        rc = meal_recall_at_k(recs, held_out_ids)
        d = meal_diversity(recs)
        n = meal_novelty(recs, pop, total_int)

        all_results.append({
            "name": exp.name,
            "precision": p,
            "recall": rc,
            "diversity": d,
            "coverage": 0.0,
            "novelty": n,
            "best_for": exp.description.split(".")[0],
        })

    for i, recs in enumerate(all_recs_for_coverage):
        cov = meal_coverage([recs], len(all_recipes))
        all_results[i]["coverage"] = cov

    # -- Comparison table ------------------------------------------------
    print("\n\n" + "=" * 60)
    print("  MEAL COMPARISON TABLE")
    print("=" * 60 + "\n")
    print(format_meal_results_table(all_results))

    print("\n" + "=" * 60)
    print("  KEY OBSERVATIONS")
    print("=" * 60)
    print("""
  1. Random meals pass hard filters (safe) but ignore nutrition goals.
  2. Most Popular works as cold-start fallback but lacks personalisation.
  3. Content-Based matches cuisine, macros, and feedback — best for our app.
  4. All experiments use the Spoonacular API as the data source.

  For the full analysis, see experiments/EXPERIMENTS.md
""")


if __name__ == "__main__":
    main()
