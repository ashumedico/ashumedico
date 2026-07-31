# NSE F&O Trading OS (Fyers) — v5

Your desk, in one folder. Daily use is two icons; everything else is there for when you
want to dig.

> **Not financial advice.** Signals are inputs; every trade decision is yours.

## The daily loop (this is 95% of it)
```
1 - Fyers Login     today's token
2 - CHECK-IN        what to hold / book / buy - then leave
```
`checkin.py` answers three questions and gets out of the way: what to do with what you
already hold, whether there is a new trade, and how the closed ones have gone. State
lives in `positions.json`, so leaving for a week and coming back still works.

```bash
python checkin.py                      # the check-in
python checkin.py --buy                # you took the suggested trade
python checkin.py --sold GNFC --price 62   # you exited
python checkin.py --sold GNFC --half --price 58   # booked half; stop moves to breakeven
```

## When you are away
`alert_watch.py` pings Telegram (or SMS) **only when a decision is due** - T1 hit, T2 hit,
stop broken, or dead money. Silence is deliberate. Set it up once with
**SETUP - Telegram Alerts**, which discovers your chat id itself and schedules the checks.

## The engine underneath
| File | Role |
|---|---|
| `rrg_engine.py` | RRG core - RS-Ratio/RS-Momentum, heading, velocity, distance, quadrant crossings, **own-trend**, signal dating, full-universe live data with a day cache |
| `rrg_strategy.py` | 9 rule-sets, walk-forward backtest, **trading profiles** (active/swing/positional), vol targeting, no-trade band, regime gate |
| `robustness.py` | Tries to **disprove** the edge: out-of-sample, cost sensitivity, regime, parameter stability |
| `trade_card.py` | Candidate -> order ticket: which option, size, entry/stop/T1/T2, exit contract |
| `journal.py` | Grades its own past calls, slices what works, prints KEEP/STOP lessons |
| `risk_gate.py` · `execution.py` · `auto_trader.py` | 5-check risk gate, paper/live broker layer, hands-free loop |
| `rrg_app.py` | The deep-dive cockpit (Streamlit) - RRG main window, action board, journal |
| `scanner.py` · `option_chain.py` · `chart_action.py` · `signal_engine.py` | OI buildup, PCR/Max-Pain/walls, support-resistance, 3-layer confluence |

## What the evidence says
On 204 real F&O names over ~1.6 years, at the **positional** cadence (~monthly
decisions, 4 slots): the vol-targeted + banded setup returned **55.8% vs NIFTY 5.4%**,
Sharpe **1.90**, maxDD **-4.4%**, on **32 trades**.

Two honest caveats, both material:
- **32 trades is a thin sample**, and that setup was the best of 27 combinations tried,
  so some of it is selection luck.
- **It is not yet out-of-sample validated** - 400 bars cannot split at a 20-bar
  rebalance. Run `python robustness.py --days 900` before sizing it up.

Why turnover matters so much here: 303 trades at a realistic 35bps is roughly 10% of
cost drag; 32 trades is about 1%. Trading less was most of the improvement.

## Setup
```bash
python setup.py            # Fyers keys -> config.py (git-ignored)
python upgrade_config.py   # adds any settings a older config.py is missing
python fyers_auth.py       # today's token
```
`config.py`, `positions.json`, `cache/` and anything personal are git-ignored. This repo
is public - keep credentials and phone numbers out of tracked files.

---

## v4.0 — the AUTO-TRADER (paper-first, Fyers-linked, risk-gated)
A 24/7 automated engine that runs the whole pipeline and can place orders — **paper by
default, live only when you deliberately arm it.**

```
SCAN → RISK GATE → EXECUTE → MANAGE → HALT
```
- **`risk_gate.py`** — the hard 5-check gate (position size · exposure · drawdown · volatility ·
  max-loss). Sizes every trade from *risk per trade*; any fail → **BLOCK**. Conservative preset:
  **0.5%/trade, 2% daily stop.**
- **`execution.py`** — broker layer. **Paper** simulates fills into `paper_book.json` and marks P&L.
  **Live** calls the Fyers order API — but a real order fires *only* if **all** are true:
  `LIVE_TRADING=True` · no kill-switch file · valid token · risk gate passed.
- **`auto_trader.py`** — the loop: scans signals, gates + sizes, executes (paper/live), manages
  exits (target/stop/invalidation/square-off), and **auto-halts** on the daily drawdown limit.

```bash
python auto_trader.py --dry-run     # one full cycle on synthetic signals (safe demo)
python auto_trader.py --paper --loop # continuous PAPER trading on live signals
```

**Kill switch:** create `STOP_TRADING.txt` in the folder (or double-click **STOP-TRADING.bat**) →
everything halts. **Going live** is a deliberate 3-step act (see the header of `auto_trader.py`):
paper-prove it → set `LIVE_TRADING=True` + real `CAPITAL`/caps in `config.py` → fresh Fyers token.
Two new desktop icons: **Auto-Trader (PAPER)** and **STOP Trading**.

> Paper P&L in `--dry-run` is a plumbing demo (assumes exits tag targets), not a backtest.
> Real fills/P&L come from live Fyers data. **You arm live trading; you own the outcome.**

## v2.1 — the derivatives picture completed
Added the pieces a futures-only scanner was missing:
- **`option_chain.py`** — PCR, **Max Pain**, Support/Resistance walls, **call/put-writing** detection,
  strike-wise OI ladder. Wired into the dashboard. Run: `python option_chain.py --dry-run`.
- **Volume confirmation** — buildup rows now flag `VOL✓` (OI up *with* rising volume = stronger).
- **F&O ban-list filter** — `BAN_LIST` in config; banned underlyings are skipped (no fresh positions allowed).

Still on the roadmap (say the word): rollover %, relative-strength vs sector, participant-wise (FII/DII) OI.

## Reconcile with your original (still worth doing)
Rebuilt from what the shortcuts revealed, not a byte-copy. Tell me and I'll merge:
your exact **universe**, **thresholds**, **futures vs option-chain (strike-wise) OI / PCR**,
and any **alerting** the original had.
