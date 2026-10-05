"""Registers the monthly partition-creation job with django_celery_beat's
DatabaseScheduler (CELERY_BEAT_SCHEDULER, already configured — see
config/settings/base.py) — a static CELERY_BEAT_SCHEDULE dict wouldn't be
picked up by that scheduler, it reads from these DB rows instead.
"""

from __future__ import annotations

from django.db import migrations


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="0",
        day_of_month="25",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="attendance: create next month's partition",
        defaults={
            "task": "attendance.tasks.create_next_month_partition_task",
            "crontab": schedule,
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name="attendance: create next month's partition"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0003_fix_partition_rls"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
