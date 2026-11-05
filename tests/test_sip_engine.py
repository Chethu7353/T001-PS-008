from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.command_processor import CommandProcessor
from src.models import SIP
from src.sip_engine import (
    SIPManager,
    calculate_first_instalment_date,
    calculate_instalment_date,
    calculate_scheduled_date,
)


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_pack"


def test_ec03_day_31_clamps_february_then_advances_weekend():
    holidays = {date(2026, 3, 20)}

    assert calculate_first_instalment_date(date(2026, 1, 31), 31, holidays) == date(2026, 3, 2)
    assert calculate_instalment_date(date(2026, 1, 31), 31, 2, holidays) == date(2026, 3, 31)
    assert calculate_scheduled_date(2026, 3, 20, holidays) == date(2026, 3, 23)


def test_exactly_seven_day_first_installment_is_allowed():
    assert calculate_first_instalment_date(
        date(2026, 1, 29), 5, set()
    ) == date(2026, 2, 5)


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


def test_pause_validates_duration_month_and_records_all_months():
    manager = SIPManager()
    manager.sips["SIP-X"] = SIP(
        "SIP-X", "FOL-001", "SCH-01", Decimal("500"), 10, date(2026, 1, 1)
    )
    requested_at = datetime(2026, 1, 1, 9, 0)

    assert manager.pause_sip("SIP-X", requested_at, "2026-11", 3) == (True, "ACCEPTED")
    assert manager.sips["SIP-X"].paused_months == {"2026-11", "2026-12", "2027-01"}
    assert manager.pause_sip("SIP-X", requested_at, "2026-02", 4) == (False, "REJECTED")
    assert manager.pause_sip("SIP-X", requested_at, "2026-13", 1) == (False, "REJECTED")


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
