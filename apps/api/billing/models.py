from __future__ import annotations

from django.db import models

from core.models import TenantModel


class InvoiceCounter(models.Model):
    """Org-scoped, not gym-scoped — rule 8 numbers invoices sequentially per
    org per fiscal year, not per branch. Deliberately not a TenantModel (no
    gym field): a sale at any branch of the org shares the same sequence.
    RLS for this table is org-scoped (see billing/migrations), so it's not
    picked up by tests/rls/test_isolation.py's generic gym-field
    introspection — that test only verifies gym-scoped tables.
    """

    org = models.ForeignKey("gyms.Organization", on_delete=models.CASCADE)
    fiscal_year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "fiscal_year"], name="unique_org_fiscal_year_counter"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.org_id}/{self.fiscal_year}: {self.last_value}"


class Invoice(TenantModel):
    """Draft-creation only this phase — sell_membership() creates these as
    status=draft with lines. Payment confirmation, status=issued/paid, and
    void are Phase 4 (rules 6/7's actual money-movement logic).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        VOID = "void", "Void"

    number = models.CharField(max_length=30)
    fiscal_year = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="invoices"
    )
    subtotal_npr = models.DecimalField(max_digits=12, decimal_places=2)
    discount_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_npr = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "number"], name="unique_org_invoice_number"),
        ]

    def __str__(self) -> str:
        return self.number


class InvoiceLine(TenantModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    line_total_npr = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.invoice_id}: {self.description}"
