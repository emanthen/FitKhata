"""Public API key auth: `Authorization: ApiKey <key>`, not JWT. Called
directly by core.middleware.TenantMiddleware (lazily imported there, same
reasoning as that middleware's existing lazy attendance.authentication
import) -- not a DRF BaseAuthentication subclass, for the identical reason
attendance.authentication.authenticate_device isn't one: an ApiKey isn't a
Django User and doesn't fit DRF's (user, auth) convention cleanly, and only
middleware can set RLS's app.gym_ids before the view runs.
"""

from __future__ import annotations

import hashlib

from publicapi.models import ApiKey

HEADER_PREFIX = "ApiKey "


def authenticate_api_key(auth_header: str) -> ApiKey | None:
    if not auth_header.startswith(HEADER_PREFIX):
        return None
    raw_key = auth_header[len(HEADER_PREFIX) :].strip()
    if not raw_key:
        return None

    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    # Resolving the key is itself cross-tenant (no gym scoped yet) -- same
    # bootstrapping case as authenticate_device's GateDevice lookup.
    from core.context import system_context

    with system_context():
        api_key = (
            ApiKey.objects.filter(key_hash=key_hash, revoked_at__isnull=True)
            .select_related("org")
            .first()
        )
    return api_key
