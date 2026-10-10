"""Registers saas.tasks.generate_invoices (01:00 Asia/Kathmandu, 1st of the
month) and saas.tasks.dunning_sweep (daily, 02:00 — after invoice
generation on the 1st, and gives any other daily nightly jobs a predictable
slot). Same get_or_create shape as reports/migrations/0005_beat_schedules.py.
"""

from __future__ import annotations

from django.db import migrations


def create_schedules(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    monthly, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="1",
        day_of_month="1",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="saas: generate monthly invoices",
        defaults={"task": "saas.tasks.generate_invoices", "crontab": monthly},
    )

    daily, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="2",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
        timezone="Asia/Kathmandu",
    )
    PeriodicTask.objects.get_or_create(
        name="saas: dunning sweep",
        defaults={"task": "saas.tasks.dunning_sweep", "crontab": daily},
    )
    PeriodicTask.objects.get_or_create(
        name="saas: anonymize deleted orgs",
        defaults={"task": "saas.tasks.anonymize_deleted_orgs", "crontab": daily},
    )


def remove_schedules(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=[
            "saas: generate monthly invoices",
            "saas: dunning sweep",
            "saas: anonymize deleted orgs",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("saas", "0003_seed_fitkhata_platform_gym"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedules, remove_schedules),
    ]
