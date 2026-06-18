"""
routers/meal_plan.py — Meal plan generation endpoints.

POST /meal-plan/generate/{session_id}   → generate full daily meal plan
GET  /meal-plan/slot-targets/{session_id} → get per-slot macro targets
"""

from typing import List
from fastapi import APIRouter, HTTPException

from meal_plan import (
    generate_meal_plan, plan_summary,
    compute_macro_targets, compute_slot_macro_targets,
    MEAL_CALORIE_SPLIT,
)
from filters import recommend_meals, score_meal
from Request_Api import fetch_recipes
from schemas import (
    MealPlanResponse, MealPlanSlot, SlotMacros,
    MacroTargetsResponse, RecipeResponse, MealRecommendRequest,
)
import state

router = APIRouter()


def _r_to_response(r, score=None) -> RecipeResponse:
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

@router.post("/generate/{session_id}", response_model=MealPlanResponse)
def generate_plan(session_id: str, body: MealRecommendRequest):
    """
    Generate a full daily meal plan for the user:
    1. Fetch recipes from Spoonacular
    2. Hard filter + score → top K
    3. Distribute across meal slots (breakfast / lunch / dinner / snacks)
    4. Return structured plan with per-slot macro targets & actual macros
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Fetch & recommend
    try:
        all_recipes = fetch_recipes(user, num_results=body.num_fetch)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spoonacular API error: {e}")

    top = recommend_meals(all_recipes, user, top_k=body.top_k)
    if not top:
        raise HTTPException(
            status_code=422,
            detail="No meals passed the hard filter. Relax diet_type or intolerances.",
        )

    # Generate plan dict  { "breakfast": [RecipeItem, ...], ... }
    plan = generate_meal_plan(top, user)
    slot_targets = compute_slot_macro_targets(user)
    daily_macros = compute_macro_targets(user)

    # Build response slots
    slots: List[MealPlanSlot] = []
    for slot, recipes in plan.items():
        tgt = slot_targets.get(slot, {})
        slots.append(
            MealPlanSlot(
                slot=slot,
                target=SlotMacros(
                    calories=tgt.get("calories", 0),
                    protein_g=tgt.get("protein_g", 0),
                    carbs_g=tgt.get("carbs_g", 0),
                    fat_g=tgt.get("fat_g", 0),
                ),
                recipes=[_r_to_response(r, score_meal(r, user)) for r in recipes],
            )
        )

    return MealPlanResponse(
        goal_type=user.goal_type,
        target_calories=user.target_calories,
        daily_macros=MacroTargetsResponse(
            **daily_macros,
            target_calories=user.target_calories,
            goal_type=user.goal_type,
        ),
        slots=slots,
        summary=plan_summary(plan, user),
    )


@router.get("/slot-targets/{session_id}", response_model=dict)
def get_slot_targets(session_id: str):
    """
    Return per-slot macro targets for the user's current
    meals_per_day and goal_type (no API call needed).
    """
    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return {
        "meals_per_day": user.meals_per_day,
        "goal_type": user.goal_type,
        "target_calories": user.target_calories,
        "slot_targets": compute_slot_macro_targets(user),
    }
