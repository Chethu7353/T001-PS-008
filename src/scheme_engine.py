"""Scheme Engine for validating and loading mutual fund schemes (BR-04)."""

import csv
from datetime import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.models import Scheme, SchemeType


DEFAULT_SCHEMES_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_pack" / "schemes.csv"
)

REQUIRED_SCHEME_HEADERS = [
    "scheme_id",
    "scheme_name",
    "scheme_type",
    "elss",
    "cutoff_time",
    "min_first_purchase",
    "min_additional",
    "min_sip",
    "min_redemption",
]

EQUITY_DEBT_CUTOFF = time(15, 0)
LIQUID_CUTOFF = time(13, 30)
MIN_SIP_FLOOR = Decimal("500.00")


def validate_scheme(scheme: Scheme) -> None:
    """Validate a Scheme instance according to BR-04 domain rules."""
    # 1. Scheme ID validation
    scheme_id = scheme.scheme_id.strip() if scheme.scheme_id else ""
    if not scheme_id:
        raise ValueError("Scheme scheme_id is required")
    if any(c.isspace() for c in scheme_id) or not scheme_id.isupper():
        raise ValueError(
            f"Invalid scheme identifier '{scheme.scheme_id}': must be uppercase with no whitespace"
        )

    # 2. Scheme Name validation
    name = scheme.name.strip() if scheme.name else ""
    if not name:
        raise ValueError("Scheme name is required")

    # 3. Scheme Type validation
    if not isinstance(scheme.scheme_type, SchemeType):
        raise ValueError(f"Invalid scheme_type: {scheme.scheme_type}")

    # 4. ELSS constraint: Only EQUITY schemes can be ELSS
    if scheme.elss and scheme.scheme_type != SchemeType.EQUITY:
        raise ValueError(
            f"Scheme {scheme_id}: only EQUITY schemes can be ELSS (got {scheme.scheme_type.value})"
        )

    # 5. Cut-off time validation (BR-01 alignment)
    if scheme.scheme_type in (SchemeType.EQUITY, SchemeType.DEBT):
        if scheme.cutoff_time != EQUITY_DEBT_CUTOFF:
            raise ValueError(
                f"Scheme {scheme_id}: cut-off time for {scheme.scheme_type.value} must be "
                f"{EQUITY_DEBT_CUTOFF.strftime('%H:%M:%S')} (got {scheme.cutoff_time.strftime('%H:%M:%S')})"
            )
    elif scheme.scheme_type == SchemeType.LIQUID:
        if scheme.cutoff_time != LIQUID_CUTOFF:
            raise ValueError(
                f"Scheme {scheme_id}: cut-off time for LIQUID must be "
                f"{LIQUID_CUTOFF.strftime('%H:%M:%S')} (got {scheme.cutoff_time.strftime('%H:%M:%S')})"
            )

    # 6. Financial thresholds validation
    for attr, min_val in [
        ("min_first_purchase", None),
        ("min_additional", None),
        ("min_sip", MIN_SIP_FLOOR),
        ("min_redemption", None),
    ]:
        val: Decimal = getattr(scheme, attr)
        if not isinstance(val, Decimal):
            raise ValueError(f"Scheme {scheme_id}: {attr} must be a Decimal")
        if not val.is_finite():
            raise ValueError(f"Scheme {scheme_id}: {attr} must be a finite number")
        if val <= Decimal("0"):
            raise ValueError(f"Scheme {scheme_id}: {attr} must be greater than zero")
        if val.as_tuple().exponent != -2:
            raise ValueError(f"Scheme {scheme_id}: {attr} must have exactly two decimal places")
        if min_val is not None and val < min_val:
            raise ValueError(
                f"Scheme {scheme_id}: {attr} ({val}) cannot be below regulatory minimum {min_val}"
            )

    # Additional threshold relations
    if scheme.min_additional > scheme.min_first_purchase:
        raise ValueError(
            f"Scheme {scheme_id}: min_additional ({scheme.min_additional}) cannot exceed "
            f"min_first_purchase ({scheme.min_first_purchase})"
        )


def load_schemes(schemes_file: Path = DEFAULT_SCHEMES_FILE) -> dict[str, Scheme]:
    """Load and validate Scheme catalog from CSV file (BR-04)."""
    if not schemes_file.exists():
        raise ValueError(f"Schemes file not found: {schemes_file}")

    schemes: dict[str, Scheme] = {}
    with schemes_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Schemes file {schemes_file} is empty")

        missing_headers = [h for h in REQUIRED_SCHEME_HEADERS if h not in reader.fieldnames]
        if missing_headers:
            raise ValueError(
                f"Schemes file missing required column(s): {', '.join(missing_headers)}"
            )

        for row_num, row in enumerate(reader, start=2):
            raw_id = row.get("scheme_id")
            scheme_id = (raw_id or "").strip()
            if not scheme_id:
                raise ValueError(f"Schemes row {row_num}: scheme_id is required")
            if any(c.isspace() for c in scheme_id) or not scheme_id.isupper():
                raise ValueError(
                    f"Schemes row {row_num}: invalid scheme identifier '{scheme_id}'"
                )
            if scheme_id in schemes:
                raise ValueError(
                    f"Schemes row {row_num}: duplicate scheme_id '{scheme_id}'"
                )

            raw_name = row.get("scheme_name")
            scheme_name = (raw_name or "").strip()
            if not scheme_name:
                raise ValueError(f"Schemes row {row_num}: scheme_name is required")

            raw_type = (row.get("scheme_type") or "").strip()
            try:
                scheme_type = SchemeType(raw_type)
            except ValueError as e:
                raise ValueError(
                    f"Schemes row {row_num}: invalid scheme_type '{raw_type}'"
                ) from e

            raw_elss = (row.get("elss") or "").strip().lower()
            if raw_elss == "true":
                elss = True
            elif raw_elss == "false":
                elss = False
            else:
                raise ValueError(
                    f"Schemes row {row_num}: invalid elss value '{row.get('elss')}' (must be true or false)"
                )

            raw_cutoff = (row.get("cutoff_time") or "").strip()
            try:
                cutoff_time = time.fromisoformat(raw_cutoff)
            except ValueError as e:
                raise ValueError(
                    f"Schemes row {row_num}: invalid cutoff_time '{raw_cutoff}'"
                ) from e

            # Parse financial threshold columns
            decimals: dict[str, Decimal] = {}
            for field_name in (
                "min_first_purchase",
                "min_additional",
                "min_sip",
                "min_redemption",
            ):
                raw_val = (row.get(field_name) or "").strip()
                if not raw_val:
                    raise ValueError(f"Schemes row {row_num}: {field_name} is required")
                try:
                    val = Decimal(raw_val)
                except (InvalidOperation, ValueError) as e:
                    raise ValueError(
                        f"Schemes row {row_num}: {field_name} must be a valid decimal"
                    ) from e
                decimals[field_name] = val

            scheme = Scheme(
                scheme_id=scheme_id,
                name=scheme_name,
                scheme_type=scheme_type,
                elss=elss,
                cutoff_time=cutoff_time,
                min_first_purchase=decimals["min_first_purchase"],
                min_additional=decimals["min_additional"],
                min_sip=decimals["min_sip"],
                min_redemption=decimals["min_redemption"],
            )

            # Apply full business rule validation
            try:
                validate_scheme(scheme)
            except ValueError as e:
                raise ValueError(f"Schemes row {row_num}: {e}") from e

            schemes[scheme_id] = scheme

    return schemes
