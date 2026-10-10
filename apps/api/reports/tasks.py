"""Celery Beat: materialized-view refresh + the 21:00 owner summary.
Schedules registered via migrations/0005_beat_schedules.py and
0006_owner_summary_schedule.py, Asia/Kathmandu times — same
django_celery_beat DatabaseScheduler reasoning as retention/tasks.py.

refresh_mv_* run under system_context() for two reasons at once: (1)
REFRESH MATERIALIZED VIEW requires owning the MV, which the migrations
(reports/migrations/0001's docstring) deliberately transfer to
fitkhata_system; (2) the SELECT inside that refresh reads every gym's rows
across the source tables, all of which have FORCE ROW LEVEL SECURITY —
BYPASSRLS is required to see more than one gym's data, and (confirmed
empirically) does NOT inherit through role membership in Postgres the way
ordinary GRANTed privileges do, so simply being a member of fitkhata_system
isn't enough; the role must actually BE fitkhata_system for the refresh.

send_owner_daily_summary additionally needs tenant_context() per gym
(nested inside the outer system_context(), same double-context shape
retention/tasks.py uses) because reports/services.py's MV-backed reads go
through the *_scoped views, whose WHERE clause depends on app.gym_ids
actually being set; system_context() alone leaves it unset and those
views return nothing.
"""

from __future__ import annotations

from celery import shared_task
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from accounts.models import StaffRole
from core.context import system_context, tenant_context
from gyms.models import Gym
from notifications.providers import email as email_provider
from notifications.providers import whatsapp as whatsapp_provider
from reports.services import assemble_owner_summary

MV_NAMES = [
    "mv_daily_revenue",
    "mv_membership_flow",
    "mv_attendance_hourly",
    "mv_cohort_retention",
]


def _refresh_all() -> None:
    with system_context(), connection.cursor() as cursor:
        for name in MV_NAMES:
            cursor.execute(f"REFRESH MATERIALIZED VIEW {name}")


@shared_task
def refresh_mv_today() -> None:
    """Every 15 minutes. Postgres has no partial/incremental materialized-
    view refresh — this re-runs the exact same full refresh as the nightly
    job; the only difference between the two schedules is frequency.
    """
    _refresh_all()


@shared_task
def refresh_mv_nightly() -> None:
    """00:45 Asia/Kathmandu — after expire_memberships (00:05), churn_engine
    (00:30), and notify_risk_transitions (00:35), so the day's churn/flow
    signal already exists when this reads it.
    """
    _refresh_all()


def _owners_for(gym) -> list:
    return list(
        StaffRole.objects.filter(org=gym.org, role=StaffRole.Role.OWNER, is_active=True)
        .filter(Q(gym=gym) | Q(gym__isnull=True))
        .select_related("user")
    )


def _send_owner_summary(gym, owner_role, summary: dict) -> None:
    user = owner_role.user
    by_mode = ", ".join(f"{k}: NPR {v}" for k, v in summary["revenue_by_mode"].items()) or "none"
    body = (
        f"{gym.name} — {summary['day']}\n"
        f"Revenue: {by_mode}\n"
        f"New {summary['new_count']}, renewed {summary['renewed_count']}, "
        f"expired {summary['expired_count']}\n"
        f"Red list: {summary['red_list_count']}\n"
        f"Cash variance: NPR {summary['cash_variance_npr']}"
    )
    if user.email:
        email_provider.send(user.email, f"FitKhata daily summary — {gym.name}", body)
    if user.phone:
        # Pending Meta template approval, same caveat every other seeded
        # WhatsApp template in this codebase already carries.
        whatsapp_provider.send(
            user.phone,
            "fitkhata_owner_daily_summary",
            "en",
            [gym.name, by_mode, str(summary["red_list_count"]), str(summary["cash_variance_npr"])],
        )


@shared_task
def send_owner_daily_summary() -> None:
    """FR-10.8, 21:00 Asia/Kathmandu."""
    today = timezone.localdate()
    with system_context():
        gyms = list(Gym.objects.all())

    for gym in gyms:
        with tenant_context([str(gym.pk)]):
            summary = assemble_owner_summary(gym, today)
            for owner_role in _owners_for(gym):
                _send_owner_summary(gym, owner_role, summary)
