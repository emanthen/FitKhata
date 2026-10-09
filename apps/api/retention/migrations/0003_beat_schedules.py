"""Registers Phase 5's four nightly/morning retention jobs with
django_celery_beat's DatabaseScheduler -- same pattern as
attendance/migrations/0004_partition_schedule.py and
billing/migrations/0007_pending_payment_reverification_schedule.py (this
project's CELERY_BEAT_SCHEDULER reads from these DB rows, not a static
CELERY_BEAT_SCHEDULE dict).
"""

from __future__ import annotations

from django.db import migrations

SCHEDULES = [
    ("retention: expire memberships", "retention.tasks.expire_memberships", "5", "0"),
    ("retention: churn engine", "retention.tasks.churn_engine", "30", "0"),
    ("retention: build call queue", "retention.tasks.build_call_queue", "0", "5"),
    ("retention: expiry reminders", "retention.tasks.expiry_reminders", "0", "9"),
]


def create_schedules(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    for name, task, minute, hour in SCHEDULES:
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_month="*",
            month_of_year="*",
            day_of_week="*",
            timezone="Asia/Kathmandu",
        )
        PeriodicTask.objects.get_or_create(name=name, defaults={"task": task, "crontab": schedule})


def remove_schedules(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name__in=[name for name, *_ in SCHEDULES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("retention", "0002_rls"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedules, remove_schedules),
    ]
