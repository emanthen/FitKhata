"""FR-2.8: CSV/XLSX import via Celery. CELERY_TASK_ALWAYS_EAGER=True in
config/settings/test.py runs the task synchronously here.
"""

from __future__ import annotations

import csv
import io
import time

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from core.context import system_context
from gyms.models import Gym, Organization
from members.models import ImportJob, Member
from members.tasks import import_members_task

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Import Test Org")
        return Gym.objects.create(org=org, code="IMP1", name="Import Test Gym")


def _row(full_name: str, phone: str, **extra: str) -> dict[str, str]:
    row = {"full_name": full_name, "phone": phone, "gender": "", "dob": "", "tags": ""}
    row.update(extra)
    return row


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["full_name", "phone", "gender", "dob", "tags"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def test_import_valid_rows_creates_members(gym):
    rows = [
        _row("Ram Shrestha", "+9779811000001"),
        _row("Sita Gurung", "+9779811000002"),
    ]
    file_path = default_storage.save(
        f"members/{gym.pk}/imports/test.csv", SimpleUploadedFile("test.csv", _csv_bytes(rows))
    )

    with system_context():
        job = ImportJob.objects.create(org=gym.org, gym=gym, total_rows=0)

    import_members_task(str(job.pk), str(gym.pk), file_path, "")

    with system_context():
        job.refresh_from_db()
        assert job.status == ImportJob.Status.DONE
        assert job.total_rows == 2
        assert job.success_count == 2
        assert Member.objects.filter(gym=gym).count() == 2


def test_import_invalid_rows_are_reported_not_fatal(gym):
    rows = [
        _row("Ram Shrestha", "+9779811000001"),
        _row("", "+9779811000002"),
        _row("Bad Dob", "+9779811000003", dob="not-a-date"),
    ]
    file_path = default_storage.save(
        f"members/{gym.pk}/imports/test2.csv", SimpleUploadedFile("test2.csv", _csv_bytes(rows))
    )

    with system_context():
        job = ImportJob.objects.create(org=gym.org, gym=gym, total_rows=0)

    import_members_task(str(job.pk), str(gym.pk), file_path, "")

    with system_context():
        job.refresh_from_db()
        assert job.status == ImportJob.Status.DONE
        assert job.total_rows == 3
        assert job.success_count == 1
        assert job.error_report.name

        report = job.error_report.read().decode()
        assert "full_name and phone are required" in report
        assert "dob must be" in report


def test_import_duplicate_phone_in_batch_reports_one_error(gym):
    rows = [
        _row("Ram Shrestha", "+9779811000009"),
        _row("Duplicate Phone", "+9779811000009"),
    ]
    file_path = default_storage.save(
        f"members/{gym.pk}/imports/test3.csv", SimpleUploadedFile("test3.csv", _csv_bytes(rows))
    )

    with system_context():
        job = ImportJob.objects.create(org=gym.org, gym=gym, total_rows=0)

    import_members_task(str(job.pk), str(gym.pk), file_path, "")

    with system_context():
        job.refresh_from_db()
        assert job.success_count == 1
        assert job.total_rows - job.success_count == 1


@pytest.mark.benchmark
def test_import_1000_rows_completes_under_two_minutes(gym):
    rows = [
        {
            "full_name": f"Test Member {i}",
            "phone": f"+97798{i:08d}",
            "gender": "",
            "dob": "",
            "tags": "",
        }
        for i in range(1000)
    ]
    file_path = default_storage.save(
        f"members/{gym.pk}/imports/bulk.csv", SimpleUploadedFile("bulk.csv", _csv_bytes(rows))
    )

    with system_context():
        job = ImportJob.objects.create(org=gym.org, gym=gym, total_rows=0)

    started = time.perf_counter()
    import_members_task(str(job.pk), str(gym.pk), file_path, "")
    elapsed = time.perf_counter() - started

    with system_context():
        job.refresh_from_db()
        assert job.success_count == 1000

    assert elapsed < 120, f"import took {elapsed:.1f}s, acceptance is <120s"
