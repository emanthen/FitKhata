"""Seeds the platform-default Template catalog (org=NULL) — FR-6.1's 13
keys, one row per (key, channel, language) across all four channels so
resolve_template() always has something to fall back to no matter which
channel notify() ends up picking (an org can later override any individual
row through the template editor). whatsapp_template_name is a placeholder
("fitkhata_<key>") pending real approval in Meta's Business Manager —
sending on the whatsapp channel before that's done fails with a clear
ProviderPermanentError (unapproved template), the same failure Meta's own
API would report for a real template name that isn't approved yet.
"""

from __future__ import annotations

from django.db import migrations

# (key, body_ne, body_en)
TEMPLATES: list[tuple[str, str, str]] = [
    ("welcome", "नमस्ते {{name}}, FitKhata मा स्वागत छ!", "Welcome to FitKhata, {{name}}!"),
    (
        "payment_receipt",
        "{{name}} जी, तपाईंको NPR {{amount}} को भुक्तानी प्राप्त भयो। रसिद: {{invoice_number}}",
        "Hi {{name}}, we received your payment of NPR {{amount}}. Receipt: {{invoice_number}}",
    ),
    (
        "expiry_7d",
        "{{name}} जी, तपाईंको सदस्यता 7 दिनमा समाप्त हुन्छ।",
        "Hi {{name}}, your membership expires in 7 days.",
    ),
    (
        "expiry_3d",
        "{{name}} जी, तपाईंको सदस्यता 3 दिनमा समाप्त हुन्छ।",
        "Hi {{name}}, your membership expires in 3 days.",
    ),
    (
        "expiry_1d",
        "{{name}} जी, तपाईंको सदस्यता भोलि समाप्त हुन्छ।",
        "Hi {{name}}, your membership expires tomorrow.",
    ),
    (
        "expired_1d",
        "{{name}} जी, तपाईंको सदस्यता हिजो समाप्त भयो। फिर्ता आउनुहोस्!",
        "Hi {{name}}, your membership expired yesterday. Come back!",
    ),
    (
        "expired_7d",
        "{{name}} जी, तपाईंको सदस्यता 7 दिन अघि समाप्त भयो।",
        "Hi {{name}}, your membership expired 7 days ago.",
    ),
    ("birthday", "जन्मदिनको शुभकामना, {{name}}!", "Happy birthday, {{name}}!"),
    (
        "red_list_day7",
        "{{name}} जी, हामीले तपाईंलाई याद गर्यौं! फिर्ता आउनुहोस्।",
        "Hi {{name}}, we miss you! Come back soon.",
    ),
    (
        "red_list_day10",
        "{{name}} जी, तपाईं धेरै दिनदेखि आउनुभएको छैन। के सबै ठिक छ?",
        "Hi {{name}}, it's been a while since your last visit. Everything okay?",
    ),
    (
        "freeze_applied",
        "तपाईंको सदस्यता {{start_date}} देखि {{end_date}} सम्म स्थगित गरिएको छ।",
        "Your membership is frozen from {{start_date}} to {{end_date}}.",
    ),
    (
        "class_booked",
        "तपाईंले {{class_name}} कक्षा {{date}} मा बुक गर्नुभयो।",
        "You booked {{class_name}} on {{date}}.",
    ),
    (
        "winback",
        "तपाईंलाई फेरि भेट्न चाहन्छौं! फर्कनुहोस् र विशेष छुट पाउनुहोस्।",
        "We'd love to see you again! Come back for a special offer.",
    ),
]

CHANNELS = ["sms", "whatsapp", "push", "email"]


def seed_templates(apps, schema_editor):
    Template = apps.get_model("notifications", "Template")
    rows = []
    for key, body_ne, body_en in TEMPLATES:
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


def remove_templates(apps, schema_editor):
    Template = apps.get_model("notifications", "Template")
    Template.objects.filter(org__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_rls"),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
