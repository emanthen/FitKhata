from django.urls import path
from rest_framework.routers import DefaultRouter

from staff.views import (
    AdvanceViewSet,
    ChecklistCompletionViewSet,
    ConfirmTaxSlabsView,
    LeaveBalanceViewSet,
    LeaveRequestViewSet,
    PayrollRunViewSet,
    PayslipPdfView,
    PayslipViewSet,
    ShiftChecklistViewSet,
    ShiftTemplateViewSet,
    StaffAttendanceViewSet,
    StaffGateCheckinsBatchView,
    StaffLeaderboardView,
    StaffProfileViewSet,
    StaffShiftViewSet,
)

router = DefaultRouter()
router.register("staff-profiles", StaffProfileViewSet, basename="staff-profile")
router.register("staff-shift-templates", ShiftTemplateViewSet, basename="staff-shift-template")
router.register("staff-shifts", StaffShiftViewSet, basename="staff-shift")
router.register("staff-attendances", StaffAttendanceViewSet, basename="staff-attendance")
router.register("leave-requests", LeaveRequestViewSet, basename="leave-request")
router.register("leave-balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("advances", AdvanceViewSet, basename="advance")
router.register("payroll-runs", PayrollRunViewSet, basename="payroll-run")
router.register("payslips", PayslipViewSet, basename="payslip")
router.register("shift-checklists", ShiftChecklistViewSet, basename="shift-checklist")
router.register(
    "checklist-completions", ChecklistCompletionViewSet, basename="checklist-completion"
)

urlpatterns = [
    path(
        "staff/gate/checkins/batch",
        StaffGateCheckinsBatchView.as_view(),
        name="staff-gate-checkins-batch",
    ),
    path("staff/leaderboard", StaffLeaderboardView.as_view(), name="staff-leaderboard"),
    path(
        "payslips/<int:payslip_id>/pdf",
        PayslipPdfView.as_view(),
        name="payslip-pdf",
    ),
    path(
        # <path:...> (not <str:...>) because fiscal_year contains a slash,
        # e.g. "2083/84".
        "staff/tax/slabs/<path:fiscal_year>/confirm",
        ConfirmTaxSlabsView.as_view(),
        name="staff-confirm-tax-slabs",
    ),
    *router.urls,
]
