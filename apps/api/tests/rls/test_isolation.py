"""RLS isolation, for every tenant-scoped model. CLAUDE.md rule 2b.

Two kinds of test here:
1. Per-model isolation: a session scoped to Gym A sees 0 Gym B rows, via the
   ORM *and* raw SQL — proving Postgres itself enforces this, not just
   Django's query filtering.
2. A generic policy-coverage check that introspects pg_class/pg_policies for
   *every* model with a `gym` field (or Gym itself), so a future tenant model
   added without an RLS policy fails CI automatically instead of silently
   leaking data.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from django.apps import apps
from django.db import connection

from accounts.models import StaffRole, User
from attendance.models import Attendance, GateDevice
from core.context import system_context
from core.models import AuditLog
from gyms.models import Gym, Organization
from members.models import Member

pytestmark = [pytest.mark.rls, pytest.mark.django_db]

# Our own apps — third-party apps (admin, auth, token_blacklist, otp_totp,
# django_celery_beat, ...) are deliberately excluded; add a new app here when
# it's added to INSTALLED_APPS and might grow a gym-scoped model.
OUR_APP_LABELS = {
    "core",
    "accounts",
    "gyms",
    "members",
    "attendance",
    "billing",
    "retention",
    "notifications",
    "coaching",
    "staff",
    "reports",
    "saas",
}


def _set_session(*, user_id: object = None, gym_id: object = None) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.user_id', %s, true)", [str(user_id) if user_id else ""]
        )
        cursor.execute(
            "SELECT set_config('app.gym_ids', %s, true)", [str(gym_id) if gym_id else ""]
        )


@pytest.fixture
def tenants():
    """Two fully separate orgs/gyms/users/data, created under
    system_context() since nothing in app.gym_ids exists yet to create into —
    the same bootstrapping problem onboarding and TenantMiddleware have."""
    with system_context():
        org_a = Organization.objects.create(name="Org A")
        org_b = Organization.objects.create(name="Org B")
        gym_a = Gym.objects.create(org=org_a, code="A1", name="Gym A")
        gym_b = Gym.objects.create(org=org_b, code="B1", name="Gym B")
        user_a = User.objects.create_user(phone="+9771000000001", password="x")
        user_b = User.objects.create_user(phone="+9771000000002", password="x")
        role_a = StaffRole.objects.create(
            user=user_a, org=org_a, gym=gym_a, role=StaffRole.Role.OWNER
        )
        role_b = StaffRole.objects.create(
            user=user_b, org=org_b, gym=gym_b, role=StaffRole.Role.OWNER
        )
        log_a = AuditLog.objects.create(
            org=org_a, gym=gym_a, table_name="x", row_id="1", action=AuditLog.Action.CREATE
        )
        log_b = AuditLog.objects.create(
            org=org_b, gym=gym_b, table_name="x", row_id="1", action=AuditLog.Action.CREATE
        )
    return {
        "org_a": org_a,
        "org_b": org_b,
        "gym_a": gym_a,
        "gym_b": gym_b,
        "user_a": user_a,
        "user_b": user_b,
        "role_a": role_a,
        "role_b": role_b,
        "log_a": log_a,
        "log_b": log_b,
    }


def _raw_ids(table: str, id_column: str = "id") -> set:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {id_column} FROM {table}")  # noqa: S608 — fixed, test-only
        return {row[0] for row in cursor.fetchall()}


class TestGymIsolation:
    def test_orm(self, tenants):
        _set_session(user_id=tenants["user_a"].id, gym_id=tenants["gym_a"].id)
        assert set(Gym.objects.values_list("id", flat=True)) == {tenants["gym_a"].id}

    def test_raw_sql(self, tenants):
        _set_session(user_id=tenants["user_a"].id, gym_id=tenants["gym_a"].id)
        assert _raw_ids("gyms_gym") == {tenants["gym_a"].id}


class TestStaffRoleIsolation:
    def test_orm(self, tenants):
        _set_session(user_id=tenants["user_a"].id, gym_id=tenants["gym_a"].id)
        assert set(StaffRole.objects.values_list("id", flat=True)) == {tenants["role_a"].id}

    def test_raw_sql(self, tenants):
        _set_session(user_id=tenants["user_a"].id, gym_id=tenants["gym_a"].id)
        assert _raw_ids("accounts_staffrole") == {tenants["role_a"].id}

    def test_own_row_visible_without_a_gym_selected(self, tenants):
        """Powers /gyms/mine-adjacent self-lookups: your own StaffRole row
        is visible even with no gym in app.gym_ids, via app.user_id."""
        _set_session(user_id=tenants["user_a"].id, gym_id=None)
        assert set(StaffRole.objects.values_list("id", flat=True)) == {tenants["role_a"].id}


class TestAuditLogIsolation:
    def test_orm(self, tenants):
        _set_session(user_id=tenants["user_a"].id, gym_id=tenants["gym_a"].id)
        assert set(AuditLog.objects.values_list("id", flat=True)) == {tenants["log_a"].id}

    def test_raw_sql(self, tenants):
        _set_session(user_id=tenants["user_a"].id, gym_id=tenants["gym_a"].id)
        assert _raw_ids("core_auditlog") == {tenants["log_a"].id}

    def test_append_only_trigger_blocks_update(self, tenants):
        # pytest.raises must be the OUTER context manager: if it were inner,
        # it would swallow the exception before system_context()'s
        # transaction.atomic() sees it, and atomic() would then try to COMMIT
        # a transaction Postgres already aborted — a confusing second error.
        with pytest.raises(Exception, match="append-only"), system_context():
            AuditLog.objects.filter(pk=tenants["log_a"].pk).update(action=AuditLog.Action.VOID)

    def test_append_only_trigger_blocks_delete(self, tenants):
        with pytest.raises(Exception, match="append-only"), system_context():
            tenants["log_a"].delete()


@pytest.fixture
def attendance_tenants(tenants):
    """Extends `tenants` with a Member + Attendance row per gym — the
    partitioned table is exactly the thing worth checking behaviorally, not
    just via the generic schema-level policy-coverage test.
    """
    with system_context():
        member_a = Member.objects.create(
            org=tenants["org_a"],
            gym=tenants["gym_a"],
            member_code="A-0001",
            full_name="Member A",
            phone="+9771000000011",
            qr_secret=os.urandom(32),
        )
        member_b = Member.objects.create(
            org=tenants["org_b"],
            gym=tenants["gym_b"],
            member_code="B-0001",
            full_name="Member B",
            phone="+9771000000012",
            qr_secret=os.urandom(32),
        )
        check_in_a = Attendance.objects.create(
            org=tenants["org_a"],
            gym=tenants["gym_a"],
            member=member_a,
            check_in_at=datetime(2026, 10, 4, 10, 0, tzinfo=UTC),
            source=Attendance.Source.QR_GATE,
            client_uuid=uuid.uuid4(),
        )
        check_in_b = Attendance.objects.create(
            org=tenants["org_b"],
            gym=tenants["gym_b"],
            member=member_b,
            check_in_at=datetime(2026, 10, 4, 10, 0, tzinfo=UTC),
            source=Attendance.Source.QR_GATE,
            client_uuid=uuid.uuid4(),
        )
        device_a = GateDevice.objects.create(
            org=tenants["org_a"], gym=tenants["gym_a"], name="Gate A", device_key_hash="a" * 64
        )
        device_b = GateDevice.objects.create(
            org=tenants["org_b"], gym=tenants["gym_b"], name="Gate B", device_key_hash="b" * 64
        )
    return {
        **tenants,
        "check_in_a": check_in_a,
        "check_in_b": check_in_b,
        "device_a": device_a,
        "device_b": device_b,
    }


class TestAttendanceIsolation:
    """Attendance is partitioned (attendance/migrations/0001_initial.py) —
    confirms RLS is actually enforced through the parent table's query
    routing to partitions, not just present in the schema.
    """

    def test_orm(self, attendance_tenants):
        _set_session(
            user_id=attendance_tenants["user_a"].id, gym_id=attendance_tenants["gym_a"].id
        )
        assert set(Attendance.objects.values_list("id", flat=True)) == {
            attendance_tenants["check_in_a"].id
        }

    def test_raw_sql(self, attendance_tenants):
        _set_session(
            user_id=attendance_tenants["user_a"].id, gym_id=attendance_tenants["gym_a"].id
        )
        assert _raw_ids("attendance_attendance") == {attendance_tenants["check_in_a"].id}

    def test_direct_partition_access_is_not_rls_scoped(self, attendance_tenants):
        """Documents a real, deliberate boundary (see
        attendance/migrations/0003_fix_partition_rls.py): a partition only
        evaluates RLS policies defined on itself, which this codebase
        doesn't define — so querying a partition's own table name directly
        sees every gym's rows, not just the current session's. This is not
        a path the application ever takes (the ORM and every view only ever
        reference the parent `attendance_attendance`, which *is* correctly
        scoped — see test_orm/test_raw_sql above); this test exists so a
        future change doesn't "fix" this by accident into the broken
        enabled-but-policy-less state 0003 moved away from.
        """
        _set_session(
            user_id=attendance_tenants["user_a"].id, gym_id=attendance_tenants["gym_a"].id
        )
        assert _raw_ids("attendance_attendance_y2026m10") == {
            attendance_tenants["check_in_a"].id,
            attendance_tenants["check_in_b"].id,
        }


class TestGateDeviceIsolation:
    def test_orm(self, attendance_tenants):
        _set_session(
            user_id=attendance_tenants["user_a"].id, gym_id=attendance_tenants["gym_a"].id
        )
        assert set(GateDevice.objects.values_list("id", flat=True)) == {
            attendance_tenants["device_a"].id
        }

    def test_raw_sql(self, attendance_tenants):
        _set_session(
            user_id=attendance_tenants["user_a"].id, gym_id=attendance_tenants["gym_a"].id
        )
        assert _raw_ids("attendance_gatedevice") == {attendance_tenants["device_a"].id}


def test_no_gym_selected_sees_nothing(tenants):
    """Empty app.gym_ids (no X-Gym-Id header resolved) denies everything
    gym_id-scoped — the NULLIF guard in app_gym_ids() turning an unset
    session var into NULL, not an empty-string cast error."""
    _set_session(user_id=None, gym_id=None)
    assert Gym.objects.count() == 0
    assert AuditLog.objects.count() == 0


def _tenant_models() -> list[type]:
    models = []
    for model in apps.get_models():
        if model._meta.app_label not in OUR_APP_LABELS:
            continue
        field_names = {f.name for f in model._meta.get_fields()}
        if model is Gym or "gym" in field_names:
            models.append(model)
    return models


def test_every_tenant_model_has_rls_policy():
    """The safety net: fails CI if a new gym-scoped model ships without RLS
    enabled, forced, and at least one policy — introspects Postgres directly
    rather than trusting Django model declarations."""
    tenant_models = _tenant_models()
    assert tenant_models, "no tenant models found — OUR_APP_LABELS or the gym-field check is wrong"

    with connection.cursor() as cursor:
        for model in tenant_models:
            table = model._meta.db_table
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
                [table],
            )
            row = cursor.fetchone()
            assert row is not None, f"{table}: table not found in pg_class"
            enabled, forced = row
            assert enabled, f"{table}: RLS is not ENABLEd — add a RunSQL migration"
            assert forced, f"{table}: RLS is not FORCEd — table owner would bypass it"

            cursor.execute("SELECT count(*) FROM pg_policies WHERE tablename = %s", [table])
            (policy_count,) = cursor.fetchone()
            assert policy_count > 0, f"{table}: RLS enabled but no policy defined"
