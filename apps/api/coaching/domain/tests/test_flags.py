from __future__ import annotations

from datetime import date, timedelta

from coaching.domain.flags import (
    ProteinDay,
    WeightEntry,
    WorkoutLogEntry,
    low_attendance,
    low_protein,
    missed_leg_day,
    weight_stall,
)

AS_OF = date(2026, 10, 8)


# --- missed_leg_day ----------------------------------------------------------


def test_leg_day_exactly_at_the_cutoff_counts():
    logs = [WorkoutLogEntry(logged_on=AS_OF - timedelta(days=7), muscle_groups=frozenset({"legs"}))]
    assert missed_leg_day(logs, AS_OF) is False


def test_leg_day_one_day_past_the_cutoff_does_not_count():
    logs = [WorkoutLogEntry(logged_on=AS_OF - timedelta(days=8), muscle_groups=frozenset({"legs"}))]
    assert missed_leg_day(logs, AS_OF) is True


def test_a_chest_only_day_does_not_count_as_leg_day():
    logs = [WorkoutLogEntry(logged_on=AS_OF, muscle_groups=frozenset({"chest"}))]
    assert missed_leg_day(logs, AS_OF) is True


def test_glutes_counts_as_lower_body():
    logs = [WorkoutLogEntry(logged_on=AS_OF, muscle_groups=frozenset({"glutes"}))]
    assert missed_leg_day(logs, AS_OF) is False


def test_missed_leg_day_is_order_independent():
    logs_a = [
        WorkoutLogEntry(logged_on=AS_OF, muscle_groups=frozenset({"chest"})),
        WorkoutLogEntry(logged_on=AS_OF, muscle_groups=frozenset({"legs"})),
    ]
    logs_b = list(reversed(logs_a))
    assert missed_leg_day(logs_a, AS_OF) == missed_leg_day(logs_b, AS_OF) is False


# --- weight_stall --------------------------------------------------------------


def test_fewer_than_two_measurements_in_window_is_not_a_stall():
    measurements = [WeightEntry(measured_on=AS_OF, weight_kg=70.0)]
    assert weight_stall(measurements, AS_OF) is False


def test_delta_of_exactly_threshold_is_not_a_stall():
    measurements = [
        WeightEntry(measured_on=AS_OF - timedelta(days=20), weight_kg=70.0),
        WeightEntry(measured_on=AS_OF, weight_kg=70.3),
    ]
    assert weight_stall(measurements, AS_OF, threshold_kg=0.3) is False


def test_delta_just_under_threshold_is_a_stall():
    measurements = [
        WeightEntry(measured_on=AS_OF - timedelta(days=20), weight_kg=70.0),
        WeightEntry(measured_on=AS_OF, weight_kg=70.29),
    ]
    assert weight_stall(measurements, AS_OF, threshold_kg=0.3) is True


def test_a_measurement_outside_the_window_is_excluded():
    measurements = [
        WeightEntry(measured_on=AS_OF - timedelta(days=30), weight_kg=80.0),  # outside 21d window
        WeightEntry(measured_on=AS_OF - timedelta(days=20), weight_kg=70.0),
        WeightEntry(measured_on=AS_OF, weight_kg=70.1),
    ]
    # If the 30-day-old 80kg entry were included, the delta would be huge
    # (not a stall); excluding it correctly leaves a tiny delta (a stall).
    assert weight_stall(measurements, AS_OF, threshold_kg=0.3) is True


# --- low_protein ---------------------------------------------------------------


def test_exactly_three_low_days_triggers_the_flag():
    days = [ProteinDay(day=AS_OF, protein_g=50.0) for _ in range(3)]
    assert low_protein(days, target_g=100.0, min_pct=80.0, min_days=3) is True


def test_two_low_days_does_not_trigger_the_flag():
    days = [ProteinDay(day=AS_OF, protein_g=50.0) for _ in range(2)]
    assert low_protein(days, target_g=100.0, min_pct=80.0, min_days=3) is False


def test_zero_target_never_triggers_the_flag():
    days = [ProteinDay(day=AS_OF, protein_g=0.0) for _ in range(5)]
    assert low_protein(days, target_g=0.0) is False


# --- low_attendance ---------------------------------------------------------------


def test_zero_expected_visits_never_triggers_the_flag():
    assert low_attendance(0, 0) is False


def test_exactly_at_the_50_percent_boundary_does_not_trigger():
    assert low_attendance(6, 12, threshold_pct=50.0) is False


def test_just_below_the_boundary_triggers():
    assert low_attendance(5, 12, threshold_pct=50.0) is True
