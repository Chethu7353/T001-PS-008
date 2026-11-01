# Open Questions and Assumptions

## Mentor questions

- What exact fields and validations are required for Scheme and Investor?
- Can an order be received on a weekend or holiday, and which business date should be used?
- For Liquid schemes, does “previous business day's NAV” mean the immediately prior business date even when the order arrives before the cut-off on a business day?
- What timestamp timezone should the system use, and can orders arrive with timezone offsets?
- What should happen when funds are not realised, NAV data is missing, or a CSV row is invalid?
- What amount precision and unit rounding rule should apply?
- What are the exact exit-load periods/rates, ELSS lock-in period, and SIP calendar rules?
- What are the permitted order-status transitions and rejection reasons?
- Which official holiday calendar should be used?

## Current assumptions

- Timestamps are naive local datetimes; timezone handling is not implemented.
- The holiday CSV contains ISO dates (`YYYY-MM-DD`) and is illustrative.
- The sample NAV CSV is illustrative and is not used to look up values yet.
- “Next” and “previous” business day helpers return a strictly later or earlier date.
- Equity/Debt on a non-business timestamp map to the next business day; the listed ambiguity is recorded above.
