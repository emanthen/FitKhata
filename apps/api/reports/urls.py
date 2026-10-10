from django.urls import path

from reports.views import (
    AttendanceHeatmapView,
    CohortRetentionView,
    DashboardSummaryView,
    DuesAgeingView,
    MembershipFlowView,
    PlanMixView,
    RevenueTrendView,
    VatSalesRegisterView,
)

urlpatterns = [
    path(
        "reports/dashboard-summary",
        DashboardSummaryView.as_view(),
        name="reports-dashboard-summary",
    ),
    path("reports/revenue-trend", RevenueTrendView.as_view(), name="reports-revenue-trend"),
    path("reports/plan-mix", PlanMixView.as_view(), name="reports-plan-mix"),
    path(
        "reports/membership-flow",
        MembershipFlowView.as_view(),
        name="reports-membership-flow",
    ),
    path(
        "reports/attendance-heatmap",
        AttendanceHeatmapView.as_view(),
        name="reports-attendance-heatmap",
    ),
    path(
        "reports/cohort-retention",
        CohortRetentionView.as_view(),
        name="reports-cohort-retention",
    ),
    path("reports/dues-ageing", DuesAgeingView.as_view(), name="reports-dues-ageing"),
    path("reports/vat-register", VatSalesRegisterView.as_view(), name="reports-vat-register"),
]
