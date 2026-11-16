"""Tests for the Interactive Terminal Application (src/interactive.py)."""

from datetime import date
from decimal import Decimal
import io
from pathlib import Path
import pytest

from src.interactive import InteractiveApp


@pytest.fixture
def test_env(tmp_path):
    """Create a temporary test environment with sample data and clean interactive state."""
    workspace_dir = tmp_path
    sample_dir = Path(__file__).resolve().parent.parent / "data" / "sample_pack"
    return workspace_dir, sample_dir


def run_app_with_inputs(inputs: list[str], test_env) -> tuple[str, InteractiveApp]:
    """Helper to run InteractiveApp with provided simulated stdin inputs."""
    workspace_dir, sample_dir = test_env
    input_str = "\n".join(inputs) + "\n"
    stdin = io.StringIO(input_str)
    stdout = io.StringIO()

    app = InteractiveApp(
        workspace_dir=workspace_dir,
        data_dir=sample_dir,
        stdin=stdin,
        stdout=stdout,
    )
    app.run()
    return stdout.getvalue(), app


def test_menu_display_and_exit(test_env):
    """Test standard menu rendering and clean exit on option 12."""
    output, app = run_app_with_inputs(["12"], test_env)
    assert "MUTUAL FUND ORDER PROCESSING SYSTEM" in output
    assert "1. Purchase Mutual Fund" in output
    assert "12. Exit" in output
    assert "Saving session state and exiting." in output


def test_view_available_schemes(test_env):
    """Test viewing available schemes (Option 8)."""
    output, app = run_app_with_inputs(["8", "12"], test_env)
    assert "AVAILABLE MUTUAL FUND SCHEMES" in output
    assert "SCH-01" in output
    assert "SCH-06" in output
    assert "Total schemes available: 6" in output


def test_view_investor_folio(test_env):
    """Test viewing investor portfolio (Option 7)."""
    output, app = run_app_with_inputs(["7", "FOL-001", "2026-02-01", "12"], test_env)
    assert "FOLIO STATEMENT: FOL-001" in output
    assert "Varsha Patil" in output
    assert "LOT-001" in output
    assert "SCH-05" in output
    assert "4103.137" in output


def test_view_nonexistent_folio(test_env):
    """Test viewing a folio that does not exist."""
    output, app = run_app_with_inputs(["7", "FOL-999", "2026-02-01", "12"], test_env)
    assert "Folio 'FOL-999' not found" in output


def test_interactive_purchase_success(test_env):
    """Test placing a successful purchase order interactively (Option 1)."""
    inputs = [
        "1",                    # Menu 1: Purchase
        "FOL-001",              # Folio
        "SCH-01",               # Scheme
        "10000",                # Amount
        "2026-02-02T10:00:00",  # Order TS
        "2026-02-02T11:00:00",  # Realised TS
        "12",                   # Exit
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "Transaction Result:" in output
    assert "Decision       : ACCEPTED" in output
    assert "Applicable NAV : 76.2197 on 2026-02-02" in output
    assert "Allotted Units : 131.193" in output
    assert len(app.processor.confirmations) == 1

    # Verify command was saved to persistence file
    cmd_file = app.interactive_commands_file
    assert cmd_file.exists()
    content = cmd_file.read_text(encoding="utf-8")
    assert "PURCHASE|ORD-INT-0001|2026-02-02T10:00:00|FOL-001|SCH-01|10000|2026-02-02T11:00:00" in content


def test_interactive_purchase_validation_error(test_env):
    """Test purchase input validation rejecting invalid amount."""
    inputs = [
        "1",                    # Menu 1: Purchase
        "FOL-001",              # Folio
        "SCH-01",               # Scheme
        "-5000",                # Negative Amount (invalid)
        "2026-02-02T10:00:00",  # Order TS
        "2026-02-02T11:00:00",  # Realised TS
        "12",                   # Exit
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "Error: Amount must be greater than zero." in output


def test_interactive_redemption_success(test_env):
    """Test placing a successful redemption order interactively (Option 2)."""
    # FOL-001 has 84.529 units of SCH-06 (Liquid fund, no lock-in)
    inputs = [
        "2",                    # Menu 2: Redeem
        "FOL-001",              # Folio
        "SCH-06",               # Scheme
        "UNITS",                # Mode
        "50.000",               # Value
        "2026-02-02T10:00:00",  # Order TS
        "12",                   # Exit
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "Redemption Result:" in output
    assert "Decision       : ACCEPTED" in output
    assert "Redeemed Units : 50.000" in output
    assert "Payout Date    : 2026-02-02" in output


def test_interactive_switch_success(test_env):
    """Test placing a switch order interactively (Option 3)."""
    inputs = [
        "3",                    # Menu 3: Switch
        "FOL-001",              # Folio
        "SCH-06",               # From Scheme
        "SCH-01",               # To Scheme
        "UNITS",                # Mode
        "30.000",               # Value
        "2026-02-02T10:00:00",  # Order TS
        "12",                   # Exit
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "Switch Result:" in output
    assert "[SWITCH_OUT] Decision: ACCEPTED" in output
    assert "[SWITCH_IN] Decision: ACCEPTED" in output


def test_interactive_sip_register_and_pause(test_env):
    """Test SIP registration and pause interactively (Options 4 & 5)."""
    inputs = [
        # 1. Register SIP
        "4",
        "SIP-INT-999",
        "FOL-001",
        "SCH-01",
        "5000",
        "10",
        "2026-02-01T10:00:00",
        # 2. Pause SIP
        "5",
        "SIP-INT-999",
        "2026-02-15T10:00:00",
        "2026-03",
        "2",
        "12",
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "SIP Registration Result:" in output
    assert "SIP ID         : SIP-INT-999" in output
    assert "Result         : ACCEPTED" in output
    assert "SIP Pause Result:" in output
    assert "Result     : ACCEPTED" in output
    assert "Rule IDs   : BR-10" in output


def test_view_transaction_history_and_filters(test_env):
    """Test viewing transaction history with filter options (Option 9)."""
    inputs = [
        "1",                    # Purchase
        "FOL-001",
        "SCH-01",
        "10000",
        "2026-02-02T10:00:00",
        "2026-02-02T11:00:00",
        "9",                    # View History
        "1",                    # All transactions
        "12",                   # Exit
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "Displaying 1 transaction records:" in output
    assert "ORD-INT-0001" in output
    assert "ACCEPTED" in output


def test_generate_reports_interactively(test_env):
    """Test generating CSV reports via Option 10."""
    inputs = [
        "1",                    # Purchase
        "FOL-001",
        "SCH-01",
        "10000",
        "2026-02-02T10:00:00",
        "2026-02-02T11:00:00",
        "10",                   # Generate Reports
        "12",                   # Exit
    ]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "Reports generated successfully:" in output
    assert "confirmations.csv (1 rows)" in output
    assert "sip_status.csv (0 rows)" in output
    assert "folio_statement.csv (0 rows)" in output


def test_batch_processing_interactively(test_env):
    """Test running official batch processing from Option 11."""
    inputs = ["11", "12"]
    output, app = run_app_with_inputs(inputs, test_env)
    assert "EXECUTING OFFICIAL SAMPLE PACK BATCH RUN" in output
    assert "Commands Processed : 92 (Expected: 92)" in output
    assert "Commands Accepted  : 86 (Expected: 86)" in output
    assert "Commands Rejected  : 6 (Expected: 6)" in output
    assert "Confirmations File : confirmations.csv (77 rows, Expected: 77)" in output
    assert "SIP Status File    : sip_status.csv (17 rows, Expected: 17)" in output
    assert "Folio Statement    : folio_statement.csv (88 rows, Expected: 88)" in output
    assert "Official Batch Benchmark Verification: 100% PASSED" in output


def test_restart_persistence_restores_state(test_env):
    """Test that restarting the application restores interactive transactions."""
    workspace_dir, sample_dir = test_env

    # Session 1: Place a purchase
    s1_inputs = ["1", "FOL-001", "SCH-01", "10000", "2026-02-02T10:00:00", "2026-02-02T11:00:00", "12"]
    run_app_with_inputs(s1_inputs, test_env)

    # Session 2: Launch fresh app instance, verify lot exists in folio
    s2_inputs = ["7", "FOL-001", "2026-02-05", "12"]
    s2_output, s2_app = run_app_with_inputs(s2_inputs, test_env)

    assert "ORD-INT-0001" in s2_output
    assert "131.193" in s2_output
    assert len(s2_app.processor.confirmations) == 1
