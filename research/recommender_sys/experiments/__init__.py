"""
experiments — Separate recommender experiment modules for seminar evaluation.

Each experiment implements a different recommendation strategy and can be
evaluated against the same dataset and user profiles for comparison.

WORKOUT EXPERIMENTS (megaGymDataset):
    exp1_random            — Random Recommender (worst-case baseline)
    exp2_most_popular      — Most Popular Recommender (naive baseline)
    exp3_content_based     — Content-Based Filtering (our reference system)
    exp4_collaborative_filtering — User-Based Collaborative Filtering (stub)
    exp5_hybrid                  — Hybrid Content + Popularity (stub)
    exp6_weighted_content        — Feature-Weighted Content-Based (stub)

MEAL EXPERIMENTS (Spoonacular API):
    meal_exp1_random            — Random Meal Recommender
    meal_exp2_most_popular      — Most Popular Meal Recommender
    meal_exp3_content_based     — Content-Based Meal Recommender (our reference)
    meal_exp4_collaborative_filtering — User-Based CF for Meals (stub)
    meal_exp5_hybrid                  — Hybrid Meal Recommender (stub)
    meal_exp6_weighted_content        — Feature-Weighted Meal Recommender (stub)
"""
