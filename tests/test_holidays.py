"""Tests for BR-06: Holiday Calendar Update and Invalid-Date Handling."""

from datetime import date, datetime, time
from pathlib import Path
import pytest

from src.models import SchemeType
from src.nav_engine import (
    DEFAULT_HOLIDAYS_FILE,
    get_applicable_nav_date,
    is_business_day,
    load_holidays,
    next_business_day,
    previous_business_day,
)
from src.redemption_engine import calculate_payout_date
from src.sip_engine import calculate_scheduled_date


def create_temp_holidays_file(tmp_path: Path, content: str) -> Path:
    """Helper to create a temporary holidays CSV file."""
    p = tmp_path / "holidays.csv"
    p.write_text(content, encoding="utf-8")
    return p


# --- 1. Official Sample Pack & Legacy File Loading ---

def test_load_sample_pack_holidays():
    """Verify loading official sample-pack holidays loads all 6 expected dates."""
    holidays = load_holidays(DEFAULT_HOLIDAYS_FILE)
    assert len(holidays) == 6
    assert holidays == {
        date(2025, 12, 25),  # Christmas
        date(2026, 1, 26),   # Republic Day
        date(2026, 3, 4),    # Holi
        date(2026, 3, 20),   # Id-ul-Fitr
        date(2026, 4, 3),    # Good Friday
        date(2026, 4, 14),   # Ambedkar Jayanti
    }


def test_load_legacy_holidays_file():
    """Verify legacy data/holidays.csv with 'description' column loads properly."""
    legacy_path = (
        Path(__file__).resolve().parent.parent / "data" / "holidays.csv"
    )
    if legacy_path.exists():
        holidays = load_holidays(legacy_path)
        assert date(2026, 1, 26) in holidays


# --- 2. File & Header Validation ---

def test_missing_holidays_file_raises_value_error():
    """Verify non-existent holidays file raises ValueError."""
    with pytest.raises(ValueError, match="Holidays file not found"):
        load_holidays(Path("non_existent_holidays.csv"))


def test_empty_holidays_file_raises_value_error(tmp_path):
    """Verify empty holidays CSV raises ValueError."""
    f = create_temp_holidays_file(tmp_path, "")
    with pytest.raises(ValueError, match="is empty"):
        load_holidays(f)


def test_missing_date_header_raises_value_error(tmp_path):
    """Verify CSV without 'date' column raises ValueError."""
    content = "holiday_name,notes\nRepublic Day,National Holiday\n"
    f = create_temp_holidays_file(tmp_path, content)
    with pytest.raises(ValueError, match="missing required column: 'date'"):
        load_holidays(f)


# --- 3. Date Value & Format Validation ---

def test_empty_date_value_raises_value_error(tmp_path):
    """Verify row with missing date raises ValueError."""
    content = "date,holiday_name\n  ,Republic Day\n"
    f = create_temp_holidays_file(tmp_path, content)
    with pytest.raises(ValueError, match="Holidays row 2: date is required"):
        load_holidays(f)


@pytest.mark.parametrize(
    "bad_date_format",
    [
        "26-01-2026",
        "26/01/2026",
        "2026/01/26",
        "2026-1-26",
        "2026-01-6",
        "2026.01.26",
        "Jan 26, 2026",
    ],
)
def test_invalid_date_format_rejected(tmp_path, bad_date_format):
    """Verify non-ISO-8601 date formats are rejected with meaningful message."""
    content = f"date,holiday_name\n{bad_date_format},Holiday\n"
    f = create_temp_holidays_file(tmp_path, content)
    with pytest.raises(ValueError, match="Holidays row 2: invalid date"):
        load_holidays(f)


@pytest.mark.parametrize(
    "impossible_date",
    [
        "2026-02-30",
        "2026-04-31",
        "2026-13-01",
        "2026-00-10",
        "2026-01-32",
        "2025-02-29",  # 2025 is not a leap year
    ],
)
def test_impossible_calendar_date_rejected(tmp_path, impossible_date):
    """Verify invalid calendar dates are rejected."""
    content = f"date,holiday_name\n{impossible_date},Holiday\n"
    f = create_temp_holidays_file(tmp_path, content)
    with pytest.raises(ValueError, match="Holidays row 2: invalid date"):
        load_holidays(f)


# --- 4. Holiday Name & Duplicate Detection ---

def test_missing_holiday_name_rejected(tmp_path):
    """Verify row with empty holiday name is rejected."""
    content = "date,holiday_name\n2026-01-26,   \n"
    f = create_temp_holidays_file(tmp_path, content)
    with pytest.raises(ValueError, match="Holidays row 2: holiday name is required"):
        load_holidays(f)


def test_duplicate_holiday_date_rejected(tmp_path):
    """Verify duplicate holiday date raises ValueError."""
    content = (
        "date,holiday_name\n"
        "2026-01-26,Republic Day\n"
        "2026-01-26,Republic Day Duplicate\n"
    )
    f = create_temp_holidays_file(tmp_path, content)
    with pytest.raises(ValueError, match="Holidays row 3: duplicate holiday for date '2026-01-26'"):
        load_holidays(f)


# --- 5. Weekend & Consecutive Holidays Handling ---

def test_weekend_holiday_loaded_and_handled():
    """Verify a weekend holiday (e.g. Sunday) is safely handled without breaking logic."""
    sunday_holiday = date(2026, 8, 15)  # Suppose Independence Day falls on weekend
    holidays = {sunday_holiday}
    assert not is_business_day(sunday_holiday, holidays)
    # Friday before moves past weekend to Monday
    assert next_business_day(date(2026, 8, 14), holidays) == date(2026, 8, 17)


def test_consecutive_holidays_skipping():
    """Verify consecutive holidays (Thursday + Friday) advance all the way to Monday."""
    thursday = date(2026, 10, 1)
    friday = date(2026, 10, 2)
    holidays = {thursday, friday}
    wednesday = date(2026, 9, 30)
    assert next_business_day(wednesday, holidays) == date(2026, 10, 5)  # Monday


def test_year_boundary_holidays():
    """Verify holidays spanning year end (Dec 31, Jan 1) roll to Jan 2 (or next business day)."""
    # 2025-12-31 Wednesday, 2026-01-01 Thursday
    dec_31 = date(2025, 12, 31)
    jan_01 = date(2026, 1, 1)
    holidays = {dec_31, jan_01}
    dec_30 = date(2025, 12, 30)  # Tuesday
    assert next_business_day(dec_30, holidays) == date(2026, 1, 2)  # Friday


# --- 6. Calendar Helper Type Validation ---

def test_calendar_helpers_validate_date_instances():
    """Verify is_business_day, next_business_day, previous_business_day require date objects."""
    with pytest.raises(ValueError, match="Day must be a date instance"):
        is_business_day("2026-01-23")

    with pytest.raises(ValueError, match="Day must be a date instance"):
        next_business_day("2026-01-23")

    with pytest.raises(ValueError, match="Day must be a date instance"):
        previous_business_day("2026-01-23")


# --- 7. Business Rule Integrations (NAV, SIP, Payout) ---

def test_nav_determination_around_holiday_ec02():
    """EC-02: Friday 16:00 order before Monday Republic Day resolves to Tuesday 2026-01-27."""
    holidays = {date(2026, 1, 26)}
    order_ts = datetime(2026, 1, 23, 16, 0, 0)
    nav_date = get_applicable_nav_date(
        SchemeType.EQUITY, order_ts, holidays=holidays
    )
    assert nav_date == date(2026, 1, 27)


def test_payout_date_skips_holiday():
    """FOL-007 SCH-02: Equity redemption on Tuesday 2026-03-03 skips Holi (2026-03-04) -> 2026-03-06."""
    holidays = {date(2026, 3, 4)}  # Holi
    payout = calculate_payout_date(SchemeType.EQUITY, date(2026, 3, 3), holidays)
    assert payout == date(2026, 3, 6)


def test_sip_installment_scheduling_around_holiday():
    """SIP installment due on holiday (Id-ul-Fitr Friday 2026-03-20) advances to Monday 2026-03-23."""
    holidays = {date(2026, 3, 20)}
    scheduled = calculate_scheduled_date(2026, 3, 20, holidays)
    assert scheduled == date(2026, 3, 23)
