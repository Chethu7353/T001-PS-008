"""SIP engine for managing Systematic Investment Plans, debit results, and pauses."""

import calendar
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from src.models import SIP, Scheme


DEFAULT_EXISTING_SIPS_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "existing_sips.csv"
)
DEFAULT_SIP_HISTORY_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "sip_history.csv"
)


def calculate_scheduled_date(
    year: int,
    month: int,
    sip_day: int,
    holidays: set[date],
) -> date:
    """Calculate the scheduled date for a SIP instalment, advancing to next business day."""
    last_day = calendar.monthrange(year, month)[1]
    clamped_day = min(sip_day, last_day)
    candidate = date(year, month, clamped_day)

    while candidate.weekday() >= 5 or candidate in holidays:
        candidate += timedelta(days=1)
    return candidate


def calculate_first_instalment_date(
    registered_date: date,
    sip_day: int,
    holidays: set[date],
) -> date:
    """Determine the first scheduled instalment date (must be >= 7 days after registration)."""
    # Candidate in same month
    cand = calculate_scheduled_date(
        registered_date.year, registered_date.month, sip_day, holidays
    )
    if (cand - registered_date).days >= 7:
        return cand

    # Candidate in next month
    year = registered_date.year
    month = registered_date.month + 1
    if month > 12:
        month = 1
        year += 1
    return calculate_scheduled_date(year, month, sip_day, holidays)


class SIPManager:
    """Manages active SIPs, failure tracking, pauses, and instalment generation."""

    def __init__(self) -> None:
        self.sips: dict[str, SIP] = {}

    def load_existing_sips(
        self,
        sips_file: Path = DEFAULT_EXISTING_SIPS_FILE,
        history_file: Path = DEFAULT_SIP_HISTORY_FILE,
    ) -> None:
        """Load registered SIPs and their historical failure status."""
        if not sips_file.exists():
            return

        with sips_file.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                sip = SIP(
                    sip_id=row["sip_id"],
                    folio_id=row["folio_id"],
                    scheme_id=row["scheme_id"],
                    amount=Decimal(row["amount"]),
                    sip_day=int(row["sip_day"]),
                    registered_date=date.fromisoformat(row["registered_date"]),
                    status=row.get("status", "ACTIVE"),
                    consecutive_failures=int(row.get("consecutive_failures", 0)),
                )
                self.sips[sip.sip_id] = sip

    def register_sip(
        self,
        sip_id: str,
        registered_ts: datetime,
        folio_id: str,
        scheme_id: str,
        amount: Decimal,
        sip_day: int,
        scheme: Scheme,
        holidays: set[date],
    ) -> tuple[bool, str, date | None]:
        """Validate and register a new SIP."""
        if amount < scheme.min_sip:
            return False, "REJECTED", None

        first_date = calculate_first_instalment_date(
            registered_ts.date(), sip_day, holidays
        )
        sip = SIP(
            sip_id=sip_id,
            folio_id=folio_id,
            scheme_id=scheme_id,
            amount=amount,
            sip_day=sip_day,
            registered_date=registered_ts.date(),
            status="ACTIVE",
            consecutive_failures=0,
        )
        self.sips[sip_id] = sip
        return True, "ACCEPTED", first_date

    def pause_sip(
        self,
        sip_id: str,
        request_ts: datetime,
        from_month: str,
        months: int,
    ) -> tuple[bool, str]:
        """Pause a SIP for a given number of months (max 3 months allowed)."""
        sip = self.sips.get(sip_id)
        if not sip or months > 3 or months <= 0:
            return False, "REJECTED"

        sip.paused_until_month = from_month
        return True, "ACCEPTED"

    def record_debit_result(
        self,
        sip_id: str,
        instalment_no: int,
        result: str,
    ) -> tuple[bool, int, str]:
        """Update consecutive failures and SIP status after debit attempt."""
        sip = self.sips.get(sip_id)
        if not sip:
            raise ValueError(f"Unknown SIP ID: {sip_id}")

        if result == "SUCCESS":
            sip.consecutive_failures = 0
            sip.status = "ACTIVE"
            return True, sip.consecutive_failures, sip.status

        # FAILED
        sip.consecutive_failures += 1
        if sip.consecutive_failures >= 3:
            sip.status = "CANCELLED"
        return False, sip.consecutive_failures, sip.status
