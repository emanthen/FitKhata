"""Registers coaching's weekly Celery Beat jobs — same django_celery_beat
DatabaseScheduler pattern as retention/migrations/0003_beat_schedules.py
and notifications/migrations/0004_beat_schedule.py. First *weekly*
schedule in the repo: day_of_week follows cron convention (0 = Sunday).
generate_branch_coaching_reports runs an hour after the client job so
per-client reports have landed before the rollup reads them — same stagger
reasoning as retention's churn_engine -> notify_risk_transitions 5-minute gap.
"""

from __future__ import annotations

from django.db import migrations

SCHEDULES = [
    ("coaching: weekly client reports", "coaching.tasks.generate_weekly_coaching_reports", "0", "22"),
    ("coaching: weekly branch reports", "coaching.tasks.generate_branch_coaching_reports", "0", "23"),
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
            day_of_week="0",
            timezone="Asia/Kathmandu",
        )
        PeriodicTask.objects.get_or_create(name=name, defaults={"task": task, "crontab": schedule})


def remove_schedules(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name__in=[name for name, *_ in SCHEDULES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coaching", "0004_seed_food_items"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedules, remove_schedules),
    ]
