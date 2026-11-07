"""Unit and integration tests for mutual fund purchase calculations and BR-07."""

from decimal import Decimal
import pytest

from src.command_processor import CommandProcessor
from src.purchase_engine import (
    calculate_investible_amount,
    calculate_purchase,
    calculate_stamp_duty,
    calculate_units,
)


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


@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_purchase_amount_is_rejected(val):
    with pytest.raises(ValueError, match="finite number"):
        calculate_purchase(val, Decimal("100.0000"), is_first_purchase=True)


@pytest.mark.parametrize("val", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_nav_is_rejected(val):
    with pytest.raises(ValueError, match="finite number"):
        calculate_purchase(Decimal("5000"), val, is_first_purchase=True)


def test_stamp_duty_half_up_rounding():
    # 0.005% of 300 = 0.015 -> rounds up to 0.02
    assert calculate_stamp_duty(Decimal("300.00")) == Decimal("0.02")
    # 0.005% of 290 = 0.0145 -> rounds down to 0.01
    assert calculate_stamp_duty(Decimal("290.00")) == Decimal("0.01")


def test_units_round_down_strictly():
    # Investible: 1000.00, NAV: 9.9999 -> 100.00100001 -> 100.001
    # Investible: 99.9999, NAV: 1.0000 -> 99.999 (NOT 100.000)
    assert calculate_units(Decimal("99.9999"), Decimal("1.0000")) == Decimal("99.999")
    # Exact 3 decimals
    assert calculate_units(Decimal("100.000"), Decimal("10.0000")) == Decimal("10.000")


def test_custom_scheme_minimums():
    custom_first = Decimal("10000.00")
    custom_add = Decimal("2000.00")

    # Below custom first purchase minimum
    with pytest.raises(ValueError, match="at least ₹10000.00"):
        calculate_purchase(
            Decimal("9999.00"),
            Decimal("100.0000"),
            is_first_purchase=True,
            min_first_purchase=custom_first,
            min_additional=custom_add,
        )

    # Valid custom first purchase
    res1 = calculate_purchase(
        Decimal("10000.00"),
        Decimal("100.0000"),
        is_first_purchase=True,
        min_first_purchase=custom_first,
        min_additional=custom_add,
    )
    assert res1["investible_amount"] == Decimal("9999.50")

    # Below custom additional minimum
    with pytest.raises(ValueError, match="at least ₹2000.00"):
        calculate_purchase(
            Decimal("1999.00"),
            Decimal("100.0000"),
            is_first_purchase=False,
            min_first_purchase=custom_first,
            min_additional=custom_add,
        )

    # Valid custom additional purchase
    res2 = calculate_purchase(
        Decimal("2000.00"),
        Decimal("100.0000"),
        is_first_purchase=False,
        min_first_purchase=custom_first,
        min_additional=custom_add,
    )
    assert res2["investible_amount"] == Decimal("1999.90")


def test_command_processor_purchase_creates_lot_and_confirmation():
    cp = CommandProcessor()
    cp.load_reference_data()

    # Process valid first purchase
    initial_lots = len(cp.lot_manager.get_remaining_lots_for_folio("FOL-006"))
    cp.process_purchase(
        order_id="ORD-TEST-01",
        order_ts_str="2026-02-24 13:29:59",
        folio_id="FOL-006",
        scheme_id="SCH-06",
        amount_str="5000.00",
        realised_ts_str="2026-02-24 13:29:59",
    )

    new_lots = cp.lot_manager.get_remaining_lots_for_folio("FOL-006")
    assert len(new_lots) == initial_lots + 1
    created_lot = [lot for lot in new_lots if lot.lot_id == "ORD-TEST-01"][0]
    assert created_lot.lot_id == "ORD-TEST-01"
    assert created_lot.scheme_id == "SCH-06"
    assert created_lot.units > Decimal("0")

    last_conf = cp.confirmations[-1]
    assert last_conf["order_id"] == "ORD-TEST-01"
    assert last_conf["decision"] == "ACCEPTED"
    assert last_conf["txn_type"] == "PURCHASE"
    assert last_conf["rule_ids"] == "BR-01;BR-02;BR-07"
    assert last_conf["exit_load"] == "0.00"
    assert last_conf["payout_date"] == ""


def test_command_processor_purchase_below_minimum_rejected():
    cp = CommandProcessor()
    cp.load_reference_data()

    cp.process_purchase(
        order_id="ORD-TEST-REJ",
        order_ts_str="2026-02-24 11:00:00",
        folio_id="FOL-006",
        scheme_id="SCH-06",
        amount_str="4999.99",
        realised_ts_str="2026-02-24 11:00:00",
    )

    last_conf = cp.confirmations[-1]
    assert last_conf["order_id"] == "ORD-TEST-REJ"
    assert last_conf["decision"] == "REJECTED"
    assert last_conf["rule_ids"] == "BR-07"
    assert last_conf["units"] == ""
    assert last_conf["nav"] == ""
    assert last_conf["gross_amount"] == ""
