import uuid

from django.db import models


class Organization(models.Model):
    """A billing/ownership account; one Organization can run multiple Gym locations."""

    class SaasPlan(models.TextChoices):
        TRIAL = "trial", "Trial"
        BASIC = "basic", "Basic"
        PRO = "pro", "Pro"

    class SaasStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    pan_vat_no = models.CharField(max_length=32, blank=True)
    is_vat_registered = models.BooleanField(default=False)
    saas_plan = models.CharField(max_length=20, choices=SaasPlan.choices, default=SaasPlan.TRIAL)
    saas_status = models.CharField(
        max_length=20, choices=SaasStatus.choices, default=SaasStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


def default_gym_settings() -> dict:
    return {"warning_days": 7, "red_list_days": 10, "anti_passback_min": 5}


class Gym(models.Model):
    """A single gym location — the tenant unit RLS scopes queries by."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="gyms")
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default="Asia/Kathmandu")
    settings = models.JSONField(default=default_gym_settings)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
