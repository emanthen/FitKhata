"""FitKhata-staff-only access for the /api/v1/platform/... surface.

Not request.role-based like accounts/permissions.py's hierarchy — platform
staff aren't gym staff (no StaffRole row at all), so this checks
request.user.is_staff directly, with mandatory 2FA and an optional IP
allowlist layered on top.
"""

from __future__ import annotations

import ipaddress

from django.conf import settings
from rest_framework.permissions import BasePermission


def _client_ip(request) -> str | None:
    # Same precedence as accounts/tokens.py::_client_ip.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _ip_allowed(request) -> bool:
    allowlist = settings.PLATFORM_IP_ALLOWLIST
    if not allowlist:
        return True
    ip = _client_ip(request)
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in ipaddress.ip_network(entry, strict=False) for entry in allowlist)


class IsPlatformStaff(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or not user.is_staff:
            return False
        # django-otp's reverse accessor isn't in django-stubs' User shape —
        # same ignore accounts/tokens.py already carries for this exact call.
        has_totp = user.totpdevice_set.filter(confirmed=True).exists()  # type: ignore[attr-defined]
        if not has_totp:
            return False
        return _ip_allowed(request)
