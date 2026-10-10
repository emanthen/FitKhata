"""mv_cohort_retention(gym_id, join_month, cohort_size, retained_m1,
retained_m3, retained_m6, retained_m12) — join_month is the member's
created_at truncated to month (no separate "joined_on" field exists);
retained_mN counts cohort members with a Membership row covering
join_month + N months. Fractions are computed at read time (count /
cohort_size), not stored, to dodge divide-by-zero in SQL.
"""

from __future__ import annotations

from django.db import migrations

CREATE_SQL = """
CREATE MATERIALIZED VIEW mv_cohort_retention AS
WITH cohorts AS (
    SELECT id AS member_id, gym_id,
           date_trunc('month', created_at AT TIME ZONE 'Asia/Kathmandu')::date AS join_month
    FROM members_member
)
SELECT
    c.gym_id,
    c.join_month,
    COUNT(*) AS cohort_size,
    COUNT(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM members_membership mm WHERE mm.member_id = c.member_id
        AND mm.start_date <= (c.join_month + interval '1 month')::date
        AND mm.expiry_date >= (c.join_month + interval '1 month')::date
    )) AS retained_m1,
    COUNT(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM members_membership mm WHERE mm.member_id = c.member_id
        AND mm.start_date <= (c.join_month + interval '3 month')::date
        AND mm.expiry_date >= (c.join_month + interval '3 month')::date
    )) AS retained_m3,
    COUNT(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM members_membership mm WHERE mm.member_id = c.member_id
        AND mm.start_date <= (c.join_month + interval '6 month')::date
        AND mm.expiry_date >= (c.join_month + interval '6 month')::date
    )) AS retained_m6,
    COUNT(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM members_membership mm WHERE mm.member_id = c.member_id
        AND mm.start_date <= (c.join_month + interval '12 month')::date
        AND mm.expiry_date >= (c.join_month + interval '12 month')::date
    )) AS retained_m12
FROM cohorts c
GROUP BY c.gym_id, c.join_month;

CREATE INDEX mv_cohort_retention_gym_idx ON mv_cohort_retention (gym_id);

-- See reports/migrations/0001_mv_daily_revenue.py's docstring for why.
ALTER MATERIALIZED VIEW mv_cohort_retention OWNER TO fitkhata_system;
GRANT SELECT ON mv_cohort_retention TO fitkhata_app;

CREATE VIEW mv_cohort_retention_scoped AS
SELECT row_number() OVER () AS id, *
FROM mv_cohort_retention WHERE gym_id = ANY (app_gym_ids());
"""

DROP_SQL = """
DROP VIEW IF EXISTS mv_cohort_retention_scoped;
DROP MATERIALIZED VIEW IF EXISTS mv_cohort_retention;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0003_mv_attendance_hourly"),
    ]

    operations = [
        migrations.RunSQL(CREATE_SQL, reverse_sql=DROP_SQL),
    ]
