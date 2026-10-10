"""Pure SaaS invoice pricing — no Django imports, see rule 9."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class PlanPricing:
    """Duck-typed view of SaasPlan — lets tests build one without the ORM."""

    monthly_npr: Decimal
    annual_npr: Decimal
    per_branch_pricing: bool


def amount_for(plan: Any, billing_cycle: str, branches: int) -> Decimal:
    """plan: a SaasPlan instance or PlanPricing. billing_cycle: "monthly"
    or "annual". Per-branch plans (enterprise) multiply by `branches`;
    others charge the flat rate regardless of branch count.
    """
    base = plan.monthly_npr if billing_cycle == "monthly" else plan.annual_npr
    if not plan.per_branch_pricing:
        return base
    return base * branches
