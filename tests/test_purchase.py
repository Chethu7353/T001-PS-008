from decimal import Decimal

import pytest

from src.purchase_engine import calculate_purchase


def test_first_purchase_calculates_stamp_duty_and_rounds_units_down():
    result = calculate_purchase(Decimal("5000"), Decimal("100"), is_first_purchase=True)

    assert result["stamp_duty"] == Decimal("0.25")
    assert result["investible_amount"] == Decimal("4999.75")
    assert result["units"] == Decimal("49.997")


def test_additional_purchase_at_minimum_is_valid():
    result = calculate_purchase(Decimal("1000"), Decimal("125"), is_first_purchase=False)

    assert result["stamp_duty"] == Decimal("0.05")
    assert result["units"] == Decimal("7.999")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1")])
def test_zero_or_negative_purchase_is_rejected(amount):
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_purchase(amount, Decimal("100"), is_first_purchase=True)


@pytest.mark.parametrize(
    ("amount", "is_first_purchase"),
    [(Decimal("4999.99"), True), (Decimal("999.99"), False)],
)
def test_purchase_below_minimum_is_rejected(amount, is_first_purchase):
    with pytest.raises(ValueError, match="at least"):
        calculate_purchase(amount, Decimal("100"), is_first_purchase)


@pytest.mark.parametrize("nav", [Decimal("0"), Decimal("-1")])
def test_zero_or_negative_nav_is_rejected(nav):
    with pytest.raises(ValueError, match="NAV must be greater than zero"):
        calculate_purchase(Decimal("5000"), nav, is_first_purchase=True)
