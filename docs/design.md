# System Design — Mutual Fund Order Processing System

**Project ID:** T001-PS-008

## 1. Purpose

The Mutual Fund Order Processing System processes mutual fund transactions and maintains investor holdings. It accepts investor and scheme data, NAV records, holiday information and transaction commands. It validates each request, calculates the transaction and produces reports.

## 2. Scope

The system supports:

1. Mutual fund purchase.
2. Redemption by amount, units or all available unlocked units.
3. Switching from one mutual fund scheme to another.
4. SIP registration, pause and debit-result processing.
5. Investor folio and transaction reporting.
6. Interactive terminal use and file-based batch processing.

## 3. Inputs

Batch input files are stored in data/sample_pack/.

| Input | Description | Main information used |
|---|---|---|
| schemes.csv | Scheme master | Scheme ID, name, category, ELSS flag, cut-off and minimum amounts |
| navs.csv | NAV master | NAV date, scheme ID and NAV value |
| holidays.csv | Business calendar | Holiday date and name |
| exit_loads.csv | Exit-load configuration | Scheme category, holding-day range and load percentage |
| folios.csv | Investor records | Folio ID, investor and bank details |
| lots_opening.csv | Opening holdings | Lot ID, folio, scheme, allotment date, units and purchase NAV |
| existing_sips.csv | Existing SIP registrations | SIP ID, folio, scheme, amount, SIP day and status |
| sip_history.csv | Previous SIP results | SIP ID, instalment number, date and debit result |
| commands.txt | Transaction requests | Commands and arguments, processed in file order |

### Supported command inputs

| Command | Purpose |
|---|---|
| PURCHASE | Invest an amount in a scheme |
| REDEEM | Redeem by amount, units or all eligible units |
| SWITCH | Redeem from one scheme and invest the proceeds in another |
| SIP_REGISTER | Register a new SIP |
| SIP_DEBIT_RESULT | Record a successful or failed SIP debit |
| SIP_PAUSE | Pause SIP instalments for a permitted period |
| PRINT_FOLIO | Generate a folio holdings statement |

The sample command field order is documented in data/sample_pack/README.md.

## 4. Processing

### 4.1 Startup and data validation

The application loads scheme, NAV, holiday, exit-load, folio, lot and SIP data. Required columns, identifiers, dates and numeric values are validated. Invalid requests are rejected with a reason.

### 4.2 NAV determination

The applicable NAV is selected using scheme category, order timestamp, funds-realisation timestamp and business calendar.

- Equity and Debt schemes use a 3:00 PM cut-off.
- Liquid schemes use a 1:30 PM cut-off.
- Funds-realisation time is considered alongside order time.
- Weekends and configured holidays are non-business days.

### 4.3 Purchase

The system validates the folio, scheme and minimum investment. It calculates stamp duty, deducts it from the investment amount, calculates units using the applicable NAV and rounds units down to three decimal places. An accepted purchase creates an investment lot.

### 4.4 Redemption

The system supports redemption by amount, units or all eligible units. It checks available units and the minimum redemption amount. Amount-based redemption converts the requested amount into units using upward rounding to three decimal places.

Eligible lots are selected in FIFO order. The system checks ELSS lock-in restrictions, calculates exit loads and determines the payout date.

### 4.5 Switch

A switch contains two transaction legs:

- Switch out: redeem units from the source scheme and calculate applicable exit load.
- Switch in: invest the net proceeds in the target scheme and calculate stamp duty and target units.

The target purchase minimum is waived for a switch. Both legs are recorded as transaction confirmations.

### 4.6 SIP

The SIP module handles registration, monthly instalment scheduling, debit results and pause requests. It adjusts scheduled dates for month length and non-business days, enforces the first-instalment waiting period and pause restrictions, and cancels a SIP after three consecutive failed debits. A successful debit resets the consecutive-failure count and creates a SIP purchase.

### 4.7 Folio and reports

Folio functionality reports remaining investment lots, including ELSS lock-in dates where applicable. After processing, the system writes transaction confirmations, SIP status records and folio statements as CSV files.

## 5. Business Rule Summary

| Area | Main conditions |
|---|---|
| NAV | Equity/Debt cut-off 3:00 PM; Liquid cut-off 1:30 PM; funds-realisation and business calendar considered |
| Purchase | First investment ₹5,000; additional investment ₹1,000; stamp duty 0.005%; units rounded down to 3 decimals |
| Redemption | Partial minimum ₹1,000; amount-to-unit conversion rounded up to 3 decimals |
| Exit load | Depends on scheme category and holding period of each lot |
| FIFO | Oldest eligible investment lot is redeemed first |
| ELSS | Each lot has a three-year lock-in; locked units cannot be redeemed |
| Switch | Source redemption and target purchase; target purchase minimum waived |
| SIP | Minimum ₹500; first instalment at least 7 days after registration; maximum 3-month pause once per year; cancellation after 3 consecutive failed debits |
| Payout | Equity T+2 business days; Debt/Liquid T+1 business day |

For exact detailed conditions and exceptions, refer to docs/business_rules.md and the sample-pack specification.

## 6. Outputs

The application generates the following CSV files in the repository root.

### confirmations.csv

Contains one record for each purchase, redemption and SIP purchase. A switch creates two records: SWITCH_OUT and SWITCH_IN.

The report includes order and folio IDs, scheme and transaction type, decision and rule references, NAV date and NAV, gross amount, stamp duty, units, exit load, net amount and payout date.

### sip_status.csv

Contains SIP registration, pause and debit-result events, including scheduled dates, results, consecutive failure count and current SIP status.

### folio_statement.csv

Contains remaining investment lots for each folio statement request, including scheme, lot, allotment date, units and ELSS lock-in date where applicable.

## 7. Main Source Modules

| Module | Responsibility |
|---|---|
| src/main.py | Starts interactive mode or batch mode |
| src/interactive.py | Menu-driven terminal interface |
| src/command_processor.py | Reads commands, coordinates processing and writes reports |
| src/models.py | Shared data models and enumerations |
| src/scheme_engine.py | Loads and validates scheme master data |
| src/nav_engine.py | Loads NAVs and applies cut-off and business-day rules |
| src/purchase_engine.py | Purchase calculations and unit allocation |
| src/redemption_engine.py | Redemption calculations and payout dates |
| src/switch_engine.py | Coordinates switch-out and switch-in transactions |
| src/sip_engine.py | SIP registration, scheduling, pause and debit tracking |
| src/exit_load_engine.py | Exit-load schedule and calculations |
| src/lot_manager.py | Investor holdings, FIFO lot selection and ELSS lock-in |

## 8. Execution

Interactive mode:

```bash
python -m src.main
```

Batch mode:

```bash
python -m src.main --batch
```

Automated tests:

```bash
python -m pytest -q
```

## 9. Assumptions and Reference

The batch process uses the supplied sample data and command-file order. Scheme NAVs, holidays, exit-load schedules and investor opening holdings are supplied as input data; they are not fetched from an external financial service.

The detailed business-rule register and sample input specification are the references for exact field formats, edge cases and evaluation expectations.
