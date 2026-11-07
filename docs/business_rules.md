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
| BR-08 | Redemption eligibility, available units, and payout rules. | Pending mentor clarification |
| BR-09 | Scheme switch processing and related NAV dates. | Pending mentor clarification |
| BR-10 | SIP schedule, missed installment, and processing rules. | Pending mentor clarification |
| BR-11 | FIFO lot selection, exit load, ELSS lock-in, and investor confirmations. | Pending mentor clarification |

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
