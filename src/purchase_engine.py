"""Calculations for one time mutual fund purchases."""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


FIRST_PURCHASE_MINIMUM = Decimal("5000")
ADDITIONAL_PURCHASE_MINIMUM = Decimal("1000")
STAMP_DUTY_RATE = Decimal("0.00005")  # 0.005 percent
PAISE = Decimal("0.01")
UNIT_PRECISION = Decimal("0.001")


def calculate_purchase(amount: Decimal, nav: Decimal, is_first_purchase: bool) -> dict[str, Decimal]:
    """Validate a purchase and return its stamp duty, investible amount, and units."""
    if amount <= 0:
        raise ValueError("Purchase amount must be greater than zero")

    minimum = FIRST_PURCHASE_MINIMUM if is_first_purchase else ADDITIONAL_PURCHASE_MINIMUM
    if amount < minimum:
        raise ValueError(f"Purchase amount must be at least ₹{minimum}")

    if nav <= 0:
        raise ValueError("NAV must be greater than zero")

    stamp_duty = (amount * STAMP_DUTY_RATE).quantize(PAISE, rounding=ROUND_HALF_UP)
    investible_amount = amount - stamp_duty
    units = (investible_amount / nav).quantize(UNIT_PRECISION, rounding=ROUND_DOWN)

    return {
        "stamp_duty": stamp_duty,
        "investible_amount": investible_amount,
        "units": units,
    }
