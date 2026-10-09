"""Phase 7 (coaching) cross-app edit: adds the two new Template.Key choices
(models.py) and seeds their platform-default rows — same per-channel
seeding shape as migrations/0003_seed_templates.py. coaching.services
calls notify() with these two event keys from approve_coaching_report()
and cancel_booking()'s waitlist promotion.
"""

from __future__ import annotations

from django.db import migrations, models

CHANNELS = ["sms", "whatsapp", "push", "email"]

# (key, body_ne, body_en)
NEW_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "coaching_report_ready",
        "{{name}} जी, तपाईंको यस हप्ताको कोचिंग रिपोर्ट तयार छ।",
        "Hi {{name}}, your coaching report for this week is ready.",
    ),
    (
        "class_booking_promoted",
        "तपाईं {{class_name}} कक्षाको वेटलिस्टबाट बुक भएको स्थानमा सारिनुभयो।",
        "You've been moved from the waitlist into a confirmed spot for {{class_name}}.",
    ),
]


def seed_new_templates(apps, schema_editor):
    Template = apps.get_model("notifications", "Template")
    rows = []
    for key, body_ne, body_en in NEW_TEMPLATES:
        for channel in CHANNELS:
            for language, body in (("ne", body_ne), ("en", body_en)):
                rows.append(
                    Template(
                        org=None,
                        key=key,
                        channel=channel,
                        language=language,
                        body=body,
                        whatsapp_template_name=f"fitkhata_{key}" if channel == "whatsapp" else "",
                    )
                )
    Template.objects.bulk_create(rows)


def remove_new_templates(apps, schema_editor):
    Template = apps.get_model("notifications", "Template")
    Template.objects.filter(
        org__isnull=True, key__in=[key for key, _, _ in NEW_TEMPLATES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_beat_schedule"),
    ]

    operations = [
        migrations.AlterField(
            model_name="template",
            name="key",
            field=models.CharField(
                choices=[
                    ("welcome", "Welcome"),
                    ("payment_receipt", "Payment receipt"),
                    ("expiry_7d", "Expiry 7d"),
                    ("expiry_3d", "Expiry 3d"),
                    ("expiry_1d", "Expiry 1d"),
                    ("expired_1d", "Expired 1d"),
                    ("expired_7d", "Expired 7d"),
                    ("birthday", "Birthday"),
                    ("red_list_day7", "Red list day 7"),
                    ("red_list_day10", "Red list day 10"),
                    ("freeze_applied", "Freeze applied"),
                    ("class_booked", "Class booked"),
                    ("winback", "Winback"),
                    ("coaching_report_ready", "Coaching report ready"),
                    ("class_booking_promoted", "Class booking promoted"),
                ],
                max_length=30,
            ),
        ),
        migrations.RunPython(seed_new_templates, remove_new_templates),
    ]
