"""Seeds a FitKhata-owned Organization+Gym purely to hang GatewayCredential
rows off of — see billing/gateways/base.py's resolve_credential(gym,
provider): it filters GatewayCredential by a real Gym FK, so collecting
FitKhata's own SaaS fees through the exact same, unmodified eSewa/Khalti
gateway classes needs a real (gym) row to own those credentials against.
Fixed ids (saas/constants.py) so every environment agrees on which row this
is, without a name-based lookup.

No GatewayCredential rows are seeded here — those hold Fernet-encrypted
merchant secrets and must never be committed; set them via a management
command (or the super-admin console once built) against
FITKHATA_PLATFORM_GYM_ID in each environment.
"""

from __future__ import annotations

from django.db import migrations

from core.context import system_context
from saas.constants import FITKHATA_PLATFORM_GYM_ID, FITKHATA_PLATFORM_ORG_ID


def seed(apps, schema_editor):
    Organization = apps.get_model("gyms", "Organization")
    Gym = apps.get_model("gyms", "Gym")

    # gyms_gym carries its own RLS policy (core/migrations/0002_rls.py) —
    # inserting a gym that isn't yet in app.gym_ids (it can't be, it
    # doesn't exist yet) needs the same BYPASSRLS escape hatch runtime code
    # uses for this exact bootstrapping problem.
    with system_context():
        org, _ = Organization.objects.get_or_create(
            id=FITKHATA_PLATFORM_ORG_ID, defaults={"name": "FitKhata (platform)"}
        )
        Gym.objects.get_or_create(
            id=FITKHATA_PLATFORM_GYM_ID,
            defaults={"org": org, "code": "FITKHATA-HQ", "name": "FitKhata Platform"},
        )


def unseed(apps, schema_editor):
    Gym = apps.get_model("gyms", "Gym")
    Organization = apps.get_model("gyms", "Organization")
    with system_context():
        Gym.objects.filter(id=FITKHATA_PLATFORM_GYM_ID).delete()
        Organization.objects.filter(id=FITKHATA_PLATFORM_ORG_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("saas", "0002_seed_plans"),
        ("gyms", "0002_organization_vat_inclusive_pricing"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
