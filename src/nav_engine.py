"""Simple calendar and NAV date rules for mutual fund orders."""

import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from src.models import SchemeType


DEFAULT_HOLIDAYS_FILE = Path(__file__).resolve().parent.parent / "data" / "holidays.csv"
DEFAULT_NAV_FILE = Path(__file__).resolve().parent.parent / "data" / "nav.csv"


def load_holidays(holidays_file: Path = DEFAULT_HOLIDAYS_FILE) -> set[date]:
    """CSV ಫೈಲ್‌ನ `date` ಕಾಲಮ್‌ನಿಂದ ರಜಾದಿನಗಳನ್ನು ಓದುತ್ತದೆ."""
    holidays = set()
    files_to_try = [holidays_file]
    sample_pack_holidays = (
        Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "holidays.csv"
    )
    if sample_pack_holidays != holidays_file and sample_pack_holidays.exists():
        files_to_try.append(sample_pack_holidays)

    for file_path in files_to_try:
        if not file_path.exists():
            continue
        with file_path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if "date" in row and row["date"].strip():
                    holidays.add(date.fromisoformat(row["date"].strip()))
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


def get_nav_value(
    scheme_id: str,
    nav_date: date,
    nav_file: Path = DEFAULT_NAV_FILE,
) -> Decimal:
    """Read one scheme NAV from the NAV CSV file."""
    files_to_try = [nav_file]
    sample_pack_navs = (
        Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "navs.csv"
    )
    if sample_pack_navs != nav_file and sample_pack_navs.exists():
        files_to_try.append(sample_pack_navs)

    for file_path in files_to_try:
        if not file_path.exists():
            continue
        navs = load_navs(file_path)
        key = (scheme_id, nav_date)
        if key in navs:
            return navs[key]

    raise ValueError(f"NAV not found for scheme {scheme_id} on {nav_date.isoformat()}")


def load_navs(nav_file: Path) -> dict[tuple[str, date], Decimal]:
    """Load NAV records, rejecting invalid values and duplicate scheme/date keys."""
    navs: dict[tuple[str, date], Decimal] = {}
    with nav_file.open(newline="", encoding="utf-8") as file:
        for row_number, row in enumerate(csv.DictReader(file), start=2):
            scheme_id = (row.get("scheme_id") or "").strip()
            date_text = (row.get("nav_date") or "").strip()
            value_text = (row.get("nav") or row.get("nav_value") or "").strip()
            if not scheme_id:
                raise ValueError(f"NAV row {row_number}: scheme_id is required")
            try:
                nav_date = date.fromisoformat(date_text)
            except ValueError as error:
                raise ValueError(f"NAV row {row_number}: invalid NAV date") from error
            if nav_date.isoformat() != date_text:
                raise ValueError(f"NAV row {row_number}: NAV date must use YYYY-MM-DD")
            try:
                nav = Decimal(value_text)
            except (InvalidOperation, ValueError) as error:
                raise ValueError(f"NAV row {row_number}: NAV must be a valid decimal") from error
            if not nav.is_finite() or nav <= 0:
                raise ValueError(f"NAV row {row_number}: NAV must be greater than zero")
            if nav.as_tuple().exponent != -4:
                raise ValueError(f"NAV row {row_number}: NAV must have four decimal places")

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
