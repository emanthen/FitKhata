"""Risk-state thresholds (FR-5.1). Pure Python, no Django imports — rule 9.

Thresholds are per-gym (Gym.settings "warning_days"/"red_list_days"), so this
takes them as plain ints rather than reading settings itself.
"""

from __future__ import annotations

NORMAL = "normal"
WARNING = "warning"
RED_LIST = "red_list"


def risk_state(days_absent: int, warning_days: int, red_days: int) -> str:
    """< warning_days -> normal; [warning_days, red_days) -> warning;
    >= red_days -> red_list. Boundaries are inclusive on the riskier side,
    so a member hits "warning" exactly on day `warning_days`, not the day after.
    """
    if days_absent >= red_days:
        return RED_LIST
    if days_absent >= warning_days:
        return WARNING
    return NORMAL
