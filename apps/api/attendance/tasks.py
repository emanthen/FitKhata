"""Celery Beat creates the next month's Attendance partition on the 25th of
each month (schedule: migrations/0004_partition_schedule.py, a data
migration registering a CrontabSchedule+PeriodicTask row — this project's
CELERY_BEAT_SCHEDULER is django_celery_beat's DatabaseScheduler, so a static
CELERY_BEAT_SCHEDULE dict wouldn't be picked up).
"""

from __future__ import annotations

from datetime import date, timedelta

import redis
from celery import shared_task
from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from core.context import system_context

OFFLINE_THRESHOLD = timedelta(minutes=10)
_OFFLINE_ALERT_TTL_SECONDS = 60 * 60  # don't re-SMS the same device more than once/hour


def _month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    next_month = start.month % 12 + 1
    next_year = start.year + (1 if start.month == 12 else 0)
    end = start.replace(year=next_year, month=next_month)
    return start, end


@shared_task
def create_next_month_partition_task() -> str:
    """DDL only — no row data, so no tenant_context()/system_context()
    needed (those scope RLS session vars, irrelevant to CREATE TABLE).
    """
    today = date.today()
    # Compute "next month" relative to today by stepping one month past the
    # start of the current month, then one more.
    this_month_start, next_month_start = _month_bounds(today)
    _, month_after_start = _month_bounds(next_month_start)

    table_name = f"attendance_attendance_y{next_month_start:%Y}m{next_month_start:%m}"
    # DDL literals, not DML parameters — Postgres doesn't reliably support
    # bound parameters in CREATE TABLE ... FOR VALUES the way it does for
    # SELECT/INSERT. Safe to format directly: both dates are server-computed
    # `date` objects (first-of-month, from the stdlib `date` type), never
    # user input, and isoformat() can't contain SQL-special characters.
    sql = (
        f"CREATE TABLE IF NOT EXISTS {table_name} "
        f"PARTITION OF attendance_attendance "
        f"FOR VALUES FROM ('{next_month_start.isoformat()}') "
        f"TO ('{month_after_start.isoformat()}')"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
    return table_name


def _notify_managers_sms(gym, text: str) -> None:
    """Same shape as members.services._notify_managers / billing.views's
    _notify_owners_of_variance -- direct SMS to gym-or-org-wide owners and
    managers, bypassing notifications.notify() since that's member-only.
    """
    from accounts.models import StaffRole
    from accounts.sms import get_sms_provider

    managers = (
        StaffRole.objects.filter(
            org=gym.org, role__in=[StaffRole.Role.OWNER, StaffRole.Role.MANAGER], is_active=True
        )
        .filter(Q(gym=gym) | Q(gym__isnull=True))
        .select_related("user")
    )
    provider = get_sms_provider()
    for staff_role in managers:
        if staff_role.user.phone:
            provider.send(staff_role.user.phone, text)


@shared_task
def alert_offline_gate_devices() -> int:
    """Runs every 5 min (schedule: migrations/0005_offline_alert_schedule.py).
    Cross-tenant scan, so needs system_context() -- same reasoning as every
    other cross-gym Celery Beat job (CLAUDE.md rule 3).
    """
    from attendance.models import GateDevice

    threshold = timezone.now() - OFFLINE_THRESHOLD
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    alerted = 0

    with system_context():
        offline_devices = GateDevice.objects.filter(
            revoked_at__isnull=True, last_seen_at__lt=threshold
        ).select_related("gym", "gym__org")

        for device in offline_devices:
            dedupe_key = f"gate:offline_alerted:{device.pk}"
            if redis_client.set(dedupe_key, "1", nx=True, ex=_OFFLINE_ALERT_TTL_SECONDS):
                _notify_managers_sms(
                    device.gym,
                    f"FitKhata alert: gate device '{device.name}' at {device.gym.name} "
                    f"has been offline for over 10 minutes.",
                )
                alerted += 1

    return alerted
