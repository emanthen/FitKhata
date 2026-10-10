from __future__ import annotations

from decimal import Decimal

import pytest

from saas.domain.pricing import PlanPricing, amount_for

STARTER = PlanPricing(Decimal("999"), Decimal("9990"), per_branch_pricing=False)
PRO = PlanPricing(Decimal("1999"), Decimal("19990"), per_branch_pricing=False)
ENTERPRISE = PlanPricing(Decimal("4999"), Decimal("49990"), per_branch_pricing=True)


@pytest.mark.parametrize(
    "plan,cycle,branches,expected",
    [
        (STARTER, "monthly", 1, Decimal("999")),
        (STARTER, "annual", 1, Decimal("9990")),
        (STARTER, "monthly", 3, Decimal("999")),  # flat rate, branches ignored
        (PRO, "monthly", 1, Decimal("1999")),
        (PRO, "annual", 5, Decimal("19990")),
        (ENTERPRISE, "monthly", 1, Decimal("4999")),
        (ENTERPRISE, "monthly", 3, Decimal("14997")),
        (ENTERPRISE, "annual", 2, Decimal("99980")),
    ],
)
def test_amount_for(plan, cycle, branches, expected):
    assert amount_for(plan, cycle, branches) == expected
