from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    DeviceSessionListView,
    DeviceSessionRevokeView,
    LoginView,
    OtpSendView,
    OtpVerifyView,
    RegisterView,
    StaffInviteAcceptView,
    StaffInviteCreateView,
    TokenReissueView,
    TotpConfirmView,
    TotpSetupView,
)

urlpatterns = [
    path("otp/send", OtpSendView.as_view(), name="otp-send"),
    path("otp/verify", OtpVerifyView.as_view(), name="otp-verify"),
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/reissue", TokenReissueView.as_view(), name="token-reissue"),
    path("totp/setup", TotpSetupView.as_view(), name="totp-setup"),
    path("totp/confirm", TotpConfirmView.as_view(), name="totp-confirm"),
    path("sessions", DeviceSessionListView.as_view(), name="sessions-list"),
    path(
        "sessions/<uuid:session_id>/revoke",
        DeviceSessionRevokeView.as_view(),
        name="sessions-revoke",
    ),
    path("invites", StaffInviteCreateView.as_view(), name="invites-create"),
    path("invites/accept", StaffInviteAcceptView.as_view(), name="invites-accept"),
]
