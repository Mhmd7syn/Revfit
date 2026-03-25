from typing import List, Dict
from recipe_Item import RecipeItem


# Calorie distribution across daily meal slots
MEAL_CALORIE_SPLIT = {
    1: {"breakfast": 1.0},
    2: {"breakfast": 0.45, "dinner": 0.55},
    3: {"breakfast": 0.30, "lunch": 0.40, "dinner": 0.30},
    4: {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.30, "snack": 0.10},
    5: {"breakfast": 0.20, "lunch": 0.30, "dinner": 0.30, "snack1": 0.10, "snack2": 0.10},
}

# Macro ratio targets per goal  (protein%, carb%, fat%)
GOAL_MACRO_RATIO = {
    "fat_loss":    (0.40, 0.30, 0.30),
    "muscle_gain": (0.35, 0.45, 0.20),
    "maintenance": (0.30, 0.40, 0.30),
    "endurance":   (0.25, 0.55, 0.20),
}


# ------------------------------------------------------------------ #
#  Macro target helpers                                               #
# ------------------------------------------------------------------ #

def compute_macro_targets(user) -> Dict[str, float]:
    """
    Return daily protein / carb / fat targets in grams based on
    the user's calorie goal and goal_type macro split.

    Protein & carbs: 4 kcal/g   Fat: 9 kcal/g
    """
    cal = user.target_calories or 2000
    p_pct, c_pct, f_pct = GOAL_MACRO_RATIO.get(user.goal_type, (0.30, 0.40, 0.30))
    return {
        "protein_g": round(cal * p_pct / 4, 1),
        "carbs_g":   round(cal * c_pct / 4, 1),
        "fat_g":     round(cal * f_pct / 9, 1),
    }


def compute_slot_macro_targets(user) -> Dict[str, Dict[str, float]]:
    """
    Break daily macro targets down per meal slot
    using the same calorie split ratios.
    """
    daily = compute_macro_targets(user)
    meals = max(1, min(user.meals_per_day, 5))
    split = MEAL_CALORIE_SPLIT.get(meals, MEAL_CALORIE_SPLIT[3])

    slot_targets = {}
    for slot, fraction in split.items():
        slot_targets[slot] = {
            "calories":  round((user.target_calories or 2000) * fraction),
            "protein_g": round(daily["protein_g"] * fraction, 1),
            "carbs_g":   round(daily["carbs_g"]   * fraction, 1),
            "fat_g":     round(daily["fat_g"]      * fraction, 1),
        }
    return slot_targets


# ------------------------------------------------------------------ #
#  Meal plan generation                                               #
# ------------------------------------------------------------------ #

def generate_meal_plan(recipes: List[RecipeItem], user) -> Dict[str, List[RecipeItem]]:
    """
    Distribute recommended recipes into daily meal slots.

    Returns
    -------
    {"breakfast": [RecipeItem, ...], "lunch": [...], ...}
    """
    meals = max(1, min(user.meals_per_day, 5))
    split = MEAL_CALORIE_SPLIT.get(meals, MEAL_CALORIE_SPLIT[3])
    plan: Dict[str, List[RecipeItem]] = {slot: [] for slot in split}

    slots = list(split.keys())
    for i, slot in enumerate(slots):
        if i < len(recipes):
            plan[slot].append(recipes[i])

    return plan


# ------------------------------------------------------------------ #
#  Display helpers                                                    #
# ------------------------------------------------------------------ #

def plan_summary(plan: Dict[str, List[RecipeItem]], user) -> str:
    """
    Human-readable daily meal plan with:
    - Per-slot macro targets (goal-adjusted P/C/F)
    - Actual macro values of the assigned recipe
    - Deviation indicators
    """
    slot_targets = compute_slot_macro_targets(user)
    daily_targets = compute_macro_targets(user)

    lines = [
        "╔══════════════════════════════════════════════╗",
        "║           📅  Daily Meal Plan                ║",
        "╚══════════════════════════════════════════════╝",
        f"  Goal: {user.goal_type.replace('_',' ').title()}"
        f"  |  Target: {user.target_calories} kcal/day",
        f"  Daily macros → "
        f"P: {daily_targets['protein_g']}g  "
        f"C: {daily_targets['carbs_g']}g  "
        f"F: {daily_targets['fat_g']}g",
        "",
    ]

    total_cal = total_p = total_c = total_f = 0.0

    for slot, items in plan.items():
        tgt = slot_targets.get(slot, {})
        tgt_cal = tgt.get("calories", 0)
        tgt_p   = tgt.get("protein_g", 0)
        tgt_c   = tgt.get("carbs_g", 0)
        tgt_f   = tgt.get("fat_g", 0)

        lines.append(f"  🍽  {slot.upper()}")
        lines.append(
            f"      Target → {tgt_cal} kcal  |  "
            f"P:{tgt_p}g  C:{tgt_c}g  F:{tgt_f}g"
        )

        if not items:
            lines.append("      (no recipe assigned)")
        else:
            for r in items:
                # Deviation arrows
                def arrow(actual, target):
                    if target == 0:
                        return "~"
                    pct = (actual - target) / target * 100
                    if pct > 15:   return "↑"
                    if pct < -15:  return "↓"
                    return "✓"

                lines.append(
                    f"      • {r.title}"
                )
                lines.append(
                    f"        {r.calories:.0f} kcal {arrow(r.calories, tgt_cal)}  |  "
                    f"P:{r.protein_g:.1f}g {arrow(r.protein_g, tgt_p)}  "
                    f"C:{r.carbs_g:.1f}g {arrow(r.carbs_g, tgt_c)}  "
                    f"F:{r.fat_g:.1f}g {arrow(r.fat_g, tgt_f)}"
                )
                total_cal += r.calories
                total_p   += r.protein_g
                total_c   += r.carbs_g
                total_f   += r.fat_g

        lines.append("")

    lines += [
        "──────────────────────────────────────────────",
        f"  TOTAL  →  {total_cal:.0f} kcal  |  "
        f"P:{total_p:.1f}g  C:{total_c:.1f}g  F:{total_f:.1f}g",
        f"  TARGET →  {user.target_calories} kcal  |  "
        f"P:{daily_targets['protein_g']}g  "
        f"C:{daily_targets['carbs_g']}g  "
        f"F:{daily_targets['fat_g']}g",
        "",
        "  Legend:  ✓ on target   ↑ over target   ↓ under target  (±15%)",
        "══════════════════════════════════════════════",
    ]

    return "\n".join(lines)
