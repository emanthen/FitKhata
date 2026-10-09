from django.urls import path
from rest_framework.routers import DefaultRouter

from retention.views import (
    CampaignViewSet,
    FreezeBatchRevertView,
    FreezeBulkConfirmView,
    FreezeIndividualView,
    FreezePreviewView,
    FreezeRequestViewSet,
    MemberFreezeRequestCreateView,
    MembershipFreezeViewSet,
    RetentionCallViewSet,
    RetentionDashboardView,
)

router = DefaultRouter()
router.register("retention/calls", RetentionCallViewSet, basename="retention-call")
router.register("retention/freezes", MembershipFreezeViewSet, basename="retention-freeze")
router.register(
    "retention/freeze-requests", FreezeRequestViewSet, basename="retention-freeze-request"
)
router.register("retention/campaigns", CampaignViewSet, basename="retention-campaign")

urlpatterns = [
    path("retention/freezes/preview", FreezePreviewView.as_view(), name="retention-freeze-preview"),
    path("retention/freezes/bulk", FreezeBulkConfirmView.as_view(), name="retention-freeze-bulk"),
    path(
        "retention/freezes/individual",
        FreezeIndividualView.as_view(),
        name="retention-freeze-individual",
    ),
    path(
        "retention/freezes/batches/<str:batch_id>/revert",
        FreezeBatchRevertView.as_view(),
        name="retention-freeze-batch-revert",
    ),
    path("retention/dashboard", RetentionDashboardView.as_view(), name="retention-dashboard"),
    path(
        "m/pass/<str:token>/freeze-requests",
        MemberFreezeRequestCreateView.as_view(),
        name="member-freeze-request-create",
    ),
    *router.urls,
]
