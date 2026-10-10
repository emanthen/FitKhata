from __future__ import annotations

import yaml
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsGateDevice, IsManagerOrAbove, IsOwner
from core.viewsets import TenantQuerysetMixin, TenantViewSet
from staff.domain.tax import TAX_DIR, fy_filename
from staff.models import (
    Advance,
    ChecklistCompletion,
    LeaveBalance,
    LeaveRequest,
    PayrollRun,
    Payslip,
    ShiftChecklist,
    ShiftTemplate,
    StaffAttendance,
    StaffProfile,
    StaffShift,
)
from staff.payslips import render_payslip_pdf
from staff.serializers import (
    AdvanceSerializer,
    ChecklistCompletionSerializer,
    LeaveBalanceSerializer,
    LeaveRequestSerializer,
    PayrollRunSerializer,
    PayslipSerializer,
    ShiftChecklistSerializer,
    ShiftTemplateSerializer,
    StaffAttendanceSerializer,
    StaffGateCheckinsBatchSerializer,
    StaffProfileSerializer,
    StaffShiftSerializer,
)
from staff.services import (
    InsufficientLeaveBalance,
    PayrollRunLocked,
    ShiftConflict,
    SlabsNotConfirmed,
    approve_leave_request,
    create_advance,
    create_payroll_run,
    create_shift,
    finalize_payroll_run,
    record_staff_checkins_batch,
    register_staff_profile,
    reject_leave_request,
    staff_leaderboard,
    submit_checklist_completion,
    submit_leave_request,
    update_payslip_line,
)


class StaffProfileViewSet(TenantViewSet):
    """IsManagerOrAbove gates the ViewSet, but the serializer's field-level
    redaction (StaffProfileSerializer) is what actually protects bank/PAN —
    a manager sees every profile, just never the decrypted sensitive
    fields, which come back null unless request.role == owner.
    """

    serializer_class = StaffProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = StaffProfile.objects.select_related("user")

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        validated = dict(serializer.validated_data)
        raw_account = validated.pop("bank_account_input", "")
        profile = register_staff_profile(
            self.request.gym,
            validated.pop("user"),
            actor=self.request.user,
            **validated,
        )
        if raw_account:
            from core.crypto import encrypt_bytes

            profile.bank_account_encrypted = encrypt_bytes(raw_account.encode("utf-8"))
            profile.save(update_fields=["bank_account_encrypted"])
        serializer.instance = profile


class ShiftTemplateViewSet(TenantViewSet):
    serializer_class = ShiftTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = ShiftTemplate.objects.all()


class StaffShiftViewSet(TenantViewSet):
    """create() goes through staff.services.create_shift (conflict check)
    instead of a bare serializer.save().
    """

    serializer_class = StaffShiftSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = StaffShift.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            shift = create_shift(
                data["staff"], data["date"], data["start"], data["end"], data.get("template")
            )
        except ShiftConflict as exc:
            return Response(
                {"detail": str(exc), "conflicting_shift_id": exc.conflicting_shift.pk}, status=400
            )
        return Response(StaffShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


class StaffAttendanceViewSet(TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = StaffAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = StaffAttendance.objects.select_related("staff").order_by("-clock_in")


class StaffGateCheckinsBatchView(APIView):
    """Separate from attendance.GateCheckinsBatchView — staff clock-in/out
    pairing has no equivalent in the member check-in path, so this stays
    its own small endpoint rather than branching the member one.
    """

    permission_classes = [IsGateDevice]

    def post(self, request):
        serializer = StaffGateCheckinsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gym = request.gate_device.gym
        rows = []
        for row in serializer.validated_data["checkins"]:
            staff = get_object_or_404(StaffProfile, gym=gym, badge_code=row["badge_code"])
            rows.append({"staff": staff, "scanned_at": row["scanned_at"]})
        result = record_staff_checkins_batch(rows)
        return Response(result)


class LeaveRequestViewSet(TenantViewSet):
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = LeaveRequest.objects.select_related("staff")

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        leave = submit_leave_request(data.pop("staff"), **data)
        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsManagerOrAbove],
    )
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        try:
            leave_request = approve_leave_request(leave_request, actor=request.user)
        except InsufficientLeaveBalance as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(LeaveRequestSerializer(leave_request).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsManagerOrAbove],
    )
    def reject(self, request, pk=None):
        leave_request = reject_leave_request(self.get_object(), actor=request.user)
        return Response(LeaveRequestSerializer(leave_request).data)


class LeaveBalanceViewSet(TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = LeaveBalance.objects.select_related("staff")

    @action(detail=False, methods=["post"])
    def adjust(self, request):
        from decimal import Decimal

        from staff.services import adjust_leave_balance

        staff = get_object_or_404(StaffProfile, pk=request.data.get("staff"), gym=request.gym)
        balance = adjust_leave_balance(
            staff,
            request.data.get("kind"),
            Decimal(str(request.data.get("delta_days", "0"))),
            actor=request.user,
        )
        return Response(LeaveBalanceSerializer(balance).data)


class AdvanceViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """create+list only — no edit/delete, matching rule 7."""

    serializer_class = AdvanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = Advance.objects.select_related("staff").order_by("-date")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        advance = create_advance(
            data["staff"], data["amount_npr"], data["date"], actor=request.user
        )
        return Response(AdvanceSerializer(advance).data, status=status.HTTP_201_CREATED)


class PayrollRunViewSet(
    TenantQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PayrollRunSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = PayrollRun.objects.prefetch_related("payslips").order_by("-period_bs")

    def create(self, request, *args, **kwargs):
        period_bs = request.data.get("period_bs")
        if not period_bs:
            return Response({"detail": "period_bs is required."}, status=400)
        try:
            run = create_payroll_run(request.gym, period_bs, actor=request.user)
        except PayrollRunLocked as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PayrollRunSerializer(run).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsOwner]
    )
    def finalize(self, request, pk=None):
        run = self.get_object()
        try:
            run = finalize_payroll_run(run, actor=request.user)
        except (SlabsNotConfirmed, PayrollRunLocked) as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PayrollRunSerializer(run).data)


class PayslipViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = PayslipSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = Payslip.objects.select_related("staff", "run")

    def get_queryset(self):
        qs = super().get_queryset()
        run_id = self.request.query_params.get("run")
        if run_id:
            qs = qs.filter(run_id=run_id)
        return qs

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsManagerOrAbove],
    )
    def set_incentives(self, request, pk=None):
        """The incentives line has no automatic source — a manager enters
        it manually, pre-finalize only.
        """
        from decimal import Decimal

        payslip = self.get_object()
        try:
            payslip = update_payslip_line(
                payslip, actor=request.user,
                incentives_npr=Decimal(str(request.data.get("incentives_npr", "0"))),
            )
        except PayrollRunLocked as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PayslipSerializer(payslip).data)


class PayslipPdfView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request, payslip_id: int):
        payslip = get_object_or_404(Payslip, pk=payslip_id, gym=request.gym)
        lang = request.query_params.get("lang", "en")
        pdf_bytes = render_payslip_pdf(payslip, lang=lang)
        from django.http import HttpResponse

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="payslip-{payslip.pk}.pdf"'
        return response


class ShiftChecklistViewSet(TenantViewSet):
    serializer_class = ShiftChecklistSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = ShiftChecklist.objects.all()


class ChecklistCompletionViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    serializer_class = ChecklistCompletionSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = ChecklistCompletion.objects.select_related("checklist").order_by("-date")

    @action(detail=False, methods=["post"])
    def submit(self, request):
        checklist = get_object_or_404(
            ShiftChecklist, pk=request.data.get("checklist"), gym=request.gym
        )
        completion = submit_checklist_completion(
            checklist,
            request.data.get("date") or timezone.localdate(),
            request.data.get("checked_items", []),
            actor=request.user,
        )
        return Response(ChecklistCompletionSerializer(completion).data)


class StaffLeaderboardView(APIView):
    """FR-9.7: renewals sold / calls completed / saves, per staff, for one
    BS period. See staff.services.staff_leaderboard for the exact field
    definitions (especially "saves", which the task doesn't define itself).
    """

    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        period_bs = request.query_params.get("period_bs")
        if not period_bs:
            return Response({"detail": "period_bs is required."}, status=400)
        return Response(staff_leaderboard(request.gym, period_bs))


class ConfirmTaxSlabsView(APIView):
    """Owner-only: flips a tax slab file's `confirmed` flag + stamps who/
    when, by rewriting the YAML in place. The confirmed numbers and the
    confirmation live in the same artifact — see staff/tax/*.yaml's own
    comment on why.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, fiscal_year: str):
        path = TAX_DIR / fy_filename(fiscal_year)
        if not path.exists():
            return Response({"detail": f"No slab file for {fiscal_year}."}, status=404)

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["confirmed"] = True
        data["confirmed_by"] = str(request.user.pk)
        data["confirmed_at"] = timezone.now().isoformat()
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return Response(data)
