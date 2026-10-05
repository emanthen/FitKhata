"""RLS for the billing tables. Invoice/InvoiceLine are gym-scoped like any
other tenant table; InvoiceCounter is org-scoped (rule 8: numbering is per
org, not per branch) so it gets the same org-wide clause StaffRole's policy
uses in core/0002_rls.py, instead of app_gym_ids()'s gym_id = ANY(...).
"""

from __future__ import annotations

from django.db import migrations

GYM_SCOPED_TABLES = ["billing_invoice", "billing_invoiceline"]


def _gym_rls_sql(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_{table} ON {table}
    USING (gym_id = ANY (app_gym_ids()));
"""


def _drop_gym_rls_sql(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


COUNTER_RLS = """
ALTER TABLE billing_invoicecounter ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_invoicecounter FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_billing_invoicecounter ON billing_invoicecounter
    USING (
        org_id IN (SELECT org_id FROM gyms_gym WHERE id = ANY (app_gym_ids()))
    );
"""

DROP_COUNTER_RLS = """
DROP POLICY IF EXISTS tenant_isolation_billing_invoicecounter ON billing_invoicecounter;
ALTER TABLE billing_invoicecounter DISABLE ROW LEVEL SECURITY;
"""

RLS_SQL = "\n".join(_gym_rls_sql(t) for t in GYM_SCOPED_TABLES) + COUNTER_RLS
DROP_RLS_SQL = "\n".join(_drop_gym_rls_sql(t) for t in GYM_SCOPED_TABLES) + DROP_COUNTER_RLS


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_initial"),
        ("core", "0002_rls"),  # app_gym_ids()
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
