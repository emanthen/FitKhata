"""Seeds the global Exercise catalog (FR-7.1: "seed 300 exercises"). These
are NOT 300 hand-curated lifts — they're ~134 real canonical exercises
across 9 muscle groups (each listed with the equipment it's actually
performed on) mechanically extended with grip/stance variants (Seated,
Standing, Single-Arm) on their dumbbell/cable/band versions until the count
reaches exactly 300, deduplicated. name_ne is a colloquial transliteration
(the way these lifts are actually said in a Nepali gym), not a literal
dictionary translation.
"""

from __future__ import annotations

from django.db import migrations

# (name_en, name_ne, muscle_group, [equipment...])
BASE_EXERCISES: list[tuple[str, str, str, list[str]]] = [
    # Chest
    ("Bench Press", "बेन्च प्रेस", "chest", ["barbell", "dumbbell", "machine", "cable"]),
    ("Incline Press", "इन्क्लाइन प्रेस", "chest", ["barbell", "dumbbell", "machine", "cable"]),
    ("Decline Press", "डिक्लाइन प्रेस", "chest", ["barbell", "dumbbell", "machine"]),
    ("Chest Fly", "चेस्ट फ्लाई", "chest", ["dumbbell", "cable", "machine", "band"]),
    ("Push-Up", "पुश-अप", "chest", ["bodyweight"]),
    ("Chest Dip", "चेस्ट डिप", "chest", ["bodyweight", "machine"]),
    ("Pec Deck", "पेक डेक", "chest", ["machine"]),
    # Back
    ("Deadlift", "डेडलिफ्ट", "back", ["barbell", "dumbbell", "kettlebell"]),
    ("Barbell Row", "बारबेल रो", "back", ["barbell"]),
    ("Dumbbell Row", "डम्बेल रो", "back", ["dumbbell"]),
    ("Lat Pulldown", "ल्याट पुलडाउन", "back", ["cable", "machine", "band"]),
    ("Pull-Up", "पुल-अप", "back", ["bodyweight"]),
    ("Seated Cable Row", "सिटेड केबल रो", "back", ["cable", "machine"]),
    ("T-Bar Row", "टी-बार रो", "back", ["barbell", "machine"]),
    ("Face Pull", "फेस पुल", "back", ["cable", "band"]),
    # Shoulders
    ("Overhead Press", "ओभरहेड प्रेस", "shoulders", ["barbell", "dumbbell", "machine", "kettlebell"]),
    ("Lateral Raise", "लेटरल रेज", "shoulders", ["dumbbell", "cable", "band", "machine"]),
    ("Front Raise", "फ्रन्ट रेज", "shoulders", ["dumbbell", "cable", "band"]),
    ("Rear Delt Fly", "रियर डेल्ट फ्लाई", "shoulders", ["dumbbell", "cable", "band", "machine"]),
    ("Arnold Press", "अर्नोल्ड प्रेस", "shoulders", ["dumbbell"]),
    ("Upright Row", "अपराइट रो", "shoulders", ["barbell", "dumbbell", "cable"]),
    # Biceps
    ("Bicep Curl", "बाइसेप कर्ल", "biceps", ["barbell", "dumbbell", "cable", "band", "machine"]),
    ("Hammer Curl", "ह्यामर कर्ल", "biceps", ["dumbbell", "cable", "band"]),
    ("Preacher Curl", "प्रिचर कर्ल", "biceps", ["barbell", "dumbbell", "machine"]),
    ("Concentration Curl", "कन्सन्ट्रेशन कर्ल", "biceps", ["dumbbell"]),
    # Triceps
    ("Tricep Pushdown", "ट्राइसेप पुशडाउन", "triceps", ["cable", "band", "machine"]),
    ("Tricep Extension", "ट्राइसेप एक्सटेन्शन", "triceps", ["dumbbell", "cable", "band"]),
    ("Skull Crusher", "स्कल क्रशर", "triceps", ["barbell", "dumbbell"]),
    ("Close-Grip Bench Press", "क्लोज-ग्रिप बेन्च प्रेस", "triceps", ["barbell"]),
    ("Tricep Dip", "ट्राइसेप डिप", "triceps", ["bodyweight", "machine"]),
    # Legs
    ("Squat", "स्क्वाट", "legs", ["barbell", "dumbbell", "bodyweight", "kettlebell", "machine"]),
    ("Leg Press", "लेग प्रेस", "legs", ["machine"]),
    ("Lunge", "लन्ज", "legs", ["dumbbell", "barbell", "bodyweight", "kettlebell"]),
    ("Leg Extension", "लेग एक्सटेन्शन", "legs", ["machine"]),
    ("Leg Curl", "लेग कर्ल", "legs", ["machine", "band"]),
    ("Romanian Deadlift", "रोमानियन डेडलिफ्ट", "legs", ["barbell", "dumbbell", "kettlebell"]),
    ("Calf Raise", "काल्फ रेज", "legs", ["machine", "dumbbell", "bodyweight", "barbell"]),
    ("Bulgarian Split Squat", "बल्गेरियन स्प्लिट स्क्वाट", "legs", ["dumbbell", "bodyweight", "kettlebell"]),
    ("Step-Up", "स्टेप-अप", "legs", ["dumbbell", "bodyweight", "kettlebell"]),
    # Glutes
    ("Hip Thrust", "हिप थ्रस्ट", "glutes", ["barbell", "machine", "bodyweight", "band"]),
    ("Glute Bridge", "ग्लुट ब्रिज", "glutes", ["bodyweight", "barbell", "band"]),
    ("Cable Kickback", "केबल किकब्याक", "glutes", ["cable", "band"]),
    ("Sumo Deadlift", "सुमो डेडलिफ्ट", "glutes", ["barbell", "kettlebell"]),
    # Core
    ("Plank", "प्ल्यांक", "core", ["bodyweight"]),
    ("Crunch", "क्रन्च", "core", ["bodyweight", "cable", "machine"]),
    ("Russian Twist", "रसियन ट्विस्ट", "core", ["bodyweight", "dumbbell", "kettlebell"]),
    ("Leg Raise", "लेग रेज", "core", ["bodyweight", "cable"]),
    ("Cable Woodchop", "केबल वुडचप", "core", ["cable", "band"]),
    ("Ab Wheel Rollout", "एब व्हील रोलआउट", "core", ["bodyweight"]),
    # Cardio
    ("Treadmill Run", "ट्रेडमिल रन", "cardio", ["machine"]),
    ("Stationary Bike", "स्टेशनरी बाइक", "cardio", ["machine"]),
    ("Rowing Machine", "रोइंग मेसिन", "cardio", ["machine"]),
    ("Jump Rope", "जम्प रोप", "cardio", ["bodyweight"]),
    ("Burpees", "बर्पीज", "cardio", ["bodyweight"]),
    ("Mountain Climbers", "माउन्टेन क्लाइम्बर्स", "cardio", ["bodyweight"]),
    ("Battle Ropes", "ब्याटल रोप्स", "cardio", ["bodyweight"]),
    ("Stair Climber", "स्टेयर क्लाइम्बर", "cardio", ["machine"]),
    ("Elliptical", "इलिप्टिकल", "cardio", ["machine"]),
]

# Grip/stance variants, applied only to dumbbell/cable/band versions of a
# base lift (the equipment that actually supports these variations) until
# the catalog reaches 300 rows.
PREFIXES_EN = ["Seated", "Standing", "Single-Arm", "Wide-Grip", "Close-Grip", "Alternating"]
PREFIXES_NE = ["सिटेड", "स्ट्यान्डिङ", "सिङ्गल-आर्म", "वाइड-ग्रिप", "क्लोज-ग्रिप", "अल्टरनेटिङ"]
VARIANT_EQUIPMENT = {"dumbbell", "cable", "band"}

TARGET_COUNT = 300


def seed_exercises(apps, schema_editor):
    Exercise = apps.get_model("coaching", "Exercise")

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(name_en: str, name_ne: str, muscle_group: str, equipment: str) -> None:
        key = (name_en, equipment)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "name_en": name_en,
                "name_ne": name_ne,
                "muscle_group": muscle_group,
                "equipment": equipment,
                "media_url": f"https://cdn.fitkhata.com/exercises/{equipment}/{name_en.lower().replace(' ', '-').replace('/', '-')}.mp4",
            }
        )

    for name_en, name_ne, muscle_group, equipment_list in BASE_EXERCISES:
        for equipment in equipment_list:
            add(name_en, name_ne, muscle_group, equipment)

    # Pad with grip/stance variants, cycling through eligible base lifts,
    # until exactly TARGET_COUNT rows exist.
    variant_sources = [
        (name_en, name_ne, muscle_group, equipment)
        for name_en, name_ne, muscle_group, equipment_list in BASE_EXERCISES
        for equipment in equipment_list
        if equipment in VARIANT_EQUIPMENT
    ]
    prefix_index = 0
    source_index = 0
    while len(rows) < TARGET_COUNT and variant_sources:
        name_en, name_ne, muscle_group, equipment = variant_sources[source_index % len(variant_sources)]
        prefix_en = PREFIXES_EN[prefix_index % len(PREFIXES_EN)]
        prefix_ne = PREFIXES_NE[prefix_index % len(PREFIXES_NE)]
        add(f"{prefix_en} {name_en}", f"{prefix_ne} {name_ne}", muscle_group, equipment)
        source_index += 1
        if source_index % len(variant_sources) == 0:
            prefix_index += 1

    Exercise.objects.bulk_create(Exercise(**row) for row in rows[:TARGET_COUNT])


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("coaching", "Exercise")
    Exercise.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coaching", "0002_rls"),
    ]

    operations = [
        migrations.RunPython(seed_exercises, remove_exercises),
    ]
