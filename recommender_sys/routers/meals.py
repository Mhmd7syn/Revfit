"""
routers/meals.py — Meal / recipe endpoints.

POST /meals/fetch/{session_id}        → fetch recipes from Spoonacular + filter
POST /meals/recommend/{session_id}    → fetch + filter + score → top K
GET  /meals/recipe/{recipe_id}        → fetch a single recipe by Spoonacular ID
"""

from typing import List
from fastapi import APIRouter, HTTPException

from filters import recommend_meals, hard_filter_meals, score_meal
from Request_Api import fetch_recipes, fetch_recipe_by_id
from schemas import RecipeResponse, MealRecommendRequest
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


# ------------------------------------------------------------------ #

@router.post("/fetch/{session_id}", response_model=dict)
def fetch_and_filter(session_id: str, body: MealRecommendRequest):
    """
    Fetch recipes from Spoonacular for the user's preferences,
    apply hard filters, and return all valid meals (no scoring).
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        all_recipes = fetch_recipes(user, num_results=body.num_fetch)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spoonacular API error: {e}")

    valid = hard_filter_meals(all_recipes, user)
    return {
        "fetched": len(all_recipes),
        "after_filter": len(valid),
        "meals": [_r_to_response(r) for r in valid],
    }


@router.post("/recommend/{session_id}", response_model=List[RecipeResponse])
def recommend_meals_endpoint(session_id: str, body: MealRecommendRequest):
    """
    Fetch → hard filter → score → return top-K meals personalised for the user.
    Feedback history (liked/disliked) is automatically applied.
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        all_recipes = fetch_recipes(user, num_results=body.num_fetch)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spoonacular API error: {e}")

    top = recommend_meals(all_recipes, user, top_k=body.top_k)
    return [_r_to_response(r, score_meal(r, user)) for r in top]


@router.get("/recipe/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: str):
    """Fetch a single recipe from Spoonacular by its numeric ID."""
    try:
        r = fetch_recipe_by_id(recipe_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spoonacular API error: {e}")
    if r is None:
        raise HTTPException(status_code=404, detail=f"Recipe '{recipe_id}' not found")
    return _r_to_response(r)
