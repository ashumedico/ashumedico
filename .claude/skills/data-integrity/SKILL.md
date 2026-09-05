---
name: data-integrity
description: The pre-flight for any market number before it reaches a screen, a ticket or an order. Use whenever a figure is about to be displayed, compared, sized on, or ordered against — lot sizes, prev closes, averages, premiums, universes, backtest results, "nothing passes" results. Runs seven checks that each caught a real bug in this system. Trigger on new data sources, new screens, unexpected results, empty results, and any number that looks fine.
---

# DATA INTEGRITY — the checks that stand between a number and an order

Every bug worth remembering in this system has been the same bug in a new costume: **a
number that looked like an answer and was not.** None of them announced themselves. They
were the right shape, the right magnitude, in the right column, and wrong.

The eight that produced this file:

| What it printed | What was true |
|---|---|
| `qty 18365` on a live BUY button | that was the **freeze quantity**, not the lot — a ₹102 crore contract |
| `R:R 1.5` on a ticket | at its own stated entry it was **1.20** — levels came off spot, entry was a limit |
| `TP3` between TP1 and TP2 | three targets, three different formulas |
| `-₹446` from a backtest | the backtest **restated** the signal instead of calling it; the real figure was +₹997 |
| every winning put marked a loss | option exit used the **call** formula |
| `20-day mean` in intraday mode | 20 bars of 15 minutes = **five hours** |
| a name 50% below its mean | a **1:2 split** the history had not applied |
| `nothing passes` | the demo opened every session at the prior close — gaps were **impossible**, not absent |

Seven checks follow. Each one exists because it would have caught one of those.

---

## 1. PROVENANCE — derived, or authoritative?

For every number that decides something, name its source and ask whether that source
*defines* the number or merely *reflects* it.

- The exchange **publishes** the previous close. A daily candle **reflects** it.
- The option chain **carries** the lot size. A symbol master has a column that might be
  the lot, or might be the freeze quantity, or might be neither.

> Prefer the source that defines the number. Where two exist, name on screen which one
> priced this row — two runs returning different lists must be tellable apart.

## 2. BASIS — are both sides of the comparison in the same units?

A comparison silently becomes meaningless when one side moves basis.

- `Close > SMA20` — is the mean built from the **same adjustment basis** as the price?
  After a split, the history is pre-adjustment and the quote is post. Fix: the
  disagreement between quote and candle *is* the factor. Rescale, do not warn.
- "20 days" on a 15-minute chart is five hours. "10 bars" is ten months on a monthly.
  **Any rule that mentions time must resolve it through one function**, never restate it.
- A put's intrinsic is `strike − spot`. Using the call formula makes every ITM put look
  absurd and rejects every real quote.

## 3. MAGNITUDE — does this imply something absurd?

Put an economic band on any figure that multiplies. Two-sided, always.

- An NSE F&O contract is ~₹5–10 lakh. Below ₹2 lakh or above ₹20 lakh, **block the
  button** — a one-sided band let a ₹102 crore contract through to a live order.
- A short-dated slightly-ITM call is 3–5% of the contract value. 20% means premium or
  lot is wrong.
- A backtest returning 191,000% is not an edge, it is a data bug.

## 4. STALENESS — how old is this input, and can it expire?

A cache with no expiry is used forever.

- The F&O universe changed monthly; the cache never expired. A list written in March was
  still the universe in August, and **every name NSE had added since was invisible on
  every screen**. A missing name looks exactly like a name that did not qualify.
- Rule: every cached input carries an age, an expiry, and a label. A degraded source is
  named as degraded **on screen** — a console line is not a warning.

## 5. ABSENCE — is empty an observation, or an impossibility?

The hardest failure to see, because it looks like a finding.

- The demo market opened every session at exactly the prior close, so a gap screen was
  **structurally incapable** of returning a name. "Nothing passes" read as a market
  observation and was arithmetic.
- Rule: before reporting empty, prove the data **could** have produced non-empty. Report
  the enabling count beside the result — *"0 of 187 pass; 185 gapped at all"*.
- And: empty ≠ zero. "No name qualifies" and "every name scored 0.00%" are different
  claims. Filling an unknown with a zero is a lie with a decimal point.

## 6. AGREEMENT — when two sources differ, which one, and by how much?

Never resolve a conflict silently; never accept it as fate either.

1. Is one **authoritative**? Use it.
2. Is the difference a **known transform** (a corporate action, a currency, a lot
   multiple)? Then it is repairable arithmetic — do it.
3. Only what survives both is a real limitation, and it ships with the command that
   checks it.

Also: a **partial** second source is worse than none. A quote with an open but no
previous close, paired with the candle's previous close, invents a third number belonging
to neither feed. Take it whole or ignore it.

## 7. SELF-CONSISTENCY — do the derived numbers agree with each other?

Correctness is often unprovable; consistency almost never is.

- The stop is on the losing side of the **entry**, not of spot.
- Targets step away in order. Derive all of them from **one** formula (R-multiples), so
  their ordering is arithmetic rather than luck.
- The R:R printed is the R:R obtained at the stated entry.
- The option legs come off the **same entry** as the stock legs.
- Backtests **call** the production function; they never restate its logic. Restating it
  is how −₹446 and +₹997 came from "the same" rule.

---

## THE HABIT

Any new source, screen or figure: walk all seven, and write a test for the one that
would have hurt most. Then check the negative case — a test that only asserts the happy
path proves the code can succeed, not that it can fail when it should.

**When a number is wrong, the failure is almost never in the formula. It is in what was
fed to it.** Read the input before rereading the maths.
