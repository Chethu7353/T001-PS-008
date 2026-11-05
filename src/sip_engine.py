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
    if not 1 <= sip_day <= 31:
        raise ValueError("SIP day must be between 1 and 31")
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


def calculate_instalment_date(
    registered_date: date,
    sip_day: int,
    instalment_no: int,
    holidays: set[date],
) -> date:
    """Calculate an installment's adjusted date from its monthly cycle number."""
    if instalment_no < 1:
        raise ValueError("Instalment number must be at least one")

    year, month = registered_date.year, registered_date.month
    number = 0
    while True:
        candidate = calculate_scheduled_date(year, month, sip_day, holidays)
        if (candidate - registered_date).days >= 7:
            number += 1
            if number == instalment_no:
                return candidate

        month += 1
        if month > 12:
            month = 1
            year += 1


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
        history_by_sip: dict[str, list[tuple[int, str]]] = {}
        if history_file.exists():
            with history_file.open(newline="", encoding="utf-8") as file:
                for row in csv.DictReader(file):
                    history_by_sip.setdefault(row["sip_id"], []).append(
                        (int(row["instalment_no"]), row["result"])
                    )

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
                # The opening file's count is an as-of snapshot; history is retained
                # as the preceding installment ledger and checked against that state.
                history = sorted(history_by_sip.get(sip.sip_id, []))
                if history:
                    trailing_failures = 0
                    for _, result in reversed(history):
                        if result == "FAILED":
                            trailing_failures += 1
                        elif result == "SUCCESS":
                            break
                        else:
                            raise ValueError(f"Invalid SIP history result: {result}")
                    if trailing_failures != sip.consecutive_failures:
                        raise ValueError(
                            f"SIP history does not match opening failure count for {sip.sip_id}"
                        )
                self.sips[sip.sip_id] = sip

    def scheduled_date(
        self, sip_id: str, instalment_no: int, holidays: set[date]
    ) -> date:
        """Return the expected date for a SIP installment number."""
        sip = self.sips[sip_id]
        return calculate_instalment_date(
            sip.registered_date, sip.sip_day, instalment_no, holidays
        )

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
        if amount < scheme.min_sip or not 1 <= sip_day <= 31:
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

        try:
            first_month = datetime.strptime(from_month, "%Y-%m").date()
        except ValueError:
            return False, "REJECTED"

        pause_months = set()
        year, month = first_month.year, first_month.month
        for _ in range(months):
            pause_months.add(f"{year:04d}-{month:02d}")
            month += 1
            if month > 12:
                month = 1
                year += 1
        sip.paused_months.update(pause_months)
        sip.paused_until_month = max(sip.paused_months)
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

        if result not in {"SUCCESS", "FAILED"}:
            raise ValueError("SIP debit result must be SUCCESS or FAILED")

        if result == "SUCCESS":
            sip.consecutive_failures = 0
            sip.status = "ACTIVE"
            return True, sip.consecutive_failures, sip.status

        # FAILED
        sip.consecutive_failures += 1
        if sip.consecutive_failures >= 3:
            sip.status = "CANCELLED"
        return False, sip.consecutive_failures, sip.status
