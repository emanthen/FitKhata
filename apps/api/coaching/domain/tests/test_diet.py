from __future__ import annotations

from coaching.domain.diet import FoodItemMacros, MealItem, meal_plan_totals


def test_sums_known_items_by_grams_over_100():
    food_items = {
        "rice": FoodItemMacros(
            kcal_per_100g=130, protein_g_per_100g=2.7, carbs_g_per_100g=28, fat_g_per_100g=0.3
        ),
        "dal": FoodItemMacros(
            kcal_per_100g=116, protein_g_per_100g=9.0, carbs_g_per_100g=20, fat_g_per_100g=0.4
        ),
    }
    meals = [[MealItem(food_item_id="rice", grams=200), MealItem(food_item_id="dal", grams=150)]]

    totals = meal_plan_totals(meals, food_items)

    assert totals.kcal == 130 * 2 + 116 * 1.5
    assert totals.protein_g == 2.7 * 2 + 9.0 * 1.5


def test_unknown_food_item_contributes_zero_instead_of_raising():
    meals = [[MealItem(food_item_id="deleted-item", grams=100)]]
    totals = meal_plan_totals(meals, food_items={})
    assert totals.kcal == 0.0
    assert totals.protein_g == 0.0


def test_sums_across_multiple_meals():
    food_items = {
        "egg": FoodItemMacros(
            kcal_per_100g=155, protein_g_per_100g=13, carbs_g_per_100g=1.1, fat_g_per_100g=11
        )
    }
    meals = [
        [MealItem(food_item_id="egg", grams=100)],
        [MealItem(food_item_id="egg", grams=50)],
    ]
    totals = meal_plan_totals(meals, food_items)
    assert totals.kcal == 155 * 1.5
