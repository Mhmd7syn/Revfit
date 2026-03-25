import requests
from typing import List, Optional
from recipe_Item import RecipeItem

# ------------------------------------------------------------------ #
#  Spoonacular API wrapper                                             #
#  Docs: https://spoonacular.com/food-api/docs                        #
#  Free tier: 150 requests/day                                        #
#  Set your key here or pass it as an argument                        #
# ------------------------------------------------------------------ #

API_KEY = "90d29dbebd3e4773acfee698e1f39a37"   # ← replace with your key
BASE_URL = "https://api.spoonacular.com"


def fetch_recipes(
    user,
    num_results: int = 20,
    api_key: str = API_KEY,
) -> List[RecipeItem]:
    """
    Fetch recipes from Spoonacular that match the user's preferences.

    Parameters
    ----------
    user        : UserProfile
    num_results : How many recipes to request from the API
    api_key     : Spoonacular API key

    Returns
    -------
    List[RecipeItem]
    """
    params = {
        "apiKey": api_key,
        "number": num_results,
        "addRecipeNutrition": True,
        "fillIngredients": False,
    }

    # Diet type (Spoonacular uses: vegetarian, vegan, paleo, ketogenic, …)
    if user.diet_type and user.diet_type != "omnivore":
        params["diet"] = user.diet_type

    # Intolerances (comma-separated)
    if user.intolerances:
        params["intolerances"] = ",".join(user.intolerances)

    # Preferred cuisine derived from country
    if user.preferred_cuisine:
        params["cuisine"] = user.preferred_cuisine

    # Max calories per serving
    if user.target_calories:
        # Rough per-meal budget (assume 3 meals, take main meal = 35%)
        meals = max(user.meals_per_day, 1)
        per_meal_cal = int(user.target_calories / meals)
        params["maxCalories"] = per_meal_cal

    response = requests.get(f"{BASE_URL}/recipes/complexSearch", params=params)
    response.raise_for_status()

    data = response.json()
    recipes = []

    for item in data.get("results", []):
        nutrition = item.get("nutrition", {})
        nutrients = {n["name"]: n["amount"] for n in nutrition.get("nutrients", [])}

        recipe = RecipeItem(
            recipe_id=str(item["id"]),
            title=item.get("title", ""),
            cuisine=_pick_cuisine(item.get("cuisines", []), user.preferred_cuisine),
            diet_labels=item.get("diets", []),
            intolerances=[],           # Spoonacular doesn't return intolerances on items
            calories=nutrients.get("Calories", 0.0),
            protein_g=nutrients.get("Protein", 0.0),
            carbs_g=nutrients.get("Carbohydrates", 0.0),
            fat_g=nutrients.get("Fat", 0.0),
            prep_time_min=item.get("readyInMinutes", 0),
            image_url=item.get("image"),
            source_url=item.get("sourceUrl"),
        )
        recipes.append(recipe)

    return recipes


def fetch_recipe_by_id(recipe_id: str, api_key: str = API_KEY) -> Optional[RecipeItem]:
    """Fetch a single recipe by its Spoonacular ID."""
    params = {"apiKey": api_key, "includeNutrition": True}
    response = requests.get(f"{BASE_URL}/recipes/{recipe_id}/information", params=params)
    response.raise_for_status()

    item = response.json()
    nutrition = item.get("nutrition", {})
    nutrients = {n["name"]: n["amount"] for n in nutrition.get("nutrients", [])}

    return RecipeItem(
        recipe_id=str(item["id"]),
        title=item.get("title", ""),
        cuisine=_pick_cuisine(item.get("cuisines", []), None),
        diet_labels=item.get("diets", []),
        intolerances=[],
        calories=nutrients.get("Calories", 0.0),
        protein_g=nutrients.get("Protein", 0.0),
        carbs_g=nutrients.get("Carbohydrates", 0.0),
        fat_g=nutrients.get("Fat", 0.0),
        prep_time_min=item.get("readyInMinutes", 0),
        image_url=item.get("image"),
        source_url=item.get("sourceUrl"),
    )


# ---- Helpers ---- #

def _pick_cuisine(cuisines: List[str], preferred: Optional[str]) -> str:
    """Return the best cuisine label for a recipe."""
    if not cuisines:
        return preferred or "unknown"
    if preferred:
        for c in cuisines:
            if c.lower() == preferred.lower():
                return c.lower()
    return cuisines[0].lower()