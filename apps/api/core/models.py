from django.conf import settings
from django.db import models


class TenantQuerySet(models.QuerySet):
    """Rule 2a: app-level scoping layer on top of Postgres RLS (belt and suspenders)."""

    def for_gym(self, gym: "models.Model | str") -> "TenantQuerySet":
        gym_id = gym.pk if isinstance(gym, models.Model) else gym
        return self.filter(gym_id=gym_id)


class TenantModel(models.Model):
    """Abstract base every tenant-scoped table inherits. CLAUDE.md rule 1."""

    org = models.ForeignKey("gyms.Organization", on_delete=models.CASCADE)
    gym = models.ForeignKey("gyms.Gym", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Append-only: a DB trigger (core/migrations/0002_rls.py) blocks UPDATE
    and DELETE on this table outright. Rule 7. Not a TenantModel subclass —
    no updated_at makes sense on a row that's never updated.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        VOID = "void", "Void"

    org = models.ForeignKey("gyms.Organization", on_delete=models.CASCADE)
    gym = models.ForeignKey("gyms.Gym", on_delete=models.CASCADE)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    table_name = models.CharField(max_length=100)
    row_id = models.CharField(max_length=64)
    action = models.CharField(max_length=20, choices=Action.choices)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["gym", "table_name", "row_id"])]

    def __str__(self) -> str:
        return f"{self.action} {self.table_name}:{self.row_id}"
