"""SRS §12.1 pricing — starter/pro/enterprise."""

from __future__ import annotations

from decimal import Decimal

from django.db import migrations

PLANS = [
    {
        "code": "starter",
        "setup_fee_npr": Decimal("3000.00"),
        "monthly_npr": Decimal("999.00"),
        "annual_npr": Decimal("9990.00"),
        "member_limit": 150,
        "per_branch_pricing": False,
    },
    {
        "code": "pro",
        "setup_fee_npr": Decimal("5000.00"),
        "monthly_npr": Decimal("1999.00"),
        "annual_npr": Decimal("19990.00"),
        "member_limit": 1000,
        "per_branch_pricing": False,
    },
    {
        "code": "enterprise",
        "setup_fee_npr": Decimal("15000.00"),
        "monthly_npr": Decimal("4999.00"),
        "annual_npr": Decimal("49990.00"),
        "member_limit": None,
        "per_branch_pricing": True,
    },
]


def seed_plans(apps, schema_editor):
    SaasPlan = apps.get_model("saas", "SaasPlan")
    for plan in PLANS:
        SaasPlan.objects.get_or_create(code=plan["code"], defaults=plan)


def remove_plans(apps, schema_editor):
    SaasPlan = apps.get_model("saas", "SaasPlan")
    SaasPlan.objects.filter(code__in=[p["code"] for p in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [("saas", "0001_initial")]

    operations = [migrations.RunPython(seed_plans, remove_plans)]
