"""Simple mutual fund redemption calculations."""

from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Iterable

from src.models import InvestmentLot, SchemeType
from src.nav_engine import next_business_day


MINIMUM_REDEMPTION_AMOUNT = Decimal("1000.00")
UNIT_PRECISION = Decimal("0.001")
PAISE = Decimal("0.01")


def validate_redemption_amount(amount: Decimal) -> None:
    """Reject non-positive redemption amounts."""
    if amount <= 0:
        raise ValueError("Redemption amount must be greater than zero")


def calculate_redemption_amount(units: Decimal, nav: Decimal) -> Decimal:
    """Return the rupee amount for the units redeemed at the given NAV."""
    if units <= 0:
        raise ValueError("Redemption units must be greater than zero")
    if nav <= 0:
        raise ValueError("NAV must be greater than zero")
    return (units * nav).quantize(PAISE, rounding=ROUND_HALF_UP)


def get_available_units(
    lots: Iterable[InvestmentLot],
    investor_id: str | None = None,
    scheme_id: str | None = None,
) -> Decimal:
    """Add units from matching investment lots."""
    available = Decimal("0")
    for lot in lots:
        if investor_id is not None and lot.investor_id != investor_id:
            continue
        if scheme_id is not None and lot.scheme_id != scheme_id:
            continue
        available += lot.units
    return available


def redeem_units(
    available_units: Decimal,
    units_to_redeem: Decimal,
    nav: Decimal,
) -> dict[str, Decimal]:
    """Validate a unit-based redemption and calculate its payout amount."""
    if available_units <= 0:
        raise ValueError("Investor has no available units")
    if units_to_redeem <= 0:
        raise ValueError("Redemption units must be greater than zero")
    if nav <= 0:
        raise ValueError("NAV must be greater than zero")
    if units_to_redeem > available_units:
        raise ValueError("Insufficient available units for redemption")

    amount = calculate_redemption_amount(units_to_redeem, nav)
    redeem_all_units = units_to_redeem == available_units
    if not redeem_all_units and amount < MINIMUM_REDEMPTION_AMOUNT:
        raise ValueError("Redemption amount must be at least ₹1000 or redeem all available units")

    return {
        "units": units_to_redeem.quantize(UNIT_PRECISION, rounding=ROUND_DOWN),
        "amount": amount,
        "remaining_units": (available_units - units_to_redeem).quantize(
            UNIT_PRECISION, rounding=ROUND_DOWN
        ),
    }


def redeem_by_amount(
    available_units: Decimal,
    amount: Decimal,
    nav: Decimal,
) -> dict[str, Decimal]:
    """Convert a rupee amount into units and validate the redemption."""
    validate_redemption_amount(amount)
    if available_units <= 0:
        raise ValueError("Investor has no available units")
    if nav <= 0:
        raise ValueError("NAV must be greater than zero")

    total_amount = calculate_redemption_amount(available_units, nav)
    if amount > total_amount:
        raise ValueError("Insufficient available units for redemption")

    redeem_all_units = amount == total_amount
    if redeem_all_units:
        units = available_units
        redeemed_amount = total_amount
    else:
        if amount < MINIMUM_REDEMPTION_AMOUNT:
            raise ValueError(
                "Redemption amount must be at least ₹1000 or redeem all available units"
            )
        units = (amount / nav).quantize(UNIT_PRECISION, rounding=ROUND_DOWN)
        if units <= 0:
            raise ValueError("Redemption amount is too small to redeem units")
        if units > available_units:
            raise ValueError("Insufficient available units for redemption")
        redeemed_amount = calculate_redemption_amount(units, nav)

    return {
        "units": units.quantize(UNIT_PRECISION, rounding=ROUND_DOWN),
        "amount": redeemed_amount,
        "remaining_units": (available_units - units).quantize(
            UNIT_PRECISION, rounding=ROUND_DOWN
        ),
    }


def calculate_payout_date(
    scheme_type: SchemeType,
    transaction_date: date,
    holidays: Iterable[date] = (),
) -> date:
    """Calculate T+2 for Equity and T+1 for Debt or Liquid schemes."""
    if not isinstance(transaction_date, date):
        raise ValueError("Transaction date must be a date")

    if scheme_type == SchemeType.EQUITY:
        business_days = 2
    elif scheme_type in (SchemeType.DEBT, SchemeType.LIQUID):
        business_days = 1
    else:
        raise ValueError(f"Unsupported scheme type: {scheme_type}")

    payout_date = transaction_date
    holiday_set = set(holidays)
    for _ in range(business_days):
        payout_date = next_business_day(payout_date, holiday_set)
    return payout_date
