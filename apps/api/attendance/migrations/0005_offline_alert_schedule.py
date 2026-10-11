"""Registers attendance.tasks.alert_offline_gate_devices with
django_celery_beat's DatabaseScheduler every 5 minutes -- same pattern as
notifications/migrations/0004_beat_schedule.py.
"""

from __future__ import annotations

from django.db import migrations


def create_schedule(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = IntervalSchedule.objects.get_or_create(every=5, period="minutes")
    PeriodicTask.objects.get_or_create(
        name="attendance: offline gate device alerts",
        defaults={"task": "attendance.tasks.alert_offline_gate_devices", "interval": schedule},
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="attendance: offline gate device alerts").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0004_partition_schedule"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
