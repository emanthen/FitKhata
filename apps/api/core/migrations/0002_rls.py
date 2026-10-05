"""Row-level security for every tenant table. CLAUDE.md rule 2b: the app DB
role (fitkhata_app) is not a superuser and does not bypass RLS, so FORCE ROW
LEVEL SECURITY actually binds for it.

Two helper SQL functions keep every policy's "is the session scoped to this
row" expression in one place instead of repeating the NULLIF/string_to_array
dance per table — future tenant-model migrations should reuse app_gym_ids()/
app_user_id() rather than reinventing the expression.
"""

from django.db import migrations

HELPERS = """
CREATE OR REPLACE FUNCTION app_gym_ids() RETURNS uuid[] AS $$
  SELECT string_to_array(NULLIF(current_setting('app.gym_ids', true), ''), ',')::uuid[]
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_user_id() RETURNS uuid AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$ LANGUAGE sql STABLE;
"""

DROP_HELPERS = """
DROP FUNCTION IF EXISTS app_gym_ids();
DROP FUNCTION IF EXISTS app_user_id();
"""

# gyms_gym: a row's own id is the "gym_id" to check (it's the gym itself).
GYM_RLS = """
ALTER TABLE gyms_gym ENABLE ROW LEVEL SECURITY;
ALTER TABLE gyms_gym FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_gyms_gym ON gyms_gym
    USING (id = ANY (app_gym_ids()));
"""

DROP_GYM_RLS = """
DROP POLICY IF EXISTS tenant_isolation_gyms_gym ON gyms_gym;
ALTER TABLE gyms_gym DISABLE ROW LEVEL SECURITY;
"""

# accounts_staffrole: visible if it's scoped to the active gym, OR it's an
# org-wide role (gym IS NULL) for the org that owns the active gym, OR it's
# the caller's own row — the last clause is what lets "list my gyms" and
# login work before any gym has been selected at all.
STAFFROLE_RLS = """
ALTER TABLE accounts_staffrole ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_staffrole FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_accounts_staffrole ON accounts_staffrole
    USING (
        gym_id = ANY (app_gym_ids())
        OR (gym_id IS NULL AND org_id IN (
            SELECT org_id FROM gyms_gym WHERE id = ANY (app_gym_ids())
        ))
        OR user_id = app_user_id()
    );
"""

DROP_STAFFROLE_RLS = """
DROP POLICY IF EXISTS tenant_isolation_accounts_staffrole ON accounts_staffrole;
ALTER TABLE accounts_staffrole DISABLE ROW LEVEL SECURITY;
"""

AUDITLOG_RLS = """
ALTER TABLE core_auditlog ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_auditlog FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_core_auditlog ON core_auditlog
    USING (gym_id = ANY (app_gym_ids()));
"""

DROP_AUDITLOG_RLS = """
DROP POLICY IF EXISTS tenant_isolation_core_auditlog ON core_auditlog;
ALTER TABLE core_auditlog DISABLE ROW LEVEL SECURITY;
"""

AUDITLOG_APPEND_ONLY = """
CREATE OR REPLACE FUNCTION core_auditlog_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'core_auditlog is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER core_auditlog_append_only
    BEFORE UPDATE OR DELETE ON core_auditlog
    FOR EACH ROW EXECUTE FUNCTION core_auditlog_block_mutation();
"""

DROP_AUDITLOG_APPEND_ONLY = """
DROP TRIGGER IF EXISTS core_auditlog_append_only ON core_auditlog;
DROP FUNCTION IF EXISTS core_auditlog_block_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("gyms", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=HELPERS, reverse_sql=DROP_HELPERS),
        migrations.RunSQL(sql=GYM_RLS, reverse_sql=DROP_GYM_RLS),
        migrations.RunSQL(sql=STAFFROLE_RLS, reverse_sql=DROP_STAFFROLE_RLS),
        migrations.RunSQL(sql=AUDITLOG_RLS, reverse_sql=DROP_AUDITLOG_RLS),
        migrations.RunSQL(sql=AUDITLOG_APPEND_ONLY, reverse_sql=DROP_AUDITLOG_APPEND_ONLY),
    ]
