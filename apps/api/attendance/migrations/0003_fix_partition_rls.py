"""0002_rls.py enabled+forced RLS on each Attendance partition directly,
assuming a partition "inherits" the parent's policy. It doesn't: a
partition only evaluates policies defined *on itself*. With FORCE ROW
LEVEL SECURITY enabled and zero policies attached, Postgres defaults to
denying all rows — proven by tests.rls.test_isolation's
test_raw_sql_against_partition_directly, which got back an empty set even
for its own gym's session.

In practice this didn't affect the application: Django's ORM (and every
other query path in this codebase) only ever references the parent table
name `attendance_attendance`; Postgres evaluates RLS against the table
actually named in the query and only routes to partitions internally
*after* that, so the parent's policy (0002_rls.py, still correct) was
always what governed real access. The partition-level ENABLE/FORCE here
was dead and misleading at best — direct access to a partition's own table
name is not a path the application uses, and "protecting" it would mean
duplicating the policy on every partition the monthly Celery Beat task
creates forever, for a trust boundary (raw SQL against an internal
partition name) that's already outside what RLS is relied on for elsewhere
in this codebase. Simplest correct fix: just disable RLS on the partitions
again, matching how they'd exist with no special handling at all.
"""

from __future__ import annotations

from django.db import migrations

PARTITIONS = [
    "attendance_attendance_y2026m09",
    "attendance_attendance_y2026m10",
    "attendance_attendance_y2026m11",
    "attendance_attendance_y2026m12",
]

DISABLE_SQL = "\n".join(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;" for t in PARTITIONS)
ENABLE_SQL = "\n".join(
    f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;\nALTER TABLE {t} FORCE ROW LEVEL SECURITY;"
    for t in PARTITIONS
)


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_rls"),
    ]

    operations = [
        migrations.RunSQL(DISABLE_SQL, reverse_sql=ENABLE_SQL),
    ]
