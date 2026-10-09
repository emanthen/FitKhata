"""Churn-risk scoring (FR-5.2). Pure Python, no Django imports — rule 9.

No SRS formula is available for this (docs/SRS.md doesn't exist in this
repo) — this is this implementation's own weighting, chosen so the one hard
requirement (monotonic in days_absent: more absence never lowers the score)
holds by construction, not by coincidence.

Weights (sum to 100, each component independently bounded to [0, 1] * its
weight so the total never needs an upstream clamp, though one is kept
defensively):

- absence       40 -- min(days_absent / 30, 1) * 40
  The only days_absent-dependent term, and monotonic non-decreasing in it
  by construction (min() of a non-decreasing function and a constant) --
  this is what makes the whole score monotonic in days_absent regardless
  of the other components, since none of them depend on days_absent.
- visit decline 20 -- max(0, (visits_prev_30 - visits_last_30) / visits_prev_30) * 20
  0 when visits_prev_30 is 0 (no prior baseline to decline from).
- expiry        15 -- max(0, 1 - days_to_expiry / 14) * 15
  Maxed out once days_to_expiry <= 0 (already expired).
- dues          10 -- 10 if dues_npr > 0 else 0
- tenure        15 -- max(0, (180 - tenure_days) / 180) * 15
  Newer members (< 6 months) score riskier; zero past 180 days.
"""

from __future__ import annotations

ABSENCE_WEIGHT = 40.0
VISIT_DECLINE_WEIGHT = 20.0
EXPIRY_WEIGHT = 15.0
DUES_WEIGHT = 10.0
TENURE_WEIGHT = 15.0

ABSENCE_SATURATION_DAYS = 30.0
EXPIRY_HORIZON_DAYS = 14.0
NEW_MEMBER_HORIZON_DAYS = 180.0


def churn_score(
    days_absent: int,
    visits_last_30: int,
    visits_prev_30: int,
    days_to_expiry: int,
    dues_npr: float,
    tenure_days: int,
) -> float:
    absence = min(days_absent / ABSENCE_SATURATION_DAYS, 1.0) * ABSENCE_WEIGHT

    if visits_prev_30 > 0:
        decline_ratio = max(0.0, (visits_prev_30 - visits_last_30) / visits_prev_30)
    else:
        decline_ratio = 0.0
    visit_decline = decline_ratio * VISIT_DECLINE_WEIGHT

    expiry = min(1.0, max(0.0, 1.0 - days_to_expiry / EXPIRY_HORIZON_DAYS)) * EXPIRY_WEIGHT
    dues = DUES_WEIGHT if dues_npr > 0 else 0.0
    tenure_ratio = max(0.0, (NEW_MEMBER_HORIZON_DAYS - tenure_days) / NEW_MEMBER_HORIZON_DAYS)
    tenure = tenure_ratio * TENURE_WEIGHT

    total = absence + visit_decline + expiry + dues + tenure
    return min(100.0, max(0.0, total))
