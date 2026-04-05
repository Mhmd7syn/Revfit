"""
run_experiments.py — Execute and compare implemented experiments.

Runs Experiments 1-3 (Random, Most Popular, Content-Based) against the
megaGymDataset and a simulated user, then prints a comparison table.

Usage
-----
    cd a:\\Collage\\Gp Project\\Revfit\\recommender_sys
    python experiments/run_experiments.py
"""

import sys
import os
import io

# Fix Windows console encoding for special characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure parent directory is on the path so we can import project modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from user_profile import UserProfile
from workouts import load_workouts_csv
from feedback import FeedbackStore

from experiments.experiment_base import (
    generate_synthetic_interactions,
    compute_popularity,
    precision_at_k,
    recall_at_k,
    diversity,
    coverage,
    novelty,
    format_results_table,
)
from experiments.exp1_random import RandomRecommender
from experiments.exp2_most_popular import MostPopularRecommender
from experiments.exp3_content_based import ContentBasedRecommender


def main():
    # ── Load workout catalogue ──────────────────────────────────────
    csv_path = os.path.join(os.path.dirname(__file__), "..", "megaGymDataset.csv")
    workouts = load_workouts_csv(csv_path)
    print(f"  Loaded {len(workouts)} workouts from megaGymDataset.csv\n")

    # ── Create test user ────────────────────────────────────────────
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

    # Load persisted feedback (if any)
    store_path = os.path.join(os.path.dirname(__file__), "..", "feedback_store.json")
    if os.path.exists(store_path):
        store = FeedbackStore(store_path)
        store.load_into_user(user)

    # ── Generate synthetic interaction data for evaluation ──────────
    interactions = generate_synthetic_interactions(workouts, n_users=50, interactions_per_user=15)
    pop, total_int = compute_popularity(interactions)

    # Use user 0's interactions as the "target user" held-out set
    held_out_ids = set(interactions.get(0, []))

    # ── Instantiate experiments ─────────────────────────────────────
    experiments = [
        RandomRecommender(),
        MostPopularRecommender(),
        ContentBasedRecommender(),
    ]

    TOP_K = 10
    all_results = []
    all_recs_for_coverage = []

    print("=" * 60)
    print("  EXPERIMENT RESULTS")
    print("=" * 60)

    for exp in experiments:
        print(f"\n  ── {exp.name} ──")
        print(f"  {exp.description}")

        # Get recommendations
        if hasattr(exp, 'recommend'):
            recs = exp.recommend(
                user, workouts, top_k=TOP_K,
                popularity=pop, seed=42,
            )
        else:
            recs = []

        all_recs_for_coverage.append(recs)

        # Print top recommendations
        for i, w in enumerate(recs[:5], start=1):
            rating_str = f"  * {w.rating:.1f}" if w.rating else ""
            print(f"    {i}. {w.name}  [{w.workout_type} | {w.body_part} | {w.level}]{rating_str}")

        if len(recs) > 5:
            print(f"    ... and {len(recs) - 5} more")

        # Compute metrics
        p = precision_at_k(recs, held_out_ids)
        r = recall_at_k(recs, held_out_ids)
        d = diversity(recs)
        n = novelty(recs, pop, total_int)

        all_results.append({
            "name": exp.name,
            "precision": p,
            "recall": r,
            "diversity": d,
            "coverage": 0.0,  # filled below
            "novelty": n,
            "best_for": exp.description.split(".")[0],
        })

    # Compute coverage across all experiments
    for i, recs in enumerate(all_recs_for_coverage):
        cov = coverage([recs], len(workouts))
        all_results[i]["coverage"] = cov

    # ── Print comparison table ──────────────────────────────────────
    print("\n\n" + "=" * 60)
    print("  COMPARISON TABLE")
    print("=" * 60 + "\n")
    print(format_results_table(all_results))

    # ── Discussion points ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  KEY OBSERVATIONS")
    print("=" * 60)
    print("""
  1. Random has lowest precision but highest diversity — pure exploration.
  2. Most Popular improves precision but everyone gets the same list.
  3. Content-Based provides personalised recommendations tuned to the
     user's goal, equipment, and feedback history.
  4. Content-Based is the best fit for our sparse-data fitness app.

  For the full analysis, see experiments/EXPERIMENTS.md
""")


if __name__ == "__main__":
    main()
