"""Simple calendar and NAV date rules for mutual fund orders."""

import csv
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable

from src.models import SchemeType


DEFAULT_HOLIDAYS_FILE = Path(__file__).resolve().parent.parent / "data" / "holidays.csv"


def load_holidays(holidays_file: Path = DEFAULT_HOLIDAYS_FILE) -> set[date]:
    """CSV ಫೈಲ್‌ನ `date` ಕಾಲಮ್‌ನಿಂದ ರಜಾದಿನಗಳನ್ನು ಓದುತ್ತದೆ."""
    holidays = set()
    if not holidays_file.exists():
        return holidays
    with holidays_file.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            holidays.add(date.fromisoformat(row["date"]))
    return holidays


def is_business_day(day: date, holidays: Iterable[date] = ()) -> bool:
    """ದಿನವು ವಾರಾಂತ್ಯ ಅಥವಾ ರಜಾದಿನವಲ್ಲದಿದ್ದರೆ True ನೀಡುತ್ತದೆ."""
    return day.weekday() < 5 and day not in holidays


def next_business_day(day: date, holidays: Iterable[date] = ()) -> date:
    """ಕೊಟ್ಟ ದಿನದ ನಂತರ ಬರುವ ಮೊದಲ ಕೆಲಸದ ದಿನವನ್ನು ನೀಡುತ್ತದೆ."""
    candidate = day + timedelta(days=1)
    holiday_set = set(holidays)
    while not is_business_day(candidate, holiday_set):
        candidate += timedelta(days=1)
    return candidate


def previous_business_day(day: date, holidays: Iterable[date] = ()) -> date:
    """ಕೊಟ್ಟ ದಿನದ ಮೊದಲು ಬರುವ ಮೊದಲ ಕೆಲಸದ ದಿನವನ್ನು ನೀಡುತ್ತದೆ."""
    candidate = day - timedelta(days=1)
    holiday_set = set(holidays)
    while not is_business_day(candidate, holiday_set):
        candidate -= timedelta(days=1)
    return candidate


def get_nav_cutoff(scheme_type: SchemeType) -> time:
    """Scheme ಪ್ರಕಾರಕ್ಕೆ assignment ನೀಡಿರುವ NAV cut-off ಸಮಯವನ್ನು ನೀಡುತ್ತದೆ."""
    if scheme_type == SchemeType.LIQUID:
        return time(13, 30)
    if scheme_type in (SchemeType.EQUITY, SchemeType.DEBT):
        return time(15, 0)
    raise ValueError(f"Unsupported scheme type: {scheme_type}")


def get_applicable_nav_date(
    scheme_type: SchemeType,
    order_received_at: datetime,
    funds_realised_at: datetime | None = None,
    holidays: Iterable[date] = (),
) -> date:
    """ನಂತರದ timestamp ಮತ್ತು scheme cut-off ಬಳಸಿ ಅನ್ವಯಿಸುವ NAV ದಿನಾಂಕ ಆಯ್ಕೆಮಾಡುತ್ತದೆ."""
    effective_time = order_received_at
    if funds_realised_at is not None and funds_realised_at > effective_time:
        effective_time = funds_realised_at

    holiday_set = set(holidays)
    effective_date = effective_time.date()
    cutoff = get_nav_cutoff(scheme_type)

    if scheme_type == SchemeType.LIQUID:
        if effective_time.time() < cutoff and is_business_day(effective_date, holiday_set):
            return previous_business_day(effective_date, holiday_set)
        return next_business_day(effective_date, holiday_set)

    if effective_time.time() < cutoff and is_business_day(effective_date, holiday_set):
        return effective_date
    return next_business_day(effective_date, holiday_set)
