"""Registers retention.tasks.notify_risk_transitions, 5 minutes after
churn_engine (00:30) so today's RiskStateChange rows already exist when it
runs. Deliberately a separate task/schedule from churn_engine itself — see
that task's own docstring for why (the 50k-member benchmark in
tests/test_churn_engine_benchmark.py exists specifically to catch a
per-member Python loop creeping back into churn_engine's hot path).
"""

from __future__ import annotations

from django.db import migrations


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="35",
        hour="0",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="retention: notify risk transitions",
        defaults={"task": "retention.tasks.notify_risk_transitions", "crontab": schedule},
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="retention: notify risk transitions").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("retention", "0003_beat_schedules"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
