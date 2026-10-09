from __future__ import annotations

import uuid

from django.db import models

from core.models import TenantModel
from members.models import Member, Membership, PromoCode


class RiskStateChange(TenantModel):
    """One row per actual risk_state transition (not one per nightly run --
    churn_engine only writes this when a member's state really changed).
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="risk_state_changes")
    from_state = models.CharField(max_length=20, choices=Member.RiskState.choices)
    to_state = models.CharField(max_length=20, choices=Member.RiskState.choices)
    days_absent = models.PositiveIntegerField()
    changed_on = models.DateField()

    class Meta:
        indexes = [models.Index(fields=["gym", "member", "changed_on"])]

    def __str__(self) -> str:
        return f"{self.member_id}: {self.from_state}->{self.to_state} ({self.changed_on})"


class RetentionCall(TenantModel):
    class Outcome(models.TextChoices):
        REACHED = "reached", "Reached"
        NO_ANSWER = "no_answer", "No answer"
        COMING_BACK = "coming_back", "Coming back"
        INJURED = "injured", "Injured"
        QUITTING = "quitting", "Quitting"
        CALL_BACK = "call_back", "Call back later"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="retention_calls")
    queue_date = models.DateField()
    assigned_to = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices, blank=True)
    call_back_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["gym", "member", "queue_date"])]

    def __str__(self) -> str:
        return f"{self.member_id} queued {self.queue_date} ({self.outcome or 'pending'})"


class MembershipFreeze(TenantModel):
    class Reason(models.TextChoices):
        DASHAIN = "dashain", "Dashain"
        TIHAR = "tihar", "Tihar"
        CHHATH = "chhath", "Chhath"
        TRAVEL = "travel", "Travel"
        INJURY = "injury", "Injury"
        OTHER = "other", "Other"

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="freezes")
    # Shared by every row one bulk-freeze call creates; an individual freeze
    # just gets its own fresh uuid -- either way, "one batch_id" (FR-5.8) is
    # exactly what makes a bulk Undo able to revert the whole group at once.
    batch_id = models.UUIDField(default=uuid.uuid4)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveIntegerField()
    previous_expiry = models.DateField()
    fee_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    reverted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["gym", "batch_id"]),
            models.Index(fields=["gym", "membership"]),
        ]

    def __str__(self) -> str:
        return f"freeze {self.membership_id}: {self.start_date}..{self.end_date}"


class FreezeRequest(TenantModel):
    """FR-8.6: a member-initiated freeze request, pending a manager's
    approval before apply_individual_freeze actually runs -- unlike
    MembershipFreeze above, nothing here mutates the membership until
    approve_freeze_request() calls that existing function.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="freeze_requests")
    membership = models.ForeignKey(
        Membership, on_delete=models.CASCADE, related_name="freeze_requests"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return (
            f"freeze request {self.member_id}: "
            f"{self.start_date}..{self.end_date} ({self.status})"
        )


class Campaign(TenantModel):
    class Kind(models.TextChoices):
        WINBACK_30 = "winback_30", "Winback 30"
        WINBACK_60 = "winback_60", "Winback 60"
        WINBACK_90 = "winback_90", "Winback 90"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    promo = models.ForeignKey(
        PromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns"
    )
    sent_count = models.PositiveIntegerField(default=0)
    converted_count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.kind} ({self.sent_count} sent, {self.converted_count} converted)"
