"""Org-scoped RLS for FitKhata's own platform-level tables (saas/models.py,
notifications.SmsWallet) — defense-in-depth, not a behavior change.

These tables are deliberately plain models.Model, not TenantModel (see
saas/models.py's module docstring): they describe orgs/platform actions,
not gym-scoped tenant data, so app.gym_ids (and the existing
tenant_isolation_* policies from 0002_rls) don't apply to them directly.
Every current read/write site already wraps these in system_context()
(SET LOCAL ROLE fitkhata_system, which has BYPASSRLS) — confirmed across
the whole codebase, every Organization.objects.create call included — so
FORCE RLS here changes nothing for that code. What it adds is a DB-level
backstop against a *future* bug that queries one of these models without
system_context(): instead of silently leaking another org's SaaS invoice,
subscription, support ticket, or SMS wallet balance, the query now simply
returns nothing (RLS) rather than everything (no policy at all).

app_org_ids() derives allowed org ids from two sources, same precedent as
0002_rls's accounts_staffrole policy allowing its own gym_id IS NULL
org-wide rows: (a) the session's already-scoped gyms (app_gym_ids()), and
(b) every org the current user (app_user_id()) holds ANY StaffRole in —
gym-scoped or org-wide. (b) matters specifically for the "org exists,
first gym doesn't yet" bootstrap case: an org-wide owner (StaffRole with
gym=NULL) creating their first branch has nothing in app_gym_ids() yet
(no gym to scope to), but legitimately needs to read their own
Organization row to satisfy that create request's FK validation.
"""

from django.db import migrations

APP_ORG_IDS = """
CREATE OR REPLACE FUNCTION app_org_ids() RETURNS uuid[] AS $$
  SELECT COALESCE(ARRAY_AGG(DISTINCT org_id), ARRAY[]::uuid[]) FROM (
    SELECT org_id FROM gyms_gym WHERE id = ANY (app_gym_ids())
    UNION
    SELECT org_id FROM accounts_staffrole WHERE user_id = app_user_id()
  ) reachable_orgs
$$ LANGUAGE sql STABLE;
"""

DROP_APP_ORG_IDS = "DROP FUNCTION IF EXISTS app_org_ids();"


def _org_scoped_rls(table: str, org_column: str = "org_id") -> tuple[str, str]:
    policy = f"tenant_isolation_{table}"
    up = f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

    CREATE POLICY {policy} ON {table}
        USING ({org_column} = ANY (app_org_ids()));
    """
    down = f"""
    DROP POLICY IF EXISTS {policy} ON {table};
    ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
    """
    return up, down


ORGANIZATION_RLS = """
ALTER TABLE gyms_organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE gyms_organization FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_gyms_organization ON gyms_organization
    USING (id = ANY (app_org_ids()));
"""

DROP_ORGANIZATION_RLS = """
DROP POLICY IF EXISTS tenant_isolation_gyms_organization ON gyms_organization;
ALTER TABLE gyms_organization DISABLE ROW LEVEL SECURITY;
"""

SUBSCRIPTION_RLS, DROP_SUBSCRIPTION_RLS = _org_scoped_rls("saas_subscription")
SAASINVOICE_RLS, DROP_SAASINVOICE_RLS = _org_scoped_rls("saas_saasinvoice")
SUPPORTTICKET_RLS, DROP_SUPPORTTICKET_RLS = _org_scoped_rls("saas_supportticket")
SMSWALLET_RLS, DROP_SMSWALLET_RLS = _org_scoped_rls("notifications_smswallet")

# No direct org_id column — scoped via the parent they belong to.
SUPPORTTICKETMESSAGE_RLS = """
ALTER TABLE saas_supportticketmessage ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_supportticketmessage FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_saas_supportticketmessage ON saas_supportticketmessage
    USING (ticket_id IN (
        SELECT id FROM saas_supportticket WHERE org_id = ANY (app_org_ids())
    ));
"""

DROP_SUPPORTTICKETMESSAGE_RLS = """
DROP POLICY IF EXISTS tenant_isolation_saas_supportticketmessage ON saas_supportticketmessage;
ALTER TABLE saas_supportticketmessage DISABLE ROW LEVEL SECURITY;
"""

SMSWALLETTX_RLS = """
ALTER TABLE notifications_smswallettx ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_smswallettx FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_notifications_smswallettx ON notifications_smswallettx
    USING (wallet_id IN (
        SELECT id FROM notifications_smswallet WHERE org_id = ANY (app_org_ids())
    ));
"""

DROP_SMSWALLETTX_RLS = """
DROP POLICY IF EXISTS tenant_isolation_notifications_smswallettx ON notifications_smswallettx;
ALTER TABLE notifications_smswallettx DISABLE ROW LEVEL SECURITY;
"""

# org is nullable (several platform-only actions have none, e.g. a global
# feature-flag toggle) — those rows are system_context()-only by design,
# never org-scoped-visible, so NULL must not match ANY() ambiguity.
PLATFORMAUDITLOG_RLS = """
ALTER TABLE saas_platformauditlog ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_platformauditlog FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_saas_platformauditlog ON saas_platformauditlog
    USING (org_id IS NOT NULL AND org_id = ANY (app_org_ids()));
"""

DROP_PLATFORMAUDITLOG_RLS = """
DROP POLICY IF EXISTS tenant_isolation_saas_platformauditlog ON saas_platformauditlog;
ALTER TABLE saas_platformauditlog DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_system_role_grants"),
        ("accounts", "0001_initial"),
        ("gyms", "0003_remove_saas_fields"),
        ("saas", "0007_lead"),
        ("notifications", "0005_seed_coaching_templates"),
    ]

    operations = [
        migrations.RunSQL(sql=APP_ORG_IDS, reverse_sql=DROP_APP_ORG_IDS),
        migrations.RunSQL(sql=ORGANIZATION_RLS, reverse_sql=DROP_ORGANIZATION_RLS),
        migrations.RunSQL(sql=SUBSCRIPTION_RLS, reverse_sql=DROP_SUBSCRIPTION_RLS),
        migrations.RunSQL(sql=SAASINVOICE_RLS, reverse_sql=DROP_SAASINVOICE_RLS),
        migrations.RunSQL(sql=SUPPORTTICKET_RLS, reverse_sql=DROP_SUPPORTTICKET_RLS),
        migrations.RunSQL(
            sql=SUPPORTTICKETMESSAGE_RLS, reverse_sql=DROP_SUPPORTTICKETMESSAGE_RLS
        ),
        migrations.RunSQL(sql=SMSWALLET_RLS, reverse_sql=DROP_SMSWALLET_RLS),
        migrations.RunSQL(sql=SMSWALLETTX_RLS, reverse_sql=DROP_SMSWALLETTX_RLS),
        migrations.RunSQL(sql=PLATFORMAUDITLOG_RLS, reverse_sql=DROP_PLATFORMAUDITLOG_RLS),
    ]
