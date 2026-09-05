---
name: option-selection
description: What makes an option worth BUYING, as opposed to what makes a stock worth trading. Use whenever choosing a strike or expiry, judging a premium, sizing an option position, translating a stock-level backtest into option P&L, or asking whether a signal is tradeable as a long option. The gates a professional buyer screens on — IV against realised, measured spread, liquidity, theta in rupees, delta, expiry fit, event risk.
---

# OPTION SELECTION — the contract is the trade

Every skill before this one is about not being wrong. This one is about the thing that
decides whether the system makes money: **a correct read on a name, expressed through the
wrong contract, loses.** That is not a rounding error. Leverage, spread and theta sit
between the stock and the option, and on a short hold they are larger than the edge.

The failure this exists to prevent, which shipped and ran for months: **selection was
entirely stock-level.** Trend, VWAP, RVOL, squeeze, expansion — all of it about the
underlying. The option was chosen *afterwards* (ATM, current expiry), priced, and never
judged. Implied volatility appeared nowhere in the codebase at all. The bid-ask was a
constant, `0.02`, applied identically to a ₹12 premium on a thin name and a ₹300 premium
on RELIANCE. Delta was `0.50`, typed in.

---

## THE SEVEN GATES, in the order they kill trades

### 1. IMPLIED vs REALISED — are you paying for a bigger move than you are forecasting?

The first thing a professional buyer screens. Buying a 1.5% move when implied vol sits at
twice what the name has actually been delivering means the direction can be **right** and
the trade still loses, because the premium already contained the move.

- Solve IV from the market price (bisection, not Newton — vega collapses on wings).
- Compare to the stock's own realised vol over the same horizon.
- `IV/RV ≥ 1.5` is EXPENSIVE. `< 0.85` is CHEAP and is a buyer's actual edge.
- **IV RANK** (where today's IV sits in its own past year) is the professional standard
  and requires a year of recorded IV. Do not fake a percentile from three days. Record
  the series and let the rank become available; report IV/RV until it does.
- No solvable IV → `None` and "unknown". Never a default. A fabricated vol lands in the
  exact column the trade is supposed to be judged by.

### 2. SPREAD — measured, never assumed

Paid twice, on the **premium**, not the notional. A 4% round trip on a single-stock strike
eats a whole day's expected move before the thesis has a chance.

- Take bid and ask off the chain. `(ask − bid) / mid`.
- Cap it (5% is a reasonable ceiling) and **block** past that.
- If the chain gives no bid/ask, fall back to an estimate, **label it as an estimate, and
  never block on it.** Refusing a trade on an invented number is worse than not checking.

### 3. LIQUIDITY — can you get out?

- Open interest at the strike (≥ ~500–1000 contracts).
- **Traded volume today** at that strike. OI without volume is a position people are
  stuck in, not a market you can exit. This is the gate everyone forgets.

### 4. THETA — in rupees, per day, including the weekend

"theta −0.70" means nothing at 9:20am. **"This gives up ₹875 a day if the stock does
nothing, and ₹2,625 across a weekend"** decides whether a two-day hold is worth starting.

- Decay is charged on calendar days. Friday-to-Monday is three days, not one — that is
  the leak a buyer feels and cannot explain.
- Theta accelerates into expiry: ~4x the daily burn at 3 DTE versus 60 DTE. That is what
  a minimum-expiry rule is for.

### 5. DELTA and the strike — computed, not assumed

Delta is both the participation rate and the rough probability of finishing in the money.
Compute it. A hardcoded 0.50 is right only for the strike it was typed for.

### 6. EVENT RISK — the gate that is about neither the stock nor the contract

Implied vol **rises into a results date** because the market knows a jump is coming. Buy
then and the premium already contains the move; the result prints, the uncertainty
resolves, and IV collapses — often 30–50% in one session. The stock can do exactly what
was predicted and the option still loses. It is the most reliable way to be right about a
company and wrong about the trade.

Black out **both sides**: a couple of days before (paying for the jump) and at least a
day after (holding through the crush).

**The answer has three states, not two.** A boolean collapses "no event near this name"
and "no calendar has ever been loaded" into the same `False` — and `False` renders as a
green tick, possibly one day before results. So: `clear` / `blackout` / **`unchecked`**,
and `unchecked` is printed as loudly as `blackout`. *An empty calendar cannot clear a
name; it can only fail to find one.*

Practical note: there is no dependable free NSE results feed — endpoints move, rate-limit
and block server IPs. Build for a small local calendar he controls, with a best-effort
fetch layered on top that **fails loudly and changes nothing**. A refresh that silently
leaves the calendar empty is how "no event found" starts meaning "not checked".

### 7. EXPIRY FIT — the hold must be shorter than the option's life

**A hold longer than the expiry is not a pessimistic trade, it is an incoherent one.**
Found here by arithmetic: the validated setup was *positional* (a 20-day hold) while
the option config was *intraday* (15-day expiry). The translation produced a 100% theta
charge and kept going, printing an "average return" for a contract that expired mid-trade.
The honest output is not a bad number, it is **"these two do not fit — fix the cadence or
fix the expiry."**

---

## TRANSLATING A STOCK EDGE INTO AN OPTION RESULT

A stock-level backtest is not an answer for an option buyer. It is an input.

```
option_return = stock_return × (delta / premium_pct) − theta_pct − spread_pct
                                └── leverage ──┘
```

Three ways this goes wrong, all of which did:

1. **No floor.** A long option cannot lose more than the premium. Unbounded, a 30%
   adverse move at 40x leverage prints −1200% — a loss larger than the money ever at
   risk — and every statistic built on it is wrong in the direction nobody double-checks.
   **Floor at −100%.**
2. **Assumed premium.** Leverage is `delta / premium_pct`, so that one constant sets the
   entire translation. A config carrying `OPT_PREMIUM_PCT = 0.012` was about **half** the
   real cost of a 15-day ATM option, which **doubled** the leverage and doubled the
   apparent edge. Price it: Black-Scholes ATM, at the volatility the universe actually
   ran, for the expiry actually bought.
3. **Silent incoherence.** See gate 7.

Report it beside the stock headline, always, and label it a **model** — average premium,
average delta, average spread, not the chain that existed on each day. Directionally
right; not a P&L statement.

---

## THE CONTEXT THAT SETS THE BAR

SEBI, FY22–FY24: **93% of individual F&O traders lost money**, ₹1.8 lakh crore in
aggregate; roughly **1%** cleared ₹1 lakh after costs. Of the money that *was* made, by
proprietary desks and FPIs, **96–97% came from algorithmic trading**.

The reading is not "don't". It is that discretionary option buying against algorithmic
counterparties is the losing side, and the only durable answer is the systematic,
cost-aware, gate-driven one — which is what this system is trying to be. It is also why
**every** cost has to be real: statutory charges, the measured spread, theta on calendar
days. An edge that survives only when the costs are assumed is not an edge.

---

## THE RULE THIS ALL REDUCES TO

Pick the name with the stock rules. Then make the **contract** earn the order separately:
fairly priced, exitable, and alive longer than the hold. A system that selects only on
the underlying is a stock system that happens to route through options — and it will pay
option costs for stock-quality decisions.
