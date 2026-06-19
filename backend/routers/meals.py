"""
routers/meals.py — Meal / recipe endpoints (Content-Based Filtering).

POST /meals/fetch/{session_id}        → fetch recipes from Spoonacular + filter
POST /meals/recommend/{session_id}    → fetch + filter + score → top K
GET  /meals/recipe/{recipe_id}        → fetch a single recipe by Spoonacular ID

Recommendation Architecture
---------------------------
Uses Content-Based Filtering (Experiment 3) as the production scoring engine:
  hard_filter_meals → score_meal → sort → top-K

Scoring signals:
  - Cuisine match:       +2.0 (if recipe.cuisine == user.preferred_cuisine)
  - Protein focus match: +1.5 (if protein_g falls in user's target range)
  - Feedback memory:     +2.0 (liked) / -3.0 (disliked)
  - Calorie proximity:   +0.0 to +1.0 (linear decay from target)
  - Rating bonus:        +0.2 × rating

All user constraints (diet type, allergies, calorie ceiling, cooking time)
are read from the active session profile via state.get_user(session_id).
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query
import requests as http_requests

from filters import recommend_meals, hard_filter_meals, score_meal
from Request_Api import fetch_recipes, fetch_recipe_by_id
from schemas import RecipeResponse
import state

router = APIRouter()


def _r_to_response(r, score: float = None) -> RecipeResponse:
    return RecipeResponse(
        recipe_id=r.recipe_id,
        title=r.title,
        cuisine=r.cuisine,
        diet_labels=r.diet_labels,
        intolerances=r.intolerances,
        calories=r.calories,
        protein_g=r.protein_g,
        carbs_g=r.carbs_g,
        fat_g=r.fat_g,
        prep_time_min=r.prep_time_min,
        rating=r.rating,
        image_url=r.image_url,
        source_url=r.source_url,
        score=round(score, 4) if score is not None else None,
    )


def _handle_spoonacular_error(e: Exception):
    """
    Convert Spoonacular API errors into appropriate HTTP responses.
    Specifically handles rate-limit (402/429) errors with a clear message.
    """
    if isinstance(e, http_requests.exceptions.HTTPError):
        status = e.response.status_code if e.response is not None else 502
        if status in (402, 429):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Spoonacular API rate limit exceeded. "
                    "The free tier allows 150 requests/day. "
                    "Please try again later or upgrade your Spoonacular plan."
                ),
            )
    raise HTTPException(status_code=502, detail=f"Spoonacular API error: {e}")


# ------------------------------------------------------------------ #

@router.post("/fetch/{session_id}", response_model=dict)
def fetch_and_filter(
    session_id: str,
    num_fetch: int = Query(20, ge=5, le=100),
):
    """
    Fetch recipes from Spoonacular for the user's preferences,
    apply hard filters, and return all valid meals (no scoring).

    All user constraints are read from the session profile.
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        all_recipes = fetch_recipes(user, num_results=num_fetch)
    except Exception as e:
        _handle_spoonacular_error(e)

    valid = hard_filter_meals(all_recipes, user)
    return {
        "fetched": len(all_recipes),
        "after_filter": len(valid),
        "meals": [_r_to_response(r) for r in valid],
    }


@router.post("/recommend/{session_id}", response_model=List[RecipeResponse])
def recommend_meals_endpoint(
    session_id: str,
    top_k: int = Query(5, ge=1, le=50),
    num_fetch: int = Query(20, ge=5, le=100),
):
    """
    Fetch → hard filter → score → return top-K meals personalised for the user.

    Uses the Content-Based Filtering pipeline (Experiment 3):
      1. Hard filters — remove recipes violating diet constraints,
         allergens, calorie ceiling (120% of per-meal budget), prep time.
      2. Soft scoring — cuisine match, protein focus, feedback memory,
         calorie proximity, rating bonus.
      3. Sort and return top-K.

    Feedback history (liked/disliked) is automatically applied via the
    session profile. No request body is required.
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        all_recipes = fetch_recipes(user, num_results=num_fetch)
    except Exception as e:
        _handle_spoonacular_error(e)

    top = recommend_meals(all_recipes, user, top_k=top_k)
    return [_r_to_response(r, score_meal(r, user)) for r in top]


@router.get("/recipe/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: str):
    """Fetch a single recipe from Spoonacular by its numeric ID."""
    try:
        r = fetch_recipe_by_id(recipe_id)
    except Exception as e:
        _handle_spoonacular_error(e)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Recipe '{recipe_id}' not found")
    return _r_to_response(r)

