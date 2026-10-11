from __future__ import annotations

from rest_framework.permissions import BasePermission


def require_scope(scope: str) -> type[BasePermission]:
    """Factory mirroring accounts.permissions.IsGateDevice's shape -- checks
    request.api_key (set by core.middleware.TenantMiddleware's ApiKey-auth
    branch) rather than request.user, since a key isn't a Django user.
    """

    class _HasScope(BasePermission):
        def has_permission(self, request, view) -> bool:
            api_key = getattr(request, "api_key", None)
            if api_key is None:
                return False
            return scope in api_key.scopes

    _HasScope.__name__ = f"HasScope_{scope.replace(':', '_')}"
    return _HasScope
