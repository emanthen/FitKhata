"""Role-based DRF permission classes. CLAUDE.md FR-1 / "SRS 2.2" — the SRS
file wasn't available when this was written, so this hierarchy (owner >
manager > front_desk, trainer lateral) is this implementation's own
interpretation, not a verified match against a spec section. Revisit against
the real docs/SRS.md 2.2 once it exists.

All of these read request.role, set by core.middleware.TenantMiddleware from
a live StaffRole lookup each request — never from JWT claims, which are a
point-in-time convenience for the client, not an authorization source.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

ROLE_RANK = {"owner": 3, "manager": 2, "front_desk": 1, "trainer": 0}


class _MinimumRole(BasePermission):
    minimum_role: str

    def has_permission(self, request, view) -> bool:
        role = getattr(request, "role", None)
        if role is None:
            return False
        return ROLE_RANK.get(role, -1) >= ROLE_RANK[self.minimum_role]


class IsOwner(_MinimumRole):
    minimum_role = "owner"


class IsManagerOrAbove(_MinimumRole):
    minimum_role = "manager"


class IsFrontDeskOrAbove(_MinimumRole):
    minimum_role = "front_desk"


class IsTrainer(BasePermission):
    def has_permission(self, request, view) -> bool:
        return getattr(request, "role", None) == "trainer"


class IsGateDevice(BasePermission):
    """A paired kiosk, not a Django user — request.gate_device is set by
    core.middleware.TenantMiddleware's Device-auth branch. Use alone (not
    combined with IsAuthenticated) on gate-only views: a device request
    never has a real request.user.
    """

    def has_permission(self, request, view) -> bool:
        return getattr(request, "gate_device", None) is not None


class IsMemberSelf(BasePermission):
    """Placeholder shape for member self-service endpoints — the Member
    model doesn't exist yet (a later phase). Compares request.user to
    obj.user once there's an object with a user FK to check.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        return getattr(obj, "user_id", None) == request.user.id
