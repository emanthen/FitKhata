from django.urls import path

from attendance.views import (
    GateCheckinsBatchView,
    GateHeartbeatView,
    GatePairingCodeView,
    GatePairView,
    GateSnapshotView,
    ManualCheckinView,
    MemberAttendanceCalendarView,
    MemberLoginOtpSendView,
    MemberLoginOtpVerifyView,
    MemberPassLinkView,
    MemberPassView,
)

urlpatterns = [
    path("gate/pairing-codes", GatePairingCodeView.as_view(), name="gate-pairing-codes"),
    path("gate/pair", GatePairView.as_view(), name="gate-pair"),
    path("gate/snapshot", GateSnapshotView.as_view(), name="gate-snapshot"),
    path("gate/checkins:batch", GateCheckinsBatchView.as_view(), name="gate-checkins-batch"),
    path("gate/heartbeat", GateHeartbeatView.as_view(), name="gate-heartbeat"),
    path("attendance/manual", ManualCheckinView.as_view(), name="attendance-manual"),
    path(
        "attendance/member-pass-links",
        MemberPassLinkView.as_view(),
        name="attendance-member-pass-links",
    ),
    path("m/pass/<str:token>", MemberPassView.as_view(), name="member-pass"),
    path(
        "m/login/otp/send", MemberLoginOtpSendView.as_view(), name="member-login-otp-send"
    ),
    path(
        "m/login/otp/verify",
        MemberLoginOtpVerifyView.as_view(),
        name="member-login-otp-verify",
    ),
    path(
        "m/pass/<str:token>/attendance",
        MemberAttendanceCalendarView.as_view(),
        name="member-attendance-calendar",
    ),
]
