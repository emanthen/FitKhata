"""mv_membership_flow(gym_id, day, new_count, renewed_count, expired_count,
churned_count). See reports/migrations/0001 for the scoped-view (not RLS)
pattern this reuses.

Definitions (no FR gave these, so this codebase defines them):
- new/renewed: a Membership row is "new" if the member had no earlier one,
  "renewed" otherwise — same check sell_membership() itself makes.
- expired: status='expired', bucketed by expiry_date (the day it lapsed,
  from retention.tasks.expire_memberships' nightly run).
- churned: an expired membership with no newer covering membership, once
  warning_days (gym.settings, default 7) have passed since expiry. The most
  recent warning_days of any window will under-count churn because that
  grace period hasn't elapsed yet — a real consequence of attributing churn
  this way, not a bug.
"""

from __future__ import annotations

from django.db import migrations

CREATE_SQL = """
CREATE MATERIALIZED VIEW mv_membership_flow AS
WITH events AS (
    SELECT
        mm.gym_id,
        (mm.created_at AT TIME ZONE 'Asia/Kathmandu')::date AS day,
        CASE WHEN EXISTS (
            SELECT 1 FROM members_membership earlier
            WHERE earlier.member_id = mm.member_id AND earlier.created_at < mm.created_at
        ) THEN 'renewed' ELSE 'new' END AS kind
    FROM members_membership mm

    UNION ALL

    SELECT gym_id, expiry_date AS day, 'expired' AS kind
    FROM members_membership
    WHERE status = 'expired'

    UNION ALL

    SELECT m.gym_id, m.expiry_date AS day, 'churned' AS kind
    FROM members_membership m
    JOIN gyms_gym g ON g.id = m.gym_id
    WHERE m.status = 'expired'
      AND CURRENT_DATE - m.expiry_date >= COALESCE((g.settings->>'warning_days')::int, 7)
      AND NOT EXISTS (
          SELECT 1 FROM members_membership newer
          WHERE newer.member_id = m.member_id AND newer.expiry_date > m.expiry_date
      )
)
SELECT
    gym_id,
    day,
    COUNT(*) FILTER (WHERE kind = 'new') AS new_count,
    COUNT(*) FILTER (WHERE kind = 'renewed') AS renewed_count,
    COUNT(*) FILTER (WHERE kind = 'expired') AS expired_count,
    COUNT(*) FILTER (WHERE kind = 'churned') AS churned_count
FROM events
GROUP BY gym_id, day;

CREATE INDEX mv_membership_flow_gym_idx ON mv_membership_flow (gym_id);

-- See reports/migrations/0001_mv_daily_revenue.py's docstring for why.
ALTER MATERIALIZED VIEW mv_membership_flow OWNER TO fitkhata_system;
GRANT SELECT ON mv_membership_flow TO fitkhata_app;

CREATE VIEW mv_membership_flow_scoped AS
SELECT row_number() OVER () AS id, *
FROM mv_membership_flow WHERE gym_id = ANY (app_gym_ids());
"""

DROP_SQL = """
DROP VIEW IF EXISTS mv_membership_flow_scoped;
DROP MATERIALIZED VIEW IF EXISTS mv_membership_flow;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0001_mv_daily_revenue"),
    ]

    operations = [
        migrations.RunSQL(CREATE_SQL, reverse_sql=DROP_SQL),
    ]
