# NSE options mechanics — verified facts, not memory

Every number here was checked against a source on the date shown. It exists because
carrying these from memory produced a live ticket claiming one option lot cost
₹11,94,540, and the impossible figure was reported to Aashish as a real constraint
instead of being recognised as broken input.

**Re-verify after any Budget or SEBI circular.** Rates and bands move; the code reads
them from `charges.py` and `test_option_math.py`, so update those together with this file.

Last verified: **31 July 2026**

---

## 1. Lot size and contract value

SEBI fixes lot size so that contract value stays inside a mandated band.

| Segment | Contract value band | Notes |
|---|---|---|
| **Single stock** F&O | **₹5–10 lakh** | reviewed roughly every 6 months |
| **Index** F&O (NIFTY, BANKNIFTY) | **₹15–20 lakh** | raised in the 2024 revision, first change in 9 years |

`lot = contract value ÷ share price`, so lots are revised when a stock moves enough to
push its contract outside the band.

Reference lots (Jan 2026): **NIFTY 65**, **BANKNIFTY 30**, NIFTY NEXT 50 25.

**Consequence for code:** a stock-band sanity check would wrongly flag every index name.
`lot_audit.py` excludes indices for exactly this reason, and derives its acceptable band
from the universe median rather than hard-coding today's numbers — the band itself moves.

## 2. What buying an option costs

An option **buyer pays the premium and nothing else** — no margin, unlike futures.

```
outlay for one lot = premium × lot size
```

At-the-money premium ≈ `0.4 × σ_daily × √(days) × spot`.

Worked through for a stock at 1.5% daily vol, 30 days out: premium ≈ 3% of spot, so one
lot of a ₹5–10 lakh contract costs roughly **₹20,000–40,000**.

| Name | Contract | Premium | One lot costs |
|---|---|---|---|
| COFORGE | ₹6.55L | ₹57 | ₹21,530 |
| NESTLEIND | ₹7.20L | ₹79 | ₹23,662 |
| SBIN | ₹6.15L | ₹27 | ₹20,211 |
| RELIANCE | ₹7.25L | ₹48 | ₹23,826 |

**Consequence:** on a ₹2 lakh account these are all 10–12%. Any report that a stock
option lot is unaffordable on such an account is a broken input, not a constraint.

## 3. Statutory charges (round trip)

| Charge | Rate | Side |
|---|---|---|
| **STT** | **0.15%** of premium | sell only — raised from 0.125% in Budget 2026, effective 1 Apr 2026 |
| STT on **exercise** | 0.125% of **intrinsic** value | why you square off instead of letting ITM options exercise |
| Exchange transaction | **₹35.03 per lakh** of premium (0.03503%) | both |
| SEBI turnover | 0.0001% | both |
| Stamp duty | 0.003% | buy only |
| GST | 18% on brokerage + exchange + SEBI (**not** on STT) | — |
| Brokerage | ₹20/order flat, or 0.03% of turnover if lower (Fyers) | both |

Worked example — buy 375 @ ₹73 (₹27,375), sell flat:

```
brokerage 16.42 · STT 41.06 · exchange 19.18 · stamp 0.82 · SEBI 0.05 · GST 6.42
TOTAL Rs 83.96  =  0.31% of premium
```

**Statutory charges are ~0.31%. The bid-ask spread is ~2%.** The spread is roughly six
times everything the government takes — so a cost model that skips charges is only
slightly wrong, but one that skips spread is badly wrong.

## 4. Liquidity

Single-stock option liquidity concentrates in the **near month**. Far-month contracts
quote, but not in size and not at a fair price. Modelling spread as flat across expiries
makes distant contracts look costless and pushes recommendations into contracts that
cannot be exited — `option_pnl.spread_for_dte()` widens it with distance for this reason.

Expiry week widens spreads again as market makers step back.

## 5. Choosing the expiry

Two forces pull opposite ways: a nearer option is cheaper and more levered, but decays
far faster. The question that resolves them is *how far must the stock move before the
option has paid for its own decay and spread*, and that has a minimum.

For a 2.5-hour hold:

```
DTE    PREMIUM   LEVERAGE   THETA   SPREAD   STOCK MUST MOVE
  1      0.72%      83.3x   22.5%     4.0%           0.32%
  3      1.25%      48.1x    6.9%     2.0%           0.19%
 10      2.28%      26.4x    2.0%     2.0%           0.15%   <- cheapest
 15      2.79%      21.5x    1.3%     2.0%           0.16%
 45      4.83%      12.4x    0.4%     4.0%           0.36%
```

The intuition that a short hold wants a near expiry is **wrong**: expiry week is the
worst choice, because decay per session overwhelms the extra leverage.

**Aashish's rule: minimum 15 days to expiry, else roll to the next month.** It costs
0.16% against the optimum 0.15% — nothing — and it can be applied from the expiry date
alone without re-running anything. `MIN_EXPIRY_DAYS` carries it and takes precedence
over the optimiser.

## 6. Sanity checks the code enforces

Three independent guards, because each catches what the others cannot:

1. **Premium** — a slightly-ITM call is worth its intrinsic plus a few percent of spot.
   A quote near the share price means a deep-ITM strike, a stale print, or another
   instrument. Rejected in favour of an estimate, and the rejection is stated.
2. **Cost vs contract value** — an outlay above 20% of the contract's own value means
   the **lot** is wrong rather than the premium. The premium check cannot see this.
3. **Lot vs the universe** — contract values cluster because SEBI makes them cluster;
   an outlier is a parsing error. Derived from the median, never hard-coded.

## Sources

- [Business Standard — SEBI's six F&O measures](https://www.business-standard.com/markets/news/sebi-announces-six-key-changes-to-curb-speculation-in-derivatives-trading-124100101316_1.html)
- [ICICI Direct — index derivatives lot size changes](https://www.icicidirect.com/futures-and-options/articles/latest-nse-bse-lot-size-changes-for-index-derivatives)
- [Flattrade — NSE derivative lot size revision](https://flattrade.in/kosh/nse-revises-derivatives/)
- [Zerodha — charges](https://zerodha.com/charges/)
- [NSE Clearing — Securities Transaction Tax](https://www.nseclearing.in/clearing-settlement/equity-derivatives/securities-transaction-tax)
- [Zerodha support — exchange transaction charges](https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/exchange-transaction-charges)
- [Zerodha — SEBI's new index derivatives rules](https://zerodha.com/z-connect/business-updates/sebis-new-rules-for-index-derivatives-heres-whats-changing)

*Not financial advice.*
