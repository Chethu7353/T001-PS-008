from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from src.models import SchemeType
from src.nav_engine import (
    get_applicable_nav_date,
    get_nav_cutoff,
    get_nav_value,
    is_business_day,
    load_navs,
    next_business_day,
    previous_business_day,
)


HOLIDAY = date(2026, 1, 26)


def test_normal_weekday_is_business_day():
    assert is_business_day(date(2026, 1, 23))


def test_weekend_is_not_business_day():
    assert not is_business_day(date(2026, 1, 24))


def test_listed_holiday_is_not_business_day():
    assert not is_business_day(HOLIDAY, {HOLIDAY})


def test_next_business_day_skips_weekend_and_holiday():
    assert next_business_day(date(2026, 1, 23), {HOLIDAY}) == date(2026, 1, 27)


def test_previous_business_day_skips_weekend():
    assert previous_business_day(date(2026, 1, 26), {HOLIDAY}) == date(2026, 1, 23)


def test_equity_before_cutoff_uses_same_day():
    result = get_applicable_nav_date(SchemeType.EQUITY, datetime(2026, 1, 23, 14, 59))
    assert result == date(2026, 1, 23)


def test_equity_exactly_at_cutoff_uses_next_business_day():
    result = get_applicable_nav_date(SchemeType.EQUITY, datetime(2026, 1, 23, 15, 0), holidays={HOLIDAY})
    assert result == date(2026, 1, 27)


def test_debt_before_cutoff_uses_same_day():
    result = get_applicable_nav_date(SchemeType.DEBT, datetime(2026, 1, 23, 14, 59))
    assert result == date(2026, 1, 23)


def test_funds_realised_after_cutoff_determine_nav():
    received = datetime(2026, 1, 23, 14, 0)
    realised = datetime(2026, 1, 23, 15, 10)
    result = get_applicable_nav_date(SchemeType.EQUITY, received, realised, {HOLIDAY})
    assert result == date(2026, 1, 27)


def test_liquid_before_cutoff_uses_previous_business_day():
    result = get_applicable_nav_date(SchemeType.LIQUID, datetime(2026, 1, 27, 13, 29), holidays={HOLIDAY})
    assert result == date(2026, 1, 23)


def test_liquid_exactly_at_cutoff_uses_next_business_day():
    result = get_applicable_nav_date(
        SchemeType.LIQUID, datetime(2026, 1, 23, 13, 30), holidays={HOLIDAY}
    )
    assert result == date(2026, 1, 27)


def test_friday_followed_by_monday_holiday_moves_to_tuesday():
    result = get_applicable_nav_date(SchemeType.EQUITY, datetime(2026, 1, 23, 15, 0), holidays={HOLIDAY})
    assert result == date(2026, 1, 27)


def test_scheme_cutoff_times():
    assert get_nav_cutoff(SchemeType.EQUITY) == time(15, 0)
    assert get_nav_cutoff(SchemeType.DEBT) == time(15, 0)
    assert get_nav_cutoff(SchemeType.LIQUID) == time(13, 30)


def _write_nav_file(path: Path, rows: list[str]) -> Path:
    path.write_text(
        "nav_date,scheme_id,nav\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )
    return path


def test_load_navs_accepts_valid_records(tmp_path):
    nav_file = _write_nav_file(
        tmp_path / "navs.csv", ["2026-01-23,SCH-TEST,12.3456"]
    )

    assert load_navs(nav_file) == {
        ("SCH-TEST", date(2026, 1, 23)): Decimal("12.3456")
    }


def test_duplicate_scheme_date_nav_is_rejected(tmp_path):
    nav_file = _write_nav_file(
        tmp_path / "navs.csv",
        ["2026-01-23,SCH-TEST,12.3456", "2026-01-23,SCH-TEST,12.5000"],
    )

    with pytest.raises(ValueError, match="duplicate NAV"):
        load_navs(nav_file)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("23-01-2026,SCH-TEST,12.3456", "invalid NAV date"),
        ("2026-01-23,SCH-TEST,not-a-number", "valid decimal"),
        ("2026-01-23,SCH-TEST,12.34", "four decimal places"),
        ("2026-01-23,SCH-TEST,0", "greater than zero"),
        ("2026-01-23,SCH-TEST,-1.25", "greater than zero"),
    ],
)
def test_invalid_nav_records_are_rejected(tmp_path, row, message):
    nav_file = _write_nav_file(tmp_path / "navs.csv", [row])

    with pytest.raises(ValueError, match=message):
        load_navs(nav_file)


def test_missing_nav_lookup_raises_clear_error(tmp_path):
    nav_file = _write_nav_file(
        tmp_path / "navs.csv", ["2026-01-23,SCH-TEST,12.3456"]
    )

    with pytest.raises(ValueError, match="NAV not found for scheme SCH-OTHER"):
        get_nav_value("SCH-OTHER", date(2026, 1, 23), nav_file)


def test_invalid_nav_file_stops_processing_before_any_command(tmp_path):
    _write_nav_file(tmp_path / "navs.csv", ["2026-01-23,SCH-TEST,0"])
    commands = tmp_path / "commands.txt"
    commands.write_text(
        "PURCHASE|ORD-VALID|2026-01-23 10:00:00|FOL-001|SCH-01|5000.00|2026-01-23 10:00:00\n",
        encoding="utf-8",
    )
    from src.command_processor import CommandProcessor

    processor = CommandProcessor(data_dir=tmp_path)
    with pytest.raises(ValueError, match="greater than zero"):
        processor.process_file(commands)
    assert processor.commands_processed == 0
