"""RLS for members_memberfeedback -- same app_gym_ids() policy shape as
0002_rls_and_trgm.py.
"""

from __future__ import annotations

from django.db import migrations

TABLE = "members_memberfeedback"

RLS_SQL = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_{TABLE} ON {TABLE}
    USING (gym_id = ANY (app_gym_ids()));
"""

DROP_RLS_SQL = f"""
DROP POLICY IF EXISTS tenant_isolation_{TABLE} ON {TABLE};
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0006_member_referred_by"),
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
