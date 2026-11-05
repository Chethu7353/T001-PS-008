"""Command Processing Engine for mutual fund orders, SIPs, and folio tracking."""

import csv
from datetime import date, datetime, time
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from typing import TextIO

from src.exit_load_engine import ExitLoadSchedule, load_exit_loads
from src.lot_manager import LotManager, get_elss_lock_in_date
from src.models import Folio, InvestmentLot, Scheme, SchemeType
from src.nav_engine import get_applicable_nav_date, load_holidays, load_navs
from src.redemption_engine import calculate_payout_date
from src.sip_engine import SIPManager
from src.switch_engine import process_switch


STAMP_DUTY_RATE = Decimal("0.00005")
PAISE = Decimal("0.01")
UNIT_PRECISION = Decimal("0.001")


class CommandProcessor:
    """Processes commands from commands.txt and generates official output CSV files."""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is None:
            data_dir = (
                Path(__file__).resolve().parent.parent / "data" / "sample_pack"
            )
        self.data_dir = Path(data_dir)

        self.holidays: set[date] = set()
        self.schedules: list[ExitLoadSchedule] = []
        self.schemes: dict[str, Scheme] = {}
        self.folios: dict[str, Folio] = {}
        self.navs: dict[tuple[str, date], Decimal] = {}

        self.lot_manager = LotManager()
        self.sip_manager = SIPManager()

        self.confirmations: list[dict[str, str]] = []
        self.sip_statuses: list[dict[str, str]] = []
        self.folio_statements: list[dict[str, str]] = []

        self.commands_processed = 0
        self.commands_accepted = 0
        self.commands_rejected = 0

    def load_reference_data(self) -> None:
        """Load all initial static and opening state files."""
        # Holidays
        holidays_file = self.data_dir / "holidays.csv"
        if holidays_file.exists():
            self.holidays = load_holidays(holidays_file)

        # Exit loads
        exit_loads_file = self.data_dir / "exit_loads.csv"
        if exit_loads_file.exists():
            self.schedules = load_exit_loads(exit_loads_file)

        # Schemes
        schemes_file = self.data_dir / "schemes.csv"
        if schemes_file.exists():
            with schemes_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.schemes[row["scheme_id"]] = Scheme(
                        scheme_id=row["scheme_id"],
                        name=row["scheme_name"],
                        scheme_type=SchemeType(row["scheme_type"]),
                        elss=row["elss"].strip().lower() == "true",
                        cutoff_time=time.fromisoformat(row["cutoff_time"].strip()),
                        min_first_purchase=Decimal(row["min_first_purchase"]),
                        min_additional=Decimal(row["min_additional"]),
                        min_sip=Decimal(row["min_sip"]),
                        min_redemption=Decimal(row["min_redemption"]),
                    )

        # Folios
        folios_file = self.data_dir / "folios.csv"
        if folios_file.exists():
            with folios_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.folios[row["folio_id"]] = Folio(
                        folio_id=row["folio_id"],
                        investor_name=row["investor_name"],
                        pan=row["pan"],
                        mobile=row["mobile"],
                        bank_account=row["bank_account"],
                        ifsc=row["ifsc"],
                        opened_date=date.fromisoformat(row["opened_date"]),
                    )

        # NAVs
        navs_file = self.data_dir / "navs.csv"
        if navs_file.exists():
            self.navs = load_navs(navs_file)

        # Lots opening
        lots_file = self.data_dir / "lots_opening.csv"
        if lots_file.exists():
            self.lot_manager.load_opening_lots(lots_file)

        # SIPs and history
        sips_file = self.data_dir / "existing_sips.csv"
        history_file = self.data_dir / "sip_history.csv"
        self.sip_manager.load_existing_sips(sips_file, history_file)

    def get_nav(self, scheme_id: str, nav_date: date) -> Decimal:
        """Lookup NAV for scheme on date."""
        key = (scheme_id, nav_date)
        if key not in self.navs:
            raise ValueError(f"NAV not found for scheme {scheme_id} on {nav_date.isoformat()}")
        return self.navs[key]

    def process_purchase(
        self,
        order_id: str,
        order_ts_str: str,
        folio_id: str,
        scheme_id: str,
        amount_str: str,
        realised_ts_str: str,
    ) -> None:
        """Process a lump-sum PURCHASE command."""
        self.commands_processed += 1
        order_ts = datetime.fromisoformat(order_ts_str)
        realised_ts = datetime.fromisoformat(realised_ts_str)
        amount = Decimal(amount_str)

        scheme = self.schemes[scheme_id]
        is_first = not self.lot_manager.has_holding(folio_id, scheme_id)
        min_amount = scheme.min_first_purchase if is_first else scheme.min_additional

        if amount < min_amount:
            self.commands_rejected += 1
            self.confirmations.append({
                "order_id": order_id,
                "folio_id": folio_id,
                "scheme_id": scheme_id,
                "txn_type": "PURCHASE",
                "decision": "REJECTED",
                "rule_ids": "BR-07",
                "nav_date": "",
                "nav": "",
                "gross_amount": "",
                "stamp_duty": "",
                "units": "",
                "exit_load": "",
                "net_amount": "",
                "payout_date": "",
            })
            return

        self.commands_accepted += 1
        nav_date = get_applicable_nav_date(
            scheme.scheme_type,
            order_ts,
            realised_ts,
            holidays=self.holidays,
            use_calendar_day_for_liquid=True,
        )
        nav = self.get_nav(scheme_id, nav_date)
        stamp_duty = (amount * STAMP_DUTY_RATE).quantize(PAISE, rounding=ROUND_HALF_UP)
        investible = amount - stamp_duty
        units = (investible / nav).quantize(UNIT_PRECISION, rounding=ROUND_DOWN)

        lot = InvestmentLot(
            lot_id=order_id,
            investor_id=folio_id,
            scheme_id=scheme_id,
            purchase_date=nav_date,
            units=units,
            purchase_nav=nav,
        )
        self.lot_manager.add_lot(lot)

        self.confirmations.append({
            "order_id": order_id,
            "folio_id": folio_id,
            "scheme_id": scheme_id,
            "txn_type": "PURCHASE",
            "decision": "ACCEPTED",
            "rule_ids": "BR-01;BR-02;BR-07",
            "nav_date": nav_date.isoformat(),
            "nav": f"{nav:.4f}",
            "gross_amount": f"{amount:.2f}",
            "stamp_duty": f"{stamp_duty:.2f}",
            "units": f"{units:.3f}",
            "exit_load": "0.00",
            "net_amount": f"{investible:.2f}",
            "payout_date": "",
        })

    def process_redeem(
        self,
        order_id: str,
        order_ts_str: str,
        folio_id: str,
        scheme_id: str,
        mode: str,
        value_str: str,
    ) -> None:
        """Process a REDEEM command."""
        self.commands_processed += 1
        order_ts = datetime.fromisoformat(order_ts_str)
        scheme = self.schemes[scheme_id]
        nav_date = get_applicable_nav_date(
            scheme.scheme_type,
            order_ts,
            holidays=self.holidays,
            use_calendar_day_for_liquid=True,
        )
        nav = self.get_nav(scheme_id, nav_date)
        available_units = self.lot_manager.get_available_unlocked_units(
            folio_id, scheme_id, nav_date, scheme
        )

        is_valid = True
        fail_rule = "BR-08"
        units_to_redeem = Decimal("0.000")

        # Check if units exist but are locked under ELSS
        if available_units <= Decimal("0.000") and self.lot_manager.has_holding(folio_id, scheme_id):
            if scheme.elss:
                fail_rule = "BR-11"

        if mode == "ALL":
            if available_units <= Decimal("0.000"):
                is_valid = False
            else:
                units_to_redeem = available_units
        elif mode == "UNITS":
            try:
                req_units = Decimal(value_str).quantize(UNIT_PRECISION)
                if req_units <= Decimal("0.000") or req_units > available_units:
                    is_valid = False
                else:
                    gross = (req_units * nav).quantize(PAISE, rounding=ROUND_HALF_UP)
                    if req_units < available_units and gross < scheme.min_redemption:
                        is_valid = False
                    else:
                        units_to_redeem = req_units
            except Exception:
                is_valid = False
        elif mode == "AMOUNT":
            try:
                req_amount = Decimal(value_str).quantize(PAISE)
                if req_amount <= Decimal("0.00"):
                    is_valid = False
                else:
                    units_needed = (req_amount / nav).quantize(
                        UNIT_PRECISION, rounding=ROUND_CEILING
                    )
                    if units_needed > available_units:
                        is_valid = False
                    elif units_needed < available_units and req_amount < scheme.min_redemption:
                        is_valid = False
                    else:
                        units_to_redeem = units_needed
            except Exception:
                is_valid = False
        else:
            is_valid = False

        if not is_valid:
            self.commands_rejected += 1
            self.confirmations.append({
                "order_id": order_id,
                "folio_id": folio_id,
                "scheme_id": scheme_id,
                "txn_type": "REDEMPTION",
                "decision": "REJECTED",
                "rule_ids": fail_rule,
                "nav_date": "",
                "nav": "",
                "gross_amount": "",
                "stamp_duty": "",
                "units": "",
                "exit_load": "",
                "net_amount": "",
                "payout_date": "",
            })
            return

        self.commands_accepted += 1
        exit_load = self.lot_manager.deplete_units_fifo(
            folio_id,
            scheme_id,
            units_to_redeem,
            nav_date,
            scheme,
            self.schedules,
            nav,
        )
        gross_amount = (units_to_redeem * nav).quantize(PAISE, rounding=ROUND_HALF_UP)
        net_amount = gross_amount - exit_load
        payout_date = calculate_payout_date(
            scheme.scheme_type, nav_date, self.holidays
        )

        self.confirmations.append({
            "order_id": order_id,
            "folio_id": folio_id,
            "scheme_id": scheme_id,
            "txn_type": "REDEMPTION",
            "decision": "ACCEPTED",
            "rule_ids": "BR-01;BR-08;BR-11",
            "nav_date": nav_date.isoformat(),
            "nav": f"{nav:.4f}",
            "gross_amount": f"{gross_amount:.2f}",
            "stamp_duty": "0.00",
            "units": f"{units_to_redeem:.3f}",
            "exit_load": f"{exit_load:.2f}",
            "net_amount": f"{net_amount:.2f}",
            "payout_date": payout_date.isoformat(),
        })

    def process_switch_cmd(
        self,
        order_id: str,
        order_ts_str: str,
        folio_id: str,
        from_scheme_id: str,
        to_scheme_id: str,
        mode: str,
        value_str: str,
    ) -> None:
        """Process a SWITCH command."""
        self.commands_processed += 1
        order_ts = datetime.fromisoformat(order_ts_str)
        from_scheme = self.schemes[from_scheme_id]
        to_scheme = self.schemes[to_scheme_id]

        out_rec, in_rec = process_switch(
            order_id,
            order_ts,
            folio_id,
            from_scheme,
            to_scheme,
            mode,
            value_str,
            self.lot_manager,
            self.schedules,
            self.get_nav,
            self.holidays,
        )
        self.confirmations.append(out_rec)
        self.confirmations.append(in_rec)
        if out_rec["decision"] == "ACCEPTED":
            self.commands_accepted += 1
        else:
            self.commands_rejected += 1

    def process_sip_register(
        self,
        sip_id: str,
        reg_ts_str: str,
        folio_id: str,
        scheme_id: str,
        amount_str: str,
        day_str: str,
    ) -> None:
        """Process a SIP_REGISTER command."""
        self.commands_processed += 1
        reg_ts = datetime.fromisoformat(reg_ts_str)
        amount = Decimal(amount_str)
        sip_day = int(day_str)
        scheme = self.schemes[scheme_id]

        ok, decision, first_date = self.sip_manager.register_sip(
            sip_id, reg_ts, folio_id, scheme_id, amount, sip_day, scheme, self.holidays
        )
        if ok:
            self.commands_accepted += 1
            self.sip_statuses.append({
                "sip_id": sip_id,
                "event": "SIP_REGISTER",
                "instalment_no": "",
                "scheduled_date": first_date.isoformat() if first_date else "",
                "result": "ACCEPTED",
                "order_id": "",
                "consecutive_failures": "0",
                "sip_status": "ACTIVE",
                "rule_ids": "BR-10",
            })
        else:
            self.commands_rejected += 1
            self.sip_statuses.append({
                "sip_id": sip_id,
                "event": "SIP_REGISTER",
                "instalment_no": "",
                "scheduled_date": "",
                "result": "REJECTED",
                "order_id": "",
                "consecutive_failures": "0",
                "sip_status": "REJECTED",
                "rule_ids": "BR-10",
            })

    def process_sip_pause(
        self,
        sip_id: str,
        req_ts_str: str,
        from_month: str,
        months_str: str,
    ) -> None:
        """Process a SIP_PAUSE command."""
        self.commands_processed += 1
        req_ts = datetime.fromisoformat(req_ts_str)
        months = int(months_str)

        ok, decision = self.sip_manager.pause_sip(sip_id, req_ts, from_month, months)
        sip = self.sip_manager.sips.get(sip_id)
        if ok:
            self.commands_accepted += 1
            self.sip_statuses.append({
                "sip_id": sip_id,
                "event": "SIP_PAUSE",
                "instalment_no": "",
                "scheduled_date": "",
                "result": "ACCEPTED",
                "order_id": "",
                "consecutive_failures": str(sip.consecutive_failures if sip else 0),
                "sip_status": sip.status if sip else "PAUSED",
                "rule_ids": "BR-10",
            })
        else:
            self.commands_rejected += 1
            cf = str(sip.consecutive_failures) if sip else "0"
            st = sip.status if sip else "UNKNOWN"
            self.sip_statuses.append({
                "sip_id": sip_id,
                "event": "SIP_PAUSE",
                "instalment_no": "",
                "scheduled_date": "",
                "result": "REJECTED",
                "order_id": "",
                "consecutive_failures": cf,
                "sip_status": st,
                "rule_ids": "BR-10",
            })

    def process_sip_debit_result(
        self,
        sip_id: str,
        inst_no_str: str,
        result_str: str,
        realised_ts_str: str,
        reason: str,
    ) -> None:
        """Process a SIP_DEBIT_RESULT command."""
        self.commands_processed += 1
        inst_no = int(inst_no_str)
        realised_ts = datetime.fromisoformat(realised_ts_str)

        scheduled_date = self.sip_manager.scheduled_date(
            sip_id, inst_no, self.holidays
        )
        ok, cf, st = self.sip_manager.record_debit_result(sip_id, inst_no, result_str)
        sip = self.sip_manager.sips[sip_id]
        scheme = self.schemes[sip.scheme_id]

        if ok:  # SUCCESS
            self.commands_accepted += 1
            order_id = f"ORD-{sip_id}-{inst_no}"
            nav_date = get_applicable_nav_date(
                scheme.scheme_type,
                realised_ts,
                holidays=self.holidays,
                use_calendar_day_for_liquid=True,
            )
            nav = self.get_nav(sip.scheme_id, nav_date)
            stamp_duty = (sip.amount * STAMP_DUTY_RATE).quantize(PAISE, rounding=ROUND_HALF_UP)
            investible = sip.amount - stamp_duty
            units = (investible / nav).quantize(UNIT_PRECISION, rounding=ROUND_DOWN)

            lot = InvestmentLot(
                lot_id=order_id,
                investor_id=sip.folio_id,
                scheme_id=sip.scheme_id,
                purchase_date=nav_date,
                units=units,
                purchase_nav=nav,
            )
            self.lot_manager.add_lot(lot)

            self.confirmations.append({
                "order_id": order_id,
                "folio_id": sip.folio_id,
                "scheme_id": sip.scheme_id,
                "txn_type": "SIP_PURCHASE",
                "decision": "ACCEPTED",
                "rule_ids": "BR-01;BR-07;BR-10",
                "nav_date": nav_date.isoformat(),
                "nav": f"{nav:.4f}",
                "gross_amount": f"{sip.amount:.2f}",
                "stamp_duty": f"{stamp_duty:.2f}",
                "units": f"{units:.3f}",
                "exit_load": "0.00",
                "net_amount": f"{investible:.2f}",
                "payout_date": "",
            })

            self.sip_statuses.append({
                "sip_id": sip_id,
                "event": "SIP_DEBIT_RESULT",
                "instalment_no": str(inst_no),
                "scheduled_date": scheduled_date.isoformat(),
                "result": "SUCCESS",
                "order_id": order_id,
                "consecutive_failures": "0",
                "sip_status": st,
                "rule_ids": "BR-10",
            })
        else:  # FAILED
            self.commands_accepted += 1
            self.sip_statuses.append({
                "sip_id": sip_id,
                "event": "SIP_DEBIT_RESULT",
                "instalment_no": str(inst_no),
                "scheduled_date": scheduled_date.isoformat(),
                "result": "FAILED",
                "order_id": "",
                "consecutive_failures": str(cf),
                "sip_status": st,
                "rule_ids": "BR-10",
            })

    def process_print_folio(self, folio_id: str, as_of_date_str: str) -> None:
        """Process a PRINT_FOLIO command."""
        self.commands_processed += 1
        self.commands_accepted += 1
        as_of_date = date.fromisoformat(as_of_date_str)
        remaining_lots = self.lot_manager.get_remaining_lots_for_folio(folio_id)

        for lot in remaining_lots:
            lock_in = ""
            if self.schemes[lot.scheme_id].elss:
                lock_in = get_elss_lock_in_date(lot.allotment_date).isoformat()

            self.folio_statements.append({
                "folio_id": folio_id,
                "as_of_date": as_of_date.isoformat(),
                "scheme_id": lot.scheme_id,
                "lot_id": lot.lot_id,
                "allotment_date": lot.allotment_date.isoformat(),
                "units": f"{lot.units:.3f}",
                "lock_in_until": lock_in,
            })

    def process_line(self, raw_line: str) -> None:
        """Parse and execute a single line from commands.txt."""
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return

        parts = [p.strip() for p in line.split("|")]
        cmd = parts[0]

        if cmd == "PURCHASE":
            self.process_purchase(parts[1], parts[2], parts[3], parts[4], parts[5], parts[6])
        elif cmd == "REDEEM":
            self.process_redeem(parts[1], parts[2], parts[3], parts[4], parts[5], parts[6])
        elif cmd == "SWITCH":
            self.process_switch_cmd(parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7])
        elif cmd == "SIP_REGISTER":
            self.process_sip_register(parts[1], parts[2], parts[3], parts[4], parts[5], parts[6])
        elif cmd == "SIP_PAUSE":
            self.process_sip_pause(parts[1], parts[2], parts[3], parts[4])
        elif cmd == "SIP_DEBIT_RESULT":
            self.process_sip_debit_result(parts[1], parts[2], parts[3], parts[4], parts[5] if len(parts) > 5 else "")
        elif cmd == "PRINT_FOLIO":
            self.process_print_folio(parts[1], parts[2])
        else:
            raise ValueError(f"Unknown command: {cmd}")

    def process_file(self, commands_file: Path | None = None) -> None:
        """Read commands.txt and process all commands in order."""
        if commands_file is None:
            commands_file = self.data_dir / "commands.txt"
        else:
            commands_file = Path(commands_file)

        self.load_reference_data()

        with commands_file.open(newline="", encoding="utf-8") as f:
            for line in f:
                self.process_line(line)

    def write_csv_outputs(self, output_dir: Path | None = None) -> tuple[Path, Path, Path]:
        """Write the three official CSV output files."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        conf_file = output_dir / "confirmations.csv"
        sip_file = output_dir / "sip_status.csv"
        folio_file = output_dir / "folio_statement.csv"

        # 1. confirmations.csv
        conf_headers = [
            "order_id",
            "folio_id",
            "scheme_id",
            "txn_type",
            "decision",
            "rule_ids",
            "nav_date",
            "nav",
            "gross_amount",
            "stamp_duty",
            "units",
            "exit_load",
            "net_amount",
            "payout_date",
        ]
        with conf_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=conf_headers)
            writer.writeheader()
            for row in self.confirmations:
                writer.writerow(row)

        # 2. sip_status.csv
        sip_headers = [
            "sip_id",
            "event",
            "instalment_no",
            "scheduled_date",
            "result",
            "order_id",
            "consecutive_failures",
            "sip_status",
            "rule_ids",
        ]
        with sip_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sip_headers)
            writer.writeheader()
            for row in self.sip_statuses:
                writer.writerow(row)

        # 3. folio_statement.csv
        folio_headers = [
            "folio_id",
            "as_of_date",
            "scheme_id",
            "lot_id",
            "allotment_date",
            "units",
            "lock_in_until",
        ]
        with folio_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=folio_headers)
            writer.writeheader()
            for row in self.folio_statements:
                writer.writerow(row)

        return conf_file, sip_file, folio_file
