---
name: factor-admission
description: How a new idea earns a place in a trading system — and how to refuse one without refusing to build it. Use whenever a new indicator, screener, ranking, data source or filter is proposed (R-Factor, a gap screen, news catalysts, sentiment, anything from another platform). Prevents the failure where good ideas are bolted on one at a time until nobody knows which ones pay.
---

# FACTOR ADMISSION — the skill I actually need

Aashish brings factors. A Chartink gap screen. TradeFinder's R-Factor. News catalysts.
Each one is a reasonable idea and each one arrives the same way: *"add this."*

The failure mode is not that any of them is bad. It is that **bolting them on one at a
time produces a system nobody can attribute.** Twenty features, an edge of unknown origin,
and no way to tell which three are carrying it and which seventeen are costing turnover.
That already happened here once: RRG went into the main window because it was
sophisticated and looked right. Measured properly, it contributed **−6.3% after costs.**

So the answer to "add this" is never "no", and it is never "yes" either. It is
**"admitted as a testable arm; here is what would make it live."**

---

## THE FOUR QUESTIONS, before any code

### 1. What does this factor claim, in one sentence?

If it cannot be stated as a falsifiable claim, it cannot be tested and should not be
built. Good: *"ranking by move-intensity relative to a name's own noise beats ranking by
raw percent change."* Bad: *"R-Factor shows strong stocks."*

### 2. Is it already here under another name?

Check before building. R-Factor turned out to **already exist** in this system as
`r_factor()` with two ablation arms — the useful contribution was not the factor, it was
noticing that ours was **price-only** while the original also measures volume and range.
Half of "add this" requests are answered by a grep.

### 3. Can it be measured on his data, or only asserted?

- **Measurable** → build it as an arm and run the ablation.
- **Not measurable** (no history, no feed) → build the *mechanism* and say plainly that
  it is unmeasured. Never let it into the live selector on plausibility.

### 4. What does it cost when it is wrong?

A ranking that is wrong costs turnover. A gate that is wrong costs missed trades — which
is invisible, and therefore worse. A gate that fires on a *missing input* costs
everything: the whole book, silently.

---

## THE ADMISSION LADDER

A factor climbs; it does not teleport.

| Rung | State | What it may do |
|---|---|---|
| 0 | **Idea** | be written down as a falsifiable claim |
| 1 | **Implemented** | exist as a function, with its own test |
| 2 | **Visible** | appear on the desk, labelled *not backtested* |
| 3 | **Arm** | be an ablation arm, comparable against the control |
| 4 | **Measured** | have a walk-forward number on **his** data |
| 5 | **Live** | enter the selector — only from rung 4, only if it paid |

The gap screen sits at **2**: its own tab, saying on its face that it is not backtested,
and deliberately NOT intersected with the signal book — crossing them would produce a
list that is neither, carrying the authority of both.

R-Factor sits at **3**: two arms, plus a composite arm, none enabled.

Nothing has skipped to 5 since RRG did, and RRG is the reason for the ladder.

---

## HOW TO ADD AN ARM SO THE MEASUREMENT MEANS SOMETHING

**Change one thing.** An arm that alters the ranking *and* the filter measures their sum
and attributes nothing.

**Centre the variant on the control.** The composite R-Factor multiplier is built to
equal **1.0** at normal volume and normal range, so it reduces exactly to the price-only
version and the two arms differ *only where activity is abnormal*. Now the ablation
measures **the addition**, not two unrelated rankings. This is the single highest-leverage
trick in this file.

**Bound every input.** Each ratio capped at 3x, so one freak print cannot dominate a
ranking across the whole universe. An unbounded factor eventually measures its own
outliers.

**Keep the control honest.** `momentum_only` exists to answer *"if this scores the same
as the plain version, the machinery is decoration."* Never delete the control to make the
table look better.

---

## WHEN THERE IS NO FEED

Some factors — news catalysts, results dates, corporate actions — need data that has no
dependable free source. The answer is not to skip them and not to fake them:

1. Build a **local store he controls**, with a manual add.
2. Layer a **best-effort fetch** that **fails loudly and changes nothing**.
3. Return **three states**, never two: `clear` / `hit` / **`unchecked`**.

That third state is the whole discipline. A boolean collapses *"nothing found"* and
*"nothing was looked at"* into the same `False`, and `False` renders as a green tick. An
empty calendar cannot clear a name; it can only fail to find one.

---

## THE SENTENCE TO SAY

> "Built and testable. It is at rung 3 — an arm, not in the selector. Run
> `Tools → Ablation test` and if it pays on your data, I will switch it on and show you
> the number that justified it."

That is not a refusal, and it is not a promise. It is the only honest position between
them — and it is the one thing this system needs from me that no amount of careful code
supplies.
