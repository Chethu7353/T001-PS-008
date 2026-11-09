"""Focused unit and integration tests for FIFO lot management, exit loads, and ELSS lock-in (BR-11)."""

from datetime import date
from decimal import Decimal
import pytest

from src.exit_load_engine import calculate_lot_exit_load, ExitLoadSchedule
from src.lot_manager import (
    get_elss_lock_in_date,
    is_lot_locked,
    LotManager,
)
from src.models import InvestmentLot, Scheme, SchemeType


# --- 1. FIFO Depletion Across Three or More Lots ---

def test_fifo_depletion_across_three_or_more_lots():
    lm = LotManager()
    scheme = Scheme("SCH-01", "Bluechip Equity", SchemeType.EQUITY)
    schedules = [ExitLoadSchedule(SchemeType.EQUITY, 0, 365, Decimal("1.0000"))]
    as_of = date(2026, 6, 1)
    nav = Decimal("100.0000")

    # Add 3 lots in random order; add_lot must sort by (allotment_date, lot_id)
    l2 = InvestmentLot("LOT-02", "FOL-01", "SCH-01", date(2025, 2, 1), Decimal("75.000"), Decimal("80.0000"))
    l1 = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2025, 1, 1), Decimal("50.000"), Decimal("75.0000"))
    l3 = InvestmentLot("LOT-03", "FOL-01", "SCH-01", date(2025, 3, 1), Decimal("100.000"), Decimal("85.0000"))
    lm.add_lot(l2)
    lm.add_lot(l1)
    lm.add_lot(l3)

    # Redeem 150 units -> should completely consume LOT-01 (50) and LOT-02 (75), and 25 from LOT-03
    lm.deplete_units_fifo("FOL-01", "SCH-01", Decimal("150.000"), as_of, scheme, schedules, nav)

    assert l1.units == Decimal("0.000")
    assert l2.units == Decimal("0.000")
    assert l3.units == Decimal("75.000")

    remaining = lm.get_remaining_lots_for_folio("FOL-01")
    assert len(remaining) == 1
    assert remaining[0].lot_id == "LOT-03"
    assert remaining[0].units == Decimal("75.000")


# --- 2. Partial Depletion and Remaining Balances ---

def test_partial_depletion_and_remaining_balances():
    lm = LotManager()
    scheme = Scheme("SCH-01", "Bluechip Equity", SchemeType.EQUITY)
    schedules = []
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2025, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    lm.deplete_units_fifo("FOL-01", "SCH-01", Decimal("30.000"), date(2026, 1, 1), scheme, schedules, Decimal("60.0000"))

    assert lot.units == Decimal("70.000")
    assert lm.has_holding("FOL-01", "SCH-01") is True
    remaining = lm.get_remaining_lots_for_folio("FOL-01")
    assert len(remaining) == 1
    assert remaining[0].units == Decimal("70.000")


# --- 3. Debt Day-30 Versus Day-31 Exit-Load Boundary ---

def test_debt_day_30_vs_day_31_exit_load_boundary():
    schedules = [ExitLoadSchedule(SchemeType.DEBT, 0, 30, Decimal("0.2500"))]
    units = Decimal("1000.000")
    nav = Decimal("20.0000")
    # Gross = 20,000.00; 0.25% = 50.00

    load_day_30 = calculate_lot_exit_load(units, nav, 30, SchemeType.DEBT, schedules)
    assert load_day_30 == Decimal("50.00")

    load_day_31 = calculate_lot_exit_load(units, nav, 31, SchemeType.DEBT, schedules)
    assert load_day_31 == Decimal("0.00")


# --- 4. Liquid Exit-Load Schedule for Days 1–7 ---

def test_liquid_exit_load_schedule_days_1_to_7():
    schedules = [
        ExitLoadSchedule(SchemeType.LIQUID, 1, 1, Decimal("0.0070")),
        ExitLoadSchedule(SchemeType.LIQUID, 2, 2, Decimal("0.0065")),
        ExitLoadSchedule(SchemeType.LIQUID, 3, 3, Decimal("0.0060")),
        ExitLoadSchedule(SchemeType.LIQUID, 4, 4, Decimal("0.0055")),
        ExitLoadSchedule(SchemeType.LIQUID, 5, 5, Decimal("0.0050")),
        ExitLoadSchedule(SchemeType.LIQUID, 6, 6, Decimal("0.0045")),
    ]
    units = Decimal("100.000")
    nav = Decimal("1000.0000")
    # Gross = 100,000.00

    assert calculate_lot_exit_load(units, nav, 0, SchemeType.LIQUID, schedules) == Decimal("0.00")
    assert calculate_lot_exit_load(units, nav, 1, SchemeType.LIQUID, schedules) == Decimal("7.00")
    assert calculate_lot_exit_load(units, nav, 2, SchemeType.LIQUID, schedules) == Decimal("6.50")
    assert calculate_lot_exit_load(units, nav, 3, SchemeType.LIQUID, schedules) == Decimal("6.00")
    assert calculate_lot_exit_load(units, nav, 4, SchemeType.LIQUID, schedules) == Decimal("5.50")
    assert calculate_lot_exit_load(units, nav, 5, SchemeType.LIQUID, schedules) == Decimal("5.00")
    assert calculate_lot_exit_load(units, nav, 6, SchemeType.LIQUID, schedules) == Decimal("4.50")
    assert calculate_lot_exit_load(units, nav, 7, SchemeType.LIQUID, schedules) == Decimal("0.00")


# --- 5. ELSS Three-Year Lock-in Boundary ---

def test_elss_three_year_lock_in_boundary():
    scheme = Scheme("SCH-03", "ELSS Tax Saver", SchemeType.EQUITY, elss=True)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-03", date(2023, 2, 16), Decimal("100.000"), Decimal("50.0000"))

    # Day before 3rd anniversary -> locked
    assert is_lot_locked(lot, date(2026, 2, 15), scheme) is True

    # Exact 3rd anniversary date -> unlocked
    assert is_lot_locked(lot, date(2026, 2, 16), scheme) is False

    # After 3rd anniversary date -> unlocked
    assert is_lot_locked(lot, date(2026, 2, 17), scheme) is False


# --- 6. Leap-Year ELSS Anniversary (2024-02-29 to 2027-02-28) ---

def test_leap_year_elss_anniversary():
    allotment = date(2024, 2, 29)
    lock_in_date = get_elss_lock_in_date(allotment)
    assert lock_in_date == date(2027, 2, 28)

    scheme = Scheme("SCH-03", "ELSS Tax Saver", SchemeType.EQUITY, elss=True)
    lot = InvestmentLot("LOT-LEAP", "FOL-01", "SCH-03", allotment, Decimal("50.000"), Decimal("100.0000"))

    assert is_lot_locked(lot, date(2027, 2, 27), scheme) is True
    assert is_lot_locked(lot, date(2027, 2, 28), scheme) is False


# --- 7. Rejection When All ELSS Lots Are Locked ---

def test_rejection_when_all_elss_lots_are_locked():
    lm = LotManager()
    scheme = Scheme("SCH-03", "ELSS Tax Saver", SchemeType.EQUITY, elss=True)
    lot = InvestmentLot("LOT-LOCKED", "FOL-01", "SCH-03", date(2025, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    as_of = date(2026, 1, 1)  # Only 1 year old -> locked until 2028-01-01
    available = lm.get_available_unlocked_units("FOL-01", "SCH-03", as_of, scheme)
    assert available == Decimal("0.000")

    with pytest.raises(ValueError, match="Insufficient unlocked units"):
        lm.deplete_units_fifo("FOL-01", "SCH-03", Decimal("10.000"), as_of, scheme, [], Decimal("60.0000"))


# --- 8. Preservation of Locked Lots During REDEEM ALL (EC-07) ---

def test_preservation_of_locked_lots_during_redeem_all():
    lm = LotManager()
    scheme = Scheme("SCH-03", "ELSS Tax Saver", SchemeType.EQUITY, elss=True)

    # Exactly models EC-07: LOT-021 unlocked, LOT-022 locked
    l21 = InvestmentLot("LOT-021", "FOL-008", "SCH-03", date(2023, 2, 16), Decimal("182.406"), Decimal("88.3100"))
    l22 = InvestmentLot("LOT-022", "FOL-008", "SCH-03", date(2024, 5, 10), Decimal("96.215"), Decimal("104.5520"))
    lm.add_lot(l21)
    lm.add_lot(l22)

    as_of = date(2026, 2, 16)
    available = lm.get_available_unlocked_units("FOL-008", "SCH-03", as_of, scheme)
    assert available == Decimal("182.406")

    # Redeem all available unlocked units
    lm.deplete_units_fifo("FOL-008", "SCH-03", available, as_of, scheme, [], Decimal("121.5999"))

    assert l21.units == Decimal("0.000")
    assert l22.units == Decimal("96.215")

    remaining = lm.get_remaining_lots_for_folio("FOL-008")
    assert len(remaining) == 1
    assert remaining[0].lot_id == "LOT-022"
    assert remaining[0].units == Decimal("96.215")


# --- 9. Non-Finite Lot Units and NAV Rejected ---

@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_lot_units_rejected(val):
    lm = LotManager()
    lot = InvestmentLot("LOT-BAD", "FOL-01", "SCH-01", date(2025, 1, 1), val, Decimal("100.0000"))
    with pytest.raises(ValueError, match="finite numbers"):
        lm.add_lot(lot)


@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_lot_nav_rejected(val):
    lm = LotManager()
    lot = InvestmentLot("LOT-BAD", "FOL-01", "SCH-01", date(2025, 1, 1), Decimal("10.000"), val)
    with pytest.raises(ValueError, match="finite numbers"):
        lm.add_lot(lot)


# --- 10. Zero and Negative Lot Values Rejected ---

@pytest.mark.parametrize("units", [Decimal("0.000"), Decimal("-10.000")])
def test_zero_or_negative_lot_units_rejected(units):
    lm = LotManager()
    lot = InvestmentLot("LOT-BAD", "FOL-01", "SCH-01", date(2025, 1, 1), units, Decimal("100.0000"))
    with pytest.raises(ValueError, match="greater than zero"):
        lm.add_lot(lot)


@pytest.mark.parametrize("nav", [Decimal("0.0000"), Decimal("-50.0000")])
def test_zero_or_negative_lot_nav_rejected(nav):
    lm = LotManager()
    lot = InvestmentLot("LOT-BAD", "FOL-01", "SCH-01", date(2025, 1, 1), Decimal("10.000"), nav)
    with pytest.raises(ValueError, match="greater than zero"):
        lm.add_lot(lot)


# --- 11. Invalid Lot Dates and Negative Holding Period Rejection ---

def test_invalid_lot_allotment_date_rejected():
    lm = LotManager()
    # Passing a non-date object for allotment date
    lot = InvestmentLot("LOT-BAD", "FOL-01", "SCH-01", "2025-01-01", Decimal("10.000"), Decimal("100.0000"))  # type: ignore
    with pytest.raises(ValueError, match="valid date"):
        lm.add_lot(lot)


def test_redemption_date_earlier_than_allotment_date_rejected():
    lm = LotManager()
    scheme = Scheme("SCH-01", "Bluechip Equity", SchemeType.EQUITY)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2025, 6, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    # Attempting to redeem on 2025-01-01 (before 2025-06-01)
    with pytest.raises(ValueError, match="earlier than lot allotment date"):
        lm.deplete_units_fifo("FOL-01", "SCH-01", Decimal("50.000"), date(2025, 1, 1), scheme, [], Decimal("55.0000"))


# --- 12. No Portfolio Mutation When Validation Fails ---

def test_no_portfolio_mutation_when_validation_fails():
    lm = LotManager()
    scheme = Scheme("SCH-01", "Bluechip Equity", SchemeType.EQUITY)
    l1 = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2025, 1, 1), Decimal("50.000"), Decimal("60.0000"))
    l2 = InvestmentLot("LOT-02", "FOL-01", "SCH-01", date(2025, 2, 1), Decimal("50.000"), Decimal("65.0000"))
    lm.add_lot(l1)
    lm.add_lot(l2)

    # 1. Failure due to insufficient unlocked units (request 150 > 100 available)
    with pytest.raises(ValueError, match="Insufficient unlocked units"):
        lm.deplete_units_fifo("FOL-01", "SCH-01", Decimal("150.000"), date(2026, 1, 1), scheme, [], Decimal("70.0000"))

    # State must be completely untouched
    assert l1.units == Decimal("50.000")
    assert l2.units == Decimal("50.000")

    # 2. Failure due to invalid redemption date
    with pytest.raises(ValueError, match="earlier than lot allotment date"):
        lm.deplete_units_fifo("FOL-01", "SCH-01", Decimal("20.000"), date(2024, 1, 1), scheme, [], Decimal("70.0000"))

    # State must still be completely untouched
    assert l1.units == Decimal("50.000")
    assert l2.units == Decimal("50.000")
