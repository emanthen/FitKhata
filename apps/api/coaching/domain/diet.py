"""Meal macro totals (FR-7.1's "macros per 100g table"). Pure Python, no
Django imports — rule 9. services.py calls this only to flag a mismatch
against DietPlan.kcal_target/protein_g in the builder UI; it never
recomputes or overwrites those fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MealItem:
    food_item_id: str
    grams: float


@dataclass(frozen=True)
class FoodItemMacros:
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float


@dataclass(frozen=True)
class MacroTotals:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


def meal_plan_totals(
    meals: list[list[MealItem]], food_items: dict[str, FoodItemMacros]
) -> MacroTotals:
    """grams/100 * each macro, summed across every item in every meal.
    An item whose food_item_id isn't in `food_items` contributes 0 rather
    than raising — a plan referencing a since-deleted FoodItem degrades,
    it doesn't 500.
    """
    kcal = protein = carbs = fat = 0.0
    for meal in meals:
        for item in meal:
            macros = food_items.get(item.food_item_id)
            if macros is None:
                continue
            factor = item.grams / 100.0
            kcal += macros.kcal_per_100g * factor
            protein += macros.protein_g_per_100g * factor
            carbs += macros.carbs_g_per_100g * factor
            fat += macros.fat_g_per_100g * factor
    return MacroTotals(kcal=kcal, protein_g=protein, carbs_g=carbs, fat_g=fat)
