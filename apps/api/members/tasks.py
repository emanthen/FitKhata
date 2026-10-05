"""CSV/XLSX member import (FR-2.8). Runs under an explicit tenant_context
since Celery tasks have no request to set app.gym_ids for them — rule 3.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

import openpyxl
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError

from accounts.models import User
from core.context import tenant_context
from gyms.models import Gym
from members.models import ImportJob
from members.services import register_member


def _rows_from_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _rows_from_xlsx(raw: bytes) -> list[dict[str, str]]:
    workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
    rows = []
    for raw_row in rows_iter:
        row = {
            header[i]: ("" if v is None else str(v))
            for i, v in enumerate(raw_row)
            if i < len(header)
        }
        rows.append(row)
    return rows


def _parse_row(row: dict[str, str]) -> dict[str, Any]:
    full_name = (row.get("full_name") or "").strip()
    phone = (row.get("phone") or "").strip()
    if not full_name or not phone:
        raise ValueError("full_name and phone are required")

    fields: dict[str, Any] = {"full_name": full_name, "phone": phone}

    gender = (row.get("gender") or "").strip().lower()
    if gender:
        fields["gender"] = gender

    dob_raw = (row.get("dob") or "").strip()
    if dob_raw:
        try:
            fields["dob"] = date.fromisoformat(dob_raw)
        except ValueError as exc:
            raise ValueError(f"dob must be YYYY-MM-DD, got {dob_raw!r}") from exc

    tags_raw = (row.get("tags") or "").strip()
    if tags_raw:
        fields["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

    opt_in_raw = (row.get("marketing_opt_in") or "").strip().lower()
    fields["marketing_opt_in"] = opt_in_raw in {"true", "1", "yes"}

    return fields


@shared_task
def import_members_task(job_id: str, gym_id: str, file_path: str, actor_id: str) -> None:
    with tenant_context([gym_id]):
        job = ImportJob.objects.get(pk=job_id)
        gym = Gym.objects.get(pk=gym_id)
        actor = User.objects.filter(pk=actor_id).first() if actor_id else None

        job.status = ImportJob.Status.RUNNING
        job.save(update_fields=["status"])

        with default_storage.open(file_path, "rb") as fh:
            raw = fh.read()
        rows = _rows_from_xlsx(raw) if file_path.lower().endswith(".xlsx") else _rows_from_csv(raw)

        errors: list[dict[str, str]] = []
        success_count = 0
        for line_no, row in enumerate(rows, start=2):  # row 1 is the header
            try:
                fields = _parse_row(row)
                register_member(gym, actor=actor, **fields)
                success_count += 1
            except (ValueError, IntegrityError) as exc:
                errors.append(
                    {"row": str(line_no), "phone": row.get("phone", ""), "error": str(exc)}
                )

        job.total_rows = len(rows)
        job.success_count = success_count
        job.status = ImportJob.Status.DONE
        if errors:
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=["row", "phone", "error"])
            writer.writeheader()
            writer.writerows(errors)
            job.error_report.save(
                "errors.csv", ContentFile(buffer.getvalue().encode()), save=False
            )
        job.save(update_fields=["total_rows", "success_count", "status", "error_report"])
