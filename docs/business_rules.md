# Business Rule Register

| ID | Rule | Status |
|---|---|---|
| BR-01 | NAV cut-off: Equity and Debt use 3:00 PM. Before cut-off uses same business day's NAV; at/after cut-off uses the next business day's NAV. Liquid uses 1:30 PM; before cut-off uses the previous business day's NAV; at/after uses the next business day's NAV. | Implemented in Day 2 |
| BR-02 | Choose the applicable decision time using the later of order received and funds realised timestamps. | Implemented in Day 2 |
| BR-03 | A business day is Monday to Friday except dates listed in the holiday CSV. | Implemented for calendar helpers; confirm official calendar source with mentor |
| BR-04 | Scheme registration fields and validation rules. | Pending mentor clarification |
| BR-05 | NAV file validation, duplicate handling, and missing NAV behavior. Records must have valid uppercase scheme identifiers, strict YYYY-MM-DD dates, strictly positive finite decimal values with exactly 4 decimal places, and unique (scheme_id, nav_date) pairs. Missing NAV at order execution raises a lookup error. | Implemented in Day 6 (with documented open questions) |
| BR-06 | Holiday calendar update and invalid-date handling. | Pending mentor clarification |
| BR-07 | Purchase order eligibility, minimum amount thresholds, stamp duty, unit rounding down, and lot creation. | Implemented & Verified in Day 3 (with documented open questions) |
| BR-08 | Redemption eligibility, available units, ceiling rounding, FIFO deductions, and payout rules. | Implemented & Verified in Day 4 (with documented open questions) |
| BR-09 | Scheme switch processing and related NAV dates. | Pending mentor clarification |
| BR-10 | SIP schedule, missed installment, and processing rules. | Pending mentor clarification |
| BR-11 | FIFO lot selection, exit load, ELSS lock-in, and investor confirmations. | Implemented & Verified in Day 5 (with documented open questions) |

For weekend or holiday timestamps, Day 2 currently advances to the next business day for Equity/Debt and Liquid after-cutoff orders. Liquid before-cutoff on a non-business date also advances to the next business day. This is an implementation assumption because the assignment does not state those cases; confirm with the mentor.

## BR-05: NAV Validation and Data Integrity Rules

### Confirmed Implementation Behavior
1. **Scheme Identifier Validation**: Every NAV row must have a non-empty `scheme_id` in uppercase without internal whitespace (e.g. `SCH-01`, `SCH-TEST`).
2. **Date Format & Calendar Validity**: The `nav_date` must strictly follow `YYYY-MM-DD` and represent a real calendar day (e.g. rejects `2026-02-30`, `23-01-2026`, and `20260123`).
3. **Decimal Precision**: NAV values must be plain decimal numbers with exactly four decimal places (e.g. `12.3456`, `10.0000`), adhering to the official data pack specification. Values with fewer or more decimal places are rejected.
4. **Numeric Domain Constraints**: NAV values must be strictly greater than zero (`nav > 0`). Zero (`0`, `0.0000`) and negative values (`-1.2500`) are rejected.
5. **Finite Number Check**: Non-finite values such as `NaN`, `sNaN`, `Infinity`, and `-Infinity` are rejected.
6. **Uniqueness & Duplicate Detection**: The combination of `(scheme_id, nav_date)` forms a unique primary key. Any duplicate occurrence within the file triggers an immediate error.
7. **Missing Value Rejection**: Rows missing `scheme_id`, `nav_date`, or the NAV value itself are rejected with specific error messages.
8. **Missing NAV Lookup**: Querying a NAV for a scheme on a date that is not published raises a `ValueError("NAV not found for scheme ... on ...")`.

### Unresolved Specification Questions (Mentor Clarifications Needed)
1. **Scope of Duplicate File Rejection**: Does a single duplicate `(scheme_id, nav_date)` record invalidate the entire NAV file and abort order processing upfront (current fail-fast behavior), or should the engine use a conflict resolution policy (e.g., retain first record, update to latest record, or skip the duplicate with a warning)?
2. **Impact of Invalid NAV Records on Unrelated Orders**: If a NAV record for `SCH-01` contains an error (e.g. negative NAV), should the entire system halt before processing any command (current fail-fast behavior), or should only transactions involving `SCH-01` on that specific date be impacted while unrelated orders (e.g. for `SCH-02`) proceed?
3. **Missing NAV Handling at Transaction Level**: When an order requires a NAV that is missing from the NAV file, should the transaction be marked as `REJECTED` in `confirmations.csv` (with a specific rule code), deferred until NAV publication, or fail the entire processing batch?

## BR-07: Purchase Processing Rules

### Confirmed Implementation Behavior
1. **First-Time vs Additional Purchase Minimums**:
   - First purchase in a scheme for a given folio requires a minimum investment of ₹5,000.00 (`min_first_purchase`).
   - Subsequent/additional purchases require a minimum of ₹1,000.00 (`min_additional`).
   - A purchase is identified as "first purchase" if the folio currently holds 0 units in that scheme (`not lot_manager.has_holding(folio_id, scheme_id)`).
2. **Stamp Duty Calculation**:
   - Regulatory stamp duty is levied at 0.005% (`0.00005`) of the gross investment amount.
   - Stamp duty is quantized to the nearest paisa (2 decimal places) using standard financial rounding (`ROUND_HALF_UP`).
3. **Investible Amount**:
   - The net investible amount allocated for acquiring units is strictly: `investible_amount = amount - stamp_duty`.
4. **Unit Allocation and Strict Round-Down**:
   - Purchase units are calculated as: `units = investible_amount / nav`.
   - Units are strictly rounded **DOWN** (`ROUND_DOWN`) to three decimal places (`0.001`). Units are never rounded up, ensuring the AMC never issues unbacked fractions of a unit.
5. **Lot Creation and Portfolio State**:
   - Each successful purchase creates an `InvestmentLot` with:
     - `lot_id`: Assigned directly from the `order_id` (e.g., `ORD-0001`).
     - `purchase_date` / `allotment_date`: Applicable NAV date determined via BR-01 and BR-02.
     - `units`: Allotted units to 3 decimal places.
     - `purchase_nav`: Applicable NAV to 4 decimal places.
   - The lot is immediately appended to the folio's holdings in FIFO order.
6. **Rejection Behavior**:
   - Purchases below the mandatory threshold (e.g. ₹4,999.99 for a first purchase) are recorded in `confirmations.csv` with `decision = REJECTED` and `rule_ids = BR-07`. All financial, unit, and date fields are left empty.

### Unresolved Specification Questions (Mentor Clarifications Needed)
1. **Zero-Holding Re-Entry Status**: If an investor previously held lots in a scheme but completely redeemed all units to 0.000, should a new purchase be treated as a "first-time purchase" (requiring ₹5,000) or an "additional purchase" (requiring ₹1,000)? (Current implementation checks current non-zero holdings, requiring ₹5,000).
2. **Pre-Deduction Fee Applicability**: Does stamp duty apply to SIP instalments and switch-in transactions? (Current implementation applies 0.005% stamp duty uniformly across lump-sum purchases, SIP purchases, and switch-in purchases as per SEBI regulations).
3. **Fractional Rupee Precision in Order Input**: If an input amount contains fractions beyond paisa (e.g. ₹5,000.005), should the order be rejected upfront for invalid currency formatting or quantized?

## BR-08: Redemption Processing Rules

### Confirmed Implementation Behavior
1. **Redemption Modes**:
   - `ALL`: Redeems 100% of available unlocked units in the folio for that scheme. Permitted even if the total holding value is below ₹1,000.
   - `UNITS`: Investor specifies units up to 3 decimal places. Requested units must not exceed available unlocked units. If requested units are less than the total available units, the gross value must be at least ₹1,000.00 (`min_redemption`).
   - `AMOUNT`: Investor specifies redemption amount in rupees. Converted to units using ceiling rounding: `units = ceil_3(amount / nav)`. If required units exceed available unlocked units, the order is rejected.
2. **Amount-to-Units Ceiling Rounding (ROUND_CEILING)**:
   - When redeeming by amount, units are rounded **UP** (`ROUND_CEILING`) to 3 decimal places (`0.001`). This ensures that the gross proceeds meet or exceed the investor's requested redemption cash amount.
   - **EC-05 Insufficient Units Defense**: If `units_needed` exceeds `available_units` even by `0.001` (e.g. `708.740` required vs `708.739` available), the order is immediately rejected with `rule_ids = BR-08`.
3. **Partial vs Full Redemption Minimums**:
   - Partial redemptions (leaving positive units remaining) must have a gross redemption value of at least ₹1,000.00 (`min_redemption`).
   - Full redemptions (`mode == "ALL"` or redeeming all units) are exempted from the ₹1,000 minimum threshold.
4. **FIFO Lot Depletion and Exit Loads**:
   - Units are deducted in First-In, First-Out (FIFO) order sorted by `(allotment_date, lot_id)`.
   - Exit load is calculated individually per lot based on holding days: `days_held = (nav_date - allotment_date).days`.
   - **EC-04 Exit Load Holding Days Boundary**:
     - For Equity funds (`[0, 365]` days band at 1.0000%):
       - Day 365: exactly on the 365th day $\implies$ 1.00% exit load is deducted.
       - Day 366: on the 366th day $\implies$ nil (0.00%) exit load.
   - Total exit load is the sum of exit loads across all depleted lots, rounded to the nearest paisa (`ROUND_HALF_UP`).
5. **Net Payout Calculation**:
   - `gross_amount = (units_to_redeem * nav).quantize(0.01, ROUND_HALF_UP)`
   - `net_amount = gross_amount - total_exit_load`
6. **Payout Date Schedule**:
   - Equity schemes: $T + 2$ business days.
   - Debt & Liquid schemes: $T + 1$ business day.
   - Advances only across official market business days (skipping weekends and dates in `holidays.csv`).
7. **Rejection Behavior**:
   - Orders failing unit availability or minimum value are recorded in `confirmations.csv` with `decision = REJECTED` and `rule_ids = BR-08` (or `BR-11` if locked under ELSS). Numerical and payout date fields are empty.

### Unresolved Specification Questions (Mentor Clarifications Needed)
1. **ELSS Units Partial Lock-in Rejection Code**: When a folio holds units in an ELSS scheme, but all of them are within the 3-year lock-in period, should the rejection rule code be `BR-08` (insufficient units) or `BR-11` (ELSS lock-in)? (Current implementation reports `BR-11` when holdings exist but are locked).
2. **Weekend/Holiday Payout Initiation**: If an order arrives on a weekend/holiday, does the $T+1$ or $T+2$ counter begin from the transaction/nav date or from the next business day? (Current implementation computes $T+n$ business days from the applicable NAV date).

## BR-11: FIFO, Exit Load, and ELSS Lock-in Rules

### Confirmed Implementation Behavior
1. **FIFO Lot Ordering**:
   - Lots within each `(folio_id, scheme_id)` holding are strictly ordered by `(allotment_date, lot_id)`.
   - When a redemption or switch-out occurs, units are depleted starting from the earliest available lot.
   - Depleted lots whose units reach `0.000` are retained in history but omitted from active holdings statements.
2. **Transactional State Integrity**:
   - `LotManager.add_lot()` strictly validates that `units` and `purchase_nav` are finite positive decimals, and `allotment_date` is a valid date.
   - `deplete_units_fifo` executes pre-flight checks before altering state: if available unlocked units are insufficient or if the redemption date is earlier than an allotment date, execution halts with a `ValueError` without mutating any lot in the portfolio.
3. **Exit Load Schedule Evaluation**:
   - Exit load is determined on a per-lot basis using holding days: `days_held = (nav_date - allotment_date).days`.
   - Schedules are loaded directly from `exit_loads.csv` without hardcoding:
     - **Equity**: `[0, 365]` days $\implies$ 1.0000%; day 366+ $\implies$ nil (0.00%).
     - **Debt**: `[0, 30]` days $\implies$ 0.2500%; day 31+ $\implies$ nil (0.00%).
     - **Liquid**: Graded scale from day 1 (0.0070%) down to day 6 (0.0045%); day 7+ $\implies$ nil (0.00%).
   - The gross redemption amount per lot slice is quantized to paise (`PAISE = Decimal("0.01")`, `ROUND_HALF_UP`), and the resulting exit load is quantized to paise.
4. **ELSS Three-Year Statutory Lock-in (EC-07)**:
   - Units invested in an ELSS scheme (`elss = True`) are legally locked for exactly three calendar years from their allotment date.
   - Lock-in date formula: `allotment_date.replace(year=allotment_date.year + 3)`. For leap-day allotments (`Feb 29`), the lock-in expires on `Feb 28` of the third year.
   - A lot is locked if `as_of_date < lock_in_date`. On the exact 3-year anniversary (`as_of_date == lock_in_date`), the lot becomes unlocked and eligible for redemption.
   - **Partial Redemptions & REDEEM ALL**: Redemptions (including `REDEEM ALL`) only consume unlocked lots. Locked lots remain untouched in the folio statement.
   - **All-Locked Rejection**: If all holdings in an ELSS scheme are locked, redemption is rejected with `rule_ids = BR-11`.

### Unresolved Specification Questions (Mentor Clarifications Needed)
1. **ELSS Lot Allotment Tie-Breaking**: If an investor acquires multiple ELSS lots on the same calendar day (e.g. regular purchase and SIP debit), does sorting by `lot_id` provide sufficient determinism for audit and taxation reporting? (Current implementation uses `(allotment_date, lot_id)`).
2. **Switch-Out with Mixed ELSS Holdings**: In a switch transaction where source ELSS units are partially locked, should the switch proceed up to the unlocked limit or reject the entire switch command? (Current implementation restricts redemptions and switches to available unlocked units).
