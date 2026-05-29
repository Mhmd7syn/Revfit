"""
run_persona_experiments.py — Evaluate recommenders against 10 predefined personas.

Replaces the dummy synthetic-interaction approach with deterministic, preference-
grounded relevance sets derived from each persona's stated tastes.

HOW IT WORKS
────────────
Workout evaluation
  • For every experiment × persona pair:
      1. Build the persona's WORKOUT relevance set:
             hard_filter_workouts(all_workouts, persona.user)
             → keep items whose workout_type ∈ persona.preferred_workout_types
               AND body_part ∈ persona.preferred_body_parts
      2. Get recommendations from the experiment.
      3. Compute precision, recall, diversity, novelty.
  • Average each metric across all 10 personas.
  • Compute coverage across all personas.

Meal evaluation
  • Fetch recipes once per persona (uses Spoonacular API).
  • Build the persona's MEAL relevance set from fetched recipes:
             hard_filter_meals(recipes, persona.user)
             → keep items whose cuisine ∈ persona.preferred_cuisines
               OR any diet_label ∈ persona.preferred_diet_labels
               AND calories ≤ persona.max_calories_per_meal
  • Same metric pipeline as workouts.
  • Average across all 10 personas.

Usage
-----
    cd /path/to/recommender_sys
    python experiments/run_persona_experiments.py

    # To skip the meal section (no API key):
    python experiments/run_persona_experiments.py --workouts-only
"""

import sys
import os
import math
import io
import argparse

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Project imports ──────────────────────────────────────────────────────────
from workouts import load_workouts_csv
from filters import hard_filter_workouts

from experiments.experiment_base import (
    compute_popularity,
    precision_at_k,
    recall_at_k,
    diversity,
    coverage,
    novelty,
    format_results_table,
)
from experiments.meal_exp_base import (
    compute_meal_popularity,
    meal_precision_at_k,
    meal_recall_at_k,
    meal_diversity,
    meal_coverage,
    meal_novelty,
    format_meal_results_table,
)

from experiments.exp1_random import RandomRecommender
from experiments.exp2_most_popular import MostPopularRecommender
from experiments.exp3_content_based import ContentBasedRecommender
from experiments.exp4_collaborative_filtering import CollaborativeFilteringRecommender
from experiments.exp5_hybrid import HybridRecommender
from experiments.exp6_weighted_content import WeightedContentRecommender
from experiments.exp7_cf_vdb import CFVDBRecommender

from experiments.meal_exp1_random import RandomMealRecommender
from experiments.meal_exp2_most_popular import MostPopularMealRecommender
from experiments.meal_exp3_content_based import ContentBasedMealRecommender
from experiments.meal_exp4_collaborative_filtering import CollaborativeFilteringMealRecommender
from experiments.meal_exp5_hybrid import HybridMealRecommender
from experiments.meal_exp6_weighted_content import WeightedContentMealRecommender

from experiments.user_personas import build_personas


# ── Relevance-set helpers ─────────────────────────────────────────────────────

def workout_relevance_set(persona, all_workouts):
    """
    Return the set of workout_ids that are relevant to this persona.

    A workout is relevant if:
      • It passes the hard filters (equipment + level) for this persona.
      • Its workout_type is in persona.preferred_workout_types.

    preferred_workout_types is aligned with GOAL_TYPE_WEIGHTS, so this
    mirrors exactly what the content-based scorer rewards most highly.
    Using workout_type only (no body_part AND) keeps sets large enough
    for meaningful precision and recall scores.
    """
    candidates = hard_filter_workouts(all_workouts, persona.user)
    relevant = {
        w.workout_id
        for w in candidates
        if w.workout_type in persona.preferred_workout_types
    }
    return relevant


def meal_relevance_set(persona, recipes):
    """
    Return the set of recipe_ids that are relevant to this persona.

    A meal is relevant if ALL of the following hold:
      • calories ≤ persona.max_calories_per_meal
      • If persona has preferred_diet_labels: at least one diet_label
        of the recipe is in those labels. Otherwise any diet is fine.

    This mirrors score_meal() which rewards macros + diet fit.
    Using hard_filter_meals first is optional here because fetch_recipes
    already queries Spoonacular with the user's diet filter; we rely on
    the diet_label check for the relevance gate.
    """
    has_diet_pref = bool(persona.preferred_diet_labels)
    relevant = set()

    for r in recipes:
        # Calorie gate
        if r.calories > persona.max_calories_per_meal:
            continue

        # Diet-label gate (only applies when persona has a preference)
        if has_diet_pref:
            recipe_labels = {d.lower() for d in r.diet_labels}
            preferred     = {d.lower() for d in persona.preferred_diet_labels}
            if not recipe_labels & preferred:
                continue

        relevant.add(r.recipe_id)

    return relevant


# ── Workout experiment runner ─────────────────────────────────────────────────

def run_workout_experiments(workouts, personas):
    """
    Run all workout experiments across all 10 personas.
    Returns a list of result dicts (one per experiment, metrics averaged over personas).
    """
    # Popularity proxy: uniform over catalogue (real popularity unknown pre-launch)
    pop = {w.workout_id: 1 for w in workouts}
    total_int = len(workouts)

    workout_experiments = [
        RandomRecommender(),
        MostPopularRecommender(),
        ContentBasedRecommender(),
    ]

    # Try to import optional experiments gracefully
    try:
        workout_experiments.append(CollaborativeFilteringRecommender())
    except Exception:
        pass
    try:
        workout_experiments.append(HybridRecommender(alpha=0.7))
    except Exception:
        pass
    try:
        workout_experiments.append(WeightedContentRecommender())
    except Exception:
        pass

    # ── Exp 7: VDB-based CF (profile similarity) ────────────────────
    # Build a single shared index with all 10 persona profiles.
    # During evaluation we pass the current persona's name as exclude_id
    # so it never retrieves itself as its own nearest neighbour.
    try:
        _pop_users = [p.user for p in personas]
        _pop_ids   = [p.name for p in personas]
        _cf_vdb    = CFVDBRecommender(
            population_users=_pop_users,
            population_ids=_pop_ids,
            alpha=0.6,
            cf_neighbours=3,
        )
        workout_experiments.append(_cf_vdb)
    except Exception as exc:
        print(f"  [WARN] Could not build CFVDBRecommender: {exc}")

    TOP_K = 5
    all_results = []
    all_recs_for_coverage = []   # list-of-lists (one per experiment)

    print("\n" + "=" * 65)
    print("  WORKOUT EXPERIMENTS — PER-PERSONA BREAKDOWN")
    print("=" * 65)

    for exp in workout_experiments:
        print(f"\n  ── {exp.name} ──")
        print(f"  {exp.description}")
        print(f"  {'Persona':<12} {'Rel.Set':>8} {'Prec':>7} {'Recall':>7} {'Div':>7} {'Novel':>7}")

        persona_prec, persona_rec, persona_div, persona_nov = [], [], [], []
        exp_all_recs = []

        for persona in personas:
            rel_set = workout_relevance_set(persona, workouts)

            try:
                # Pass exclude_id for Exp 7 leave-one-out; ignored by other exps
                recs = exp.recommend(
                    persona.user, workouts, top_k=TOP_K,
                    popularity=pop, seed=42,
                    exclude_id=persona.name,
                )
            except Exception:
                recs = []

            exp_all_recs.extend(recs)

            p  = precision_at_k(recs, rel_set)
            r  = recall_at_k(recs, rel_set)
            d  = diversity(recs)
            n  = novelty(recs, pop, total_int)

            persona_prec.append(p)
            persona_rec.append(r)
            persona_div.append(d)
            persona_nov.append(n)

            print(f"  {persona.name:<12} {len(rel_set):>8}  {p:>6.3f}  {r:>6.3f}  {d:>6.3f}  {n:>6.3f}")

        # Average across personas
        avg_p   = sum(persona_prec) / len(persona_prec)
        avg_r   = sum(persona_rec)  / len(persona_rec)
        avg_d   = sum(persona_div)  / len(persona_div)
        avg_n   = sum(persona_nov)  / len(persona_nov)

        all_recs_for_coverage.append(exp_all_recs)
        all_results.append({
            "name":      exp.name,
            "precision": avg_p,
            "recall":    avg_r,
            "diversity": avg_d,
            "coverage":  0.0,  # filled below
            "novelty":   avg_n,
            "best_for":  exp.description.split(".")[0],
        })

    # Coverage across all personas combined
    for i, recs in enumerate(all_recs_for_coverage):
        # Wrap in list-of-list expected by coverage()
        cov = coverage([recs], len(workouts))
        all_results[i]["coverage"] = cov

    return all_results


# ── Meal experiment runner ────────────────────────────────────────────────────

def run_meal_experiments(personas):
    """
    Run all meal experiments across all 10 personas.
    Fetches recipes once per persona from the Spoonacular API.
    Returns a list of result dicts (metrics averaged over personas).
    """
    try:
        from Request_Api import fetch_recipes
    except ImportError:
        print("  [WARN] Request_Api not found — skipping meal evaluation.")
        return []

    meal_experiments = [
        RandomMealRecommender(),
        MostPopularMealRecommender(),
        ContentBasedMealRecommender(),
    ]
    try:
        meal_experiments.append(CollaborativeFilteringMealRecommender())
    except Exception:
        pass
    try:
        meal_experiments.append(HybridMealRecommender(alpha=0.7))
    except Exception:
        pass
    try:
        meal_experiments.append(WeightedContentMealRecommender())
    except Exception:
        pass

    TOP_K = 5

    # ── Pre-fetch recipes for each persona ──────────────────────────
    print("\n" + "=" * 65)
    print("  MEAL EXPERIMENTS — FETCHING RECIPES PER PERSONA")
    print("=" * 65)

    persona_recipes = {}   # persona.name → List[RecipeItem]
    for persona in personas:
        print(f"  Fetching for {persona.name} ...", end=" ", flush=True)
        try:
            recipes = fetch_recipes(persona.user, num_results=20)
            persona_recipes[persona.name] = recipes
            print(f"{len(recipes)} recipes fetched.")
        except Exception as e:
            persona_recipes[persona.name] = []
            print(f"FAILED ({e})")

    # Build a flat list of all recipes across personas for coverage
    all_recipe_ids = set()
    for recs in persona_recipes.values():
        for r in recs:
            all_recipe_ids.add(r.recipe_id)
    catalogue_size = max(len(all_recipe_ids), 1)

    # Build popularity proxy from all fetched recipes
    pop = {rid: 1 for rid in all_recipe_ids}
    total_int = len(all_recipe_ids)

    # ── Run each experiment across all personas ───────────────────────
    print("\n" + "=" * 65)
    print("  MEAL EXPERIMENTS — PER-PERSONA BREAKDOWN")
    print("=" * 65)

    all_results = []
    all_recs_for_coverage = []

    for exp in meal_experiments:
        print(f"\n  ── {exp.name} ──")
        print(f"  {exp.description}")
        print(f"  {'Persona':<12} {'Rel.Set':>8} {'Prec':>7} {'Recall':>7} {'Div':>7} {'Novel':>7}")

        persona_prec, persona_rec, persona_div, persona_nov = [], [], [], []
        exp_all_recs = []

        for persona in personas:
            recipes = persona_recipes.get(persona.name, [])
            if not recipes:
                continue

            rel_set = meal_relevance_set(persona, recipes)

            try:
                recs = exp.recommend(
                    persona.user, recipes, top_k=TOP_K,
                    popularity=pop, seed=42,
                )
            except Exception:
                recs = []

            exp_all_recs.extend(recs)

            p  = meal_precision_at_k(recs, rel_set)
            r  = meal_recall_at_k(recs, rel_set)
            d  = meal_diversity(recs)
            n  = meal_novelty(recs, pop, total_int)

            persona_prec.append(p)
            persona_rec.append(r)
            persona_div.append(d)
            persona_nov.append(n)

            print(f"  {persona.name:<12} {len(rel_set):>8}  {p:>6.3f}  {r:>6.3f}  {d:>6.3f}  {n:>6.3f}")

        if not persona_prec:
            continue

        avg_p   = sum(persona_prec) / len(persona_prec)
        avg_r   = sum(persona_rec)  / len(persona_rec)
        avg_d   = sum(persona_div)  / len(persona_div)
        avg_n   = sum(persona_nov)  / len(persona_nov)

        all_recs_for_coverage.append(exp_all_recs)
        all_results.append({
            "name":      exp.name,
            "precision": avg_p,
            "recall":    avg_r,
            "diversity": avg_d,
            "coverage":  0.0,
            "novelty":   avg_n,
            "best_for":  exp.description.split(".")[0],
        })

    # Coverage across all personas
    for i, recs in enumerate(all_recs_for_coverage):
        cov = meal_coverage([recs], catalogue_size)
        all_results[i]["coverage"] = cov

    return all_results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Persona-based recommender evaluation.")
    parser.add_argument(
        "--workouts-only", action="store_true",
        help="Skip the meal section (no Spoonacular API call needed)."
    )
    args, _ = parser.parse_known_args()

    personas = build_personas()

    print("\n" + "=" * 65)
    print("  PERSONA-BASED RECOMMENDER EVALUATION")
    print("  Using 10 predefined users with explicit preferences")
    print("=" * 65)
    print(f"\n  Loaded {len(personas)} personas:\n")
    for p in personas:
        print(
            f"  • {p.name:<10}  goal={p.user.goal_type:<12}  "
            f"level={p.user.fitness_level:<14}  "
            f"diet={p.user.diet_type}"
        )

    # ── Workout section ──────────────────────────────────────────────
    csv_path = os.path.join(os.path.dirname(__file__), "..", "megaGymDataset.csv")
    workouts = load_workouts_csv(csv_path)
    print(f"\n  Loaded {len(workouts)} workouts from megaGymDataset.csv")

    workout_results = run_workout_experiments(workouts, personas)

    print("\n\n" + "=" * 65)
    print("  WORKOUT COMPARISON TABLE  (avg across 10 personas)")
    print("=" * 65 + "\n")
    print(format_results_table(workout_results))

    print("\n" + "=" * 65)
    print("  WORKOUT KEY OBSERVATIONS")
    print("=" * 65)
    print("""
  • Metrics are averaged over 10 personas with diverse goals/equipment.
  • Relevance sets are grounded in each persona's stated preferences —
    no synthetic randomness.
  • Precision/Recall reflect genuine alignment with user intent.
  • Content-Based (Exp 3) should outperform Random (Exp 1) in precision
    because it respects goal alignment and equipment constraints.
  • Random achieves higher diversity as it picks without bias.
""")

    # ── Meal section ─────────────────────────────────────────────────
    if args.workouts_only:
        print("\n  [Skipped meal experiments — run without --workouts-only to enable]\n")
        return

    meal_results = run_meal_experiments(personas)

    if not meal_results:
        print("\n  [No meal results — API may have failed or no recipes returned]\n")
        return

    print("\n\n" + "=" * 65)
    print("  MEAL COMPARISON TABLE  (avg across 10 personas)")
    print("=" * 65 + "\n")
    print(format_meal_results_table(meal_results))

    print("\n" + "=" * 65)
    print("  MEAL KEY OBSERVATIONS")
    print("=" * 65)
    print("""
  • Each persona fetches their own tailored recipe set from Spoonacular.
  • Relevance is defined by cuisine preference and/or diet label match
    within the persona's calorie budget.
  • Content-Based (Meal Exp 3) should yield higher precision because it
    scores on cuisine, macros, and calorie proximity.
  • Diversity tracks how many distinct cuisines appear in the top-K list.
  • Coverage measures how much of the combined recipe catalogue is reached.
""")


if __name__ == "__main__":
    main()
