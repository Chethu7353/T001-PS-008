"""FIFO lot manager for mutual fund investment lots and ELSS lock-in."""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from src.exit_load_engine import calculate_lot_exit_load
from src.models import ExitLoadSchedule, InvestmentLot, Scheme


DEFAULT_LOTS_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "lots_opening.csv"
)


def get_elss_lock_in_date(allotment_date: date) -> date:
    """Return the date until which an ELSS lot is locked in (3 years)."""
    try:
        return allotment_date.replace(year=allotment_date.year + 3)
    except ValueError:
        # Handle leap day (Feb 29 -> Feb 28)
        return allotment_date.replace(year=allotment_date.year + 3, day=28)


def is_lot_locked(lot: InvestmentLot, as_of_date: date, scheme: Scheme) -> bool:
    """Check if an investment lot is locked in under ELSS as of the given date."""
    if not scheme.elss:
        return False
    lock_in_date = get_elss_lock_in_date(lot.allotment_date)
    return as_of_date < lock_in_date


class LotManager:
    """Maintains and manages lots in FIFO order per folio and scheme."""

    def __init__(self) -> None:
        # Map of (folio_id, scheme_id) -> list of InvestmentLot
        self.lots: dict[tuple[str, str], list[InvestmentLot]] = {}

    def load_opening_lots(self, lots_file: Path = DEFAULT_LOTS_FILE) -> None:
        """Load opening investment lots from CSV."""
        if not lots_file.exists():
            return

        with lots_file.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                lot = InvestmentLot(
                    lot_id=row["lot_id"],
                    investor_id=row["folio_id"],
                    scheme_id=row["scheme_id"],
                    purchase_date=date.fromisoformat(row["allotment_date"]),
                    units=Decimal(row["units"]),
                    purchase_nav=Decimal(row["purchase_nav"]),
                )
                self.add_lot(lot)

    def add_lot(self, lot: InvestmentLot) -> None:
        """Add a lot to the portfolio."""
        if not lot.units.is_finite() or not lot.purchase_nav.is_finite():
            raise ValueError("Lot units and purchase NAV must be finite numbers")
        if lot.units <= Decimal("0"):
            raise ValueError("Lot units must be greater than zero")
        if lot.purchase_nav <= Decimal("0"):
            raise ValueError("Lot purchase NAV must be greater than zero")
        if not isinstance(lot.allotment_date, date):
            raise ValueError("Lot allotment date must be a valid date")

        key = (lot.folio_id, lot.scheme_id)
        if key not in self.lots:
            self.lots[key] = []
        self.lots[key].append(lot)
        # Keep sorted by allotment_date, then lot_id
        self.lots[key].sort(key=lambda item: (item.allotment_date, item.lot_id))

    def has_holding(self, folio_id: str, scheme_id: str) -> bool:
        """Return True if folio currently holds any non-zero units in scheme."""
        key = (folio_id, scheme_id)
        if key not in self.lots:
            return False
        return any(lot.units > 0 for lot in self.lots[key])

    def get_available_unlocked_units(
        self,
        folio_id: str,
        scheme_id: str,
        as_of_date: date,
        scheme: Scheme,
    ) -> Decimal:
        """Return sum of units in eligible (unlocked) lots as of date."""
        key = (folio_id, scheme_id)
        if key not in self.lots:
            return Decimal("0.000")

        total = Decimal("0.000")
        for lot in self.lots[key]:
            if lot.units <= 0:
                continue
            if not is_lot_locked(lot, as_of_date, scheme):
                total += lot.units
        return total

    def deplete_units_fifo(
        self,
        folio_id: str,
        scheme_id: str,
        units_to_redeem: Decimal,
        as_of_date: date,
        scheme: Scheme,
        schedules: Sequence[ExitLoadSchedule],
        nav: Decimal,
    ) -> Decimal:
        """Deplete units in FIFO order and return total exit load incurred."""
        if not units_to_redeem.is_finite() or not nav.is_finite():
            raise ValueError("Units and NAV must be finite numbers")
        if units_to_redeem <= Decimal("0"):
            raise ValueError("Units to redeem must be greater than zero")
        if nav <= Decimal("0"):
            raise ValueError("NAV must be greater than zero")

        key = (folio_id, scheme_id)
        if key not in self.lots:
            raise ValueError("No lots found for folio and scheme")

        # Pre-flight check: verify date consistency on candidate lots before modifying state
        for lot in self.lots[key]:
            if lot.units <= 0:
                continue
            if is_lot_locked(lot, as_of_date, scheme):
                continue
            if as_of_date < lot.allotment_date:
                raise ValueError(
                    f"Redemption date {as_of_date.isoformat()} is earlier than lot allotment date {lot.allotment_date.isoformat()}"
                )

        # Pre-flight check: ensure sufficient unlocked units are available before modifying state
        available_unlocked = self.get_available_unlocked_units(
            folio_id, scheme_id, as_of_date, scheme
        )
        if units_to_redeem > available_unlocked:
            raise ValueError("Insufficient unlocked units available to deplete")

        remaining_to_redeem = units_to_redeem
        total_exit_load = Decimal("0.00")

        for lot in self.lots[key]:
            if remaining_to_redeem <= 0:
                break
            if lot.units <= 0:
                continue
            if is_lot_locked(lot, as_of_date, scheme):
                continue

            take_units = min(lot.units, remaining_to_redeem)
            days_held = (as_of_date - lot.allotment_date).days
            lot_load = calculate_lot_exit_load(
                take_units, nav, days_held, scheme.scheme_type, schedules
            )
            total_exit_load += lot_load
            lot.units -= take_units
            remaining_to_redeem -= take_units

        if remaining_to_redeem > Decimal("0.000"):
            raise ValueError("Insufficient unlocked units available to deplete")

        return total_exit_load

    def get_remaining_lots_for_folio(self, folio_id: str) -> list[InvestmentLot]:
        """Return all lots of a folio with units > 0, in FIFO order."""
        remaining: list[InvestmentLot] = []
        for (f_id, _), lot_list in self.lots.items():
            if f_id == folio_id:
                for lot in lot_list:
                    if lot.units > 0:
                        remaining.append(lot)

        remaining.sort(key=lambda item: (item.allotment_date, item.lot_id))
        return remaining
