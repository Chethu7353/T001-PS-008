"""Simple calendar and NAV date rules for mutual fund orders."""

import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from src.models import SchemeType


DEFAULT_HOLIDAYS_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "holidays.csv"
)
if not DEFAULT_HOLIDAYS_FILE.exists():
    DEFAULT_HOLIDAYS_FILE = Path(__file__).resolve().parent.parent / "data" / "holidays.csv"
DEFAULT_NAV_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "navs.csv"
)
if not DEFAULT_NAV_FILE.exists():
    DEFAULT_NAV_FILE = Path(__file__).resolve().parent.parent / "data" / "nav.csv"


def load_holidays(holidays_file: Path = DEFAULT_HOLIDAYS_FILE) -> set[date]:
    """Load holiday dates from CSV file, validating date format and duplicates (BR-06)."""
    if not holidays_file.exists():
        raise ValueError(f"Holidays file not found: {holidays_file}")

    holidays: set[date] = set()
    with holidays_file.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"Holidays file {holidays_file} is empty")
        if "date" not in reader.fieldnames:
            raise ValueError("Holidays file missing required column: 'date'")

        for row_number, row in enumerate(reader, start=2):
            raw_date = row.get("date")
            date_text = (raw_date or "").strip()
            if not date_text:
                raise ValueError(f"Holidays row {row_number}: date is required")

            try:
                holiday_date = date.fromisoformat(date_text)
            except ValueError as error:
                raise ValueError(
                    f"Holidays row {row_number}: invalid date '{date_text}'"
                ) from error

            if holiday_date.isoformat() != date_text:
                raise ValueError(
                    f"Holidays row {row_number}: invalid date format '{date_text}' (must use YYYY-MM-DD)"
                )

            name = (row.get("holiday_name") or row.get("description") or "").strip()
            if (
                "holiday_name" in reader.fieldnames or "description" in reader.fieldnames
            ) and not name:
                raise ValueError(f"Holidays row {row_number}: holiday name is required")

            if holiday_date in holidays:
                raise ValueError(
                    f"Holidays row {row_number}: duplicate holiday for date '{date_text}'"
                )

            holidays.add(holiday_date)

    return holidays


def is_business_day(day: date, holidays: Iterable[date] = ()) -> bool:
    """Return True if day is Monday-Friday and not listed in holidays."""
    if not isinstance(day, date):
        raise ValueError("Day must be a date instance")
    return day.weekday() < 5 and day not in holidays


def next_business_day(day: date, holidays: Iterable[date] = ()) -> date:
    """Return the first business day strictly after the given date."""
    if not isinstance(day, date):
        raise ValueError("Day must be a date instance")
    candidate = day + timedelta(days=1)
    holiday_set = set(holidays)
    while not is_business_day(candidate, holiday_set):
        candidate += timedelta(days=1)
    return candidate


def previous_business_day(day: date, holidays: Iterable[date] = ()) -> date:
    """Return the first business day strictly before the given date."""
    if not isinstance(day, date):
        raise ValueError("Day must be a date instance")
    candidate = day - timedelta(days=1)
    holiday_set = set(holidays)
    while not is_business_day(candidate, holiday_set):
        candidate -= timedelta(days=1)
    return candidate


def get_nav_value(
    scheme_id: str,
    nav_date: date,
    nav_file: Path = DEFAULT_NAV_FILE,
) -> Decimal:
    """Read one scheme NAV from the NAV CSV file."""
    if not nav_file.exists():
        raise ValueError(f"NAV file not found: {nav_file}")

    navs = load_navs(nav_file)
    key = (scheme_id, nav_date)
    if key in navs:
        return navs[key]

    raise ValueError(f"NAV not found for scheme {scheme_id} on {nav_date.isoformat()}")


def load_navs(nav_file: Path) -> dict[tuple[str, date], Decimal]:
    """Load NAV records, rejecting invalid values and duplicate scheme/date keys."""
    if not nav_file.exists():
        raise ValueError(f"NAV file not found: {nav_file}")

    navs: dict[tuple[str, date], Decimal] = {}
    with nav_file.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            raw_scheme = row.get("scheme_id")
            scheme_id = (raw_scheme or "").strip()
            if not scheme_id:
                raise ValueError(f"NAV row {row_number}: scheme_id is required")
            if any(char.isspace() for char in scheme_id) or not scheme_id.isupper():
                raise ValueError(f"NAV row {row_number}: invalid scheme identifier")

            raw_date = row.get("nav_date")
            date_text = (raw_date or "").strip()
            if not date_text:
                raise ValueError(f"NAV row {row_number}: nav_date is required")
            try:
                nav_date = date.fromisoformat(date_text)
            except ValueError as error:
                raise ValueError(f"NAV row {row_number}: invalid NAV date") from error
            if nav_date.isoformat() != date_text:
                raise ValueError(
                    f"NAV row {row_number}: invalid NAV date (must use YYYY-MM-DD)"
                )

            raw_val = row.get("nav") or row.get("nav_value")
            value_text = (raw_val or "").strip()
            if not value_text:
                raise ValueError(f"NAV row {row_number}: NAV value is required")
            try:
                nav = Decimal(value_text)
            except (InvalidOperation, ValueError) as error:
                raise ValueError(
                    f"NAV row {row_number}: NAV must be a valid decimal"
                ) from error

            if not nav.is_finite():
                raise ValueError(f"NAV row {row_number}: NAV must be a finite number")
            if nav <= 0:
                raise ValueError(f"NAV row {row_number}: NAV must be greater than zero")
            if nav.as_tuple().exponent != -4:
                raise ValueError(
                    f"NAV row {row_number}: NAV must have four decimal places"
                )

            key = (scheme_id, nav_date)
            if key in navs:
                raise ValueError(
                    f"NAV row {row_number}: duplicate NAV for {scheme_id} on {date_text}"
                )
            navs[key] = nav
    return navs


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
    use_calendar_day_for_liquid: bool = False,
) -> date:
    """ನಂತರದ timestamp ಮತ್ತು scheme cut-off ಬಳಸಿ ಅನ್ವಯಿಸುವ NAV ದಿನಾಂಕ ಆಯ್ಕೆಮಾಡುತ್ತದೆ."""
    effective_time = order_received_at
    if funds_realised_at is not None and funds_realised_at > effective_time:
        effective_time = funds_realised_at

    holiday_set = set(holidays)
    effective_date = effective_time.date()
    cutoff = get_nav_cutoff(scheme_type)

    if scheme_type == SchemeType.LIQUID:
        if use_calendar_day_for_liquid:
            if effective_time.time() < cutoff:
                return effective_date - timedelta(days=1)
            else:
                return effective_date
        if effective_time.time() < cutoff and is_business_day(effective_date, holiday_set):
            return previous_business_day(effective_date, holiday_set)
        return next_business_day(effective_date, holiday_set)

    if effective_time.time() < cutoff and is_business_day(effective_date, holiday_set):
        return effective_date
    return next_business_day(effective_date, holiday_set)
