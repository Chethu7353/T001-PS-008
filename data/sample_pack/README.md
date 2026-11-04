# PS-008 – Mutual Fund Order Processing with NAV Cut-off, SIP and Exit Load — Sample Data Pack

Prepared by 10 SECONDS for Team T001.

## Files

| File | What it holds | Row count |
|---|---|---|
| `schemes.csv` | 6 schemes with type, cut-off and minimum amounts | 6 data rows |
| `exit_loads.csv` | Exit-load schedule by scheme type (days since lot allotment) | 8 data rows |
| `navs.csv` | 61 business days of NAV for EQUITY/DEBT schemes (2026-01-01 .. 2026-03-31); every calendar day for the LIQUID scheme from 2025-12-31 | 396 data rows |
| `holidays.csv` | Market/bank holidays Dec 2025 – Apr 2026 | 6 data rows |
| `folios.csv` | 10 investor folios | 10 data rows |
| `lots_opening.csv` | Unit lots held on 2026-01-01 (FIFO order = allotment_date) | 30 data rows |
| `existing_sips.csv` | SIPs registered before the period | 2 data rows |
| `sip_history.csv` | Instalment outcomes of existing SIPs before 2026-01-01 | 3 data rows |
| `commands.txt` | ~70 orders (purchase, redemption, switch, 4 SIP registrations), SIP debit results, a pause and folio print requests | 92 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and only occurs in columns whose notes say so.

### `schemes.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| scheme_id | string | SCH-nn | — | — |
| scheme_name | string | — | — | — |
| scheme_type | enum | — | EQUITY, DEBT, LIQUID | — |
| elss | bool | — | — | true = 3-year lock-in per lot |
| cutoff_time | time | HH:MM:SS | 15:00:00, 13:30:00 | at or after cut-off = late |
| min_first_purchase | decimal | Rs | — | — |
| min_additional | decimal | Rs | — | — |
| min_sip | decimal | Rs | — | — |
| min_redemption | decimal | Rs | — | or all units |

### `exit_loads.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| scheme_type | enum | — | EQUITY, DEBT, LIQUID | — |
| from_day | int | days | — | days held = NAV date - allotment date |
| to_day | int | days | — | inclusive |
| load_pct | decimal | % | — | of redemption value; outside every band = nil |

### `navs.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| nav_date | date | — | — | — |
| scheme_id | string | — | schemes.csv | — |
| nav | decimal | Rs per unit, 4 dp | — | — |

### `holidays.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| date | date | — | — | weekends are also non-business days |
| holiday_name | string | — | — | — |

### `folios.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| folio_id | string | FOL-nnn | — | — |
| investor_name | string | — | — | — |
| pan | string | AAAAA9999A | — | — |
| mobile | string | 10 digits | — | — |
| bank_account | string | — | — | payout account |
| ifsc | string | — | — | — |
| opened_date | date | — | — | — |

### `lots_opening.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| lot_id | string | LOT-nnn | — | — |
| folio_id | string | — | folios.csv | — |
| scheme_id | string | — | schemes.csv | — |
| allotment_date | date | — | — | NAV date of the original allotment |
| units | decimal | units, 3 dp | — | units remaining |
| purchase_nav | decimal | Rs, 4 dp | — | — |

### `existing_sips.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| sip_id | string | SIP-Enn | — | — |
| folio_id | string | — | folios.csv | — |
| scheme_id | string | — | schemes.csv | — |
| amount | decimal | Rs | — | — |
| sip_day | int | day of month | 1-31 | — |
| registered_date | date | — | — | — |
| status | enum | — | ACTIVE | — |
| consecutive_failures | int | — | — | as of 2026-01-01 |

### `sip_history.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| sip_id | string | — | existing_sips.csv | — |
| instalment_no | int | — | — | — |
| instalment_date | date | — | — | — |
| result | enum | — | SUCCESS, FAILED | — |
| reason | string | — | — | empty for SUCCESS |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `PURCHASE` | `order_id|order_ts|folio_id|scheme_id|amount|funds_realised_ts` | Lump-sum purchase |
| `REDEEM` | `order_id|order_ts|folio_id|scheme_id|mode|value` | mode AMOUNT (value = Rs), UNITS (value = units, 3 dp) or ALL (value empty) |
| `SWITCH` | `order_id|order_ts|folio_id|from_scheme_id|to_scheme_id|mode|value` | Redemption in source + purchase in target; mode as for REDEEM |
| `SIP_REGISTER` | `sip_id|registered_ts|folio_id|scheme_id|amount|sip_day` | New SIP; your engine derives the instalment dates |
| `SIP_DEBIT_RESULT` | `sip_id|instalment_no|result|funds_realised_ts|reason` | Bank debit outcome for an instalment (SUCCESS / FAILED); a SUCCESS creates the SIP purchase |
| `SIP_PAUSE` | `sip_id|request_ts|from_month|months` | Pause instalments starting from_month (YYYY-MM) for `months` months |
| `PRINT_FOLIO` | `folio_id|as_of_date` | Print lot-wise holdings as at end of that date |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Order at 14:59:59 with funds realised at 15:00:00**
  - FOL-001 SCH-01: PURCHASE received 2026-01-19 14:59:59 but funds realised 15:00:00 -> realisation governs, NAV of next business day 2026-01-20 — `commands.txt line 12`
- **EC-02 Friday 16:00 order before a Monday holiday**
  - FOL-002 SCH-02: PURCHASE Friday 2026-01-23 16:00:00 (after cut-off); Monday 2026-01-26 is Republic Day -> NAV date Tuesday 2026-01-27 — `commands.txt line 20; holidays.csv 2026-01-26`
- **EC-03 SIP registered on 31st in a month followed by February**
  - SIP-N01 registered Saturday 2026-01-31 with sip_day 31: February has no 31st -> last day 2026-02-28, a Saturday -> instalment 1 on Monday 2026-03-02; instalment 2 on 2026-03-31 — `commands.txt line 28, debit results line 63, line 84`
- **EC-04 Redemption on day 365 exactly vs day 366 for equity lot**
  - FOL-004 SCH-01: single lot allotted 2025-02-10, REDEEM ALL at 2026-02-10 11:30 (NAV date 2026-02-10) = day 365 -> 1% exit load — `lots_opening.csv LOT-008 (row 8); commands.txt line 39`
  - FOL-005 SCH-01: single lot allotted 2025-02-10, REDEEM ALL at 2026-02-11 11:30 (NAV date 2026-02-11) = day 366 -> nil load — `lots_opening.csv LOT-011 (row 11); commands.txt line 40`
- **EC-05 Redemption by amount requiring units beyond holding by 0.001**
  - FOL-006 SCH-04 holds 708.739 units; REDEEM AMOUNT Rs 23822.93 at NAV 33.6131 (2026-02-16) needs ceil3(23822.93/33.6131) = 708.740 units = holding + 0.001 — `lots_opening.csv LOT-017 (row 17); commands.txt line 47`
- **EC-06 Switch where source exit load makes target amount fall below Rs 1,000**
  - FOL-007: SWITCH Rs 1,005.00 from SCH-02 (lot allotted 2025-09-15, inside 365 days -> 1% load) into SCH-05; proceeds after load fall below Rs 1,000 but the target minimum is waived for switches — `lots_opening.csv LOT-019 (row 19); commands.txt line 15`
- **EC-07 ELSS lot maturing on the redemption date itself**
  - FOL-008 SCH-03 (ELSS): lot allotted 2023-02-16 completes 3 years on 2026-02-16, the redemption date -> unlocked; the 2024-05-10 lot is still locked so REDEEM ALL redeems only the first lot — `lots_opening.csv LOT-021 (row 21), LOT-022 (row 22); commands.txt line 46`
- **EC-08 SIP with 2 failures, 1 success, 2 failures (counter reset check)**
  - SIP-E01: instalments 1-2 FAILED (history), 3 SUCCESS on 2026-01-12 (10 Jan is a Saturday), 4-5 FAILED -> counter reset by the success, only 2 consecutive failures, SIP stays ACTIVE — `existing_sips.csv SIP-E01 (row 1); sip_history.csv rows 1, 2; commands.txt line 7, lines 38, 72`
- **Extra traps (not in the brief, but realistic):**
  - SIP-E02: third consecutive failure on 2026-02-05 -> SIP auto-CANCELLED (no March instalment expected) — `commands.txt lines 3, 33`
  - SIP-N02 registered 2026-01-29 with sip_day 5: 2026-02-05 is exactly 7 days later -> allowed as first instalment; amount Rs 500 = SIP minimum (LIQUID, realised 09:55 before 13:30 -> previous calendar day NAV) — `commands.txt line 25`
  - SIP-N03 instalment Rs 499.00 is below the Rs 500 SIP minimum -> registration REJECTED — `commands.txt line 8`
  - SIP-N04: SIP_PAUSE for 4 months exceeds the 3-month maximum -> REJECTED, so the February instalment (2026-02-20) still runs; 2026-03-20 is a holiday (Id-ul-Fitr) so the March instalment moves to Monday 2026-03-23 — `commands.txt line 31, lines 52, 80`
  - FOL-006 SCH-06 (LIQUID, no prior holding): first purchase Rs 4,999.99 REJECTED (< Rs 5,000); Rs 5,000.00 at 13:29:59 accepted with previous calendar day (2026-02-23) NAV; additional Rs 1,000 at 13:30:00 next day is at/after the LIQUID cut-off -> NAV of 2026-02-25 (not the previous day) — `commands.txt line 58, line 59, line 61`
  - FOL-007 SCH-02 EQUITY redemption on 2026-03-03: T+2 business days skips Holi (2026-03-04) -> payout 2026-03-06 — `commands.txt line 66`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `confirmations.csv`

One row per order (PURCHASE, REDEEM, SWITCH, SIP instalment purchase), in file order; a SWITCH produces two rows (OUT then IN) with the same order_id.

Columns, in order: `order_id`, `folio_id`, `scheme_id`, `txn_type`, `decision`, `rule_ids`, `nav_date`, `nav`, `gross_amount`, `stamp_duty`, `units`, `exit_load`, `net_amount`, `payout_date`

### `sip_status.csv`

One row per SIP instalment due in the period and per SIP_REGISTER/SIP_PAUSE decision.

Columns, in order: `sip_id`, `event`, `instalment_no`, `scheduled_date`, `result`, `order_id`, `consecutive_failures`, `sip_status`, `rule_ids`

### `folio_statement.csv`

One row per remaining lot per PRINT_FOLIO.

Columns, in order: `folio_id`, `as_of_date`, `scheme_id`, `lot_id`, `allotment_date`, `units`, `lock_in_until`

Binding choices: `txn_type` one of PURCHASE, REDEMPTION, SWITCH_OUT, SWITCH_IN, SIP_PURCHASE; `decision` ACCEPTED or REJECTED (empty numeric columns when rejected); units to 3 decimals, NAV to 4, money to 2; `payout_date` empty for purchases; new lots created in the period get lot_id `<order_id>`; `lock_in_until` empty for non-ELSS lots.
