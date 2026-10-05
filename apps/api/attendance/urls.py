from django.urls import path

from attendance.views import (
    GateCheckinsBatchView,
    GatePairingCodeView,
    GatePairView,
    GateSnapshotView,
    ManualCheckinView,
    MemberPassLinkView,
    MemberPassView,
)

urlpatterns = [
    path("gate/pairing-codes", GatePairingCodeView.as_view(), name="gate-pairing-codes"),
    path("gate/pair", GatePairView.as_view(), name="gate-pair"),
    path("gate/snapshot", GateSnapshotView.as_view(), name="gate-snapshot"),
    path("gate/checkins:batch", GateCheckinsBatchView.as_view(), name="gate-checkins-batch"),
    path("attendance/manual", ManualCheckinView.as_view(), name="attendance-manual"),
    path(
        "attendance/member-pass-links",
        MemberPassLinkView.as_view(),
        name="attendance-member-pass-links",
    ),
    path("m/pass/<str:token>", MemberPassView.as_view(), name="member-pass"),
]
