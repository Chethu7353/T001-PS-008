# Project Clarifications & Mentor Questions

This document consolidates domain questions, operational edge-case assumptions, and points for discussion with academic mentors and industry evaluators.

---

## 1. Statutory & Regulatory Calendar Questions
1. **Exchange vs Banking Calendar Divergence (BR-06):**
   - *Context:* Equity schemes follow exchange clearing holidays (NSE/BSE), whereas Liquid and Debt schemes follow RBI/RTGS banking settlement holidays.
   - *System Behavior:* The engine currently enforces a unified holiday calendar across all scheme categories loaded from `holidays.csv`.
   - *Discussion Point:* In multi-asset AMCs, should calendar engines support dual schedules (`equity_holidays.csv` vs `banking_holidays.csv`)?

2. **Mid-Cycle Holiday Declarations (BR-06):**
   - *Context:* When unscheduled public holidays (e.g. natural emergencies or state mourning) are declared, should in-flight orders or scheduled SIP installments be retrospectively shifted or re-evaluated?
   - *System Behavior:* The calendar loads at batch execution start; transactions scheduled prior to the declaration date evaluate against the calendar published at run time.

3. **Muhurat Trading Sessions (BR-01, BR-06):**
   - *Context:* Special 1-hour Diwali evening trading sessions fall outside standard 09:00–15:00 hours on a gazetted holiday.
   - *System Behavior:* The engine treats gazetted holidays strictly as non-business days.

---

## 2. Systematic Investment Plan (SIP) Operations
1. **In-Flight Debit Processing During Pause (BR-10):**
   - *Context:* If an installment debit result arrives on the same date a pause request is submitted for that month, does the debit execute or cancel?
   - *System Behavior:* Pause commands are executed sequentially in command order, suppressing debits scheduled within the active pause window.

2. **Annual Pause Quota Interpretation (BR-10):**
   - *Context:* SEBI rules permit pausing an active SIP once per year. Does this refer to a calendar year (Jan 1 to Dec 31) or a rolling 12-month window?
   - *System Behavior:* Enforces one pause per calendar year based on the year of the starting pause month.

3. **Debit Resumption After Consecutive Failures in a Paused State (BR-10):**
   - *Context:* If a debit outcome is submitted for an installment during a period later requested as paused, how should the failure counter behave?
   - *System Behavior:* Debits submitted during an active pause are ignored or marked invalid without corrupting counter state.

---

## 3. Scheme Master & Order Processing Rules
1. **Dynamic vs Static Scheme Master Registration (BR-04):**
   - *Context:* Can new funds (New Fund Offers - NFOs) be registered dynamically mid-stream during order execution?
   - *System Behavior:* Reference schemes are loaded and validated at startup; orders referencing unlisted scheme IDs fail fast with `REJECTED` confirmation rows.

2. **Zero-Holding Re-Entry Minimums (BR-07):**
   - *Context:* When an investor previously held lots in a scheme but redeemed 100% of units to 0.000, should a new purchase require the first-purchase threshold (₹5,000) or additional purchase threshold (₹1,000)?
   - *System Behavior:* Evaluates current active holdings; an investor holding 0.000 units is treated as a first-time investor requiring the ₹5,000 minimum.

3. **ELSS Partial Lock-In Rejection Code (BR-08 vs BR-11):**
   - *Context:* When a folio holds units in an ELSS fund, but all holdings are inside the 3-year lock-in, should the rejection rule code be `BR-08` (insufficient unlocked balance) or `BR-11` (statutory lock-in)?
   - *System Behavior:* Reports `BR-11` when holdings exist but are locked under ELSS.

4. **Multi-Currency & Offshore Feeder Schemes:**
   - *Context:* Do international funds support USD or non-INR currency denominations?
   - *System Behavior:* All monetary amounts strictly require INR representation with 2 decimal places (paise precision).
