"""FR-12.3 (public API keys) and FR-12.4 (outgoing webhooks). Deliberately
plain models.Model, never TenantModel -- same reasoning as saas/models.py's
own docstring: these describe an org's integration config (an Enterprise
subscription is itself org-level, per saas.models.Subscription), not
gym-scoped tenant data. An authenticated key/request is scoped to every
gym under its org by setting app.gym_ids to that full list -- see
publicapi.authentication.ApiKeyAuthentication, reusing the same multi-gym
RLS support core.context.tenant_context already has.
"""

from __future__ import annotations

import uuid

from django.db import models


class ApiKey(models.Model):
    """key_hash is SHA-256 of the raw key -- same never-store-the-raw-value
    shape as attendance.models.GateDevice.device_key_hash. key_prefix (the
    first few chars of the raw key) is stored so the owner can tell which
    key is which in a list without the server ever holding the full value.
    """

    class Scope(models.TextChoices):
        MEMBERS_READ = "members:read", "Read members"
        MEMBERSHIPS_READ = "memberships:read", "Read memberships"
        INVOICES_READ = "invoices:read", "Read invoices"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=100)
    key_prefix = models.CharField(max_length=12)
    key_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix}...)"


class WebhookSubscription(models.Model):
    class Event(models.TextChoices):
        MEMBER_CREATED = "member.created", "Member created"
        PAYMENT_COMPLETED = "payment.completed", "Payment completed"
        CHECKIN_CREATED = "checkin.created", "Check-in created"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.CASCADE, related_name="webhook_subscriptions"
    )
    url = models.URLField(max_length=500)
    # Fernet via core.crypto, same field shape as billing.models.Payment's
    # own secret_encrypted (payment-gateway credentials) -- CLAUDE.md rule 10.
    secret_encrypted = models.BinaryField(editable=False)
    events = models.JSONField(default=list)  # subset of Event.values
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.url} ({self.org_id})"


class WebhookDelivery(models.Model):
    """One row per delivery attempt-cycle for one (subscription, event)
    firing -- this IS the delivery log the spec asks for, not a separate
    audit mechanism.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    MAX_ATTEMPTS = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        WebhookSubscription, on_delete=models.CASCADE, related_name="deliveries"
    )
    event = models.CharField(max_length=50)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.CharField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.event} -> {self.subscription_id} ({self.status})"
