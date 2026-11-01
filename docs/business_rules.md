# Business Rule Register

| ID | Rule | Status |
|---|---|---|
| BR-01 | NAV cut-off: Equity and Debt use 3:00 PM. Before cut-off uses same business day's NAV; at/after cut-off uses the next business day's NAV. Liquid uses 1:30 PM; before cut-off uses the previous business day's NAV; at/after uses the next business day's NAV. | Implemented in Day 2 |
| BR-02 | Choose the applicable decision time using the later of order received and funds realised timestamps. | Implemented in Day 2 |
| BR-03 | A business day is Monday to Friday except dates listed in the holiday CSV. | Implemented for calendar helpers; confirm official calendar source with mentor |
| BR-04 | Scheme registration fields and validation rules. | Pending mentor clarification |
| BR-05 | NAV file validation, duplicate handling, and missing NAV behavior. | Pending mentor clarification |
| BR-06 | Holiday calendar update and invalid-date handling. | Pending mentor clarification |
| BR-07 | Purchase order eligibility, amount rules, and unit rounding. | Pending mentor clarification |
| BR-08 | Redemption eligibility, available units, and payout rules. | Pending mentor clarification |
| BR-09 | Scheme switch processing and related NAV dates. | Pending mentor clarification |
| BR-10 | SIP schedule, missed installment, and processing rules. | Pending mentor clarification |
| BR-11 | FIFO lot selection, exit load, ELSS lock-in, and investor confirmations. | Pending mentor clarification |

For weekend or holiday timestamps, Day 2 currently advances to the next business day for Equity/Debt and Liquid after-cutoff orders. Liquid before-cutoff on a non-business date also advances to the next business day. This is an implementation assumption because the assignment does not state those cases; confirm with the mentor.
