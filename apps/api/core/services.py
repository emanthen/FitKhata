"""Business-logic helpers that don't belong on a view. Rule 9."""

from __future__ import annotations

from typing import Any

from core.models import AuditLog


def audit(
    obj: Any,
    action: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    actor: Any = None,
    ip: str | None = None,
) -> AuditLog:
    """Record an AuditLog row for a tenant-model change. Rule 7: payments,
    invoices and cash shifts call this instead of editing in place.
    """
    return AuditLog.objects.create(
        org_id=obj.org_id,
        gym_id=obj.gym_id,
        actor=actor,
        table_name=obj._meta.db_table,
        row_id=str(obj.pk),
        action=action,
        before=before,
        after=after,
        ip=ip,
    )
