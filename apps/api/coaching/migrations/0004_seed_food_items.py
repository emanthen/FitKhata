"""Seeds the global FoodItem catalog (FR-7.1's "macros per 100g table") with
the Nepali staples the FR names (dal-bhat, roti-tarkari, chana, paneer,
eggs, chicken, sel roti) plus a few more to round out real meal templates.
Macro values are approximate per-100g figures for the raw/cooked form named,
standard reference-table numbers, not lab-measured for any specific gym.
"""

from __future__ import annotations

from django.db import migrations

# (name_en, name_ne, kcal, protein_g, carbs_g, fat_g) per 100g
FOOD_ITEMS: list[tuple[str, str, float, float, float, float]] = [
    ("Rice (bhat)", "भात", 130, 2.7, 28.0, 0.3),
    ("Lentils (dal)", "दाल", 116, 9.0, 20.0, 0.4),
    ("Roti (whole wheat)", "रोटी", 297, 11.0, 48.0, 7.0),
    ("Mixed vegetable curry (tarkari)", "तरकारी", 90, 2.5, 10.0, 4.5),
    ("Chickpeas (chana)", "चना", 164, 8.9, 27.4, 2.6),
    ("Paneer", "पनिर", 265, 18.3, 1.2, 20.8),
    ("Egg (whole, boiled)", "अन्डा", 155, 13.0, 1.1, 11.0),
    ("Chicken breast (cooked)", "कुखुराको मासु", 165, 31.0, 0.0, 3.6),
    ("Sel roti", "सेल रोटी", 350, 5.0, 45.0, 16.0),
    ("Potato (aloo, boiled)", "आलु", 87, 1.9, 20.1, 0.1),
    ("Plain yogurt (dahi)", "दही", 61, 3.5, 4.7, 3.3),
    ("Milk (whole)", "दुध", 61, 3.2, 4.8, 3.3),
]


def seed_food_items(apps, schema_editor):
    FoodItem = apps.get_model("coaching", "FoodItem")
    FoodItem.objects.bulk_create(
        FoodItem(
            name_en=name_en,
            name_ne=name_ne,
            kcal_per_100g=kcal,
            protein_g_per_100g=protein,
            carbs_g_per_100g=carbs,
            fat_g_per_100g=fat,
        )
        for name_en, name_ne, kcal, protein, carbs, fat in FOOD_ITEMS
    )


def remove_food_items(apps, schema_editor):
    FoodItem = apps.get_model("coaching", "FoodItem")
    FoodItem.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coaching", "0003_seed_exercises"),
    ]

    operations = [
        migrations.RunPython(seed_food_items, remove_food_items),
    ]
