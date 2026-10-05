"""Gate device auth: `Authorization: Device <token>`, not JWT. Called
directly by core.middleware.TenantMiddleware (lazily imported there to
avoid a core<->attendance circular import — same reasoning as that
middleware's existing lazy StaffRole import), the same way JWTAuthentication
is — not a DRF BaseAuthentication subclass, since a paired device isn't a
Django User and doesn't fit DRF's (user, auth) convention cleanly.
"""

from __future__ import annotations

import hashlib

from attendance.models import GateDevice
from core.context import system_context

HEADER_PREFIX = "Device "


def authenticate_device(auth_header: str) -> tuple[GateDevice | None, str | None]:
    """Returns (device, raw_token) — raw_token is only ever kept on the
    request transiently (attendance.views.GateSnapshotView derives the
    AES-GCM key from it); nothing persists it.
    """
    if not auth_header.startswith(HEADER_PREFIX):
        return None, None
    raw_token = auth_header[len(HEADER_PREFIX) :].strip()
    if not raw_token:
        return None, None

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    # Resolving the device inherently requires seeing across tenants — no
    # gym is scoped yet. Same bootstrapping case as _resolve_gym's StaffRole
    # lookup.
    with system_context():
        device = (
            GateDevice.objects.filter(device_key_hash=token_hash, revoked_at__isnull=True)
            .select_related("gym")
            .first()
        )
    if device is None:
        return None, None
    return device, raw_token
