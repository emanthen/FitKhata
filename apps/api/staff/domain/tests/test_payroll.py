from decimal import Decimal

import pytest

from staff.domain.payroll import gross_pay, net_pay


def test_gross_pay_monthly_ignores_hours() -> None:
    assert gross_pay("monthly", Decimal("30000.00"), None, Decimal("5")) == Decimal("30000.00")


def test_gross_pay_hourly_multiplies_rate_by_hours() -> None:
    assert gross_pay("hourly", None, Decimal("200.00"), Decimal("8")) == Decimal("1600.00")


def test_gross_pay_hourly_zero_hours_is_zero() -> None:
    assert gross_pay("hourly", None, Decimal("200.00"), Decimal("0")) == Decimal("0.00")


def test_gross_pay_unknown_employment_type_raises() -> None:
    with pytest.raises(ValueError):
        gross_pay("daily", Decimal("1"), None, Decimal("1"))


def test_net_pay_subtracts_advances_and_tax() -> None:
    net = net_pay(
        gross_npr=Decimal("30000.00"),
        commission_npr=Decimal("2000.00"),
        incentives_npr=Decimal("500.00"),
        advances_npr=Decimal("5000.00"),
        tds_npr=Decimal("1000.00"),
        social_security_npr=Decimal("300.00"),
    )
    assert net == Decimal("26200.00")


def test_net_pay_floors_at_zero_when_advances_exceed_earnings() -> None:
    net = net_pay(
        gross_npr=Decimal("10000.00"),
        commission_npr=Decimal("0.00"),
        incentives_npr=Decimal("0.00"),
        advances_npr=Decimal("50000.00"),
        tds_npr=Decimal("0.00"),
        social_security_npr=Decimal("0.00"),
    )
    assert net == Decimal("0.00")
