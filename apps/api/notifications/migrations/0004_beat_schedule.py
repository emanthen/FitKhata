"""Registers notifications.tasks.send_birthday_notifications with
django_celery_beat's DatabaseScheduler — same pattern as
billing/migrations/0007_pending_payment_reverification_schedule.py and
retention/migrations/0003_beat_schedules.py. 08:00 Asia/Kathmandu, after
quiet hours end (07:00) so a birthday message is never itself held.
"""

from __future__ import annotations

from django.db import migrations


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="8",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="notifications: birthday messages",
        defaults={"task": "notifications.tasks.send_birthday_notifications", "crontab": schedule},
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="notifications: birthday messages").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_seed_templates"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
