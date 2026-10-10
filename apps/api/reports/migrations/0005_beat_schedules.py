"""Registers reports.tasks.refresh_mv_today (every 15 min) and
refresh_mv_nightly (00:45 Asia/Kathmandu — after expire_memberships 00:05,
churn_engine 00:30, and notify_risk_transitions 00:35). Same
get_or_create shape as retention/migrations/0004_notify_risk_transitions_schedule.py.
"""

from __future__ import annotations

from django.db import migrations


def create_schedules(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    interval, _ = IntervalSchedule.objects.get_or_create(every=15, period="minutes")
    PeriodicTask.objects.get_or_create(
        name="reports: refresh materialized views (today)",
        defaults={"task": "reports.tasks.refresh_mv_today", "interval": interval},
    )

    nightly, _ = CrontabSchedule.objects.get_or_create(
        minute="45",
        hour="0",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="reports: refresh materialized views (nightly)",
        defaults={"task": "reports.tasks.refresh_mv_nightly", "crontab": nightly},
    )


def remove_schedules(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=[
            "reports: refresh materialized views (today)",
            "reports: refresh materialized views (nightly)",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0004_mv_cohort_retention"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedules, remove_schedules),
    ]
