"""Celery: monthly billing generation, daily dunning sweep, data export,
and deferred account anonymization. Rule 9: thin wrappers around
saas/services.py.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import timedelta

from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from accounts.models import StaffRole
from core.context import system_context
from notifications.providers import email as email_provider
from saas import services
from saas.services import ACCOUNT_DELETION_GRACE_DAYS


@shared_task
def generate_invoices() -> None:
    """FR-11.3, 01:00 Asia/Kathmandu on the 1st (saas/migrations/0004)."""
    services.generate_monthly_invoices()


@shared_task
def dunning_sweep() -> None:
    """FR-11.3, daily."""
    services.run_dunning_sweep()


def _rows_to_csv_bytes(rows: list) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


@shared_task
def export_org_data_task(org_id: str) -> None:
    """FR-11.7: zips every tenant CSV + each invoice's PDF, uploads to
    object storage, emails org owners a signed link — same
    default_storage/signed-URL pattern reports/views.py's own large-export
    path already uses. Runs well within the 24h window as a single task.
    """
    from billing.models import Invoice
    from billing.receipts import render_invoice_pdf
    from gyms.models import Organization

    with system_context():
        org = Organization.objects.get(pk=org_id)
        tables = services.export_org_data_rows(org)
        invoices = list(Invoice.objects.filter(org=org))
        owners = list(
            StaffRole.objects.filter(org=org, role=StaffRole.Role.OWNER, is_active=True)
            .select_related("user")
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, rows in tables.items():
            zf.writestr(filename, _rows_to_csv_bytes(rows))
        for invoice in invoices:
            zf.writestr(f"invoices/{invoice.number}.pdf", render_invoice_pdf(invoice))

    path = f"exports/{org_id}/fitkhata-data-export-{timezone.now():%Y%m%d%H%M%S}.zip"
    default_storage.save(path, ContentFile(buf.getvalue()))
    url = default_storage.url(path)

    for owner_role in owners:
        if owner_role.user.email:
            email_provider.send(
                owner_role.user.email,
                "Your FitKhata data export is ready",
                f"Download it here: {url}",
            )


@shared_task
def anonymize_deleted_orgs() -> None:
    """FR-11.7, daily — orgs ACCOUNT_DELETION_GRACE_DAYS past their deletion
    request, not yet anonymized.
    """
    from saas.models import Subscription

    cutoff = timezone.localdate() - timedelta(days=ACCOUNT_DELETION_GRACE_DAYS)
    with system_context():
        due = Subscription.objects.filter(
            deletion_requested_at__isnull=False,
            deletion_requested_at__lte=cutoff,
            anonymized_at__isnull=True,
        ).select_related("org")
        for sub in due:
            services.anonymize_org(sub.org)
