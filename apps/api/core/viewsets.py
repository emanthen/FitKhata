from __future__ import annotations

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied


class TenantQuerysetMixin:
    """Just the request.gym filtering, for viewsets that aren't full CRUD
    (e.g. a read-only resource) and so can't inherit TenantViewSet's
    ModelViewSet base without getting write endpoints they don't want.
    """

    def get_queryset(self):
        if self.request.gym is None:
            return super().get_queryset().none()
        return super().get_queryset().for_gym(self.request.gym)


class TenantViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    """Base for every tenant-scoped resource: filters by request.gym (set by
    TenantMiddleware) and stamps org/gym on create. Rule 2a — belt-and-
    suspenders on top of the Postgres RLS policy, which is what actually
    enforces isolation.
    """

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(gym=self.request.gym, org=self.request.gym.org)
