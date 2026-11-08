"""Exit load calculations based on scheme type and holding period."""

import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Sequence

from src.models import ExitLoadSchedule, SchemeType


DEFAULT_EXIT_LOADS_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "exit_loads.csv"
)


def load_exit_loads(
    exit_loads_file: Path = DEFAULT_EXIT_LOADS_FILE,
) -> list[ExitLoadSchedule]:
    """Load exit-load schedule bands from CSV file."""
    schedules: list[ExitLoadSchedule] = []
    if not exit_loads_file.exists():
        return schedules

    with exit_loads_file.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            schedules.append(
                ExitLoadSchedule(
                    scheme_type=SchemeType(row["scheme_type"]),
                    from_day=int(row["from_day"]),
                    to_day=int(row["to_day"]),
                    load_pct=Decimal(row["load_pct"]),
                )
            )
    return schedules


def get_exit_load_pct(
    scheme_type: SchemeType,
    days_held: int,
    schedules: Sequence[ExitLoadSchedule],
) -> Decimal:
    """Return the exit load percentage for days held, or 0 if outside every band."""
    for schedule in schedules:
        if (
            schedule.scheme_type == scheme_type
            and schedule.from_day <= days_held <= schedule.to_day
        ):
            return schedule.load_pct
    return Decimal("0.0000")


def calculate_lot_exit_load(
    units: Decimal,
    nav: Decimal,
    days_held: int,
    scheme_type: SchemeType,
    schedules: Sequence[ExitLoadSchedule],
) -> Decimal:
    """Calculate exit load in rupees for given units and NAV, rounded to paise."""
    if not units.is_finite() or not nav.is_finite():
        raise ValueError("Units and NAV must be finite numbers")
    if units <= Decimal("0") or nav <= Decimal("0"):
        return Decimal("0.00")
    if days_held < 0:
        raise ValueError("Days held cannot be negative")
    gross = (units * nav).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    load_pct = get_exit_load_pct(scheme_type, days_held, schedules)
    if load_pct <= 0:
        return Decimal("0.00")
    rate = load_pct / Decimal("100")
    return (gross * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
