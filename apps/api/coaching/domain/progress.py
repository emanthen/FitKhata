"""Progress-metric formulas (FR-7.2). Pure Python, no Django imports — rule 9.

No docs/SRS.md exists in this repo — same situation retention/domain/churn.py
was in — so these are this implementation's own formulas, not a verified
match against a spec. The hard, tested contract is: every function clamps to
[0, 100] and handles a zero/degenerate denominator without raising.
"""

from __future__ import annotations


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, value))


def goal_progress_pct(
    starting_weight_kg: float, current_weight_kg: float, target_weight_kg: float
) -> float:
    """100 * actual_change / required_change. required_change == 0 means the
    goal needed no change at all, so it's trivially met -> 100. Loss and
    gain need no separate branches: numerator and denominator flip sign
    together, so movement in the wrong direction or overshoot both clamp
    naturally (to 0 and 100 respectively) rather than needing an if/else.
    """
    required_change = target_weight_kg - starting_weight_kg
    if required_change == 0:
        return 100.0
    actual_change = current_weight_kg - starting_weight_kg
    return clamp((actual_change / required_change) * 100)


def attendance_pct(visits_in_period: int, expected_visits: int) -> float:
    if expected_visits <= 0:
        return 0.0
    return clamp((visits_in_period / expected_visits) * 100)


def adherence_pct(workout_days_logged: int, planned_days_in_period: int) -> float:
    if planned_days_in_period <= 0:
        return 0.0
    return clamp((workout_days_logged / planned_days_in_period) * 100)


def macro_pct(protein_logged_g: float, protein_target_g: float) -> float:
    if protein_target_g <= 0:
        return 0.0
    return clamp((protein_logged_g / protein_target_g) * 100)
