"""Organization.saas_plan/saas_status predate Phase 11, were unused by any
logic (read-only in OrganizationSerializer), and don't fit the richer
status machine saas.Subscription now owns — removed in favor of a single
source of truth rather than carrying two parallel, driftable concepts.
"""

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("gyms", "0002_organization_vat_inclusive_pricing"),
        ("saas", "0003_seed_fitkhata_platform_gym"),
    ]

    operations = [
        migrations.RemoveField(model_name="organization", name="saas_plan"),
        migrations.RemoveField(model_name="organization", name="saas_status"),
    ]
