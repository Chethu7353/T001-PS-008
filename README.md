# Mutual Fund Order Processing System

**Project ID:** T001-PS-008  
**Language:** Python 3.10+  
**Type:** Command-line application with batch processing

## Overview

The Mutual Fund Order Processing System is a Python-based application that simulates the processing of mutual fund transactions. It accepts investor, scheme, NAV and transaction data, validates each request against configured business rules, calculates the transaction details and generates CSV reports.

The project is designed to demonstrate the core workflow of a mutual fund transaction-processing system using structured input files and modular Python code.

## Key Features

- **Purchase:** Validate investments, calculate stamp duty and allocate mutual fund units.
- **Redemption:** Redeem investments by amount, units or all eligible units.
- **Switch:** Move an investment from one scheme to another through switch-out and switch-in transactions.
- **SIP Management:** Register SIPs, calculate instalment dates, record debit results and process pause requests.
- **NAV Processing:** Apply scheme cut-off times, funds-realisation timestamps, NAV records and business-day calendars.
- **Holding Management:** Track investment lots, apply FIFO redemption and enforce ELSS lock-in checks.
- **Exit Load:** Calculate applicable charges using the configured scheme category and holding period.
- **Reports:** Generate transaction confirmations, SIP status records and folio statements.

## Transaction Workflow

1. Load scheme, NAV, holiday, investor, holding and SIP data.
2. Read transaction commands from the input file or interactive terminal.
3. Validate each request against the configured business rules.
4. Determine the applicable NAV and calculate transaction values.
5. Update holdings and SIP records when a transaction is accepted.
6. Generate CSV reports for review and reconciliation.

## Project Structure

```text
T001-PS-008/
├── data/
│   └── sample_pack/       # Sample master data and transaction commands
├── docs/                  # Design and business-rule documentation
├── src/
│   ├── main.py             # Application entry point
│   ├── interactive.py      # Menu-driven terminal interface
│   ├── command_processor.py# Transaction orchestration and reports
│   ├── models.py           # Shared data models and enums
│   ├── scheme_engine.py    # Scheme data loading and validation
│   ├── nav_engine.py       # NAV and business-day calculations
│   ├── purchase_engine.py  # Purchase validation and calculations
│   ├── redemption_engine.py# Redemption and payout calculations
│   ├── switch_engine.py    # Switch transaction processing
│   ├── sip_engine.py       # SIP registration and processing
│   ├── exit_load_engine.py # Exit-load calculations
│   └── lot_manager.py      # Holdings, FIFO and ELSS lock-in
├── tests/                  # Automated tests
└── requirements.txt        # Test and quality-assurance dependencies
```

## Technology

- Python 3.10+
- Python standard library for runtime processing
- CSV files for sample input data and generated reports
- Pytest for automated testing

The application has no external runtime package dependencies. The packages listed in `requirements.txt` are used for testing and quality assurance.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Chethu7353/T001-PS-008.git
cd T001-PS-008
```

### 2. Create and activate a virtual environment (recommended)

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install testing dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Run the application

**Interactive mode**

```bash
python -m src.main
```

**Batch mode**

```bash
python -m src.main --batch
```

Batch mode processes the commands in `data/sample_pack/` and writes the generated reports to the repository root.

## Generated Reports

| File | Description |
|---|---|
| `confirmations.csv` | Processed purchase, redemption, SIP purchase and switch transaction records |
| `sip_status.csv` | SIP registration, pause and debit-result status records |
| `folio_statement.csv` | Remaining investment lots and relevant holding details |

## Run Tests

Run the automated test suite with:

```bash
python -m pytest -q
```

## Important Business Rules

The system applies configurable rules for:

- Equity and Debt NAV cut-off time: **3:00 PM**
- Liquid fund NAV cut-off time: **1:30 PM**
- Stamp duty: **0.005%**
- First purchase minimum: **₹5,000**
- Additional purchase minimum: **₹1,000**
- SIP minimum instalment: **₹500**
- FIFO-based lot redemption and ELSS lock-in checks
- Category- and holding-period-based exit loads
- Equity payout: **T+2 business days**
- Debt and Liquid payout: **T+1 business day**

Exact conditions, exceptions and input formats are documented in the `docs/` directory and the sample-pack documentation.

## Scope and Disclaimer

This project is an educational transaction-processing simulation that uses supplied sample data. It does not connect to live mutual fund markets, AMCs, RTAs, payment systems or external NAV services. The generated results depend on the input data and business rules configured in the repository.

---

**Project:** T001-PS-008 – Mutual Fund Order Processing System  
**Repository:** [Chethu7353/T001-PS-008](https://github.com/Chethu7353/T001-PS-008)

------------
**Demo Video :** https://drive.google.com/file/d/1m4Ax5PdAVoIR8kL8O4Z4efImbsnRDRux/view?usp=drivesdk
