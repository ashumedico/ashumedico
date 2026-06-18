# Credit Card Statement Tracker — Aashish Rajput
_Last updated: 2026-06-18 · Source: Gmail audit_

## Card Portfolio (9 Cards)

| # | Bank | Card | Last 4 | Statement Gen | Due Date | Alert Source |
|---|------|------|--------|--------------|----------|-------------|
| 1 | **ICICI Bank** | — | 8007 | **~11th** | **~30th same month** | CRED / protect@cred.club |
| 2 | **HDFC Bank** | — | 5379 | **~15th** | **~5th-6th next month** | CRED / protect@cred.club |
| 3 | **Standard Chartered** | — | — | **~18th** | *check statement* | alerts.in@sc.com |
| 4 | **HSBC** | Platinum | 9873 | **~19th-20th** | **~6th next month** | creditcardstatement@mail.hsbc.co.in |
| 5 | **YES Bank** | ACE | 9377 | **~20th** | **~8th next month** | estatement@yes.bank.in |
| 6 | **YES Bank** | Rupay | 2154 | **~20th** | **~8th next month** | estatement@yes.bank.in |
| 7 | **RBL Bank** | Paisabazaar Duet | 2579 | **~21st-22nd** | **~11th next month** | statements@rbl.bank.in |
| 8 | **SBI Card** | PULSE | 4290 | **~24th** | **~15th next month** | Statements@sbicard.com |
| 9 | **Axis Bank** | — | 1173 | **~9th** | **~30th same month** | CRED / protect@cred.club |

## Monthly Payment Calendar (Day-of-Month)

```
DAY  ACTION
─────────────────────────────────────
 9   Axis Bank 1173 statement generated
11   ICICI Bank 8007 statement generated
     RBL Bank 2579 due date
15   HDFC Bank 5379 statement generated
     SBI Card 4290 due date
18   Standard Chartered statement generated
19   HSBC 9873 statement generated
20   YES Bank ACE 9377 statement generated
     YES Bank Rupay 2154 statement generated
22   RBL Bank 2579 statement generated
24   SBI Card 4290 statement generated
30   ICICI Bank 8007 due date
     Axis Bank 1173 due date

NEXT MONTH:
 5   HDFC Bank 5379 due date
 6   HSBC 9873 due date
 8   YES Bank ACE 9377 due date
     YES Bank Rupay 2154 due date
```

## Latest Statement Snapshot (June 2026)

| Card | Total Due | Min Due | Due Date | Status |
|------|-----------|---------|----------|--------|
| HDFC 5379 | ₹20,002 | ₹7,424 | Jul 6, 2026 | UNPAID |
| ICICI 8007 | ₹24,531 | ₹1,800 | Jun 30, 2026 | UNPAID |
| RBL 2579 | ₹25,059 | ₹1,253 | Jun 11, 2026 | CHECK |
| SBI 4290 | — | — | — | Awaiting Jun statement |
| Axis 1173 | ₹8,403 | ₹169 | May 30 (last) | CHECK |
| YES 2154 | — | — | — | Awaiting Jun statement |
| YES 9377 | — | — | — | Awaiting Jun statement |
| HSBC 9873 | — | — | — | Awaiting Jun statement |
| StanChart | — | — | — | Awaiting Jun statement |

## Recent Spending Trend (from CRED/Bank Statements)

| Month | HDFC 5379 | ICICI 8007 | RBL 2579 | YES 2154 | YES 9377 | HSBC 9873 | Total Visible |
|-------|-----------|------------|----------|----------|----------|-----------|---------------|
| Jan 2026 | ₹2,540 | ₹7,381 | ₹70,419 | ₹51,644 | — | — | ₹1,31,984+ |
| Feb 2026 | ₹1,520 | — | ₹33,078 | ₹32,822 | — | — | ₹67,420+ |
| Mar 2026 | — | — | ₹2,263 | ₹51,206 | ₹1,618 | ₹7,073 | ₹62,160+ |
| Apr 2026 | — | — | ₹4,326 | — | — | — | — |
| May 2026 | ₹9,593 | ₹5,880 | ₹25,059 | — | — | — | ₹40,532+ |
| Jun 2026 | ₹20,002 | ₹24,531 | — | — | — | — | ₹44,533+ |

## Gmail Search Queries (for manual checks)

```
# All credit card statements
subject:(credit card statement) OR subject:(card statement) OR subject:(statement generated) OR subject:(smart statement)

# Per bank
from:protect@cred.club subject:statement
from:Statements@sbicard.com
from:statements@rbl.bank.in
from:estatement@yes.bank.in
from:creditcardstatement@mail.hsbc.co.in
from:alerts.in@sc.com subject:statement
```

## Alerts

- **9 active credit cards** is a lot of surface area. Consider consolidating.
- **RBL 2579 swings wildly** (₹70K → ₹2K → ₹25K) — check for recurring charges or EMIs.
- **YES 2154 is consistently high** (₹32K–₹52K range) — likely a primary spending card.
- **HDFC 5379 jumped** from ₹1.5K–₹9.6K range to ₹20K in June — flag if unexpected.
