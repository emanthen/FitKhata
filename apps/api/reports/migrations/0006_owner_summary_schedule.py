"""Registers reports.tasks.send_owner_daily_summary at 21:00 Asia/Kathmandu
(FR-10.8). Same get_or_create shape as
retention/migrations/0004_notify_risk_transitions_schedule.py.
"""

from __future__ import annotations

from django.db import migrations


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="21",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="reports: owner daily summary",
        defaults={"task": "reports.tasks.send_owner_daily_summary", "crontab": schedule},
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="reports: owner daily summary").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0005_beat_schedules"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
