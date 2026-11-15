# T001-PS-008 — Python-Based Mutual Fund Order Processing System

**Project ID:** T001-PS-008  
**Project Type:** Python-Based Financial Application  
**Domain:** Financial Technology (FinTech)  
**Programming Language:** Python  
**Repository:** [GitHub – T001-PS-008](https://github.com/Chethu7353/T001-PS-008)  
**Status:** Implementation and integration testing completed; final submission verification pending.

---

## 1. Project Overview

The **Python-Based Mutual Fund Order Processing System** is an automated financial application developed to process and manage mutual fund transactions according to predefined business rules.

The system handles four major types of transactions:

- Purchase
- Redemption
- Switch
- Systematic Investment Plan (SIP)

It validates transaction details, determines the applicable Net Asset Value (NAV), performs financial calculations, applies business-day and holiday rules, calculates stamp duty and exit loads, and generates structured transaction reports.

The primary objective is to reduce manual processing, improve financial calculation accuracy, and ensure consistent execution of mutual fund business rules.

## 2. Problem Statement

Mutual fund transaction processing involves several financial calculations and operational rules.

Processing these transactions manually can lead to:

- Incorrect NAV selection.
- Errors in transaction calculations.
- Incorrect unit allocation.
- Improper exit-load calculations.
- Incorrect handling of weekends and holidays.
- Invalid redemption of locked-in ELSS investments.
- Inconsistent SIP scheduling.
- Errors in maintaining investor transaction records.

Therefore, an automated system is required to validate, process, and record mutual fund transactions accurately while following predefined financial business rules.

## 3. Project Objectives

The main objectives of this project are:

1. Automate mutual fund purchase and redemption transactions.
2. Implement mutual fund switching between schemes.
3. Manage recurring SIP investments.
4. Apply NAV cutoff and funds-realisation rules.
5. Handle business days, weekends, and holidays.
6. Validate scheme and transaction information.
7. Calculate stamp duty and exit loads accurately.
8. Implement FIFO-based unit redemption.
9. Enforce ELSS three-year lock-in restrictions.
10. Generate structured transaction confirmations and reports.
11. Improve reliability and consistency in mutual fund order processing.

## 4. Key Features

| Feature | Description |
|---|---|
| Purchase Processing | Processes mutual fund investment orders and calculates units. |
| Redemption Processing | Processes withdrawals and calculates applicable charges. |
| Switch Processing | Transfers investments between mutual fund schemes. |
| SIP Management | Schedules and processes recurring investments. |
| NAV Management | Selects the applicable NAV based on transaction timing. |
| Holiday Calendar | Handles non-business days and holiday adjustments. |
| Scheme Validation | Validates scheme information and investment conditions. |
| Stamp Duty | Calculates applicable stamp duty. |
| Exit Load | Applies scheme-specific exit-load rules. |
| FIFO Processing | Redeems units in the order they were purchased. |
| ELSS Lock-in | Prevents redemption of units before the three-year lock-in period. |
| CSV Reports | Generates transaction confirmations, SIP status, and folio statements. |

## 5. System Architecture

The application follows a modular Python architecture in which different components handle specific responsibilities.

### Processing Workflow

```text
             INPUT DATA
                 |
                 v
       CSV Data and Transaction
              Commands
                 |
                 v
       COMMAND PROCESSOR
                 |
                 v
       INPUT VALIDATION
                 |
                 v
          NAV ENGINE
                 |
                 v
       BUSINESS RULE ENGINE
                 |
       +---------+----------+
       |         |          |
       v         v          v
    PURCHASE  REDEMPTION   SWITCH
       |         |          |
       +---------+----------+
                 |
                 v
            SIP ENGINE
                 |
                 v
       FINANCIAL CALCULATIONS
                 |
                 v
        TRANSACTION RESULTS
                 |
          +------+------+
          |             |
          v             v
       ACCEPTED      REJECTED
          |             |
          +------+------+
                 |
                 v
          OUTPUT REPORTS
                 |
       +---------+----------+
       |         |          |
       v         v          v
 Confirmations  SIP Status  Folio
     CSV          CSV      Statement
                            CSV
```

### Main Components

- **Command Processor:** Reads and processes transaction commands.
- **NAV Engine:** Determines the applicable NAV based on cutoff and business-day rules.
- **Scheme Engine:** Validates mutual fund scheme information.
- **Purchase Engine:** Processes investment transactions.
- **Redemption Engine:** Handles withdrawals, FIFO allocation, and exit loads.
- **Switch Engine:** Manages transfers between mutual fund schemes.
- **SIP Engine:** Manages recurring investment schedules and transaction states.
- **Holiday Calendar:** Determines business days and adjusts transaction dates.
- **Models:** Maintains the application's transaction and investment data structures.

## 6. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application development |
| CSV | Input data and output report management |
| Decimal | Financial arithmetic and precision |
| Pytest | Unit and integration testing |
| Git | Version control |
| GitHub | Source code repository |
| PowerShell | Development and execution environment |

## 7. Business Rules Implemented

The system implements 11 major business rules.

| Rule | Business Rule | Description |
|---|---|---|
| BR-01 | NAV Cutoff | Applies scheme-specific NAV cutoff timings. |
| BR-02 | Funds Realisation | Uses the later of order receipt and funds-realisation time for NAV eligibility. |
| BR-03 | Business-Day Calendar | Handles weekends and non-business days. |
| BR-04 | Scheme Master Validation | Validates scheme IDs, types, cutoffs, and investment limits. |
| BR-05 | NAV File Validation | Validates NAV input data and handles missing or duplicate records. |
| BR-06 | Holiday Calendar | Validates holiday dates and handles holiday-based business-day adjustments. |
| BR-07 | Purchase Engine | Calculates investment amounts and units. |
| BR-08 | Redemption Engine | Processes withdrawals and applies redemption rules. |
| BR-09 | Switch Engine | Handles source redemption and target scheme investment. |
| BR-10 | SIP Engine | Manages recurring investment schedules and SIP states. |
| BR-11 | FIFO, Exit Load and ELSS | Implements FIFO allocation, exit-load calculations, and ELSS lock-in restrictions. |

### Important Financial Rules

**NAV Cutoff Times**

| Scheme Type | Cutoff Time |
|---|---|
| Equity | 3:00 PM |
| Debt | 3:00 PM |
| Liquid | 1:30 PM |

**Minimum Investment Amounts**

| Transaction | Minimum Amount |
|---|---:|
| First Purchase | ₹5,000 |
| Additional Purchase | ₹1,000 |
| SIP | ₹500 |
| Partial Redemption | ₹1,000 or all available units |

**Stamp Duty**

- Stamp duty rate: 0.005%.
- Calculated using decimal arithmetic and rounded to two decimal places.

**Purchase Unit Calculation**

Units are calculated using the investible amount divided by the applicable NAV and rounded down to three decimal places.

**Redemption**

For amount-based redemption, the required units are rounded up to three decimal places to ensure that the requested redemption amount is covered.

**Exit Load**

- Equity: 1% up to and including day 365; zero from day 366.
- Debt: 0.25% up to and including day 30.
- Liquid: Uses the applicable graded exit-load schedule.

**Payout Period**

| Scheme Type | Payout |
|---|---|
| Equity | T+2 |
| Debt | T+1 |
| Liquid | T+1 |

**ELSS Lock-in**

ELSS investments have a three-year lock-in period. Units cannot be redeemed before their individual lock-in completion dates.

## 8. Supported Transaction Types

### 8.1 Purchase

The purchase module processes mutual fund investment orders.

It:
- Validates investor and scheme details.
- Determines the applicable NAV.
- Calculates stamp duty.
- Calculates investible amount.
- Determines the number of units allocated.
- Generates transaction confirmation.

### 8.2 Redemption

The redemption module processes investor withdrawal requests.

It:
- Validates the redemption request.
- Checks available units.
- Applies FIFO lot allocation.
- Calculates exit load.
- Calculates net redemption proceeds.
- Checks ELSS lock-in restrictions.
- Determines the applicable payout date.

### 8.3 Switch

The switch module transfers investments from one mutual fund scheme to another.

It:
- Processes the source scheme redemption.
- Applies applicable exit load.
- Calculates net proceeds.
- Processes the target scheme investment.
- Generates switch-out and switch-in confirmations.

### 8.4 Systematic Investment Plan (SIP)

The SIP module manages recurring mutual fund investments.

It supports:
- SIP registration.
- Monthly installment scheduling.
- Month-end date adjustment.
- Weekend and holiday adjustments.
- SIP pause and cancellation.
- Consecutive failure tracking.
- Automatic cancellation after three consecutive failures.

## 9. Project Directory Structure

The project is organized into modular directories.

```text
T001-PS-008/
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── command_processor.py
│   ├── models.py
│   ├── nav_engine.py
│   ├── scheme_engine.py
│   ├── purchase_engine.py
│   ├── redemption_engine.py
│   ├── sip_engine.py
│   └── ...
│
├── tests/
│   ├── test_holidays.py
│   ├── test_sip_engine.py
│   └── ...
│
├── data/
│   └── sample_pack/
│       ├── ...
│
├── docs/
│   ├── business_rules.md
│   ├── project_overview.md
│   ├── open_questions.md
│   ├── day10_integration_audit.md
│   └── final_project_report.md
│
├── requirements.txt
└── README.md
```

*Note: The directory listing is representative. Refer to the actual repository for the complete file structure.*

## 10. Installation and Setup

### Prerequisites

- Python installed.
- Git installed.
- PowerShell or another command-line terminal.
- Access to the project repository.

### Step 1: Clone the Repository

```powershell
git clone https://github.com/Chethu7353/T001-PS-008.git
```

### Step 2: Navigate to the Project

```powershell
cd T001-PS-008
```

### Step 3: Create a Virtual Environment

```powershell
python -m venv venv
```

### Step 4: Activate the Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 5: Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

## 11. Running the Application

Execute the following command from the project root directory:

```powershell
python -m src.main
```

The application processes the transaction commands and generates the required CSV output reports.

### Sample Execution Output

```text
Mutual Fund Order Processing System

Processed 92 commands: 86 accepted, 6 rejected.

Generated confirmations.csv (77 rows)
Generated sip_status.csv (17 rows)
Generated folio_statement.csv (88 rows)
```

The above represents the verified sample-pack execution baseline.

## 12. Output Files

The system generates three primary output reports.

### 12.1 confirmations.csv

Contains transaction confirmation records.

It records the results of processed transactions, including accepted and rejected transaction details according to the application's output schema.

### 12.2 sip_status.csv

Contains SIP-related processing information, including installment status and relevant SIP state information.

### 12.3 folio_statement.csv

Contains investor folio and investment-lot statement information.

These reports help track transaction results and investment records.

## 13. Testing and Validation

The project uses Pytest for automated testing.

### Run the Complete Test Suite

```powershell
python -m pytest -q
```

### Verified Integration Cases

The project includes eight official acceptance scenarios.

| Case | Description |
|---|---|
| EC-01 | Funds-realisation cutoff validation |
| EC-02 | Weekend and holiday NAV selection |
| EC-03 | SIP month-end scheduling |
| EC-04 | Equity exit-load day 365 and day 366 |
| EC-05 | Redemption unit rounding and insufficient balance |
| EC-06 | Switch target minimum waiver |
| EC-07 | ELSS lot-level lock-in |
| EC-08 | SIP consecutive failure reset |

### Previous Verified Test Results

The Day 10 integration audit reported:

```text
225 passed
0 failed
```

### Previous Sample-Pack Baseline

| Metric | Verified Result |
|---|---:|
| Commands Processed | 92 |
| Accepted | 86 |
| Rejected | 6 |
| Confirmations | 77 |
| SIP Status | 17 |
| Folio Statement | 88 |

**Note:** These are previously verified results. Run the test suite and application again after any subsequent code changes to confirm the final submission results.

## 14. Error Handling and Validation

The system includes validation for:

- Invalid transaction commands.
- Invalid scheme information.
- Invalid folio information.
- Invalid dates.
- Duplicate scheme and holiday records.
- Missing or invalid input data.
- Insufficient redemption units.
- ELSS lock-in restrictions.
- Invalid SIP registration and scheduling conditions.
- Financial input validation.

Invalid transactions are rejected rather than being processed as valid transactions.

## 15. Limitations

The current project is designed as a Python-based order-processing application using CSV input and output files.

The following capabilities are outside the currently verified implementation:

- Live integration with mutual fund or stock exchange APIs.
- Real-time market NAV feeds.
- Online investor account management.
- Payment gateway integration.
- Production database deployment.
- Web-based investor dashboard.
- Live notification services.
- Production authentication and authorization.

The application should not be considered a live mutual fund investment platform.

## 16. Future Scope

The project can be extended with the following enhancements:

1. Integrate a relational database such as PostgreSQL.
2. Develop a web dashboard using Django or Flask.
3. Integrate live NAV data sources.
4. Add investor authentication and authorization.
5. Implement REST APIs for transaction processing.
6. Introduce transaction history and portfolio tracking.
7. Add automated email and SMS notifications.
8. Develop reporting and financial analytics dashboards.
9. Implement database transaction management and audit logs.
10. Introduce production-grade monitoring and security controls.

## 17. Advantages

- Reduces manual transaction processing.
- Improves financial calculation consistency.
- Automates repetitive SIP operations.
- Applies predefined financial business rules.
- Supports multiple transaction types.
- Provides structured transaction reports.
- Uses modular architecture for maintainability.
- Includes automated unit and integration testing.

## 18. Conclusion

The Python-Based Mutual Fund Order Processing System demonstrates how software automation can simplify mutual fund transaction management.

By integrating NAV selection, scheme validation, purchase, redemption, switching, SIP management, holiday handling, FIFO allocation, exit-load calculations, and ELSS lock-in validation, the system provides a structured approach to processing mutual fund orders.

The project demonstrates practical applications of Python programming, modular software development, financial calculations, business-rule implementation, data validation, and automated testing.

**The main goal is to automate mutual fund operations while maintaining accuracy, reliability, and consistency with defined business rules.**

---

## Project Information

| Detail | Information |
|---|---|
| Project ID | T001-PS-008 |
| Project Name | Python-Based Mutual Fund Order Processing System |
| Domain | Financial Technology |
| Language | Python |
| Testing Framework | Pytest |
| Data Format | CSV |
| Repository | [GitHub Repository](https://github.com/Chethu7353/T001-PS-008) |

**Project Motto:**

*Automating Mutual Fund Operations with Accuracy, Reliability and Business-Rule Compliance.*
