"""Comprehensive unit and edge-case tests for SIP registration, scheduling, debit results, and pauses (BR-10)."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.command_processor import CommandProcessor
from src.models import SIP, Scheme, SchemeType
from src.sip_engine import (
    SIPManager,
    calculate_first_instalment_date,
    calculate_instalment_date,
    calculate_scheduled_date,
)


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_pack"


# --- EC-03: SIP Date Clamping & Weekend/Holiday Adjustment ---

def test_ec03_day_31_clamps_february_then_advances_weekend():
    """EC-03: SIP on 31st clamps to Feb 28 (Saturday) -> advances to Mon Mar 2; next cycle Mar 31."""
    holidays = {date(2026, 3, 20)}

    assert calculate_first_instalment_date(date(2026, 1, 31), 31, holidays) == date(2026, 3, 2)
    assert calculate_instalment_date(date(2026, 1, 31), 31, 2, holidays) == date(2026, 3, 31)
    # Holiday shift check (Id-ul-Fitr on Friday 2026-03-20 moves to Monday 2026-03-23)
    assert calculate_scheduled_date(2026, 3, 20, holidays) == date(2026, 3, 23)


def test_exactly_seven_day_first_installment_is_allowed():
    """SIP-N02: Registered 2026-01-29 with sip_day 5 -> 2026-02-05 is exactly 7 days later."""
    assert calculate_first_instalment_date(
        date(2026, 1, 29), 5, set()
    ) == date(2026, 2, 5)


def test_less_than_seven_days_moves_to_subsequent_month():
    """Registered on 2026-01-29 with sip_day 1 -> only 3 days away, moves to March 1 (or next business day)."""
    assert calculate_first_instalment_date(
        date(2026, 1, 29), 1, set()
    ) == date(2026, 3, 2)  # March 1 is Sunday -> March 2 Monday


# --- EC-08: Consecutive Failure Tracking & Reset ---

def test_ec08_consecutive_failure_counter_reset_on_success():
    """EC-08: 2 failures -> 1 success (resets to 0) -> 2 failures -> remains ACTIVE with count 2."""
    manager = SIPManager()
    manager.sips["SIP-E01"] = SIP(
        "SIP-E01", "FOL-009", "SCH-01", Decimal("5000.00"), 10,
        date(2025, 10, 20), status="ACTIVE", consecutive_failures=2,
    )

    # Instalment 3: SUCCESS -> resets to 0
    ok, cf, st = manager.record_debit_result("SIP-E01", 3, "SUCCESS")
    assert ok is True
    assert cf == 0
    assert st == "ACTIVE"

    # Instalment 4: FAILED -> count 1
    ok, cf, st = manager.record_debit_result("SIP-E01", 4, "FAILED")
    assert ok is False
    assert cf == 1
    assert st == "ACTIVE"

    # Instalment 5: FAILED -> count 2
    ok, cf, st = manager.record_debit_result("SIP-E01", 5, "FAILED")
    assert ok is False
    assert cf == 2
    assert st == "ACTIVE"


def test_three_consecutive_failures_cancels_sip():
    """3 consecutive failures automatically sets status to CANCELLED."""
    manager = SIPManager()
    manager.sips["SIP-AUTO"] = SIP(
        "SIP-AUTO", "FOL-001", "SCH-01", Decimal("1000.00"), 5,
        date(2026, 1, 1), status="ACTIVE", consecutive_failures=2,
    )

    ok, cf, st = manager.record_debit_result("SIP-AUTO", 3, "FAILED")
    assert ok is False
    assert cf == 3
    assert st == "CANCELLED"

    # Further attempt on cancelled SIP returns False and stays CANCELLED
    ok, cf, st = manager.record_debit_result("SIP-AUTO", 4, "FAILED")
    assert ok is False
    assert st == "CANCELLED"


# --- SIP Registration Validations ---

def test_sip_registration_below_minimum_amount_rejected():
    """Instalment below scheme.min_sip (e.g. ₹499 < ₹500) must be rejected."""
    manager = SIPManager()
    scheme = Scheme("SCH-01", "Bluechip", SchemeType.EQUITY, min_sip=Decimal("500.00"))

    ok, dec, fdate = manager.register_sip(
        "SIP-LOW", datetime(2026, 1, 1, 10, 0), "FOL-001", "SCH-01",
        Decimal("499.00"), 10, scheme, set()
    )
    assert ok is False
    assert dec == "REJECTED"
    assert fdate is None


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("0"), Decimal("-100")])
def test_non_finite_and_negative_sip_amount_rejected(amount):
    manager = SIPManager()
    scheme = Scheme("SCH-01", "Bluechip", SchemeType.EQUITY, min_sip=Decimal("500.00"))

    ok, dec, _ = manager.register_sip(
        "SIP-BAD", datetime(2026, 1, 1, 10, 0), "FOL-001", "SCH-01",
        amount, 10, scheme, set()
    )
    assert ok is False
    assert dec == "REJECTED"


@pytest.mark.parametrize("bad_day", [0, 32, -1, 100])
def test_invalid_sip_day_rejected(bad_day):
    manager = SIPManager()
    scheme = Scheme("SCH-01", "Bluechip", SchemeType.EQUITY, min_sip=Decimal("500.00"))

    ok, dec, _ = manager.register_sip(
        "SIP-DAY", datetime(2026, 1, 1, 10, 0), "FOL-001", "SCH-01",
        Decimal("1000.00"), bad_day, scheme, set()
    )
    assert ok is False
    assert dec == "REJECTED"


def test_duplicate_sip_id_rejected():
    manager = SIPManager()
    scheme = Scheme("SCH-01", "Bluechip", SchemeType.EQUITY, min_sip=Decimal("500.00"))
    manager.sips["SIP-DUP"] = SIP("SIP-DUP", "FOL-001", "SCH-01", Decimal("1000"), 10, date(2026, 1, 1))

    ok, dec, _ = manager.register_sip(
        "SIP-DUP", datetime(2026, 1, 2, 10, 0), "FOL-001", "SCH-01",
        Decimal("1000.00"), 10, scheme, set()
    )
    assert ok is False
    assert dec == "REJECTED"


# --- Pause Validations ---

def test_pause_validates_duration_and_annual_limit():
    manager = SIPManager()
    manager.sips["SIP-P"] = SIP("SIP-P", "FOL-001", "SCH-01", Decimal("1000"), 10, date(2026, 1, 1))
    req = datetime(2026, 1, 15, 10, 0)

    # 1. More than 3 months rejected
    assert manager.pause_sip("SIP-P", req, "2026-02", 4) == (False, "REJECTED")

    # 2. 0 or negative months rejected
    assert manager.pause_sip("SIP-P", req, "2026-02", 0) == (False, "REJECTED")

    # 3. Valid 2 months accepted
    assert manager.pause_sip("SIP-P", req, "2026-02", 2) == (True, "ACCEPTED")
    assert manager.sips["SIP-P"].paused_months == {"2026-02", "2026-03"}

    # 4. Second pause in the same year rejected (annual limit)
    assert manager.pause_sip("SIP-P", req, "2026-06", 1) == (False, "REJECTED")


def test_pause_cancelled_sip_rejected():
    manager = SIPManager()
    manager.sips["SIP-C"] = SIP("SIP-C", "FOL-001", "SCH-01", Decimal("1000"), 10, date(2026, 1, 1), status="CANCELLED")
    assert manager.pause_sip("SIP-C", datetime(2026, 1, 15, 10, 0), "2026-02", 1) == (False, "REJECTED")


# --- Existing Regression & File Checks ---

def test_existing_sip_history_matches_opening_failure_snapshot():
    manager = SIPManager()
    manager.load_existing_sips(
        SAMPLE_DIR / "existing_sips.csv", SAMPLE_DIR / "sip_history.csv"
    )

    assert manager.sips["SIP-E01"].consecutive_failures == 2
    assert manager.sips["SIP-E02"].consecutive_failures == 1


def test_existing_sip_history_mismatch_is_detected(tmp_path):
    opening = tmp_path / "existing_sips.csv"
    history = tmp_path / "sip_history.csv"
    opening.write_text(
        "sip_id,folio_id,scheme_id,amount,sip_day,registered_date,status,consecutive_failures\n"
        "SIP-X,FOL-001,SCH-01,500.00,10,2025-10-20,ACTIVE,0\n",
        encoding="utf-8",
    )
    history.write_text(
        "sip_id,instalment_no,instalment_date,result,reason\n"
        "SIP-X,1,2025-11-10,FAILED,INSUFFICIENT_FUNDS\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match opening failure count"):
        SIPManager().load_existing_sips(opening, history)


def test_invalid_debit_result_is_rejected_without_changing_state():
    manager = SIPManager()
    manager.sips["SIP-X"] = SIP(
        "SIP-X", "FOL-001", "SCH-01", Decimal("500"), 10,
        date(2026, 1, 1), consecutive_failures=2,
    )

    with pytest.raises(ValueError, match="SUCCESS or FAILED"):
        manager.record_debit_result("SIP-X", 1, "PENDING")

    assert manager.sips["SIP-X"].consecutive_failures == 2
    assert manager.sips["SIP-X"].status == "ACTIVE"


def test_command_processor_sip_register_invalid_folio_or_scheme_rejected():
    cp = CommandProcessor(data_dir=SAMPLE_DIR)
    cp.load_reference_data()

    cp.process_sip_register("SIP-BADFOLIO", "2026-01-15 10:00:00", "FOL-UNKNOWN", "SCH-01", "1000.00", "10")
    assert cp.sip_statuses[-1]["sip_id"] == "SIP-BADFOLIO"
    assert cp.sip_statuses[-1]["result"] == "REJECTED"


def test_sample_sip_status_uses_schedule_and_failure_transitions():
    processor = CommandProcessor(data_dir=SAMPLE_DIR)
    processor.process_file()

    statuses = [row for row in processor.sip_statuses if row["sip_id"] == "SIP-N01"]
    assert [row["scheduled_date"] for row in statuses] == [
        "2026-03-02", "2026-03-02", "2026-03-31"
    ]

    n02 = [row for row in processor.sip_statuses if row["sip_id"] == "SIP-N02"]
    assert n02[0]["scheduled_date"] == "2026-02-05"
    assert n02[1]["scheduled_date"] == "2026-02-05"

    e01 = [row for row in processor.sip_statuses if row["sip_id"] == "SIP-E01"]
    assert [(row["consecutive_failures"], row["sip_status"]) for row in e01[-3:]] == [
        ("0", "ACTIVE"), ("1", "ACTIVE"), ("2", "ACTIVE")
    ]

    e02 = [row for row in processor.sip_statuses if row["sip_id"] == "SIP-E02"]
    assert e02[-1]["consecutive_failures"] == "3"
    assert e02[-1]["sip_status"] == "CANCELLED"


def test_scheduled_date_comes_from_cycle_not_realised_date():
    processor = CommandProcessor(data_dir=SAMPLE_DIR)
    processor.load_reference_data()
    processor.process_line(
        "SIP_DEBIT_RESULT|SIP-E01|3|SUCCESS|2026-01-13 09:40:00|"
    )

    assert processor.sip_statuses[-1]["scheduled_date"] == "2026-01-12"
