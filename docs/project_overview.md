# Project Overview: Mutual Fund Order Processing System (T001-PS-008)

## 1. System Summary
T001-PS-008 is a production-grade, regulation-compliant Python mutual fund order processing system developed for Asset Management Companies (AMCs) and mutual fund transfer agents. The system automates the validation, pricing, calculation, and ledger recording for lump-sum purchases, redemptions, scheme switches, and Systematic Investment Plans (SIPs).

## 2. Core Capabilities
- **Regulatory Cut-Off Compliance (BR-01, BR-02):** Determines applicable NAV based on statutory cut-offs (15:00 for Equity/Debt, 13:30 for Liquid) and funds-realisation timestamps.
- **Business Day & Holiday Calendar (BR-03, BR-06):** Resolves settlement and transaction dates against market holidays and weekends.
- **Master Data Ingestion (BR-04, BR-05):** Ingests scheme definitions and NAV records with fail-fast validation and row-level error reporting.
- **Purchase Accounting (BR-07):** Deducts 0.005% stamp duty and allocates units rounded down to 3 decimal places.
- **Redemption & Exit Loads (BR-08, BR-11):** Enforces ceiling rounding for amount redemptions, computes holding-day exit loads per lot, and schedules $T+1$ or $T+2$ payouts.
- **Atomic Scheme Switches (BR-09):** Coordinates source redemption and target purchase with target minimum investment waivers.
- **Comprehensive SIP Engine (BR-10):** Schedules monthly debits, clamps month-end dates, tracks failure counters, auto-cancels after 3 consecutive failures, and manages pauses.
- **ELSS Statutory Lock-In (BR-11):** Safeguards tax-saving units under an inviolable 3-year holding period.

## 3. Architecture
The application is structured into four cohesive layers:
1. **Domain Models (`src/models.py`):** Immutable dataclasses and Enums representing schemes, folios, orders, lots, schedules, and confirmations.
2. **Reference Data Engines:** `scheme_engine.py`, `nav_engine.py`, `exit_load_engine.py`, and `lot_manager.py`.
3. **Transaction Execution Engines:** `purchase_engine.py`, `redemption_engine.py`, `switch_engine.py`, and `sip_engine.py`.
4. **Batch Orchestration:** `command_processor.py` and `main.py`.

## 4. Execution & Verification
- **Run Pipeline:** `python -m src.main`
- **Run Test Suite:** `python -m pytest -q` (227 tests passed)
