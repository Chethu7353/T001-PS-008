"""Unit and edge-case tests for mutual fund switch processing (BR-09)."""

from datetime import date, datetime
from decimal import Decimal
import pytest

from src.command_processor import CommandProcessor
from src.exit_load_engine import ExitLoadSchedule
from src.lot_manager import LotManager
from src.models import InvestmentLot, Scheme, SchemeType
from src.switch_engine import process_switch


def test_successful_switch_units_mode():
    lm = LotManager()
    from_sch = Scheme("SCH-01", "Source Equity", SchemeType.EQUITY)
    to_sch = Scheme("SCH-04", "Target Debt", SchemeType.DEBT)
    schedules = [ExitLoadSchedule(SchemeType.EQUITY, 0, 365, Decimal("1.0000"))]

    # Lot held for > 365 days (allotted 2024-01-01, switch on 2026-01-15 -> 0% exit load)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2024, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    def nav_lookup(sid, d):
        return Decimal("100.0000") if sid == "SCH-01" else Decimal("25.0000")

    order_ts = datetime(2026, 1, 15, 11, 0)
    out_rec, in_rec = process_switch(
        order_id="ORD-SW-01",
        order_ts=order_ts,
        folio_id="FOL-01",
        from_scheme=from_sch,
        to_scheme=to_sch,
        mode="UNITS",
        value="50.000",
        lot_manager=lm,
        schedules=schedules,
        get_nav_func=nav_lookup,
        holidays=set(),
    )

    # Source checks
    assert out_rec["decision"] == "ACCEPTED"
    assert out_rec["units"] == "50.000"
    assert out_rec["gross_amount"] == "5000.00"
    assert out_rec["exit_load"] == "0.00"
    assert out_rec["net_amount"] == "5000.00"
    assert out_rec["payout_date"] == "2026-01-19"  # Thursday -> Friday -> Monday T+2

    # Target checks (Gross = 5000.00, stamp duty 0.005% = 0.25, investible = 4999.75, units at 25.0000 = 199.990)
    assert in_rec["decision"] == "ACCEPTED"
    assert in_rec["gross_amount"] == "5000.00"
    assert in_rec["stamp_duty"] == "0.25"
    assert in_rec["net_amount"] == "4999.75"
    assert in_rec["units"] == "199.990"
    assert in_rec["payout_date"] == ""

    # Portfolio updates
    assert lot.units == Decimal("50.000")
    target_lots = lm.get_remaining_lots_for_folio("FOL-01")
    assert any(l.scheme_id == "SCH-04" and l.units == Decimal("199.990") for l in target_lots)


def test_switch_all_mode():
    lm = LotManager()
    from_sch = Scheme("SCH-01", "Source Equity", SchemeType.EQUITY)
    to_sch = Scheme("SCH-04", "Target Debt", SchemeType.DEBT)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2024, 1, 1), Decimal("40.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    def nav_lookup(sid, d):
        return Decimal("50.0000") if sid == "SCH-01" else Decimal("10.0000")

    out_rec, in_rec = process_switch(
        order_id="ORD-SW-ALL",
        order_ts=datetime(2026, 1, 15, 11, 0),
        folio_id="FOL-01",
        from_scheme=from_sch,
        to_scheme=to_sch,
        mode="ALL",
        value="",
        lot_manager=lm,
        schedules=[],
        get_nav_func=nav_lookup,
        holidays=set(),
    )

    assert out_rec["decision"] == "ACCEPTED"
    assert out_rec["units"] == "40.000"
    assert lot.units == Decimal("0.000")
    assert in_rec["decision"] == "ACCEPTED"


def test_switch_amount_mode_ceiling_rounding():
    lm = LotManager()
    from_sch = Scheme("SCH-01", "Source Equity", SchemeType.EQUITY)
    to_sch = Scheme("SCH-04", "Target Debt", SchemeType.DEBT)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2024, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    def nav_lookup(sid, d):
        return Decimal("30.0000") if sid == "SCH-01" else Decimal("10.0000")

    # Request ₹1,000.01 at NAV 30.0000 -> 1000.01 / 30 = 33.33366... -> ceil3 = 33.334 units
    out_rec, in_rec = process_switch(
        order_id="ORD-SW-AMT",
        order_ts=datetime(2026, 1, 15, 11, 0),
        folio_id="FOL-01",
        from_scheme=from_sch,
        to_scheme=to_sch,
        mode="AMOUNT",
        value="1000.01",
        lot_manager=lm,
        schedules=[],
        get_nav_func=nav_lookup,
        holidays=set(),
    )

    assert out_rec["decision"] == "ACCEPTED"
    assert out_rec["units"] == "33.334"


def test_same_scheme_switch_rejected():
    lm = LotManager()
    sch = Scheme("SCH-01", "Source Equity", SchemeType.EQUITY)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2024, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    out_rec, in_rec = process_switch(
        order_id="ORD-SW-SAME",
        order_ts=datetime(2026, 1, 15, 11, 0),
        folio_id="FOL-01",
        from_scheme=sch,
        to_scheme=sch,
        mode="UNITS",
        value="10.000",
        lot_manager=lm,
        schedules=[],
        get_nav_func=lambda s, d: Decimal("50.0000"),
        holidays=set(),
    )

    assert out_rec["decision"] == "REJECTED"
    assert out_rec["rule_ids"] == "BR-09"
    assert in_rec["decision"] == "REJECTED"
    assert in_rec["rule_ids"] == "BR-09"
    # No portfolio change
    assert lot.units == Decimal("100.000")


def test_insufficient_source_units_rejected():
    lm = LotManager()
    from_sch = Scheme("SCH-01", "Source Equity", SchemeType.EQUITY)
    to_sch = Scheme("SCH-04", "Target Debt", SchemeType.DEBT)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2024, 1, 1), Decimal("10.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    out_rec, in_rec = process_switch(
        order_id="ORD-SW-INSUF",
        order_ts=datetime(2026, 1, 15, 11, 0),
        folio_id="FOL-01",
        from_scheme=from_sch,
        to_scheme=to_sch,
        mode="UNITS",
        value="10.001",
        lot_manager=lm,
        schedules=[],
        get_nav_func=lambda s, d: Decimal("50.0000"),
        holidays=set(),
    )

    assert out_rec["decision"] == "REJECTED"
    assert out_rec["rule_ids"] == "BR-08"
    assert in_rec["decision"] == "REJECTED"
    assert lot.units == Decimal("10.000")


def test_elss_locked_units_switch_rejected_br11():
    lm = LotManager()
    from_sch = Scheme("SCH-03", "ELSS Tax Saver", SchemeType.EQUITY, elss=True)
    to_sch = Scheme("SCH-04", "Target Debt", SchemeType.DEBT)
    # Locked lot: allotted on 2025-01-01, switch on 2026-01-15 (only 1 year old)
    lot = InvestmentLot("LOT-ELSS", "FOL-01", "SCH-03", date(2025, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    out_rec, in_rec = process_switch(
        order_id="ORD-SW-ELSS",
        order_ts=datetime(2026, 1, 15, 11, 0),
        folio_id="FOL-01",
        from_scheme=from_sch,
        to_scheme=to_sch,
        mode="ALL",
        value="",
        lot_manager=lm,
        schedules=[],
        get_nav_func=lambda s, d: Decimal("50.0000"),
        holidays=set(),
    )

    assert out_rec["decision"] == "REJECTED"
    assert out_rec["rule_ids"] == "BR-11"
    assert in_rec["decision"] == "REJECTED"
    assert in_rec["rule_ids"] == "BR-11"
    assert lot.units == Decimal("100.000")


@pytest.mark.parametrize("val", ["NaN", "Infinity", "-Infinity", "0", "-5"])
def test_non_finite_and_negative_switch_inputs_rejected(val):
    lm = LotManager()
    from_sch = Scheme("SCH-01", "Source Equity", SchemeType.EQUITY)
    to_sch = Scheme("SCH-04", "Target Debt", SchemeType.DEBT)
    lot = InvestmentLot("LOT-01", "FOL-01", "SCH-01", date(2024, 1, 1), Decimal("100.000"), Decimal("50.0000"))
    lm.add_lot(lot)

    out_rec, in_rec = process_switch(
        order_id="ORD-SW-BAD",
        order_ts=datetime(2026, 1, 15, 11, 0),
        folio_id="FOL-01",
        from_scheme=from_sch,
        to_scheme=to_sch,
        mode="UNITS",
        value=val,
        lot_manager=lm,
        schedules=[],
        get_nav_func=lambda s, d: Decimal("50.0000"),
        holidays=set(),
    )

    assert out_rec["decision"] == "REJECTED"
    assert in_rec["decision"] == "REJECTED"
    assert lot.units == Decimal("100.000")


def test_command_processor_invalid_folio_or_scheme_rejected():
    cp = CommandProcessor()
    cp.load_reference_data()

    initial_rejected = cp.commands_rejected
    cp.process_switch_cmd(
        order_id="ORD-SW-INV",
        order_ts_str="2026-01-22 12:10:00",
        folio_id="FOL-UNKNOWN",
        from_scheme_id="SCH-02",
        to_scheme_id="SCH-05",
        mode="AMOUNT",
        value_str="1005.00",
    )

    assert cp.commands_rejected == initial_rejected + 1
    assert cp.confirmations[-2]["decision"] == "REJECTED"
    assert cp.confirmations[-2]["txn_type"] == "SWITCH_OUT"
    assert cp.confirmations[-1]["decision"] == "REJECTED"
    assert cp.confirmations[-1]["txn_type"] == "SWITCH_IN"


def test_ec06_official_sample_pack_switch_behavior():
    """Verify EC-06 exact calculation: source exit load drops target proceeds below ₹1,000, target minimum waived."""
    cp = CommandProcessor()
    cp.load_reference_data()

    # Find LOT-019 for FOL-007 SCH-02 in lot_manager
    lot19 = [l for l in cp.lot_manager.lots[("FOL-007", "SCH-02")] if l.lot_id == "LOT-019"][0]
    initial_source_units = lot19.units

    # Process ORD-0008: SWITCH Rs 1005.00 from SCH-02 to SCH-05
    cp.process_switch_cmd(
        order_id="ORD-0008-TEST",
        order_ts_str="2026-01-22 12:10:00",
        folio_id="FOL-007",
        from_scheme_id="SCH-02",
        to_scheme_id="SCH-05",
        mode="AMOUNT",
        value_str="1005.00",
    )

    out_rec = cp.confirmations[-2]
    in_rec = cp.confirmations[-1]

    # Source assertions
    assert out_rec["order_id"] == "ORD-0008-TEST"
    assert out_rec["txn_type"] == "SWITCH_OUT"
    assert out_rec["decision"] == "ACCEPTED"
    assert out_rec["nav"] == "55.1985"
    assert out_rec["gross_amount"] == "1005.05"
    assert out_rec["exit_load"] == "10.05"
    assert out_rec["net_amount"] == "995.00"
    assert out_rec["units"] == "18.208"

    # Target assertions (target minimum waived despite gross ₹995.00 < ₹1,000)
    assert in_rec["order_id"] == "ORD-0008-TEST"
    assert in_rec["txn_type"] == "SWITCH_IN"
    assert in_rec["decision"] == "ACCEPTED"
    assert in_rec["gross_amount"] == "995.00"
    assert in_rec["stamp_duty"] == "0.05"
    assert in_rec["net_amount"] == "994.95"
    assert in_rec["nav"] == "28.8712"
    assert in_rec["units"] == "34.461"

    # Portfolio balance assertion
    assert lot19.units == initial_source_units - Decimal("18.208")
    target_lots = [l for l in cp.lot_manager.lots[("FOL-007", "SCH-05")] if l.lot_id == "ORD-0008-TEST"]
    assert len(target_lots) == 1
    assert target_lots[0].units == Decimal("34.461")
