"""mv_attendance_hourly(gym_id, weekday, hour, count) — weekday is 0=Monday
.. 6=Sunday (matches staff.models.ShiftTemplate.WEEKDAY_CHOICES), computed
in Asia/Kathmandu local time. See reports/migrations/0001 for the
scoped-view (not RLS) pattern.
"""

from __future__ import annotations

from django.db import migrations

CREATE_SQL = """
CREATE MATERIALIZED VIEW mv_attendance_hourly AS
SELECT
    gym_id,
    (EXTRACT(ISODOW FROM (check_in_at AT TIME ZONE 'Asia/Kathmandu'))::int - 1) AS weekday,
    EXTRACT(HOUR FROM (check_in_at AT TIME ZONE 'Asia/Kathmandu'))::int AS hour,
    COUNT(*) AS count
FROM attendance_attendance
GROUP BY gym_id, weekday, hour;

CREATE INDEX mv_attendance_hourly_gym_idx ON mv_attendance_hourly (gym_id);

-- See reports/migrations/0001_mv_daily_revenue.py's docstring for why.
ALTER MATERIALIZED VIEW mv_attendance_hourly OWNER TO fitkhata_system;
GRANT SELECT ON mv_attendance_hourly TO fitkhata_app;

CREATE VIEW mv_attendance_hourly_scoped AS
SELECT row_number() OVER () AS id, *
FROM mv_attendance_hourly WHERE gym_id = ANY (app_gym_ids());
"""

DROP_SQL = """
DROP VIEW IF EXISTS mv_attendance_hourly_scoped;
DROP MATERIALIZED VIEW IF EXISTS mv_attendance_hourly;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0002_mv_membership_flow"),
        ("attendance", "0004_partition_schedule"),
    ]

    operations = [
        migrations.RunSQL(CREATE_SQL, reverse_sql=DROP_SQL),
    ]
