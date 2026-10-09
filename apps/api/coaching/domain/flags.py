"""Deterministic coaching flags (FR-7.2) — run BEFORE any LLM call, pure
Python over plain dataclasses, no Django/ORM imports (rule 9). services.py
builds these dataclasses from WorkoutLog/BodyMeasurement querysets; this
layer never sees a queryset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Exercise.MuscleGroup values this implementation counts as "leg day" —
# everything else (chest/back/shoulders/biceps/triceps/core/cardio) doesn't.
LOWER_BODY_MUSCLE_GROUPS = frozenset({"legs", "glutes"})


@dataclass(frozen=True)
class WorkoutLogEntry:
    logged_on: date
    muscle_groups: frozenset[str]


@dataclass(frozen=True)
class WeightEntry:
    measured_on: date
    weight_kg: float


@dataclass(frozen=True)
class ProteinDay:
    day: date
    protein_g: float


def missed_leg_day(logs: list[WorkoutLogEntry], as_of: date, window_days: int = 7) -> bool:
    cutoff = as_of - timedelta(days=window_days)
    return not any(
        log.logged_on >= cutoff and log.muscle_groups & LOWER_BODY_MUSCLE_GROUPS for log in logs
    )


def weight_stall(
    measurements: list[WeightEntry],
    as_of: date,
    window_days: int = 21,
    threshold_kg: float = 0.3,
) -> bool:
    cutoff = as_of - timedelta(days=window_days)
    window = sorted(
        (m for m in measurements if m.measured_on >= cutoff), key=lambda m: m.measured_on
    )
    if len(window) < 2:
        return False  # not enough data in the window to call it a stall either way
    # Round to the same 2dp precision BodyMeasurement.weight_kg is actually
    # stored at — without this, e.g. 70.3 - 70.0 is 0.29999999999999716 in
    # float, not exactly 0.3, making an "exactly at the threshold" boundary
    # behave inconsistently depending on which two values happen to subtract
    # cleanly.
    delta = round(window[-1].weight_kg - window[0].weight_kg, 2)
    return abs(delta) < threshold_kg


def low_protein(
    days: list[ProteinDay], target_g: float, min_pct: float = 80.0, min_days: int = 3
) -> bool:
    if target_g <= 0:
        return False
    low_days = sum(1 for d in days if (d.protein_g / target_g) * 100 < min_pct)
    return low_days >= min_days


def low_attendance(
    visits_in_period: int, expected_visits: int, threshold_pct: float = 50.0
) -> bool:
    if expected_visits <= 0:
        return False
    return (visits_in_period / expected_visits) * 100 < threshold_pct
