"""Read-only models over the *_scoped views created by the mv_* migrations
(reports/migrations/0001-0004) — managed=False since Django doesn't own
these tables' schema at all, the RunSQL migrations do. Not RLS (Postgres
disallows RLS on materialized views) — see 0001_mv_daily_revenue.py's
docstring for what the _scoped views actually do instead.
"""

from __future__ import annotations

from django.db import models


class MVDailyRevenue(models.Model):
    # The view exposes row_number() OVER () as id — these rows are never
    # created/updated/deleted via the ORM, so a per-query row number is a
    # fine stand-in for a real PK (Django's ORM requires one per model).
    id = models.BigIntegerField(primary_key=True)
    gym_id = models.UUIDField()
    day = models.DateField()
    mode = models.CharField(max_length=20)
    plan_id = models.UUIDField(null=True)
    staff_id = models.UUIDField(null=True)
    amount_npr = models.DecimalField(max_digits=12, decimal_places=2)
    payment_count = models.IntegerField()

    class Meta:
        managed = False
        db_table = "mv_daily_revenue_scoped"


class MVMembershipFlow(models.Model):
    id = models.BigIntegerField(primary_key=True)
    gym_id = models.UUIDField()
    day = models.DateField()
    new_count = models.IntegerField()
    renewed_count = models.IntegerField()
    expired_count = models.IntegerField()
    churned_count = models.IntegerField()

    class Meta:
        managed = False
        db_table = "mv_membership_flow_scoped"


class MVAttendanceHourly(models.Model):
    id = models.BigIntegerField(primary_key=True)
    gym_id = models.UUIDField()
    weekday = models.IntegerField()  # 0=Monday .. 6=Sunday
    hour = models.IntegerField()
    count = models.IntegerField()

    class Meta:
        managed = False
        db_table = "mv_attendance_hourly_scoped"


class MVCohortRetention(models.Model):
    id = models.BigIntegerField(primary_key=True)
    gym_id = models.UUIDField()
    join_month = models.DateField()
    cohort_size = models.IntegerField()
    retained_m1 = models.IntegerField()
    retained_m3 = models.IntegerField()
    retained_m6 = models.IntegerField()
    retained_m12 = models.IntegerField()

    class Meta:
        managed = False
        db_table = "mv_cohort_retention_scoped"
