from __future__ import annotations

from coaching.domain.progress import (
    adherence_pct,
    attendance_pct,
    goal_progress_pct,
    macro_pct,
)


def test_goal_progress_returns_100_when_target_equals_starting():
    assert goal_progress_pct(70.0, 70.0, 70.0) == 100.0
    assert goal_progress_pct(70.0, 65.0, 70.0) == 100.0  # even if current moved


def test_goal_progress_weight_loss_on_track():
    # starting 80, target 70 (lose 10kg) -> currently 75 (lost 5kg) = 50%
    assert goal_progress_pct(80.0, 75.0, 70.0) == 50.0


def test_goal_progress_weight_gain_on_track():
    # starting 60, target 70 (gain 10kg) -> currently 65 (gained 5kg) = 50%
    assert goal_progress_pct(60.0, 65.0, 70.0) == 50.0


def test_goal_progress_overshoot_clamps_to_100():
    assert goal_progress_pct(80.0, 65.0, 70.0) == 100.0  # lost more than needed


def test_goal_progress_wrong_direction_clamps_to_0():
    assert goal_progress_pct(80.0, 85.0, 70.0) == 0.0  # gained weight on a loss goal


def test_attendance_pct_zero_expected_is_zero():
    assert attendance_pct(5, 0) == 0.0


def test_attendance_pct_normal_fraction():
    assert attendance_pct(6, 12) == 50.0


def test_attendance_pct_over_100_clamps():
    assert attendance_pct(15, 12) == 100.0


def test_adherence_pct_zero_planned_is_zero():
    assert adherence_pct(3, 0) == 0.0


def test_adherence_pct_normal_fraction():
    assert adherence_pct(4, 5) == 80.0


def test_macro_pct_zero_target_is_zero():
    assert macro_pct(50.0, 0) == 0.0


def test_macro_pct_normal_fraction():
    assert macro_pct(80.0, 100.0) == 80.0


def test_macro_pct_over_target_clamps_to_100():
    assert macro_pct(150.0, 100.0) == 100.0
