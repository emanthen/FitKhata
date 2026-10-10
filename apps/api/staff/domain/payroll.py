"""Gross/net pay math. Pure Python, no Django imports — rule 9."""

from __future__ import annotations

from decimal import Decimal

ZERO = Decimal("0.00")


def gross_pay(
    employment_type: str,
    base_salary_npr: Decimal | None,
    hourly_rate_npr: Decimal | None,
    hours_worked: Decimal,
) -> Decimal:
    """Monthly staff earn their base regardless of hours_worked (that's
    attendance/late-arrival's concern, not pay); hourly staff earn
    hourly_rate_npr * hours_worked.
    """
    if employment_type == "monthly":
        return base_salary_npr or ZERO
    if employment_type == "hourly":
        return (hourly_rate_npr or ZERO) * hours_worked
    raise ValueError(f"Unknown employment_type: {employment_type!r}")


def net_pay(
    gross_npr: Decimal,
    commission_npr: Decimal,
    incentives_npr: Decimal,
    advances_npr: Decimal,
    tds_npr: Decimal,
    social_security_npr: Decimal,
) -> Decimal:
    """Floors at zero rather than going negative — an advance larger than
    this period's earnings is a recovery-schedule problem for the next
    run, not a debt this payslip should show as owed.
    """
    net = gross_npr + commission_npr + incentives_npr - advances_npr - tds_npr - social_security_npr
    return max(net, ZERO)
