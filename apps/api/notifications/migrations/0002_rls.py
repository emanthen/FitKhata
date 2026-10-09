"""RLS for Phase 6's gym-scoped tables — same app_gym_ids() policy shape as
core/migrations/0002_rls.py and billing/migrations/0005_rls.py. Template,
SmsWallet, and SmsWalletTx aren't gym-scoped (Template is a platform/org
catalog, the wallet pair is org-scoped) so they're excluded, same reasoning
as billing's InvoiceCounter being excluded from 0005_rls.py.
"""

from __future__ import annotations

from django.db import migrations

GYM_SCOPED_TABLES = [
    "notifications_notification",
    "notifications_pushsubscription",
    "notifications_broadcast",
    "notifications_announcement",
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
        ("notifications", "0001_initial"),
        ("core", "0002_rls"),  # app_gym_ids()
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
