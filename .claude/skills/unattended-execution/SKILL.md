---
name: unattended-execution
description: What breaks when a human leaves the loop. Use before running any trading, ordering, or state-changing process autonomously — a session loop, a scheduled job, a cron, an agent. Covers the reconciliation gap (accepted is not filled), stops that die with the process, runaway-loop caps, and the absent-vs-zero distinction that decides all three.
---

# Unattended execution

> *"Is this system ready for agentic AI?"*

## The human was a component nobody documented

A person at the desk is doing work the code never had to: he sees the positions tab, he
notices the order that did not fill, he gets bored of pressing the button. Remove him and
each of those becomes a defect — not a new one, an **existing** one that was being covered
by a human standing in front of it.

So the question is never "can the loop run without me". It is **"which of my judgements is
load-bearing, and where is it written down?"**

## The three that were load-bearing here

### 1. Accepted is not filled

`broker.place()` returned `ok` when Fyers took the order and gave it an id. The book
recorded that as a position. If it never traded, the exit that followed **sold an option
that was never bought** — which is *writing* it: a margin position with open-ended risk,
the one shape of loss the system refuses by design.

A human catches this by glancing at the positions tab. Nothing else did.

The fix is two-layered, and both layers matter:
- **Confirm the fill** before recording a live quantity, and size every exit off the
  confirmed number. Decide on `filledQty` — a *quantity*, which needs no code table —
  not on a numeric status whose meaning you had to guess from forum posts.
- **Gate the sell at the choke point**: ask the broker what is held. Zero refuses.

### 2. The stop died with the process

The trailing stop was computed in the loop and fired as a market order when it broke.
Close the window, sleep the machine, drop the connection — nothing was watching.

A resting SL-M at the exchange survives all three. It cannot trail, so the two are
**complements, not substitutes**: the loop's stop for when he is watching, the resting one
for when he is not. And a resting stop demands a cancel path — an SL-M left after the
position closes is not a leftover, it is a naked short waiting for a price.

### 3. Nobody gets tired of pressing the button

No cap on orders per day. A retry that never gives up, or a signal that re-fires every
tick, is a failure mode a human does not have and an unattended process has by default.

Count from the **audit log**, not from the book. The book records trades the system
believes in; the log records what actually left the machine — and a loop re-sending the
same entry books no P&L, so a drawdown halt watches a number that never moves while the
orders keep going. Count the moment of no return (`sending`), not the reply.

## The distinction all three rest on: absent ≠ zero

This is the whole skill in one line. Every one of the fixes above is really the same
check, and getting it backwards in either direction is a separate bug:

| Reading | Wrong as | Costs you |
|---|---|---|
| unknown → **zero** | "flat", "no orders yet", "nothing held" | acts on a fact it does not have |
| unknown → **halt** | "refuse the exit" | traps him inside a live position |

So resolve it *per question*, by asking what the absence would mean:

- Transport error reading holdings → **unknown** → still let him OUT (never trap), because
  a broker blip must not lock a live position.
- Broker returns `0` held → **fact** → refuse the sell. That is the naked write.
- Log file does not exist → **zero**. A fresh day genuinely has none; halting here stands
  him down every morning.
- Log file exists and won't read → **unknown** → halt. "I cannot count today's orders" is
  not "there were none."
- Field absent because the record predates the field → **unknown** → fall back and let the
  authoritative source decide. *Reading it as zero silently strips the exit off every
  position already open on the day he upgrades.*

That last row was found by an existing test, not by the new one. Migration state is real
state.

## Before running anything unattended

- [ ] Does every write-path confirm its effect, or only its acceptance?
- [ ] If the process dies right now, what is left unprotected at the venue?
- [ ] Is there a cap on actions per period, counted from what *left*, not what was intended?
- [ ] For every "no data" branch: is that absence a fact or an unknown? Decided per question?
- [ ] Can a stale resting instruction fire after the thing it protected is gone?
- [ ] Do records written by the *previous* version still work?
- [ ] Does the loop ever refuse an exit? (It must not.)

## The part that is not plumbing

All of the above makes autonomy *safe*. None of it makes autonomy *profitable*. Before
handing a rule to an unattended loop, the rule itself has to have earned it — see
`factor-admission`. An unvalidated edge run autonomously just loses money faster and with
better uptime.

## Related

`execution-safety` (the gates on a single order) · `real-money-only` (no fabricated inputs)
· `data-integrity` (absence, staleness, agreement) · `factor-admission` (does the rule
deserve to run at all)
