from datetime import date
from decimal import Decimal

import pytest

from src.models import InvestmentLot, SchemeType
from src.redemption_engine import (
    calculate_payout_date,
    get_available_units,
    redeem_by_amount,
    redeem_units,
)


def test_valid_unit_redemption():
    result = redeem_units(Decimal("20.000"), Decimal("10.000"), Decimal("100.00"))

    assert result["units"] == Decimal("10.000")
    assert result["amount"] == Decimal("1000.00")
    assert result["remaining_units"] == Decimal("10.000")


def test_invalid_partial_redemption_amount_is_rejected():
    with pytest.raises(ValueError, match="at least"):
        redeem_units(Decimal("20.000"), Decimal("5.000"), Decimal("100.00"))

    with pytest.raises(ValueError, match="at least"):
        redeem_by_amount(Decimal("20.000"), Decimal("999.99"), Decimal("100.00"))


def test_insufficient_units_are_rejected():
    with pytest.raises(ValueError, match="Insufficient"):
        redeem_units(Decimal("10.000"), Decimal("10.001"), Decimal("100.00"))

    with pytest.raises(ValueError, match="Insufficient"):
        redeem_by_amount(Decimal("10.000"), Decimal("1001.00"), Decimal("100.00"))


def test_redemption_of_all_available_units_is_allowed_below_minimum():
    available = Decimal("5.000")
    nav = Decimal("100.00")

    result = redeem_units(available, available, nav)
    by_amount = redeem_by_amount(available, Decimal("500.00"), nav)

    assert result["amount"] == Decimal("500.00")
    assert result["remaining_units"] == Decimal("0.000")
    assert by_amount["units"] == available
    assert by_amount["amount"] == Decimal("500.00")


def test_available_units_are_added_from_matching_lots():
    lots = [
        InvestmentLot("L1", "INV1", "SCH1", date(2026, 1, 1), Decimal("4.000"), Decimal("100")),
        InvestmentLot("L2", "INV1", "SCH1", date(2026, 1, 2), Decimal("6.000"), Decimal("101")),
        InvestmentLot("L3", "INV1", "SCH2", date(2026, 1, 2), Decimal("50.000"), Decimal("25")),
        InvestmentLot("L4", "INV2", "SCH1", date(2026, 1, 2), Decimal("70.000"), Decimal("100")),
    ]

    assert get_available_units(lots, "INV1", "SCH1") == Decimal("10.000")


def test_redeem_by_amount_uses_nav_and_rounds_units_down():
    result = redeem_by_amount(Decimal("20.000"), Decimal("1500.00"), Decimal("125.00"))

    assert result["units"] == Decimal("12.000")
    assert result["amount"] == Decimal("1500.00")
    assert result["remaining_units"] == Decimal("8.000")


def test_redeem_by_amount_ceil_rounding():
    result = redeem_by_amount(Decimal("20.000"), Decimal("1500.01"), Decimal("125.00"))

    assert result["units"] == Decimal("12.001")
    assert result["amount"] == Decimal("1500.13")
    assert result["remaining_units"] == Decimal("7.999")


def test_redeem_by_amount_rejects_insufficient_units_after_ceiling():
    with pytest.raises(ValueError, match="Insufficient available units"):
        redeem_by_amount(Decimal("12.000"), Decimal("1500.01"), Decimal("125.00"))


def test_redeem_by_amount_exact_units():
    result = redeem_by_amount(Decimal("20.000"), Decimal("1500.00"), Decimal("125.00"))

    assert result["units"] == Decimal("12.000")


@pytest.mark.parametrize(
    ("scheme_type", "expected"),
    [
        (SchemeType.EQUITY, date(2026, 1, 27)),
        (SchemeType.DEBT, date(2026, 1, 26)),
        (SchemeType.LIQUID, date(2026, 1, 26)),
    ],
)
def test_payout_date_calculation(scheme_type, expected):
    holidays = {date(2026, 1, 25)}
    transaction_date = date(2026, 1, 23)

    assert calculate_payout_date(scheme_type, transaction_date, holidays) == expected


def test_payout_skips_weekend_and_holiday():
    holiday = date(2026, 1, 26)

    equity = calculate_payout_date(SchemeType.EQUITY, date(2026, 1, 23), {holiday})
    debt = calculate_payout_date(SchemeType.DEBT, date(2026, 1, 23), {holiday})

    assert equity == date(2026, 1, 28)
    assert debt == date(2026, 1, 27)
