---
name: real-money-only
description: Refuse to fabricate. Any number that could reach a decision, an artifact, or an order must come from the source that owns it - and a process allowed to invent one must never be allowed to send one. Use whenever code has a fallback, a demo mode, a placeholder, a sample, a default, or a "just so it renders" path.
---

# Real money only

> *"I dnt want anything in demo henceforth. All real things. This is real money."*

## The mistake this exists to stop

The desk had a demo mode. It was honest about it: a yellow banner across the top of the
page said **"No token — this is DEMO data. Not one number here is real."** Directly beneath
that banner sat four tickets, each quoting an entry, a stop, a target and a premium to two
decimal places, each with a BUY button under it.

That page was not lying. It was still dangerous, and the reason is worth stating precisely:

**A fabricated number is shaped like an answer.** It has the same two decimals, the same
label, the same position on the screen, the same colour. Every mark of where it came from
is stripped off by the time it reaches the eye. The banner is at the top; the number is
where you are looking. At 9:20am with the market open, you do not read the page — you find
the three numbers you came for.

**Reading is not a safety mechanism.** A warning is a request that the human do the check.
It works in the calm, and fails in exactly the conditions it was written for: hurry, habit,
the fourth time you have seen it, the screenshot forwarded without the top of the page.

So the rule is not *label it better*. The rule is *do not produce it*.

## The rule

**Default: refuse.** Data that would have to be invented is not returned, not rendered, not
written. The panel that would have held it says what is missing and the one command that
fixes it.

**Exception: explicit, per-process, expiring.** Test harnesses genuinely need to walk the
whole code path without a live feed - a path you cannot execute is a path you cannot prove
works. So permission exists, and it is:

- an **environment variable**, set at launch by the harness — `DESK_SYNTHETIC=1`
- **never** a config setting, a file, or a saved flag. Config is edited by hand, persists
  across sessions, and survives a reboot. A switch that can be left on by accident is not a
  switch, it is a trap. An environment variable dies with the process that set it.

**The invariant that actually protects the money:**

> A process permitted to **invent** a number is never permitted to **send** an order.

Enforced at the single choke point every order passes through (`broker.place()`), and it
disqualifies on the *fabrication*, not on what the fabricated symbol happens to look like.
A prefix check (`symbol.startswith("DEMO:")`) stays as a second, independent guard — two
guards fail independently, and a guard defeated by its own placeholder is worse than none.

## Where to apply it — ranked by how long the lie outlives its warning

1. **Artifacts that outlive the terminal.** A TradingView watchlist, a paper book, a CSV, a
   saved rule. The warning scrolls away; the file does not, and next week nobody can tell
   which rows were real. *The scanner used to write a full watchlist of invented names
   after printing one yellow line.* → **do not write the file at all.**
2. **Anything measured later.** A synthetic fill in the paper book is not a labelling
   problem, it is a corrupted measurement — the record you use to answer *does this
   actually work* has to be thrown away entirely. → **separate file, permanently.**
3. **Anything beside a button.** Tickets, prices, quantities, greeks. → **empty board.**
4. **Anything that decides.** Gates, limits, blackout calendars. "Not checked" must never
   render as "passed" — see `data-integrity`.

## How to refuse well

A refusal that leaves him stuck is its own failure. Every one carries the fix:

```python
raise RO.Synthetic(f"no token, so there is no market data. {RO.FIX}")
#                                                          ^ "Run the '1 - START DAY' icon"
```

- **One line**, not a paragraph — see `solution-first` and the brevity directive.
- **Name the cause, not the symptom.** "No contract", "your token expired" and "this name
  has no F&O series" are three problems with three fixes; a control that greys out
  identically for all three teaches nothing.
- **Empty is a true statement about the world.** A blank board with "no token" is honest.
  A full board of invented numbers is not. Say the empty thing plainly.

## Proving it — the test that had to be written backwards

Every other suite runs *with* the permission granted, because a page with no token has
nothing to render. That makes them structurally incapable of testing the thing that
matters. `test_real_only.py` strips `DESK_SYNTHETIC` out of the environment and tries every
door that used to hand over fabricated data.

The assertion that counts is not "a warning appeared". It is:

```
PASS  and offers nothing to press - no ticket, no BUY, no stop   PRESSABLE: []
```

Plus: permission grants must *revoke* order rights, and a **missing** `real_only.py` must
**close** the gate, not open it — an import guard that swallows the exception and carries
on is how a safety check quietly becomes decoration.

## The checklist

Before shipping any fallback, default, sample, placeholder or demo path:

- [ ] Could this number reach a screen, a file, or an order? → refuse by default
- [ ] Is the permission per-process and expiring, not persisted?
- [ ] Does permission-to-invent revoke permission-to-send?
- [ ] Does the refusal name the exact command that fixes it?
- [ ] Does a test run *without* permission and assert there is nothing to press?
- [ ] If the guard module vanished, does the gate close or open?

## Related

`data-integrity` (is this number right?) · `execution-safety` (can this send an order?) ·
`solution-first` (never hand back the excuse as the deliverable) · `screen-proof` (rendered
and visible are different claims)
