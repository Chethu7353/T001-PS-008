from datetime import date, datetime, time

from src.models import SchemeType
from src.nav_engine import (
    get_applicable_nav_date,
    get_nav_cutoff,
    is_business_day,
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
