# Risk gate — the module that can say NO

Stage 5 is a **hard gate**, not advice. Run all five checks; **any FAIL → BLOCK the trade.**
Capital preservation outranks every signal. Defaults below are starting points — tune in
`config.py` to Aashish's actual capital and rules.

```
RISK CHECK  →  Position size · Exposure · Drawdown · Volatility · Max loss
              PASS → continue        FAIL → block
```

## 1. Position size
Size from **risk per trade**, never from conviction or "gut".
```
risk_amount   = capital * RISK_PCT           # default RISK_PCT = 1% (0.01)
stop_distance = abs(entry - stop)            # in points
qty           = floor(risk_amount / stop_distance)
qty           = round down to lot size       # F&O trades in lots
```
If `qty < 1 lot`, the stop is too wide for the risk budget → **BLOCK** (or widen capital, not risk).

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

## Suggested config keys (add to `config.py`)
```python
RISK_PCT      = 0.01     # risk per trade as fraction of capital
MAX_EXPOSURE  = 0.40     # total deployed cap
MAX_PER_NAME  = 0.15
MAX_PER_SECTOR= 0.30
DAY_DD        = 0.03     # daily drawdown stop
WEEK_DD       = 0.06
MAX_LOSS      = 15000    # hard rupee worst-case cap per trade (example)
```
