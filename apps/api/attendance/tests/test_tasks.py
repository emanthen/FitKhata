from __future__ import annotations

from datetime import date
from unittest import mock

import pytest
from django.db import connection

from attendance.tasks import _month_bounds, create_next_month_partition_task

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
