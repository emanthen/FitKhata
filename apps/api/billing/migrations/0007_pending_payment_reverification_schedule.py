"""Registers billing.tasks.reverify_pending_payments (FR-4.5) with
django_celery_beat's DatabaseScheduler — same pattern as
attendance/migrations/0004_partition_schedule.py.
"""

from __future__ import annotations

from django.db import migrations


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="*/10",
        hour="*",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="billing: re-verify pending online payments",
        defaults={
            "task": "billing.tasks.reverify_pending_payments",
            "crontab": schedule,
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="billing: re-verify pending online payments").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_gatewaycredential_extra"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
