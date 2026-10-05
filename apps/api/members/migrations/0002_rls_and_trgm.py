"""RLS for every members-app tenant table, plus pg_trgm + the search
indexes. Uses the same policy expression as core/0002_rls.py's
app_gym_ids() helper — see that migration for why.
"""

from __future__ import annotations

from django.db import migrations

TABLES = [
    "members_member",
    "members_plan",
    "members_addon",
    "members_promocode",
    "members_promocoderedemption",
    "members_membership",
    "members_waiver",
    "members_membercodecounter",
    "members_importjob",
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


RLS_SQL = "\n".join(_rls_sql(t) for t in TABLES)
DROP_RLS_SQL = "\n".join(_drop_rls_sql(t) for t in TABLES)


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0001_initial"),
        ("core", "0002_rls"),  # app_gym_ids()
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
