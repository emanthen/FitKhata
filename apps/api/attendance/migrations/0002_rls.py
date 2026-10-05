"""RLS for attendance tables. GateDevice and the Attendance parent get the
standard app_gym_ids() policy (core/0002_rls.py). Each Attendance *partition*
also gets RLS explicitly enabled+forced: Postgres only guarantees a parent's
policy is enforced for queries that go through the parent name (which is all
the ORM ever does) — a direct query against a partition table name bypasses
that unless the partition itself also has RLS enabled (it then automatically
uses the parent's inherited policy, no separate CREATE POLICY needed per
partition). Defense in depth, matching this codebase's two-layers-of-
isolation standard elsewhere.
"""

from __future__ import annotations

from django.db import migrations

GYM_SCOPED_TABLES = ["attendance_gatedevice", "attendance_attendance"]

INITIAL_PARTITIONS = [
    "attendance_attendance_y2026m09",
    "attendance_attendance_y2026m10",
    "attendance_attendance_y2026m11",
    "attendance_attendance_y2026m12",
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


def _partition_rls_sql(table: str) -> str:
    # No CREATE POLICY here — partitions inherit the parent's policy once
    # RLS is enabled+forced on them.
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
"""


def _drop_partition_rls_sql(table: str) -> str:
    return f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;\n"


RLS_SQL = "\n".join(_rls_sql(t) for t in GYM_SCOPED_TABLES) + "\n".join(
    _partition_rls_sql(t) for t in INITIAL_PARTITIONS
)
DROP_RLS_SQL = "\n".join(_drop_rls_sql(t) for t in GYM_SCOPED_TABLES) + "\n".join(
    _drop_partition_rls_sql(t) for t in INITIAL_PARTITIONS
)


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0001_initial"),
        ("core", "0002_rls"),  # app_gym_ids()
    ]

    operations = [
        migrations.RunSQL(RLS_SQL, reverse_sql=DROP_RLS_SQL),
    ]
