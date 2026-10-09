"""RLS for Phase 5's new gym-scoped retention tables -- same app_gym_ids()
policy shape as billing/migrations/0005_rls.py; all four are plain
TenantModel subclasses.
"""

from __future__ import annotations

from django.db import migrations

GYM_SCOPED_TABLES = [
    "retention_riskstatechange",
    "retention_retentioncall",
    "retention_membershipfreeze",
    "retention_campaign",
]


def _rls_sql(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_{table} ON {table}
    USING (gym_id = ANY (app_gym_ids()));
"""


def _drop_rls_sql(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


RLS_SQL = "\n".join(_rls_sql(t) for t in GYM_SCOPED_TABLES)
DROP_RLS_SQL = "\n".join(_drop_rls_sql(t) for t in GYM_SCOPED_TABLES)


class Migration(migrations.Migration):
    dependencies = [
        ("retention", "0001_initial"),
        ("core", "0002_rls"),  # app_gym_ids()
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
