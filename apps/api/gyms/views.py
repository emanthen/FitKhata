"""Org/gym bootstrap endpoints for the onboarding wizard (FR-1.7).

Both run under system_context(): creating the first StaffRole for a brand
new Organization, or the first Gym under one, inherently happens before the
caller has any gym-scoped RLS context to create *into* — the same
bootstrapping problem core.middleware.TenantMiddleware's own gym resolution
has. See core.context.system_context's docstring.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StaffRole
from core.context import system_context
from gyms.serializers import GymSerializer, OrganizationSerializer


class OrganizationCreateView(APIView):
    """Any authenticated user may create an org — they become its owner."""

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with system_context():
            org = serializer.save()
            StaffRole.objects.create(
                user=request.user, org=org, gym=None, role=StaffRole.Role.OWNER
            )
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)


class GymCreateView(APIView):
    def post(self, request):
        serializer = GymSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.validated_data["org"]

        with system_context():
            is_org_admin = StaffRole.objects.filter(
                user=request.user,
                org=org,
                gym__isnull=True,
                role__in=[StaffRole.Role.OWNER, StaffRole.Role.MANAGER],
                is_active=True,
            ).exists()
            if not is_org_admin:
                return Response(
                    {"detail": "Only an org-wide owner/manager can add a branch."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            gym = serializer.save()
        return Response(GymSerializer(gym).data, status=status.HTTP_201_CREATED)
