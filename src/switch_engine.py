"""Switch transaction engine orchestrating source redemption and target purchase."""

from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP
from typing import Sequence

from src.exit_load_engine import ExitLoadSchedule
from src.lot_manager import LotManager
from src.models import Scheme
from src.nav_engine import get_applicable_nav_date
from src.redemption_engine import calculate_payout_date


STAMP_DUTY_RATE = Decimal("0.00005")  # 0.005%
PAISE = Decimal("0.01")
UNIT_PRECISION = Decimal("0.001")


def process_switch(
    order_id: str,
    order_ts: datetime,
    folio_id: str,
    from_scheme: Scheme,
    to_scheme: Scheme,
    mode: str,
    value: str,
    lot_manager: LotManager,
    schedules: Sequence[ExitLoadSchedule],
    get_nav_func,
    holidays: set[date],
) -> tuple[dict, dict]:
    """Process a switch order producing SWITCH_OUT and SWITCH_IN confirmation records."""
    from_nav_date = get_applicable_nav_date(
        from_scheme.scheme_type,
        order_ts,
        holidays=holidays,
        use_calendar_day_for_liquid=True,
    )
    to_nav_date = get_applicable_nav_date(
        to_scheme.scheme_type,
        order_ts,
        holidays=holidays,
        use_calendar_day_for_liquid=True,
    )

    available_units = lot_manager.get_available_unlocked_units(
        folio_id, from_scheme.scheme_id, from_nav_date, from_scheme
    )

    from_nav = get_nav_func(from_scheme.scheme_id, from_nav_date)
    to_nav = get_nav_func(to_scheme.scheme_id, to_nav_date)

    # Determine units to redeem
    units_to_redeem = Decimal("0.000")
    is_valid = True

    if mode == "ALL":
        if available_units <= Decimal("0.000"):
            is_valid = False
        else:
            units_to_redeem = available_units
    elif mode == "UNITS":
        try:
            req_units = Decimal(value).quantize(UNIT_PRECISION)
            if req_units <= Decimal("0.000") or req_units > available_units:
                is_valid = False
            else:
                units_to_redeem = req_units
        except Exception:
            is_valid = False
    elif mode == "AMOUNT":
        try:
            req_amount = Decimal(value).quantize(PAISE)
            if req_amount <= Decimal("0.00"):
                is_valid = False
            else:
                units_to_redeem = (req_amount / from_nav).quantize(
                    UNIT_PRECISION, rounding=ROUND_CEILING
                )
                if units_to_redeem > available_units:
                    is_valid = False
        except Exception:
            is_valid = False
    else:
        is_valid = False

    if not is_valid:
        out_record = {
            "order_id": order_id,
            "folio_id": folio_id,
            "scheme_id": from_scheme.scheme_id,
            "txn_type": "SWITCH_OUT",
            "decision": "REJECTED",
            "rule_ids": "BR-08",
            "nav_date": "",
            "nav": "",
            "gross_amount": "",
            "stamp_duty": "",
            "units": "",
            "exit_load": "",
            "net_amount": "",
            "payout_date": "",
        }
        in_record = {
            "order_id": order_id,
            "folio_id": folio_id,
            "scheme_id": to_scheme.scheme_id,
            "txn_type": "SWITCH_IN",
            "decision": "REJECTED",
            "rule_ids": "BR-08",
            "nav_date": "",
            "nav": "",
            "gross_amount": "",
            "stamp_duty": "",
            "units": "",
            "exit_load": "",
            "net_amount": "",
            "payout_date": "",
        }
        return out_record, in_record

    # Deplete source units via FIFO and calculate exit load
    exit_load = lot_manager.deplete_units_fifo(
        folio_id,
        from_scheme.scheme_id,
        units_to_redeem,
        from_nav_date,
        from_scheme,
        schedules,
        from_nav,
    )

    source_gross = (units_to_redeem * from_nav).quantize(PAISE, rounding=ROUND_HALF_UP)
    source_net = source_gross - exit_load
    source_payout = calculate_payout_date(
        from_scheme.scheme_type, from_nav_date, holidays
    )

    out_record = {
        "order_id": order_id,
        "folio_id": folio_id,
        "scheme_id": from_scheme.scheme_id,
        "txn_type": "SWITCH_OUT",
        "decision": "ACCEPTED",
        "rule_ids": "BR-01;BR-08;BR-09;BR-11",
        "nav_date": from_nav_date.isoformat(),
        "nav": f"{from_nav:.4f}",
        "gross_amount": f"{source_gross:.2f}",
        "stamp_duty": "0.00",
        "units": f"{units_to_redeem:.3f}",
        "exit_load": f"{exit_load:.2f}",
        "net_amount": f"{source_net:.2f}",
        "payout_date": source_payout.isoformat(),
    }

    # Target purchase
    target_gross = source_net
    target_stamp_duty = (target_gross * STAMP_DUTY_RATE).quantize(
        PAISE, rounding=ROUND_HALF_UP
    )
    target_investible = target_gross - target_stamp_duty
    target_units = (target_investible / to_nav).quantize(
        UNIT_PRECISION, rounding=ROUND_DOWN
    )

    from src.models import InvestmentLot

    target_lot = InvestmentLot(
        lot_id=order_id,
        investor_id=folio_id,
        scheme_id=to_scheme.scheme_id,
        purchase_date=to_nav_date,
        units=target_units,
        purchase_nav=to_nav,
    )
    lot_manager.add_lot(target_lot)

    in_record = {
        "order_id": order_id,
        "folio_id": folio_id,
        "scheme_id": to_scheme.scheme_id,
        "txn_type": "SWITCH_IN",
        "decision": "ACCEPTED",
        "rule_ids": "BR-01;BR-07;BR-09",
        "nav_date": to_nav_date.isoformat(),
        "nav": f"{to_nav:.4f}",
        "gross_amount": f"{target_gross:.2f}",
        "stamp_duty": f"{target_stamp_duty:.2f}",
        "units": f"{target_units:.3f}",
        "exit_load": "0.00",
        "net_amount": f"{target_investible:.2f}",
        "payout_date": "",
    }

    return out_record, in_record
