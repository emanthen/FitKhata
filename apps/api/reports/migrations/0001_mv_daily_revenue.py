"""mv_daily_revenue(gym_id, day, mode, plan_id, staff_id, amount_npr,
payment_count) — completed payments, grouped by Kathmandu calendar day.
plan_id comes from the payment's invoice's membership row when one exists
(add-on-only sales have no linked membership, hence the LEFT JOIN).

Not RLS (Postgres has no RLS on materialized views) — mv_daily_revenue_scoped
is a plain VIEW whose WHERE clause calls the same app_gym_ids() function
every real RLS policy uses (core/migrations/0002_rls.py). That STABLE
function re-evaluates per query, not once at view-creation time, so this
gives the same per-request tenant-isolation guarantee as a real RLS policy —
just a view predicate, since Postgres allows nothing else on a materialized
view. This is NOT RLS: no pg_policies row exists for it.

Plain REFRESH (not CONCURRENTLY) — ponytail: a brief read lock on a small
per-gym aggregate during a 15-minute refresh is fine; add CONCURRENTLY (and
the unique index it requires) only if that lock is ever actually observed
to matter.

REFRESH MATERIALIZED VIEW needs two things from whichever role runs it:
ownership of the MV (Postgres requires it — no partial "refresh" grant
exists) AND bypass of the source tables' RLS (every one of them has FORCE
ROW LEVEL SECURITY, which applies even to a table's own owner — confirmed
empirically, not assumed). No single role gets both for free here:
fitkhata_system has BYPASSRLS but, in this environment, migrations run as
fitkhata_app (RUNBOOK.md's "migrate as fitkhata_system" is a *prod*
practice, not guaranteed locally), so fitkhata_app — not fitkhata_system —
ends up owning anything a migration creates; and BYPASSRLS itself does
NOT inherit through role membership in Postgres (only ordinary GRANTed
privileges do), so fitkhata_app being a member of fitkhata_system doesn't
help either. Transferring ownership explicitly is the fix, so
reports.tasks.refresh_* can run entirely as fitkhata_system (own + bypass)
regardless of which role actually ran `migrate`:

ALTER MATERIALIZED VIEW ... OWNER TO fitkhata_system itself needs the
*new* owner to already have CREATE on the containing schema — fitkhata_app
has that on `public` only because it owns the whole database (ALTER
DATABASE fitkhata OWNER TO fitkhata_app, infra/initdb/001-app-roles.sql),
which makes it public's effective owner via pg_database_owner; granting
that same CREATE to fitkhata_system once (here) is what makes every
ALTER OWNER below possible. The GRANT SELECT back to fitkhata_app exists
because the _scoped view (created by fitkhata_app) checks its own owner's
privilege on the underlying MV, not the querying session's — without it,
fitkhata_app would lose its own (previously-implicit, owner-only) SELECT
the moment ownership moves away.
"""

from __future__ import annotations

from django.db import migrations

CREATE_SQL = """
CREATE MATERIALIZED VIEW mv_daily_revenue AS
SELECT
    p.gym_id,
    (p.created_at AT TIME ZONE 'Asia/Kathmandu')::date AS day,
    p.mode,
    mm.plan_id,
    p.collected_by_id AS staff_id,
    SUM(p.amount_npr) AS amount_npr,
    COUNT(*) AS payment_count
FROM billing_payment p
LEFT JOIN members_membership mm ON mm.invoice_id = p.invoice_id
WHERE p.status = 'completed'
GROUP BY p.gym_id, day, p.mode, mm.plan_id, p.collected_by_id;

CREATE INDEX mv_daily_revenue_gym_idx ON mv_daily_revenue (gym_id);

-- Once per schema, not once per MV — covers 0002-0004's ALTER OWNER too.
GRANT CREATE ON SCHEMA public TO fitkhata_system;
ALTER MATERIALIZED VIEW mv_daily_revenue OWNER TO fitkhata_system;
GRANT SELECT ON mv_daily_revenue TO fitkhata_app;

CREATE VIEW mv_daily_revenue_scoped AS
SELECT row_number() OVER () AS id, *
FROM mv_daily_revenue WHERE gym_id = ANY (app_gym_ids());
"""

DROP_SQL = """
DROP VIEW IF EXISTS mv_daily_revenue_scoped;
DROP MATERIALIZED VIEW IF EXISTS mv_daily_revenue;
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0002_rls"),  # app_gym_ids()
        ("billing", "0007_pending_payment_reverification_schedule"),
        ("members", "0007_memberfeedback_rls"),
    ]

    operations = [
        migrations.RunSQL(CREATE_SQL, reverse_sql=DROP_SQL),
    ]
