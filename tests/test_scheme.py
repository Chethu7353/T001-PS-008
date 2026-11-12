"""Tests for BR-04: Scheme Registration Fields and Validation Rules."""

from datetime import time
from decimal import Decimal
from pathlib import Path
import pytest

from src.models import Scheme, SchemeType
from src.scheme_engine import (
    DEFAULT_SCHEMES_FILE,
    load_schemes,
    validate_scheme,
)


VALID_CSV_HEADER = (
    "scheme_id,scheme_name,scheme_type,elss,cutoff_time,min_first_purchase,"
    "min_additional,min_sip,min_redemption\n"
)


def create_temp_schemes_file(tmp_path: Path, content: str) -> Path:
    """Helper to create a temporary schemes CSV file."""
    p = tmp_path / "schemes.csv"
    p.write_text(content, encoding="utf-8")
    return p


# --- 1. Official Sample Pack Schemes Loading ---

def test_load_official_sample_pack_schemes():
    """Verify loading the official schemes.csv produces all 6 schemes with correct metadata."""
    schemes = load_schemes(DEFAULT_SCHEMES_FILE)
    assert len(schemes) == 6
    assert set(schemes.keys()) == {
        "SCH-01",
        "SCH-02",
        "SCH-03",
        "SCH-04",
        "SCH-05",
        "SCH-06",
    }

    # Verify SCH-01 (Equity)
    sch1 = schemes["SCH-01"]
    assert sch1.name == "Sahyadri Bluechip Fund - Direct Growth"
    assert sch1.scheme_type == SchemeType.EQUITY
    assert sch1.elss is False
    assert sch1.cutoff_time == time(15, 0)
    assert sch1.min_first_purchase == Decimal("5000.00")
    assert sch1.min_additional == Decimal("1000.00")
    assert sch1.min_sip == Decimal("500.00")
    assert sch1.min_redemption == Decimal("1000.00")

    # Verify SCH-03 (ELSS)
    sch3 = schemes["SCH-03"]
    assert sch3.name == "Sahyadri Tax Saver (ELSS) - Direct Growth"
    assert sch3.scheme_type == SchemeType.EQUITY
    assert sch3.elss is True

    # Verify SCH-06 (Liquid)
    sch6 = schemes["SCH-06"]
    assert sch6.name == "Sahyadri Liquid Fund - Direct Growth"
    assert sch6.scheme_type == SchemeType.LIQUID
    assert sch6.elss is False
    assert sch6.cutoff_time == time(13, 30)


# --- 2. File and Header Validation ---

def test_schemes_file_not_found():
    """Verify missing schemes file raises ValueError."""
    with pytest.raises(ValueError, match="Schemes file not found"):
        load_schemes(Path("non_existent_schemes.csv"))


def test_schemes_file_missing_required_headers(tmp_path):
    """Verify missing required header raises ValueError."""
    content = "scheme_id,scheme_name,scheme_type\nSCH-01,Test,EQUITY\n"
    f = create_temp_schemes_file(tmp_path, content)
    with pytest.raises(ValueError, match="missing required column"):
        load_schemes(f)


# --- 3. Scheme ID Validation ---

@pytest.mark.parametrize(
    "invalid_id,error_msg",
    [
        ("", "scheme_id is required"),
        ("   ", "scheme_id is required"),
        ("sch-01", "invalid scheme identifier"),
        ("SCH 01", "invalid scheme identifier"),
        ("Sch-01", "invalid scheme identifier"),
    ],
)
def test_invalid_scheme_id_rejected(tmp_path, invalid_id, error_msg):
    """Verify empty, lowercase, or whitespace-bearing scheme_id is rejected."""
    row = f"{invalid_id},Test Fund,EQUITY,false,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match=error_msg):
        load_schemes(f)


def test_duplicate_scheme_id_rejected(tmp_path):
    """Verify duplicate scheme_id raises ValueError."""
    row1 = "SCH-01,Fund One,EQUITY,false,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    row2 = "SCH-01,Fund Duplicate,EQUITY,false,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row1 + row2)
    with pytest.raises(ValueError, match="duplicate scheme_id 'SCH-01'"):
        load_schemes(f)


# --- 4. Scheme Name Validation ---

def test_empty_scheme_name_rejected(tmp_path):
    """Verify empty or whitespace scheme_name raises ValueError."""
    row = "SCH-01,   ,EQUITY,false,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="scheme_name is required"):
        load_schemes(f)


# --- 5. Scheme Type Validation ---

def test_invalid_scheme_type_rejected(tmp_path):
    """Verify unknown scheme type raises ValueError."""
    row = "SCH-01,Hybrid Fund,HYBRID,false,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="invalid scheme_type 'HYBRID'"):
        load_schemes(f)


# --- 6. ELSS Flag Validation ---

@pytest.mark.parametrize("invalid_elss", ["yes", "no", "1", "0", "maybe", ""])
def test_invalid_elss_flag_rejected(tmp_path, invalid_elss):
    """Verify non-boolean elss value raises ValueError."""
    row = f"SCH-01,Test Fund,EQUITY,{invalid_elss},15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="invalid elss value"):
        load_schemes(f)


def test_elss_flag_case_insensitive(tmp_path):
    """Verify True / False in any casing parses properly."""
    row1 = "SCH-01,Equity Fund,EQUITY,True,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    row2 = "SCH-02,Equity Fund 2,EQUITY,False,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row1 + row2)
    schemes = load_schemes(f)
    assert schemes["SCH-01"].elss is True
    assert schemes["SCH-02"].elss is False


def test_elss_rejected_for_debt_and_liquid(tmp_path):
    """Verify elss=true on DEBT or LIQUID scheme raises ValueError."""
    row_debt = "SCH-04,Debt ELSS,DEBT,true,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f_debt = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row_debt)
    with pytest.raises(ValueError, match="only EQUITY schemes can be ELSS"):
        load_schemes(f_debt)

    row_liquid = "SCH-06,Liquid ELSS,LIQUID,true,13:30:00,5000.00,1000.00,500.00,1000.00\n"
    f_liquid = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row_liquid)
    with pytest.raises(ValueError, match="only EQUITY schemes can be ELSS"):
        load_schemes(f_liquid)


# --- 7. Cut-off Time Validation (BR-01 Alignment) ---

def test_invalid_cutoff_time_format(tmp_path):
    """Verify malformed cutoff_time raises ValueError."""
    row = "SCH-01,Test,EQUITY,false,invalid-time,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="invalid cutoff_time"):
        load_schemes(f)


def test_cutoff_time_mismatch_for_equity_debt(tmp_path):
    """Verify EQUITY or DEBT with non-15:00:00 cutoff raises ValueError."""
    row = "SCH-01,Equity Early,EQUITY,false,13:30:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="cut-off time for EQUITY must be 15:00:00"):
        load_schemes(f)


def test_cutoff_time_mismatch_for_liquid(tmp_path):
    """Verify LIQUID with non-13:30:00 cutoff raises ValueError."""
    row = "SCH-06,Liquid Late,LIQUID,false,15:00:00,5000.00,1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="cut-off time for LIQUID must be 13:30:00"):
        load_schemes(f)


# --- 8. Financial Threshold Validation ---

@pytest.mark.parametrize("bad_val", ["0.00", "-100.00", "NaN", "Infinity", "abc"])
def test_threshold_must_be_positive_finite_decimal(tmp_path, bad_val):
    """Verify financial thresholds must be positive, finite decimals."""
    row = f"SCH-01,Test,EQUITY,false,15:00:00,{bad_val},1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError):
        load_schemes(f)


@pytest.mark.parametrize("bad_precision", ["5000", "5000.0", "5000.000", "5000.005"])
def test_threshold_must_have_exactly_two_decimal_places(tmp_path, bad_precision):
    """Verify currency amounts must have exactly two decimal places."""
    row = f"SCH-01,Test,EQUITY,false,15:00:00,{bad_precision},1000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="must have exactly two decimal places"):
        load_schemes(f)


def test_min_additional_cannot_exceed_min_first_purchase(tmp_path):
    """Verify min_additional > min_first_purchase is rejected."""
    row = "SCH-01,Test,EQUITY,false,15:00:00,5000.00,6000.00,500.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="min_additional .* cannot exceed min_first_purchase"):
        load_schemes(f)


def test_min_sip_cannot_be_below_five_hundred(tmp_path):
    """Verify min_sip below 500 is rejected per BR-10."""
    row = "SCH-01,Test,EQUITY,false,15:00:00,5000.00,1000.00,499.00,1000.00\n"
    f = create_temp_schemes_file(tmp_path, VALID_CSV_HEADER + row)
    with pytest.raises(ValueError, match="min_sip .* cannot be below regulatory minimum"):
        load_schemes(f)


# --- 9. Direct Scheme Object Validation ---

def test_validate_scheme_programmatic():
    """Verify validate_scheme works directly on Scheme instances."""
    # Valid scheme
    valid = Scheme(
        scheme_id="SCH-VALID",
        name="Valid Fund",
        scheme_type=SchemeType.EQUITY,
        elss=False,
        cutoff_time=time(15, 0),
        min_first_purchase=Decimal("5000.00"),
        min_additional=Decimal("1000.00"),
        min_sip=Decimal("500.00"),
        min_redemption=Decimal("1000.00"),
    )
    validate_scheme(valid)  # Should not raise

    # Invalid scheme (Debt with ELSS)
    invalid = Scheme(
        scheme_id="SCH-INVALID",
        name="Invalid Debt Fund",
        scheme_type=SchemeType.DEBT,
        elss=True,
        cutoff_time=time(15, 0),
        min_first_purchase=Decimal("5000.00"),
        min_additional=Decimal("1000.00"),
        min_sip=Decimal("500.00"),
        min_redemption=Decimal("1000.00"),
    )
    with pytest.raises(ValueError, match="only EQUITY schemes can be ELSS"):
        validate_scheme(invalid)
