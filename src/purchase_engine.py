"""Calculations for one time mutual fund purchases and stamp duty."""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


FIRST_PURCHASE_MINIMUM = Decimal("5000")
ADDITIONAL_PURCHASE_MINIMUM = Decimal("1000")
STAMP_DUTY_RATE = Decimal("0.00005")  # 0.005 percent
PAISE = Decimal("0.01")
UNIT_PRECISION = Decimal("0.001")


def calculate_stamp_duty(amount: Decimal) -> Decimal:
    """Calculate 0.005% stamp duty rounded to the nearest paisa (two decimal places)."""
    if not amount.is_finite():
        raise ValueError("Purchase amount must be a finite number")
    if amount <= Decimal("0"):
        raise ValueError("Purchase amount must be greater than zero")
    return (amount * STAMP_DUTY_RATE).quantize(PAISE, rounding=ROUND_HALF_UP)


def calculate_investible_amount(amount: Decimal, stamp_duty: Decimal) -> Decimal:
    """Calculate the net investible amount after deducting stamp duty."""
    if not amount.is_finite() or not stamp_duty.is_finite():
        raise ValueError("Amounts must be finite numbers")
    if amount <= Decimal("0"):
        raise ValueError("Purchase amount must be greater than zero")
    if stamp_duty < Decimal("0"):
        raise ValueError("Stamp duty cannot be negative")
    return amount - stamp_duty


def calculate_units(investible_amount: Decimal, nav: Decimal) -> Decimal:
    """Calculate purchase units rounded DOWN to three decimal places."""
    if not investible_amount.is_finite():
        raise ValueError("Investible amount must be a finite number")
    if investible_amount <= Decimal("0"):
        raise ValueError("Investible amount must be greater than zero")
    if not nav.is_finite():
        raise ValueError("NAV must be a finite number")
    if nav <= Decimal("0"):
        raise ValueError("NAV must be greater than zero")
    return (investible_amount / nav).quantize(UNIT_PRECISION, rounding=ROUND_DOWN)


def calculate_purchase(
    amount: Decimal,
    nav: Decimal,
    is_first_purchase: bool,
    min_first_purchase: Decimal = FIRST_PURCHASE_MINIMUM,
    min_additional: Decimal = ADDITIONAL_PURCHASE_MINIMUM,
) -> dict[str, Decimal]:
    """Validate a purchase and return its stamp duty, investible amount, and units."""
    if not amount.is_finite():
        raise ValueError("Purchase amount must be a finite number")
    if amount <= Decimal("0"):
        raise ValueError("Purchase amount must be greater than zero")

    minimum = min_first_purchase if is_first_purchase else min_additional
    if amount < minimum:
        raise ValueError(f"Purchase amount must be at least ₹{minimum}")

    if not nav.is_finite():
        raise ValueError("NAV must be a finite number")
    if nav <= Decimal("0"):
        raise ValueError("NAV must be greater than zero")

    stamp_duty = calculate_stamp_duty(amount)
    investible_amount = calculate_investible_amount(amount, stamp_duty)
    units = calculate_units(investible_amount, nav)

    return {
        "stamp_duty": stamp_duty,
        "investible_amount": investible_amount,
        "units": units,
    }
