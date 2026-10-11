from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest import mock

import pytest
from django.db import connection

from attendance.services import register_gate_device
from attendance.tasks import (
    _month_bounds,
    alert_offline_gate_devices,
    create_next_month_partition_task,
)
from core.context import system_context
from gyms.models import Gym, Organization

pytestmark = pytest.mark.django_db


def test_month_bounds_mid_year():
    assert _month_bounds(date(2026, 10, 15)) == (date(2026, 10, 1), date(2026, 11, 1))


def test_month_bounds_december_wraps_to_next_year():
    assert _month_bounds(date(2026, 12, 1)) == (date(2026, 12, 1), date(2027, 1, 1))


def _partition_exists(table_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s) IS NOT NULL", [table_name])
        (exists,) = cursor.fetchone()
    return bool(exists)


def test_creates_next_months_partition():
    with mock.patch("attendance.tasks.date") as mock_date:
        mock_date.today.return_value = date(2026, 10, 4)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        table_name = create_next_month_partition_task()

    assert table_name == "attendance_attendance_y2026m11"
    assert _partition_exists(table_name)

    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")  # noqa: S608 — fixed, test-only


@pytest.fixture
def gym_with_owner():
    with system_context():
        from accounts.models import StaffRole, User

        org = Organization.objects.create(name="Offline Alert Org")
        gym = Gym.objects.create(org=org, code="OFF1", name="Offline Alert Gym")
        owner = User.objects.create_user(phone="+9779811111111", password="x")
        StaffRole.objects.create(org=org, gym=gym, user=owner, role=StaffRole.Role.OWNER)
        return gym


class _FakeRedis:
    """Mimics redis-py's SET NX EX for the dedupe key, nothing else."""

    def __init__(self):
        self.keys: dict[str, bool] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return False
        self.keys[key] = True
        return True


def test_alert_offline_gate_devices_notifies_managers(gym_with_owner):
    with system_context():
        device, _ = register_gate_device(gym_with_owner, "Front Gate")
        device.last_seen_at = datetime.now(tz=UTC) - timedelta(minutes=20)
        device.save(update_fields=["last_seen_at"])

    fake_redis = _FakeRedis()
    with (
        mock.patch("attendance.tasks.redis.from_url", return_value=fake_redis),
        mock.patch("accounts.sms.get_sms_provider") as mock_get_provider,
    ):
        mock_provider = mock.Mock()
        mock_get_provider.return_value = mock_provider
        alerted_count = alert_offline_gate_devices()

    assert alerted_count == 1
    mock_provider.send.assert_called_once()
    (sent_phone, sent_text), _ = mock_provider.send.call_args
    assert sent_phone == "+9779811111111"
    assert "Front Gate" in sent_text


def test_alert_offline_gate_devices_does_not_realert_within_ttl(gym_with_owner):
    with system_context():
        device, _ = register_gate_device(gym_with_owner, "Front Gate")
        device.last_seen_at = datetime.now(tz=UTC) - timedelta(minutes=20)
        device.save(update_fields=["last_seen_at"])

    fake_redis = _FakeRedis()
    with (
        mock.patch("attendance.tasks.redis.from_url", return_value=fake_redis),
        mock.patch("accounts.sms.get_sms_provider") as mock_get_provider,
    ):
        mock_get_provider.return_value = mock.Mock()
        first_run = alert_offline_gate_devices()
        second_run = alert_offline_gate_devices()

    assert first_run == 1
    assert second_run == 0


def test_is_idempotent_if_partition_already_exists():
    with mock.patch("attendance.tasks.date") as mock_date:
        mock_date.today.return_value = date(2026, 10, 4)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        table_name = create_next_month_partition_task()
        # Running it again must not raise (CREATE TABLE IF NOT EXISTS).
        table_name_again = create_next_month_partition_task()

    assert table_name == table_name_again

    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")  # noqa: S608 — fixed, test-only
