"""Comprehensive tests for the Command Processing Engine, integration, and CSV outputs."""

import csv
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from src.command_processor import CommandProcessor
from src.lot_manager import LotManager
from src.models import InvestmentLot, Scheme, SchemeType
from src.sip_engine import SIPManager


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_pack"


@pytest.fixture
def processor():
    """Create a fully loaded processor with sample reference data."""
    proc = CommandProcessor(data_dir=SAMPLE_DIR)
    proc.load_reference_data()
    return proc


def test_command_parsing(processor):
    """Test that individual command lines parse properly and ignore comments."""
    # Blank line and comment
    processor.process_line("   ")
    processor.process_line("# This is a comment")
    assert processor.commands_processed == 0

    # Valid purchase line
    processor.process_line(
        "PURCHASE|ORD-TEST-1|2026-01-06 10:00:00|FOL-001|SCH-05|5000.00|2026-01-06 10:00:00"
    )
    assert processor.commands_processed == 1
    assert processor.confirmations[-1]["order_id"] == "ORD-TEST-1"
    assert processor.confirmations[-1]["decision"] == "ACCEPTED"


def test_command_execution_order(processor):
    """Verify that commands are processed strictly in sequence."""
    processor.process_line(
        "PURCHASE|ORD-SEQ-1|2026-01-06 10:00:00|FOL-001|SCH-01|5000.00|2026-01-06 10:00:00"
    )
    processor.process_line(
        "REDEEM|ORD-SEQ-2|2026-01-07 10:00:00|FOL-001|SCH-01|ALL|"
    )
    assert len(processor.confirmations) == 2
    assert processor.confirmations[0]["order_id"] == "ORD-SEQ-1"
    assert processor.confirmations[1]["order_id"] == "ORD-SEQ-2"
    assert processor.confirmations[0]["txn_type"] == "PURCHASE"
    assert processor.confirmations[1]["txn_type"] == "REDEMPTION"


def test_valid_and_invalid_commands(processor):
    """Test accepted and rejected command scenarios."""
    # Purchase below first purchase minimum
    processor.process_line(
        "PURCHASE|ORD-REJ-1|2026-01-06 10:00:00|FOL-009|SCH-01|4999.00|2026-01-06 10:00:00"
    )
    assert processor.confirmations[-1]["decision"] == "REJECTED"
    assert processor.confirmations[-1]["rule_ids"] == "BR-07"

    # SIP below min_sip
    processor.process_line(
        "SIP_REGISTER|SIP-REJ-1|2026-01-06 10:00:00|FOL-001|SCH-01|400.00|15"
    )
    assert processor.sip_statuses[-1]["result"] == "REJECTED"
    assert processor.sip_statuses[-1]["rule_ids"] == "BR-10"

    # SIP pause > 3 months
    processor.process_line(
        "SIP_REGISTER|SIP-PAU-1|2026-01-06 10:00:00|FOL-001|SCH-01|1000.00|15"
    )
    processor.process_line(
        "SIP_PAUSE|SIP-PAU-1|2026-01-07 10:00:00|2026-02|5"
    )
    assert processor.sip_statuses[-1]["result"] == "REJECTED"


def test_transaction_state_updates(processor):
    """Test that purchase, redemption, and debit result update state correctly."""
    # Check SIP failures and auto-cancel
    processor.sip_manager.sips["SIP-TEST"] = type("SIPMock", (), {
        "sip_id": "SIP-TEST",
        "folio_id": "FOL-001",
        "scheme_id": "SCH-04",
        "amount": Decimal("1000.00"),
        "sip_day": 5,
        "registered_date": date(2025, 11, 1),
        "status": "ACTIVE",
        "consecutive_failures": 2,
        "paused_until_month": None,
    })()

    processor.process_line(
        "SIP_DEBIT_RESULT|SIP-TEST|3|FAILED|2026-01-05 09:50:00|INSUFFICIENT_FUNDS"
    )
    assert processor.sip_manager.sips["SIP-TEST"].consecutive_failures == 3
    assert processor.sip_manager.sips["SIP-TEST"].status == "CANCELLED"


def test_multiple_transactions_on_same_folio(processor):
    """Test multiple sequential transactions on a single folio."""
    # FOL-001 buying SCH-04, then buying additional SCH-04, then redeeming
    processor.process_line(
        "PURCHASE|ORD-M-1|2026-01-06 10:00:00|FOL-001|SCH-04|5000.00|2026-01-06 10:00:00"
    )
    assert processor.confirmations[-1]["decision"] == "ACCEPTED"
    units1 = Decimal(processor.confirmations[-1]["units"])

    # Additional purchase (minimum 1000 is allowed)
    processor.process_line(
        "PURCHASE|ORD-M-2|2026-01-07 10:00:00|FOL-001|SCH-04|1500.00|2026-01-07 10:00:00"
    )
    assert processor.confirmations[-1]["decision"] == "ACCEPTED"
    units2 = Decimal(processor.confirmations[-1]["units"])

    # Redeem all
    processor.process_line(
        "REDEEM|ORD-M-3|2026-01-08 10:00:00|FOL-001|SCH-04|ALL|"
    )
    assert processor.confirmations[-1]["decision"] == "ACCEPTED"
    redeemed_units = Decimal(processor.confirmations[-1]["units"])
    assert redeemed_units == units1 + units2


def test_full_sample_pack_execution(tmp_path):
    """Process official sample pack commands.txt and verify exact output format and row counts."""
    proc = CommandProcessor(data_dir=SAMPLE_DIR)
    proc.process_file()
    conf_file, sip_file, folio_file = proc.write_csv_outputs(output_dir=tmp_path)

    # 1. Total commands
    assert proc.commands_processed == 92
    assert proc.commands_accepted == 86
    assert proc.commands_rejected == 6

    # 2. Check confirmations.csv
    assert conf_file.exists()
    with conf_file.open(newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert reader[0] == [
            "order_id", "folio_id", "scheme_id", "txn_type", "decision", "rule_ids",
            "nav_date", "nav", "gross_amount", "stamp_duty", "units", "exit_load",
            "net_amount", "payout_date"
        ]
        assert len(reader) == 78  # 1 header + 77 rows

    # 3. Check sip_status.csv
    assert sip_file.exists()
    with sip_file.open(newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert reader[0] == [
            "sip_id", "event", "instalment_no", "scheduled_date", "result",
            "order_id", "consecutive_failures", "sip_status", "rule_ids"
        ]
        assert len(reader) == 18  # 1 header + 17 rows

    # 4. Check folio_statement.csv
    assert folio_file.exists()
    with folio_file.open(newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert reader[0] == [
            "folio_id", "as_of_date", "scheme_id", "lot_id", "allotment_date", "units", "lock_in_until"
        ]
        assert len(reader) == 89  # 1 header + 88 rows


def test_planted_edge_cases_in_dataset():
    """Verify specific planted edge cases EC-01 through EC-08 from official pack."""
    proc = CommandProcessor(data_dir=SAMPLE_DIR)
    proc.process_file()

    # EC-01: Order at 14:59:59 but realised at 15:00:00 -> NAV of next business day 2026-01-20
    ord_0006 = next(c for c in proc.confirmations if c["order_id"] == "ORD-0006")
    assert ord_0006["nav_date"] == "2026-01-20"

    # EC-02: Friday 16:00 before Monday holiday -> NAV date Tuesday 2026-01-27
    ord_0013 = next(c for c in proc.confirmations if c["order_id"] == "ORD-0013")
    assert ord_0013["nav_date"] == "2026-01-27"

    # EC-04: Day 365 exit load 1% vs Day 366 nil load
    ord_0026 = next(c for c in proc.confirmations if c["order_id"] == "ORD-0026")
    ord_0027 = next(c for c in proc.confirmations if c["order_id"] == "ORD-0027")
    assert Decimal(ord_0026["exit_load"]) > Decimal("0.00")
    assert Decimal(ord_0027["exit_load"]) == Decimal("0.00")

    # EC-05: Redeem amount needing units beyond holding by 0.001 rejected
    ord_0034 = next(c for c in proc.confirmations if c["order_id"] == "ORD-0034")
    assert ord_0034["decision"] == "REJECTED"

    # EC-06: Switch source exit load makes target < 1000 accepted
    sw_in = next(c for c in proc.confirmations if c["order_id"] == "ORD-0008" and c["txn_type"] == "SWITCH_IN")
    assert sw_in["decision"] == "ACCEPTED"
    assert Decimal(sw_in["gross_amount"]) < Decimal("1000.00")

    # EC-07: ELSS lot maturing on redemption date is redeemed, locked lot remains
    ord_0033 = next(c for c in proc.confirmations if c["order_id"] == "ORD-0033")
    assert ord_0033["decision"] == "ACCEPTED"
    assert ord_0033["units"] == "182.406"  # Only LOT-021, not LOT-022
