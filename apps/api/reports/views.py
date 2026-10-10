"""Thin read-only report endpoints (rule 9 — the real logic is all in
services.py/exporters.py). APIViews, not ViewSets: nothing here is CRUD.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsManagerOrAbove, IsOwner
from reports import exporters, services

LARGE_EXPORT_ROW_THRESHOLD = 5000
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
VAT_REGISTER_FIELDS = [
    "bill_date_bs",
    "number",
    "buyer_name",
    "buyer_pan",
    "taxable_npr",
    "vat_npr",
    "total_npr",
]


class _RangeMixin:
    def _range(self, request):
        from_ = request.query_params.get("from")
        to = request.query_params.get("to")
        calendar = request.query_params.get("calendar", "ad")
        if not from_ or not to:
            return None, None, Response({"detail": "'from' and 'to' are required."}, status=400)
        try:
            start, end = services.parse_date_range(from_, to, calendar)
        except services.InvalidReportRange as exc:
            return None, None, Response({"detail": str(exc)}, status=400)
        return start, end, None


class DashboardSummaryView(APIView):
    """FR-10's owner dashboard — one combined response (no live occupancy
    here, that's the websocket at ws/gym/<gym_id>/feed).
    """

    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        return Response(services.dashboard_summary(request.gym))


class RevenueTrendView(APIView, _RangeMixin):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        start, end, error = self._range(request)
        if error:
            return error
        return Response(services.revenue_trend(request.gym, start, end))


class PlanMixView(APIView, _RangeMixin):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        start, end, error = self._range(request)
        if error:
            return error
        return Response(services.plan_mix(request.gym, start, end))


class MembershipFlowView(APIView, _RangeMixin):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        start, end, error = self._range(request)
        if error:
            return error
        return Response(services.membership_flow(request.gym, start, end))


class AttendanceHeatmapView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        return Response(services.attendance_heatmap(request.gym))


class CohortRetentionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        return Response(services.cohort_retention(request.gym))


class DuesAgeingView(APIView):
    """FR-10.6. ?export=csv|xlsx downloads an export instead of JSON."""

    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        buckets = services.dues_ageing_report(request.gym)
        # "export", not "format" — the latter collides with DRF's reserved
        # URL_FORMAT_OVERRIDE query param (default renderers are json/api
        # only, so ?format=csv gets intercepted by content negotiation and
        # 404s via Http404 before this view ever runs).
        fmt = request.query_params.get("export")
        if not fmt:
            return Response(buckets)

        rows = [{"bucket": k, **v} for k, v in buckets.items()]
        fieldnames = ["bucket", "count", "total_npr"]
        lang = request.query_params.get("lang", "en")
        labels = exporters.DUES_AGEING_LABELS.get(lang, exporters.DUES_AGEING_LABELS["en"])
        if fmt == "csv":
            data = exporters.rows_to_csv(rows, fieldnames)
            content_type, ext = "text/csv", "csv"
        elif fmt == "xlsx":
            data = exporters.rows_to_xlsx(rows, fieldnames, labels)
            content_type, ext = XLSX_CONTENT_TYPE, "xlsx"
        else:
            return Response({"detail": "format must be 'csv' or 'xlsx'."}, status=400)

        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="dues-ageing.{ext}"'
        return response


class VatSalesRegisterView(APIView):
    """FR-10.7 — owner-only (tighter than the rest of the Reports section,
    which gates at manager).
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request):
        fiscal_year_raw = request.query_params.get("fiscal_year")
        if not fiscal_year_raw:
            return Response({"detail": "fiscal_year is required."}, status=400)
        try:
            fiscal_year = int(fiscal_year_raw)
        except ValueError:
            return Response({"detail": "fiscal_year must be an integer BS year."}, status=400)

        register = services.vat_sales_register(request.gym, fiscal_year)
        fmt = request.query_params.get("export")  # see DuesAgeingView.get on "export" vs "format"
        if not fmt:
            return Response(register)

        rows = register["rows"]
        fieldnames = VAT_REGISTER_FIELDS
        if len(rows) > LARGE_EXPORT_ROW_THRESHOLD:
            return self._queue_large_export(request, fiscal_year, register, fmt)

        lang = request.query_params.get("lang", "en")
        labels = exporters.VAT_REGISTER_LABELS.get(lang, exporters.VAT_REGISTER_LABELS["en"])
        if fmt == "csv":
            data = exporters.rows_to_csv(rows, fieldnames)
            content_type, ext = "text/csv", "csv"
        elif fmt == "xlsx":
            data = exporters.rows_to_xlsx(rows, fieldnames, labels)
            content_type, ext = XLSX_CONTENT_TYPE, "xlsx"
        elif fmt == "pdf":
            data = exporters.render_vat_register_pdf(request.gym, fiscal_year, register)
            content_type, ext = "application/pdf", "pdf"
        else:
            return Response({"detail": "format must be 'csv', 'xlsx', or 'pdf'."}, status=400)

        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="vat-register-{fiscal_year}.{ext}"'
        return response

    def _queue_large_export(self, request, fiscal_year, register, fmt):
        """Large export: write it to object storage now (synchronously is
        fine even here — openpyxl/csv on a few thousand rows is still fast;
        the Celery hand-off only matters once that stops being true) and
        email the requester a signed link, rather than holding the request
        open. ponytail: no job-status model/polling endpoint for this alone.
        """
        rows = register["rows"]
        fieldnames = VAT_REGISTER_FIELDS
        if fmt == "csv":
            data = exporters.rows_to_csv(rows, fieldnames)
        elif fmt == "xlsx":
            data = exporters.rows_to_xlsx(rows, fieldnames, exporters.VAT_REGISTER_LABELS["en"])
        else:
            data = exporters.render_vat_register_pdf(request.gym, fiscal_year, register)

        path = f"exports/{request.gym.pk}/vat-register-{fiscal_year}.{fmt}"
        default_storage.save(path, ContentFile(data))
        url = default_storage.url(path)

        if request.user.email:
            from notifications.providers import email as email_provider

            email_provider.send(
                request.user.email,
                f"Your VAT register export ({fiscal_year}) is ready",
                f"Download it here: {url}",
            )
        return Response({"status": "queued", "download_url": url})
