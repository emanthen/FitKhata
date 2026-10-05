from __future__ import annotations

from django.db import models

from core.models import TenantModel


class GateDevice(TenantModel):
    """A paired kiosk/scanner. device_key_hash is SHA-256 of the raw device
    token — the raw token itself is returned once at pairing time and never
    stored (see attendance.services.register_gate_device).
    """

    name = models.CharField(max_length=100)
    device_key_hash = models.CharField(max_length=64, unique=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Attendance(TenantModel):
    """Partitioned monthly by check_in_at — see migrations/0001_initial.py's
    SeparateDatabaseAndState and attendance/tasks.py for the Celery Beat job
    that creates each new month's partition.

    unique(client_uuid, check_in_at) rather than unique(client_uuid) alone:
    Postgres requires every unique constraint on a partitioned table to
    include the partition key. A true retry/replay of the same offline scan
    resends the identical check_in_at it recorded locally, so this is still
    sufficient for idempotency — see attendance.services.record_checkins_batch.
    """

    class Source(models.TextChoices):
        QR_GATE = "qr_gate", "QR gate"
        FRONT_DESK_MANUAL = "front_desk_manual", "Front desk manual"
        BIOMETRIC = "biometric", "Biometric"
        RFID = "rfid", "RFID"

    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="attendances"
    )
    check_in_at = models.DateTimeField()
    source = models.CharField(max_length=20, choices=Source.choices)
    client_uuid = models.UUIDField()
    device = models.ForeignKey(
        GateDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="checkins"
    )
    correction_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client_uuid", "check_in_at"], name="unique_client_uuid_check_in_at"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member_id}@{self.check_in_at}"
