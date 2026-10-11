"""FR-12.3 is Enterprise-only. Registers a FeatureFlag(key="public_api",
default=False) and turns it on in the enterprise SaasPlan's features dict
-- see saas.services.has_feature's resolution order (per-org override >
rollout_pct > plan.features > flag.default > True-if-no-flag-at-all). A
flag row is required here specifically so undeclared-for-this-plan reads
False, not the "no flag = open by default" fallback.
"""

from __future__ import annotations

from django.db import migrations


def gate_feature(apps, schema_editor):
    FeatureFlag = apps.get_model("saas", "FeatureFlag")
    SaasPlan = apps.get_model("saas", "SaasPlan")

    FeatureFlag.objects.get_or_create(key="public_api", defaults={"default": False})

    enterprise = SaasPlan.objects.filter(code="enterprise").first()
    if enterprise is not None:
        enterprise.features = {**enterprise.features, "public_api": True}
        enterprise.save(update_fields=["features"])


def ungate_feature(apps, schema_editor):
    FeatureFlag = apps.get_model("saas", "FeatureFlag")
    SaasPlan = apps.get_model("saas", "SaasPlan")

    FeatureFlag.objects.filter(key="public_api").delete()

    enterprise = SaasPlan.objects.filter(code="enterprise").first()
    if enterprise is not None:
        enterprise.features.pop("public_api", None)
        enterprise.save(update_fields=["features"])


class Migration(migrations.Migration):
    dependencies = [
        ("publicapi", "0001_initial"),
        ("saas", "0002_seed_plans"),
    ]

    operations = [migrations.RunPython(gate_feature, ungate_feature)]
