"""Celery Beat: nightly/morning retention jobs (FR-5.1, 5.3, 5.6, 5.7).
Schedules registered via migrations/0003_beat_schedules.py, Asia/Kathmandu
times -- same django_celery_beat DatabaseScheduler reasoning as
attendance/tasks.py and billing/tasks.py.

All four run under system_context() at the outer level (cross-tenant job,
rule 3), scoping each gym under tenant_context([gym_id]) for the actual
per-gym work -- RLS stays the enforced boundary even for churn_engine's raw
SQL. Gyms are iterated in batches of 200 so one slow/huge gym can't starve
visibility into the others' progress.
"""

from __future__ import annotations

from datetime import timedelta
from itertools import cycle

from celery import shared_task
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from accounts.models import StaffRole
from core.context import system_context, tenant_context
from core.domain.nptime import to_kathmandu
from gyms.models import Gym
from members.models import Member, Membership
from notifications.services import notify
from retention.models import RetentionCall, RiskStateChange

GYM_BATCH_SIZE = 200
NOT_RECENTLY_QUEUED_DAYS = 3
DEFAULT_WARNING_DAYS = 7
DEFAULT_RED_DAYS = 10

# FR-5.7 / FR-6.8: which notifications.Template.Key each day-offset from
# expiry maps to (positive = days before expiry, negative = days after).
EXPIRY_REMINDER_EVENTS = {
    7: "expiry_7d",
    3: "expiry_3d",
    1: "expiry_1d",
    -1: "expired_1d",
    -7: "expired_7d",
}


def _today():
    return to_kathmandu(timezone.now()).date()


def _gym_id_batches() -> list[list]:
    with system_context():
        ids = list(Gym.objects.order_by("id").values_list("id", flat=True))
    return [ids[i : i + GYM_BATCH_SIZE] for i in range(0, len(ids), GYM_BATCH_SIZE)]


@shared_task
def expire_memberships() -> int:
    today = _today()
    total = 0
    for batch in _gym_id_batches():
        for gym_id in batch:
            with tenant_context([str(gym_id)]):
                total += Membership.objects.filter(
                    gym_id=gym_id, status=Membership.Status.ACTIVE, expiry_date__lt=today
                ).update(status=Membership.Status.EXPIRED)
                still_covered = Membership.objects.filter(
                    gym_id=gym_id, status=Membership.Status.ACTIVE
                ).values_list("member_id", flat=True)
                Member.objects.filter(gym_id=gym_id, status=Member.Status.ACTIVE).exclude(
                    pk__in=still_covered
                ).update(status=Member.Status.EXPIRED)
    return total


# One statement per gym: a chain of read-only CTEs feeding a single UPDATE
# (the "updated" CTE), with a final SELECT that reports which members'
# risk_state actually changed -- all from the same query snapshot, no
# separate locking pass needed. The risk_state/churn_score expressions
# below are the SQL mirror of retention/domain/risk.py and churn.py;
# warning_days/red_days are resolved once in Python (from the gym's own
# settings) and passed as bound params, not re-read from JSON per row.
_CHURN_ENGINE_SQL = """
WITH attendance_stats AS (
    SELECT member_id,
           COUNT(*) FILTER (WHERE check_in_at >= %(last30_start)s) AS visits_last_30,
           COUNT(*) FILTER (
               WHERE check_in_at >= %(prev30_start)s AND check_in_at < %(last30_start)s
           ) AS visits_prev_30
    FROM attendance_attendance
    WHERE gym_id = %(gym_id)s AND check_in_at >= %(prev30_start)s
    GROUP BY member_id
),
dues_stats AS (
    SELECT member_id, SUM(total_npr) AS dues_npr
    FROM billing_invoice
    WHERE gym_id = %(gym_id)s AND status = 'draft'
    GROUP BY member_id
),
expiry_stats AS (
    SELECT member_id, MAX(expiry_date) AS expiry_date
    FROM members_membership
    WHERE gym_id = %(gym_id)s
    GROUP BY member_id
),
stats AS (
    SELECT
        m.id AS member_id,
        m.risk_state AS old_risk_state,
        (%(today)s::date - COALESCE(
            (m.last_check_in_at AT TIME ZONE 'Asia/Kathmandu')::date,
            (m.created_at AT TIME ZONE 'Asia/Kathmandu')::date
        )) AS days_absent,
        COALESCE(a.visits_last_30, 0) AS visits_last_30,
        COALESCE(a.visits_prev_30, 0) AS visits_prev_30,
        COALESCE(e.expiry_date - %(today)s::date, 9999) AS days_to_expiry,
        COALESCE(d.dues_npr, 0) AS dues_npr,
        (%(today)s::date - (m.created_at AT TIME ZONE 'Asia/Kathmandu')::date) AS tenure_days
    FROM members_member m
    LEFT JOIN attendance_stats a ON a.member_id = m.id
    LEFT JOIN dues_stats d ON d.member_id = m.id
    LEFT JOIN expiry_stats e ON e.member_id = m.id
    WHERE m.gym_id = %(gym_id)s
),
scored AS (
    SELECT
        member_id,
        old_risk_state,
        days_absent,
        CASE
            WHEN days_absent >= %(red_days)s THEN 'red_list'
            WHEN days_absent >= %(warning_days)s THEN 'warning'
            ELSE 'normal'
        END AS new_risk_state,
        LEAST(100.0, GREATEST(0.0,
            LEAST(days_absent / 30.0, 1.0) * 40.0
            + CASE WHEN visits_prev_30 > 0
                   THEN GREATEST(0.0, (visits_prev_30 - visits_last_30)::float
                        / visits_prev_30) * 20.0
                   ELSE 0.0 END
            + LEAST(1.0, GREATEST(0.0, 1.0 - days_to_expiry / 14.0)) * 15.0
            + CASE WHEN dues_npr > 0 THEN 10.0 ELSE 0.0 END
            + GREATEST(0.0, (180.0 - tenure_days) / 180.0) * 15.0
        )) AS new_churn_score
    FROM stats
),
-- Deliberately not referenced below: Postgres always executes a
-- data-modifying CTE's side effects regardless of whether the final query
-- reads its result (per the WITH docs), so this doesn't need to be joined
-- back against `scored` to "prove" the update happened. It used to be --
-- joining two ~50k-row materialized CTEs on a column neither has an index
-- on made Postgres pick a nested loop (CTE row-count estimates default to
-- ~1), i.e. a ~2.5 billion-comparison cross product. `scored` alone already
-- carries every column the caller needs, 1:1 with what got updated.
updated AS (
    UPDATE members_member m
    SET risk_state = scored.new_risk_state, churn_score = scored.new_churn_score
    FROM scored
    WHERE m.id = scored.member_id
)
SELECT scored.member_id, scored.old_risk_state, scored.new_risk_state, scored.days_absent
FROM scored
WHERE scored.old_risk_state IS DISTINCT FROM scored.new_risk_state
"""


@shared_task
def churn_engine() -> int:
    """Returns the total number of members whose risk_state changed this run."""
    today = _today()
    changed_total = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with system_context():
                gym = Gym.objects.get(pk=gym_id)
            warning_days = gym.settings.get("warning_days", DEFAULT_WARNING_DAYS)
            red_days = gym.settings.get("red_list_days", DEFAULT_RED_DAYS)

            with tenant_context([str(gym_id)]):
                with connection.cursor() as cursor:
                    cursor.execute(
                        _CHURN_ENGINE_SQL,
                        {
                            "gym_id": str(gym_id),
                            "today": today,
                            "last30_start": today - timedelta(days=30),
                            "prev30_start": today - timedelta(days=60),
                            "warning_days": warning_days,
                            "red_days": red_days,
                        },
                    )
                    changes = cursor.fetchall()

                if changes:
                    RiskStateChange.objects.bulk_create(
                        [
                            RiskStateChange(
                                org_id=gym.org_id,
                                gym_id=gym_id,
                                member_id=member_id,
                                from_state=old_state,
                                to_state=new_state,
                                days_absent=max(days_absent, 0),
                                changed_on=today,
                            )
                            for member_id, old_state, new_state, days_absent in changes
                        ]
                    )
                    changed_total += len(changes)

    return changed_total


@shared_task
def notify_risk_transitions() -> int:
    """Deliberately a *separate* task from churn_engine, run 5 minutes after
    it (migrations/0004_notify_risk_transitions_schedule.py) rather than
    inline in that function's loop: churn_engine's whole point is one SQL
    UPDATE per gym with no per-row Python work (see the 50k-member benchmark
    in tests/test_churn_engine_benchmark.py) — a per-member notify() call for
    every transition, inline, would reintroduce exactly the per-row Python
    loop that benchmark exists to catch. Reads today's RiskStateChange rows
    instead of needing churn_engine to hand anything over directly.
    """
    today = _today()
    notified_total = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with tenant_context([str(gym_id)]):
                changes = RiskStateChange.objects.filter(
                    gym_id=gym_id,
                    changed_on=today,
                    to_state__in=[Member.RiskState.WARNING, Member.RiskState.RED_LIST],
                ).select_related("member")

                # FR-6.8 call sites: named for the *default* warning/
                # red_list_days thresholds (7/10) even though a gym can
                # retune them — see notifications' plan judgment call 8.
                event_for_state: dict[str, str] = {
                    Member.RiskState.WARNING.value: "red_list_day7",
                    Member.RiskState.RED_LIST.value: "red_list_day10",
                }
                for change in changes:
                    event = event_for_state[change.to_state]
                    if notify(change.member, event, {"name": change.member.full_name}):
                        notified_total += 1

    return notified_total


@shared_task
def build_call_queue() -> int:
    today = _today()
    cutoff = today - timedelta(days=NOT_RECENTLY_QUEUED_DAYS)
    queued_total = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with system_context():
                gym = Gym.objects.get(pk=gym_id)

            with tenant_context([str(gym_id)]):
                recently_queued = RetentionCall.objects.filter(
                    gym_id=gym_id, queue_date__gte=cutoff
                ).values_list("member_id", flat=True)
                red_list_member_ids = list(
                    Member.objects.filter(gym_id=gym_id, risk_state=Member.RiskState.RED_LIST)
                    .exclude(pk__in=recently_queued)
                    .values_list("id", flat=True)
                )
                if not red_list_member_ids:
                    continue

                # Active front-desk staff only -- gym-scoped or org-wide
                # (gym=None), same shape as billing/views.py's owner-notify
                # query. An inactive staff row must never enter cycle()'s
                # input, which is exactly what makes round-robin skip them.
                staff_user_ids = list(
                    StaffRole.objects.filter(
                        org_id=gym.org_id, role=StaffRole.Role.FRONT_DESK, is_active=True
                    )
                    .filter(Q(gym_id=gym_id) | Q(gym__isnull=True))
                    .order_by("user_id")
                    .values_list("user_id", flat=True)
                    .distinct()
                )
                if not staff_user_ids:
                    continue

                calls = [
                    RetentionCall(
                        org_id=gym.org_id,
                        gym_id=gym_id,
                        member_id=member_id,
                        queue_date=today,
                        assigned_to_id=staff_id,
                    )
                    for member_id, staff_id in zip(red_list_member_ids, cycle(staff_user_ids))
                ]
                RetentionCall.objects.bulk_create(calls)
                queued_total += len(calls)

    return queued_total


@shared_task
def expiry_reminders() -> int:
    today = _today()
    sent_total = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with tenant_context([str(gym_id)]):
                for offset, event in EXPIRY_REMINDER_EVENTS.items():
                    target_date = today + timedelta(days=offset)
                    memberships = Membership.objects.filter(
                        gym_id=gym_id, expiry_date=target_date
                    ).select_related("member")
                    for membership in memberships:
                        if notify(membership.member, event, {"name": membership.member.full_name}):
                            sent_total += 1

    return sent_total
