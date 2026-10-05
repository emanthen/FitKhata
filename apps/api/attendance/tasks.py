"""Celery Beat creates the next month's Attendance partition on the 25th of
each month (schedule: migrations/0004_partition_schedule.py, a data
migration registering a CrontabSchedule+PeriodicTask row — this project's
CELERY_BEAT_SCHEDULER is django_celery_beat's DatabaseScheduler, so a static
CELERY_BEAT_SCHEDULE dict wouldn't be picked up).
"""

from __future__ import annotations

from datetime import date

from celery import shared_task
from django.db import connection


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
