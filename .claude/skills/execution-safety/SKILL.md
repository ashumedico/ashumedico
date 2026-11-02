---
name: execution-safety
description: The rules for anything that can send a real order — buttons, order builders, stops, exits, automation, brokers. Use before writing or changing any code path that reaches Fyers, before arming live trading, and whenever a control could place, modify or cancel an order. Covers the three gates, the two-press rule, resting vs trailing stops, order-type semantics, rejection diagnosis, and the audit trail.
---

# EXECUTION SAFETY — the path where a bug costs money

Every other part of this system can be wrong and cost a wasted morning. This part can be
wrong and cost the account. The rules below are not preferences; each one is written from
something that happened here.

---

## THE THREE GATES — none of them is about balance

An order reaches the exchange only if all three are open:

1. **`LIVE_TRADING = True`** in `config.py`. Absent or False, the order is logged and not
   sent. That is the default and it stays the default.
2. **`STOP_TRADING.txt` absent.** Creating that file halts everything instantly, no
   restart. The kill switch must work when nothing else does — it is a file check, not a
   service, not a flag in a database, not an API call.
3. **The contract came from the exchange's own chain.** A symbol assembled by hand from
   strike and expiry is one character from a *different contract* — not a rejection, a
   fill on something else.

Balance is deliberately not a gate: he funds the account himself, and that is his call.

## THE TWO-PRESS RULE

Nothing irreversible happens on one click. Press one **arms** and prints the request
verbatim; press two **confirms**; arming expires in 20 seconds.

The payload must be shown as it will be sent — symbol, side, qty, type, trigger. *The
numbers on the button and the numbers in the request have to be the same numbers, and the
only way to be sure is to print the request.*

## A GUARD THAT CANNOT FIRE IS NOT A GUARD

Two ways this failed here, both instructive:

- **Defeated by its own placeholder.** The button checked `if not payload["symbol"]`,
  but the caller passed `sym or "-"` for display. `"-"` is truthy, so the guard passed,
  the button armed, and only the broker stopped it. *A guard defeated by its own
  placeholder is worse than no guard: it reads as protection and is not.*
- **Firing on everything.** Every order button on every ticket was permanently disabled,
  and the guard was right — there was no contract, because nothing had ever fetched one.
  *When a check never passes for anything, stop auditing the check and find the missing
  input.*

And a disabled control must say **which** of its reasons it is — kill switch, no token,
no contract, absurd quantity. Four problems wearing one grey coat teaches nothing.

## QUANTITY IS A SAFETY FIELD

A wrong lot is a wrong order, not a display bug.

- The **freeze quantity** is not the lot size. A symbol-master column that looks like the
  lot printed `qty 18365` — a ₹102 crore contract — one confirm from the exchange.
- Band the implied contract value **both ways**: NSE F&O is ~₹5–10 lakh. Below ₹2 lakh or
  above ₹20 lakh, block every button on that ticket. A one-sided band is how the ₹102
  crore got through.
- Prefer the **live chain's** lot: it is the exchange's own, and it moves when a split
  revises it. When chain and symbol-master disagree, use the chain and say so.

## ORDER TYPES — the semantics, not the numbers

```
1 = LIMIT     2 = MARKET     3 = SL-M     4 = SL-LIMIT
```

- An `SL`/`SL_LIMIT` without a `stopPrice` is **refused before it is sent**. A stop with
  no trigger is not a stop.
- `productType`: `INTRADAY` auto-squares at the broker's cutoff; `MARGIN` carries. This
  system is INTRADAY — a mismatch here means a position surviving a day it was never
  sized for.

## RESTING STOP vs TRAILING STOP — they complement, they do not substitute

| | Resting SL at the exchange | Trailing stop in the session loop |
|---|---|---|
| Survives a closed laptop | **yes** | no |
| Ratchets as price moves | no | **yes** |

Place **both**: the trail for when he is watching, the resting stop for when he is not.
Offering one as a replacement for the other is how a position is left naked overnight or
never lets a winner run.

## REJECTIONS ARE INFORMATION, NOT EXCEPTIONS

A broker rejection never raises — it returns `(ok, detail)` and gets explained in plain
words. The recurring ones:

- **−50 · IP whitelist** — the app's whitelisted IP no longer matches.
- **−15 · token** — invalidated, often by changing the Fyers app settings themselves.
- **−99** — Fyers reuses it for almost anything, so the code alone is never the
  diagnosis. Read the message.

## THE AUDIT TRAIL

Every order is written to `orders.jsonl` **before** it is sent, and again with the
broker's reply. *An order that is sent but not logged is an order nobody can audit, and
on a bad day that is the only record there is.*

---

## BEFORE ARMING ANYTHING

- What exactly can this send, at what size, how many times?
- What is the **blast radius** if it misfires at 9:20am?
- What is the **rollback** — and is it a file, or does it need me?
- Least privilege and read-only by default. *Keys, not prompts, dictate safety.*

Pause and confirm when the action is irreversible, touches money, or confidence < 80%.
Speed is never the reason to skip a gate.
