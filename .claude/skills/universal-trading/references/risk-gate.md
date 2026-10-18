# Risk gate — the module that can say NO

Stage 5 is a **hard gate**, not advice. Run all five checks; **any FAIL → BLOCK the trade.**
Capital preservation outranks every signal. Defaults below are starting points — tune in
`config.py` to Aashish's actual capital and rules.

```
RISK CHECK  →  Position size · Exposure · Drawdown · Volatility · Max loss
              PASS → continue        FAIL → block
```

## 1. Position size — **fixed, and the budget is a veto**

Quantity is a **decision Aashish has already made: one lot.** It is never an output of the
risk arithmetic.

```
lots = LOTS_PER_TRADE                        # 1, by standing instruction
qty  = lots * lot_size_from_the_option_chain # never a guessed lot
```

The risk budget does not *set* the size — it **vetoes** it:

```
risk_amount = capital * RISK_PCT             # what this trade is allowed to lose
outlay      = premium * qty                  # for a buyer, max loss IS the premium
if outlay > risk_amount:  BLOCK              # answer is "no trade", never "more lots"
```

This is the direction the old code had backwards: sizing *from* the budget once proposed
**nine lots — ₹2.46 lakh of premium on ₹2 lakh of capital.** A budget that can only shrink a
position is safe; a budget that can grow one is a leak.

Also **BLOCK** when the chain gives no lot size. A zero-quantity or guessed-lot ticket is worse
than no ticket, because it looks like a decision.

## 2. Exposure limit
- Total capital deployed across **all open positions** ≤ `MAX_EXPOSURE` (default 40% of capital).
- No single **underlying** > `MAX_PER_NAME` (default 15%). No sector > `MAX_PER_SECTOR` (default 30%).
- Correlated names (e.g. two PSU banks, or a name + its index) count together.
- Over any cap → **BLOCK** the new trade until something is closed.

## 3. Drawdown control
- **Daily stop:** if realised + open loss ≤ `-DAY_DD` (default 3% of capital) → stop for the day.
- **Weekly stop:** ≤ `-WEEK_DD` (default 6%) → stand down, review, reduce size next session.
- In an active drawdown breach → **BLOCK all new risk.** No revenge trades.

## 4. Volatility check
- Option **spread** acceptable (bid-ask not blown out); **IV** not spiking into an event.
- Underlying **ATR / India VIX** within the setup's tolerance — a knife-catch in high vol is a BLOCK.
- Expiry-day theta/gamma risk sized down or skipped for buyers.
- Unacceptable volatility for the setup → **BLOCK** (or switch to a defined-risk structure).

## 5. Max loss
- Worst case **including a gap** (overnight/positional) ≤ `MAX_LOSS` (hard rupee cap).
- For option **buying**, max loss = premium — ensure that premium ≤ the trade's risk budget.
- For **writing / futures**, model the gap to the invalidation level, not just the stop.
- If worst-case can breach the cap → **BLOCK** or reduce to where it can't.

---

## Verdict
```
if all five PASS:  approve qty, place with stop + invalidation preset
else:              BLOCK, state which check failed and the one change that would pass it
```
Log every BLOCK with the reason — the blocks are data too. A gate that never says NO isn't a gate.

## Config keys (`config.py`, git-ignored — set them with `python configure.py`)
```python
LOTS_PER_TRADE = 1        # THE size. Not a starting point.
CAPITAL        = 200000
RISK_PCT       = 0.005    # veto threshold, not a sizer
MAX_EXPOSURE   = 0.40     # total deployed cap
MAX_PER_NAME   = 0.15
DAY_DD         = 0.02     # daily drawdown auto-halt
WEEK_DD        = 0.06
MAX_LOSS       = 5000     # hard worst-case rupee cap per trade
MIN_EXPIRY_DAYS = 15      # roll to next series below this
```
Change them through `configure.py` (it rewrites only the named keys and keeps a backup), not by
hand-editing — a half-edited config is how the system silently reverted to SWING once.
