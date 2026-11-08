"""Comprehensive unit and edge case tests for mutual fund redemptions, exit loads, and BR-08."""

from datetime import date
from decimal import Decimal
import pytest

from src.exit_load_engine import calculate_lot_exit_load, ExitLoadSchedule
from src.lot_manager import LotManager
from src.models import InvestmentLot, Scheme, SchemeType
from src.redemption_engine import (
    calculate_payout_date,
    calculate_redemption_amount,
    get_available_units,
    redeem_by_amount,
    redeem_units,
    validate_redemption_amount,
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
    liquid = calculate_payout_date(SchemeType.LIQUID, date(2026, 1, 23), {holiday})

    assert equity == date(2026, 1, 28)
    assert debt == date(2026, 1, 27)
    assert liquid == date(2026, 1, 27)


# --- New BR-08 and Edge Case Tests ---

def test_ec04_exit_load_boundary_day_365_vs_366():
    """EC-04: Day 365 incurs 1% exit load, Day 366 incurs 0% (nil) exit load."""
    schedules = [
        ExitLoadSchedule(SchemeType.EQUITY, 0, 365, Decimal("1.0000")),
    ]
    units = Decimal("100.000")
    nav = Decimal("100.0000")
    # Gross = 10,000.00

    # Day 365: within [0, 365] -> 1% = 100.00
    load_day_365 = calculate_lot_exit_load(units, nav, 365, SchemeType.EQUITY, schedules)
    assert load_day_365 == Decimal("100.00")

    # Day 366: outside [0, 365] -> 0% = 0.00
    load_day_366 = calculate_lot_exit_load(units, nav, 366, SchemeType.EQUITY, schedules)
    assert load_day_366 == Decimal("0.00")


def test_ec05_insufficient_units_after_ceiling_rounding():
    """EC-05: Redemption by amount ceil3 needs 708.740 units with only 708.739 available."""
    available = Decimal("708.739")
    amount = Decimal("23822.93")
    nav = Decimal("33.6131")

    # 23822.93 / 33.6131 = 708.73968... -> ceil3 = 708.740 > 708.739
    with pytest.raises(ValueError, match="Insufficient available units for redemption"):
        redeem_by_amount(available, amount, nav)


def test_multi_lot_fifo_deduction_and_remaining_balances():
    """Test FIFO order across multiple lots and correct remaining units."""
    lm = LotManager()
    scheme = Scheme("SCH-01", "Test Equity", SchemeType.EQUITY)
    schedules = [
        ExitLoadSchedule(SchemeType.EQUITY, 0, 365, Decimal("1.0000")),
    ]

    lot1 = InvestmentLot("LOT-1", "FOL-1", "SCH-01", date(2025, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lot2 = InvestmentLot("LOT-2", "FOL-1", "SCH-01", date(2025, 6, 1), Decimal("150.000"), Decimal("60.0000"))
    lm.add_lot(lot1)
    lm.add_lot(lot2)

    as_of = date(2026, 1, 15)  # lot1: >365 days (0% load); lot2: 228 days (1% load)
    nav = Decimal("80.0000")

    # Redeem 120 units: 100 units from LOT-1, 20 units from LOT-2
    exit_load = lm.deplete_units_fifo("FOL-1", "SCH-01", Decimal("120.000"), as_of, scheme, schedules, nav)

    # LOT-1 load = 0.00; LOT-2 load = 20 * 80 * 1% = 16.00
    assert exit_load == Decimal("16.00")
    assert lot1.units == Decimal("0.000")
    assert lot2.units == Decimal("130.000")

    remaining = lm.get_remaining_lots_for_folio("FOL-1")
    assert len(remaining) == 1
    assert remaining[0].lot_id == "LOT-2"
    assert remaining[0].units == Decimal("130.000")


@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_redemption_amount_rejected(val):
    with pytest.raises(ValueError, match="finite number"):
        validate_redemption_amount(val)

    with pytest.raises(ValueError, match="finite number"):
        redeem_by_amount(Decimal("100.000"), val, Decimal("50.0000"))


@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_redemption_units_rejected(val):
    with pytest.raises(ValueError, match="finite number"):
        calculate_redemption_amount(val, Decimal("50.0000"))

    with pytest.raises(ValueError, match="finite number"):
        redeem_units(Decimal("100.000"), val, Decimal("50.0000"))


@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_nav_rejected(val):
    with pytest.raises(ValueError, match="finite number"):
        calculate_redemption_amount(Decimal("10.000"), val)

    with pytest.raises(ValueError, match="finite number"):
        redeem_units(Decimal("100.000"), Decimal("10.000"), val)

    with pytest.raises(ValueError, match="finite number"):
        redeem_by_amount(Decimal("100.000"), Decimal("1000.00"), val)


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-10.00")])
def test_zero_or_negative_redemption_amount_rejected(amount):
    with pytest.raises(ValueError, match="greater than zero"):
        validate_redemption_amount(amount)

    with pytest.raises(ValueError, match="greater than zero"):
        redeem_by_amount(Decimal("100.000"), amount, Decimal("50.0000"))


@pytest.mark.parametrize("units", [Decimal("0.000"), Decimal("-5.000")])
def test_zero_or_negative_redemption_units_rejected(units):
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_redemption_amount(units, Decimal("50.0000"))

    with pytest.raises(ValueError, match="greater than zero"):
        redeem_units(Decimal("100.000"), units, Decimal("50.0000"))
