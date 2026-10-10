"""Org/gym bootstrap endpoints for the onboarding wizard (FR-1.7).

Both run under system_context(): creating the first StaffRole for a brand
new Organization, or the first Gym under one, inherently happens before the
caller has any gym-scoped RLS context to create *into* — the same
bootstrapping problem core.middleware.TenantMiddleware's own gym resolution
has. See core.context.system_context's docstring.
"""

from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StaffRole
from accounts.permissions import IsOwner
from core.context import system_context
from gyms.serializers import GymSerializer, OrganizationSerializer
from saas.services import start_trial


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
            start_trial(org)
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
            # Phase 7 cross-app edit: DietPlan is a TenantModel (no Gym row
            # exists at migration time, and a nullable gym would hide it
            # from RLS), so the 7 Nepali templates are seeded here instead —
            # lazy import, same reasoning as notifications/services.py's
            # own lazy imports of its Celery tasks.
            from coaching.services import seed_default_diet_plans

            seed_default_diet_plans(gym)
        return Response(GymSerializer(gym).data, status=status.HTTP_201_CREATED)


class GymSettingsUpdateView(APIView):
    """Updates the currently-selected gym (request.gym, via X-Gym-Id —
    TenantMiddleware already resolved and authorized it against the
    caller's own StaffRole). IsOwner-gated.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request):
        """Needed so the web event-toggle page (notifications settings) can
        read gym.settings['notification_events']/['notification_channel_order']
        before PATCHing them back — symmetric with
        OrganizationSettingsUpdateView's own get/patch pair.
        """
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        return Response(GymSerializer(request.gym).data)

    def patch(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = GymSerializer(request.gym, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        gym = serializer.save()
        return Response(GymSerializer(gym).data)


class OrganizationSettingsUpdateView(APIView):
    """Updates the currently-selected gym's Organization — PAN/VAT number,
    VAT registration, and billing/domain/vat.py's inclusive-vs-exclusive
    pricing mode. IsOwner-gated, same as GymSettingsUpdateView.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        return Response(OrganizationSerializer(request.gym.org).data)

    def patch(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = OrganizationSerializer(request.gym.org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        org = serializer.save()
        return Response(OrganizationSerializer(org).data)
