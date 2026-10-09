"""RLS for Phase 7's gym-scoped tables — same app_gym_ids() policy shape as
notifications/migrations/0002_rls.py. Exercise/FoodItem are excluded (global
catalogs, no gym_id column), same reasoning as billing's InvoiceCounter.
"""

from __future__ import annotations

from django.db import migrations

GYM_SCOPED_TABLES = [
    "coaching_clientprofile",
    "coaching_bodymeasurement",
    "coaching_bodymeasurementphoto",
    "coaching_workoutplan",
    "coaching_workoutlog",
    "coaching_dietplan",
    "coaching_dietlog",
    "coaching_ptpack",
    "coaching_ptsession",
    "coaching_classschedule",
    "coaching_classbooking",
    "coaching_trainercommission",
    "coaching_coachingreport",
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
        ("coaching", "0001_initial"),
        ("core", "0002_rls"),  # app_gym_ids()
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
