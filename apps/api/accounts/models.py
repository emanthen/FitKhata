import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{1,14}$",
    message="Phone must be in E.164 format, e.g. +9779812345678",
)


class UserManager(BaseUserManager["User"]):
    def create_user(self, phone: str, password: str | None = None, **extra) -> "User":
        if not phone:
            raise ValueError("phone is required")
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_active", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser):
    class Locale(models.TextChoices):
        NEPALI = "ne", "Nepali"
        ENGLISH = "en", "English"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True, validators=[phone_validator])
    email = models.EmailField(null=True, blank=True)
    full_name = models.CharField(max_length=200, blank=True)
    locale = models.CharField(max_length=2, choices=Locale.choices, default=Locale.NEPALI)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return self.full_name or self.phone

    def has_perm(self, perm: str, obj: object = None) -> bool:
        return self.is_staff

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_staff


class StaffRole(models.Model):
    """A user's role at a gym, or org-wide (gym=None) across every branch.

    Drives RLS scoping in core.middleware.TenantMiddleware and the
    accounts.permissions role checks.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        FRONT_DESK = "front_desk", "Front desk"
        TRAINER = "trainer", "Trainer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.CASCADE, related_name="staff_roles"
    )
    gym = models.ForeignKey(
        "gyms.Gym", on_delete=models.CASCADE, related_name="staff_roles", null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="staff_roles")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "gym", "role"], name="unique_user_gym_role"),
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=models.Q(gym__isnull=True),
                name="unique_user_org_wide_role",
            ),
        ]
        indexes = [models.Index(fields=["gym", "role"])]

    def __str__(self) -> str:
        scope = self.gym_id or f"org:{self.org_id}"
        return f"{self.user} @ {scope} ({self.role})"


class DeviceSession(models.Model):
    """One row per issued refresh token, for the "device sessions" list/revoke
    UI (FR-1.6). Revoking blacklists the matching SimpleJWT OutstandingToken —
    see accounts.tokens.revoke_device_session.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_sessions")
    jti = models.CharField(max_length=64, unique=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} · {self.jti[:8]}"
