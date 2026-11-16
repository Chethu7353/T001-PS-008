# Mutual Fund Order Processing System

**Project ID:** T001-PS-008  
**Language:** Python 3.10+  
**Type:** Command-line application and batch processing system

## 1. Problem statement

The Mutual Fund Order Processing System processes investor transactions for mutual fund schemes. It supports purchases, redemptions, scheme switches and Systematic Investment Plans (SIPs).

It applies NAV cut-off rules, funds-realisation timing, minimum investment amounts, stamp duty, exit loads, FIFO unit allocation, ELSS lock-in periods and payout timelines.

## 2. Main Features

- Purchase mutual fund units.
- Redeem units by amount, unit quantity or all available unlocked units.
- Switch investments between schemes.
- Register, pause and process SIP instalments.
- Calculate applicable NAV using order time, funds-realisation time, scheme type and business calendar.
- Apply stamp duty and exit loads.
- Maintain investment lots using FIFO.
- Enforce the three-year ELSS lock-in.
- Generate transaction, SIP and folio reports.
- Run interactively or from a batch command file.

## 3. Technology

- Python 3.10 or later
- Python Standard Library
- CSV files for input data and generated reports
- decimal.Decimal for financial calculations
- pytest for automated tests

## 4. Input

The application reads reference data and transaction commands from CSV and text files.

| File | Purpose |
|---|---|
| schemes.csv | Scheme details, category, cut-off and minimum amounts |
| navs.csv | Scheme NAV values and effective dates |
| holidays.csv | Non-business days |
| exit_loads.csv | Exit-load rates by category and holding period |
| folios.csv | Investor folio details |
| lots_opening.csv | Existing investment lots and unit balances |
| existing_sips.csv | Existing SIP registrations |
| sip_history.csv | Previous SIP debit results |
| commands.txt | Orders and SIP actions to process |

The sample input files are in data/sample_pack/.

### Supported commands

- PURCHASE
- REDEEM
- SWITCH
- SIP_REGISTER
- SIP_DEBIT_RESULT
- SIP_PAUSE
- PRINT_FOLIO

Commands are processed in the order in which they appear in commands.txt.

## 5. Output

The system generates three CSV reports in the project root.

| Output file | Contents |
|---|---|
| confirmations.csv | Accepted and rejected transaction details, NAV, units, charges and payout date |
| sip_status.csv | SIP registration, pause and debit-result history |
| folio_statement.csv | Remaining investment lots and ELSS lock-in dates |

Rejected transactions are recorded with their decision and applicable rule information.

## 6. Business Rules

- Equity and Debt NAV cut-off: 3:00 PM.
- Liquid NAV cut-off: 1:30 PM.
- Funds-realisation time is considered when deciding applicable NAV.
- Business days exclude weekends and dates in the holiday file.
- First purchase minimum: ₹5,000.
- Additional purchase minimum: ₹1,000.
- SIP minimum: ₹500.
- Partial redemption minimum: ₹1,000, subject to the all-units rule.
- Purchase stamp duty: 0.005%.
- Purchase units are rounded down to three decimal places.
- Amount-based redemption units are rounded up to three decimal places.
- Exit loads are calculated using each investment lot's holding period.
- Units are redeemed in FIFO order.
- ELSS units have a three-year lock-in from each lot's allotment date.
- Equity redemption payout: T+2 business days.
- Debt and Liquid redemption payout: T+1 business day.
- SIP scheduling, pause limits and consecutive debit failure rules are enforced.

See docs/business_rules.md for detailed rule descriptions.

## 7. Project Structure

```text
T001-PS-008/
├── data/sample_pack/       Input CSV files and commands
├── docs/                   Project documentation
│   ├── business_rules.md   Detailed business rules
│   └── design.md           System design
├── src/                    Application source code
├── tests/                  Automated tests
├── confirmations.csv       Transaction report
├── sip_status.csv          SIP report
├── folio_statement.csv     Folio report
├── requirements.txt
└── README.md
```

