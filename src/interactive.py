"""Interactive Terminal Interface for Mutual Fund Order Processing System.

Integrates with the existing CommandProcessor and domain engines to provide
a menu-driven, multi-transaction terminal experience with persistence.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys
from typing import TextIO

from src.command_processor import CommandProcessor
from src.lot_manager import get_elss_lock_in_date


def _normalize_id(val: str, prefix: str, width: int, valid_keys: dict) -> str:
    """Normalize input identifier (e.g. SCH-001 -> SCH-01, FOL-01 -> FOL-001)."""
    cleaned = val.strip().upper()
    if cleaned in valid_keys:
        return cleaned
    pattern = rf"^{prefix}-0*(\d+)$"
    match = re.match(pattern, cleaned)
    if match:
        candidate = f"{prefix}-{int(match.group(1)):0{width}d}"
        if candidate in valid_keys:
            return candidate
    return cleaned


class InteractiveApp:
    """Coordinates interactive user sessions over the mutual fund processing engines."""

    def __init__(
        self,
        workspace_dir: Path | None = None,
        data_dir: Path | None = None,
        stdin: TextIO = sys.stdin,
        stdout: TextIO = sys.stdout,
    ) -> None:
        if workspace_dir is None:
            workspace_dir = Path(__file__).resolve().parent.parent
        self.workspace_dir = Path(workspace_dir)

        if data_dir is None:
            data_dir = self.workspace_dir / "data" / "sample_pack"
        self.data_dir = Path(data_dir)

        self.interactive_commands_file = (
            self.workspace_dir / "data" / "interactive_commands.txt"
        )
        self.stdin = stdin
        self.stdout = stdout

        # Initialize processor and load opening data
        self.processor = CommandProcessor(data_dir=self.data_dir)
        self.processor.load_reference_data()

        # Replay persisted interactive transactions if present
        self._load_persisted_interactive_commands()

    def _print(self, msg: str = "") -> None:
        self.stdout.write(f"{msg}\n")
        self.stdout.flush()

    def _prompt(self, prompt_text: str) -> str:
        self.stdout.write(prompt_text)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            return ""
        return line.strip()

    def _load_persisted_interactive_commands(self) -> None:
        """Replay any saved interactive transactions from previous sessions."""
        if not self.interactive_commands_file.exists():
            return

        with self.interactive_commands_file.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    try:
                        self.processor.process_line(stripped)
                    except Exception as e:
                        self._print(
                            f"[Warning] Failed replaying saved command '{stripped}': {e}"
                        )

    def _record_interactive_command(self, cmd_line: str) -> None:
        """Append a processed interactive command to interactive_commands.txt."""
        self.interactive_commands_file.parent.mkdir(parents=True, exist_ok=True)
        with self.interactive_commands_file.open("a", encoding="utf-8") as f:
            f.write(f"{cmd_line}\n")

    def _generate_order_id(self) -> str:
        """Generate a unique order ID for interactive transactions."""
        count = self.processor.commands_processed + 1
        return f"ORD-INT-{count:04d}"

    def _generate_sip_id(self) -> str:
        """Generate a unique SIP ID for interactive transactions."""
        count = len(self.processor.sip_manager.sips) + 1
        return f"SIP-INT-{count:03d}"

    # -------------------------------------------------------------------------
    # Menu Option 1: Purchase Mutual Fund
    # -------------------------------------------------------------------------
    def handle_purchase(self) -> None:
        """Handle interactive purchase transaction."""
        self._print("\n--- Purchase Mutual Fund ---")
        order_id = self._generate_order_id()
        self._print(f"Generated Order ID: {order_id}")

        folio_id = _normalize_id(
            self._prompt("Enter Folio ID (e.g. FOL-001): "),
            "FOL",
            3,
            self.processor.folios,
        )
        scheme_id = _normalize_id(
            self._prompt("Enter Scheme ID (e.g. SCH-01): "),
            "SCH",
            2,
            self.processor.schemes,
        )
        amount_str = self._prompt("Enter Purchase Amount (INR): ").strip()
        order_ts_str = self._prompt(
            "Enter Order Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()
        realised_ts_str = self._prompt(
            "Enter Funds Realisation Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()

        # Validate basic format
        try:
            amt = Decimal(amount_str)
            if amt <= Decimal("0"):
                self._print("Error: Amount must be greater than zero.")
                return
            datetime.fromisoformat(order_ts_str)
            datetime.fromisoformat(realised_ts_str)
        except (InvalidOperation, ValueError) as e:
            self._print(f"Error: Invalid input format ({e}).")
            return

        cmd_line = (
            f"PURCHASE|{order_id}|{order_ts_str}|{folio_id}|{scheme_id}|"
            f"{amount_str}|{realised_ts_str}"
        )

        prev_count = len(self.processor.confirmations)
        self.processor.process_line(cmd_line)
        self._record_interactive_command(cmd_line)

        if len(self.processor.confirmations) > prev_count:
            conf = self.processor.confirmations[-1]
            self._print("\nTransaction Result:")
            self._print(f"  Decision       : {conf['decision']}")
            self._print(f"  Rule IDs       : {conf['rule_ids']}")
            if conf["decision"] == "ACCEPTED":
                self._print(f"  Applicable NAV : {conf['nav']} on {conf['nav_date']}")
                self._print(f"  Gross Amount   : INR {conf['gross_amount']}")
                self._print(f"  Stamp Duty     : INR {conf['stamp_duty']}")
                self._print(f"  Investible Amt : INR {conf['net_amount']}")
                self._print(f"  Allotted Units : {conf['units']}")
            else:
                self._print(f"  Order rejected under rules: {conf['rule_ids']}")

    # -------------------------------------------------------------------------
    # Menu Option 2: Redeem Mutual Fund
    # -------------------------------------------------------------------------
    def handle_redeem(self) -> None:
        """Handle interactive redemption transaction."""
        self._print("\n--- Redeem Mutual Fund ---")
        order_id = self._generate_order_id()
        self._print(f"Generated Order ID: {order_id}")

        folio_id = _normalize_id(
            self._prompt("Enter Folio ID (e.g. FOL-001): "),
            "FOL",
            3,
            self.processor.folios,
        )
        scheme_id = _normalize_id(
            self._prompt("Enter Scheme ID (e.g. SCH-01): "),
            "SCH",
            2,
            self.processor.schemes,
        )
        mode = self._prompt("Enter Redemption Mode (ALL / UNITS / AMOUNT): ").strip().upper()
        if mode not in ("ALL", "UNITS", "AMOUNT"):
            self._print("Error: Mode must be ALL, UNITS, or AMOUNT.")
            return

        value_str = "0"
        if mode != "ALL":
            value_str = self._prompt(f"Enter {mode} value: ").strip()
            try:
                val = Decimal(value_str)
                if val <= Decimal("0"):
                    self._print("Error: Value must be greater than zero.")
                    return
            except InvalidOperation:
                self._print("Error: Invalid numeric value.")
                return

        order_ts_str = self._prompt(
            "Enter Order Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()
        try:
            datetime.fromisoformat(order_ts_str)
        except ValueError:
            self._print("Error: Invalid timestamp format.")
            return

        cmd_line = (
            f"REDEEM|{order_id}|{order_ts_str}|{folio_id}|{scheme_id}|"
            f"{mode}|{value_str}"
        )

        prev_count = len(self.processor.confirmations)
        self.processor.process_line(cmd_line)
        self._record_interactive_command(cmd_line)

        if len(self.processor.confirmations) > prev_count:
            conf = self.processor.confirmations[-1]
            self._print("\nRedemption Result:")
            self._print(f"  Decision       : {conf['decision']}")
            self._print(f"  Rule IDs       : {conf['rule_ids']}")
            if conf["decision"] == "ACCEPTED":
                self._print(f"  Applicable NAV : {conf['nav']} on {conf['nav_date']}")
                self._print(f"  Redeemed Units : {conf['units']}")
                self._print(f"  Gross Amount   : INR {conf['gross_amount']}")
                self._print(f"  Exit Load      : INR {conf['exit_load']}")
                self._print(f"  Net Payout     : INR {conf['net_amount']}")
                self._print(f"  Payout Date    : {conf['payout_date']}")
            else:
                self._print(f"  Redemption rejected under rules: {conf['rule_ids']}")

    # -------------------------------------------------------------------------
    # Menu Option 3: Switch Mutual Fund
    # -------------------------------------------------------------------------
    def handle_switch(self) -> None:
        """Handle interactive switch transaction."""
        self._print("\n--- Switch Mutual Fund ---")
        order_id = self._generate_order_id()
        self._print(f"Generated Switch Order ID: {order_id}")

        folio_id = _normalize_id(
            self._prompt("Enter Folio ID (e.g. FOL-001): "),
            "FOL",
            3,
            self.processor.folios,
        )
        from_scheme = _normalize_id(
            self._prompt("Enter Source Scheme ID (e.g. SCH-01): "),
            "SCH",
            2,
            self.processor.schemes,
        )
        to_scheme = _normalize_id(
            self._prompt("Enter Target Scheme ID (e.g. SCH-02): "),
            "SCH",
            2,
            self.processor.schemes,
        )
        mode = self._prompt("Enter Switch Mode (ALL / UNITS / AMOUNT): ").strip().upper()
        if mode not in ("ALL", "UNITS", "AMOUNT"):
            self._print("Error: Mode must be ALL, UNITS, or AMOUNT.")
            return

        value_str = "0"
        if mode != "ALL":
            value_str = self._prompt(f"Enter {mode} value: ").strip()
            try:
                val = Decimal(value_str)
                if val <= Decimal("0"):
                    self._print("Error: Value must be greater than zero.")
                    return
            except InvalidOperation:
                self._print("Error: Invalid numeric value.")
                return

        order_ts_str = self._prompt(
            "Enter Order Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()
        try:
            datetime.fromisoformat(order_ts_str)
        except ValueError:
            self._print("Error: Invalid timestamp format.")
            return

        cmd_line = (
            f"SWITCH|{order_id}|{order_ts_str}|{folio_id}|{from_scheme}|"
            f"{to_scheme}|{mode}|{value_str}"
        )

        prev_count = len(self.processor.confirmations)
        self.processor.process_line(cmd_line)
        self._record_interactive_command(cmd_line)

        new_confs = self.processor.confirmations[prev_count:]
        self._print("\nSwitch Result:")
        for conf in new_confs:
            self._print(f"  [{conf['txn_type']}] Decision: {conf['decision']}, Rules: {conf['rule_ids']}")
            if conf["decision"] == "ACCEPTED":
                self._print(
                    f"    Scheme: {conf['scheme_id']} | Units: {conf['units']} | "
                    f"NAV: {conf['nav']} ({conf['nav_date']}) | Net: INR {conf['net_amount']}"
                )

    # -------------------------------------------------------------------------
    # Menu Option 4: Register SIP
    # -------------------------------------------------------------------------
    def handle_register_sip(self) -> None:
        """Handle interactive SIP registration."""
        self._print("\n--- Register Systematic Investment Plan (SIP) ---")
        sip_id = self._prompt("Enter SIP ID (or press Enter for auto-generated): ").strip()
        if not sip_id:
            sip_id = self._generate_sip_id()
            self._print(f"Using Auto-generated SIP ID: {sip_id}")

        folio_id = _normalize_id(
            self._prompt("Enter Folio ID (e.g. FOL-001): "),
            "FOL",
            3,
            self.processor.folios,
        )
        scheme_id = _normalize_id(
            self._prompt("Enter Scheme ID (e.g. SCH-01): "),
            "SCH",
            2,
            self.processor.schemes,
        )
        amount_str = self._prompt("Enter Installment Amount (INR): ").strip()
        sip_day_str = self._prompt("Enter SIP Day of Month (1-28): ").strip()
        reg_ts_str = self._prompt(
            "Enter Registration Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()

        try:
            amt = Decimal(amount_str)
            if amt <= Decimal("0"):
                self._print("Error: Amount must be greater than zero.")
                return
            day = int(sip_day_str)
            if not 1 <= day <= 28:
                self._print("Error: SIP day must be between 1 and 28.")
                return
            datetime.fromisoformat(reg_ts_str)
        except (InvalidOperation, ValueError) as e:
            self._print(f"Error: Invalid input format ({e}).")
            return

        cmd_line = (
            f"SIP_REGISTER|{sip_id}|{reg_ts_str}|{folio_id}|{scheme_id}|"
            f"{amount_str}|{sip_day_str}"
        )

        prev_count = len(self.processor.sip_statuses)
        self.processor.process_line(cmd_line)
        self._record_interactive_command(cmd_line)

        if len(self.processor.sip_statuses) > prev_count:
            status = self.processor.sip_statuses[-1]
            self._print("\nSIP Registration Result:")
            self._print(f"  SIP ID         : {status['sip_id']}")
            self._print(f"  Result         : {status['result']}")
            self._print(f"  SIP Status     : {status['sip_status']}")
            self._print(f"  Scheduled Date : {status['scheduled_date']}")
            self._print(f"  Rule IDs       : {status['rule_ids']}")

    # -------------------------------------------------------------------------
    # Menu Option 5: Pause SIP
    # -------------------------------------------------------------------------
    def handle_pause_sip(self) -> None:
        """Handle interactive SIP pause."""
        self._print("\n--- Pause Systematic Investment Plan (SIP) ---")
        sip_id = self._prompt("Enter SIP ID to pause (e.g. SIP-001): ").strip()
        req_ts_str = self._prompt(
            "Enter Pause Request Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()
        from_month = self._prompt(
            "Enter Pause Start Month (YYYY-MM, e.g. 2026-03): "
        ).strip()
        months_str = self._prompt("Enter Pause Duration (Months, e.g. 1-3): ").strip()

        try:
            datetime.fromisoformat(req_ts_str)
            months = int(months_str)
            if months <= 0:
                self._print("Error: Months must be positive integer.")
                return
        except ValueError as e:
            self._print(f"Error: Invalid format ({e}).")
            return

        cmd_line = f"SIP_PAUSE|{sip_id}|{req_ts_str}|{from_month}|{months_str}"

        prev_count = len(self.processor.sip_statuses)
        self.processor.process_line(cmd_line)
        self._record_interactive_command(cmd_line)

        if len(self.processor.sip_statuses) > prev_count:
            status = self.processor.sip_statuses[-1]
            self._print("\nSIP Pause Result:")
            self._print(f"  SIP ID     : {status['sip_id']}")
            self._print(f"  Result     : {status['result']}")
            self._print(f"  SIP Status : {status['sip_status']}")
            self._print(f"  Rule IDs   : {status['rule_ids']}")

    # -------------------------------------------------------------------------
    # Menu Option 6: Process SIP Debit Result
    # -------------------------------------------------------------------------
    def handle_sip_debit_result(self) -> None:
        """Handle interactive SIP debit result."""
        self._print("\n--- Process SIP Debit Result ---")
        sip_id = self._prompt("Enter SIP ID: ").strip()
        inst_no_str = self._prompt("Enter Installment Number: ").strip()
        result = self._prompt("Enter Result (SUCCESS / FAILED): ").strip().upper()
        if result not in ("SUCCESS", "FAILED"):
            self._print("Error: Result must be SUCCESS or FAILED.")
            return

        realised_ts_str = self._prompt(
            "Enter Realised Timestamp (YYYY-MM-DDTHH:MM:SS): "
        ).strip()
        try:
            datetime.fromisoformat(realised_ts_str)
        except ValueError:
            self._print("Error: Invalid timestamp format.")
            return

        reason = ""
        if result == "FAILED":
            reason = self._prompt(
                "Enter Failure Reason (e.g. INSUFFICIENT_FUNDS): "
            ).strip()

        cmd_line = (
            f"SIP_DEBIT_RESULT|{sip_id}|{inst_no_str}|{result}|"
            f"{realised_ts_str}|{reason}"
        )

        prev_sip_count = len(self.processor.sip_statuses)
        prev_conf_count = len(self.processor.confirmations)
        self.processor.process_line(cmd_line)
        self._record_interactive_command(cmd_line)

        if len(self.processor.sip_statuses) > prev_sip_count:
            status = self.processor.sip_statuses[-1]
            self._print("\nSIP Debit Processing Result:")
            self._print(f"  SIP ID               : {status['sip_id']}")
            self._print(f"  Installment No       : {status['instalment_no']}")
            self._print(f"  Result               : {status['result']}")
            self._print(f"  SIP Status           : {status['sip_status']}")
            self._print(f"  Consecutive Failures : {status['consecutive_failures']}")
            if status["order_id"]:
                self._print(f"  Generated Order ID   : {status['order_id']}")

        if len(self.processor.confirmations) > prev_conf_count:
            conf = self.processor.confirmations[-1]
            self._print("\nAssociated Allotment Confirmation:")
            self._print(
                f"  Units: {conf['units']} | NAV: {conf['nav']} ({conf['nav_date']}) | "
                f"Net Amount: INR {conf['net_amount']}"
            )

    # -------------------------------------------------------------------------
    # Menu Option 7: View Investor Folio
    # -------------------------------------------------------------------------
    def handle_view_folio(self) -> None:
        """Display portfolio holdings and lots for a folio."""
        self._print("\n--- View Investor Folio ---")
        folio_id = _normalize_id(
            self._prompt("Enter Folio ID (e.g. FOL-001): "),
            "FOL",
            3,
            self.processor.folios,
        )
        as_of_str = self._prompt(
            "Enter As-Of Date (YYYY-MM-DD, or press Enter for today): "
        ).strip()

        if not as_of_str:
            as_of_date = date.today()
        else:
            try:
                as_of_date = date.fromisoformat(as_of_str)
            except ValueError:
                self._print("Error: Invalid date format.")
                return

        folio = self.processor.folios.get(folio_id)
        if not folio:
            self._print(f"Folio '{folio_id}' not found in registered folios.")
            return

        self._print(f"\n=========================================================================")
        self._print(f" FOLIO STATEMENT: {folio_id}")
        self._print(f" Investor Name  : {folio.investor_name} | PAN: {folio.pan}")
        self._print(f" Bank Account   : {folio.bank_account} | IFSC: {folio.ifsc}")
        self._print(f" As-Of Date     : {as_of_date.isoformat()}")
        self._print(f"=========================================================================")

        remaining_lots = self.processor.lot_manager.get_remaining_lots_for_folio(
            folio_id
        )
        if not remaining_lots:
            self._print("No active holding lots found for this folio.")
            return

        header = f"{'Scheme ID':<10} {'Lot ID':<16} {'Allotment Date':<15} {'Units':>12} {'ELSS Lock-In':<14}"
        self._print(header)
        self._print("-" * len(header))

        scheme_totals: dict[str, Decimal] = {}
        for lot in remaining_lots:
            scheme = self.processor.schemes.get(lot.scheme_id)
            lock_in = ""
            if scheme and scheme.elss:
                lock_in = get_elss_lock_in_date(lot.allotment_date).isoformat()
            self._print(
                f"{lot.scheme_id:<10} {lot.lot_id:<16} {lot.allotment_date.isoformat():<15} "
                f"{lot.units:>12.3f} {lock_in:<14}"
            )
            scheme_totals[lot.scheme_id] = scheme_totals.get(lot.scheme_id, Decimal("0")) + lot.units

        self._print("-" * len(header))
        self._print("Summary by Scheme:")
        for sid, total_u in sorted(scheme_totals.items()):
            sname = self.processor.schemes[sid].name if sid in self.processor.schemes else ""
            self._print(f"  {sid} ({sname}): {total_u:.3f} units")

    # -------------------------------------------------------------------------
    # Menu Option 8: View Available Schemes
    # -------------------------------------------------------------------------
    def handle_view_schemes(self) -> None:
        """Display list of available mutual fund schemes."""
        self._print("\n=========================================================================")
        self._print(" AVAILABLE MUTUAL FUND SCHEMES")
        self._print("=========================================================================")
        header = f"{'ID':<9} {'Scheme Name':<28} {'Type':<8} {'Cutoff':<8} {'Min 1st':>9} {'Min Add':>9} {'Min Red':>9} {'ELSS':<5}"
        self._print(header)
        self._print("-" * len(header))

        for sid, s in sorted(self.processor.schemes.items()):
            elss_str = "YES" if s.elss else "NO"
            self._print(
                f"{s.scheme_id:<9} {s.name[:27]:<28} {s.scheme_type.value:<8} "
                f"{s.cutoff_time.strftime('%H:%M'):<8} "
                f"{s.min_first_purchase:>9.2f} {s.min_additional:>9.2f} {s.min_redemption:>9.2f} {elss_str:<5}"
            )
        self._print("-" * len(header))
        self._print(f"Total schemes available: {len(self.processor.schemes)}")

    # -------------------------------------------------------------------------
    # Menu Option 9: View Transaction History
    # -------------------------------------------------------------------------
    def handle_view_history(self) -> None:
        """Display transaction confirmations with optional filtering."""
        self._print("\n--- View Transaction History ---")
        self._print("Filter options:")
        self._print("1. All transactions")
        self._print("2. Filter by Folio ID")
        self._print("3. Filter by Scheme ID")
        self._print("4. Filter by Transaction Type (PURCHASE/REDEEM/SWITCH)")
        self._print("5. Filter by Decision (ACCEPTED/REJECTED)")
        choice = self._prompt("Select filter (1-5, default 1): ").strip()

        records = self.processor.confirmations
        if choice == "2":
            fid = self._prompt("Enter Folio ID to filter: ").strip().upper()
            records = [r for r in records if r["folio_id"].upper() == fid]
        elif choice == "3":
            sid = self._prompt("Enter Scheme ID to filter: ").strip().upper()
            records = [r for r in records if r["scheme_id"].upper() == sid]
        elif choice == "4":
            ttype = self._prompt("Enter Txn Type (PURCHASE/REDEEM/SWITCH_IN/SWITCH_OUT): ").strip().upper()
            records = [r for r in records if r["txn_type"].upper() == ttype]
        elif choice == "5":
            dec = self._prompt("Enter Decision (ACCEPTED/REJECTED): ").strip().upper()
            records = [r for r in records if r["decision"].upper() == dec]

        if not records:
            self._print("No transactions found matching criteria.")
            return

        self._print(f"\nDisplaying {len(records)} transaction records:")
        header = f"{'Order ID':<14} {'Folio ID':<9} {'Scheme':<9} {'Type':<11} {'Decision':<9} {'NAV Date':<11} {'Units':>11} {'Net Amt':>13}"
        self._print(header)
        self._print("-" * len(header))

        for r in records[-30:]:  # Show recent 30 to keep display legible
            units_val = r["units"] if r["units"] else "-"
            net_val = r["net_amount"] if r["net_amount"] else "-"
            nav_d = r["nav_date"] if r["nav_date"] else "-"
            self._print(
                f"{r['order_id']:<14} {r['folio_id']:<9} {r['scheme_id']:<9} "
                f"{r['txn_type']:<11} {r['decision']:<9} {nav_d:<11} "
                f"{units_val:>11} {net_val:>13}"
            )
        self._print("-" * len(header))
        if len(records) > 30:
            self._print(f"(Showing most recent 30 of {len(records)} matching records)")

    # -------------------------------------------------------------------------
    # Menu Option 10: Generate Reports
    # -------------------------------------------------------------------------
    def handle_generate_reports(self) -> None:
        """Generate output CSV files from current cumulative state."""
        self._print("\n--- Generating System Reports ---")
        conf_file, sip_file, folio_file = self.processor.write_csv_outputs(
            output_dir=self.workspace_dir
        )
        self._print("Reports generated successfully:")
        self._print(f"  1. {conf_file.name} ({len(self.processor.confirmations)} rows)")
        self._print(f"  2. {sip_file.name} ({len(self.processor.sip_statuses)} rows)")
        self._print(f"  3. {folio_file.name} ({len(self.processor.folio_statements)} rows)")

    # -------------------------------------------------------------------------
    # Menu Option 11: Run Batch Processing
    # -------------------------------------------------------------------------
    def handle_run_batch(self) -> None:
        """Run batch processing on official data/sample_pack/commands.txt."""
        self._print("\n=========================================================================")
        self._print(" EXECUTING OFFICIAL SAMPLE PACK BATCH RUN")
        self._print("=========================================================================")
        batch_processor = CommandProcessor(data_dir=self.data_dir)
        batch_processor.process_file()
        conf_f, sip_f, folio_f = batch_processor.write_csv_outputs(
            output_dir=self.workspace_dir
        )

        self._print("Batch Execution Summary:")
        self._print(f"  Commands Processed : {batch_processor.commands_processed} (Expected: 92)")
        self._print(f"  Commands Accepted  : {batch_processor.commands_accepted} (Expected: 86)")
        self._print(f"  Commands Rejected  : {batch_processor.commands_rejected} (Expected: 6)")
        self._print(f"  Confirmations File : {conf_f.name} ({len(batch_processor.confirmations)} rows, Expected: 77)")
        self._print(f"  SIP Status File    : {sip_f.name} ({len(batch_processor.sip_statuses)} rows, Expected: 17)")
        self._print(f"  Folio Statement    : {folio_f.name} ({len(batch_processor.folio_statements)} rows, Expected: 88)")

        if (
            batch_processor.commands_processed == 92
            and batch_processor.commands_accepted == 86
            and batch_processor.commands_rejected == 6
            and len(batch_processor.confirmations) == 77
            and len(batch_processor.sip_statuses) == 17
            and len(batch_processor.folio_statements) == 88
        ):
            self._print(">> Official Batch Benchmark Verification: 100% PASSED <<")
        else:
            self._print(">> Warning: Batch metrics diverged from expected baseline! <<")

    # -------------------------------------------------------------------------
    # Main Event Loop
    # -------------------------------------------------------------------------
    def run(self) -> None:
        """Run the interactive terminal menu loop."""
        while True:
            self._print("===============================================")
            self._print("       MUTUAL FUND ORDER PROCESSING SYSTEM     ")
            self._print("===============================================")
            self._print("1. Purchase Mutual Fund")
            self._print("2. Redeem Mutual Fund")
            self._print("3. Switch Mutual Fund")
            self._print("4. Register SIP")
            self._print("5. Pause SIP")
            self._print("6. Process SIP Debit Result")
            self._print("7. View Investor Folio")
            self._print("8. View Available Schemes")
            self._print("9. View Transaction History")
            self._print("10. Generate Reports")
            self._print("11. Run Batch Processing")
            self._print("12. Exit")
            self._print("===============================================")

            choice = self._prompt("Enter your choice (1-12): ").strip()

            if choice == "1":
                self.handle_purchase()
            elif choice == "2":
                self.handle_redeem()
            elif choice == "3":
                self.handle_switch()
            elif choice == "4":
                self.handle_register_sip()
            elif choice == "5":
                self.handle_pause_sip()
            elif choice == "6":
                self.handle_sip_debit_result()
            elif choice == "7":
                self.handle_view_folio()
            elif choice == "8":
                self.handle_view_schemes()
            elif choice == "9":
                self.handle_view_history()
            elif choice == "10":
                self.handle_generate_reports()
            elif choice == "11":
                self.handle_run_batch()
            elif choice == "12":
                self._print("\nSaving session state and exiting. Thank you!")
                break
            else:
                self._print(f"Invalid option '{choice}'. Please select between 1 and 12.")

            self._print()  # Empty spacer line between interactions
