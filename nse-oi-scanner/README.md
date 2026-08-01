# NSE F&O Trading OS (Fyers) — v5

Your desk, in one folder. Daily use is two icons; everything else is there for when you
want to dig.

> **Not financial advice.** Signals are inputs; every trade decision is yours.

## The daily loop (this is 95% of it)
```
1 - START DAY       token + lot check + paper trader + today's check-in
2 - CHECK-IN        what to hold / book / buy - then leave
3 - DESK            the website, when you want to look
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

## The website — `3 - DESK`
```bash
streamlit run desk.py          # or the icon: 3 - DESK (website)
```
One page, laid out the way you read a chart: a left rail to pick the name, a **status
banner** that says in one line whether a trend is identified, a **ribbon** with spot ·
trend · VWAP · RVOL · ATR · squeeze · expansion, the **ticket** (contract, qty, cost,
stop, T1/T2), the **chart** with R2/R1/S1/S2 drawn, named, and labelled with how many bars
actually traded against each level, a **scenario block** (Bullish / Sideways / Bearish)
that states what would have to happen and what invalidates it, the **Mauke** table, and
the **paper score** against what the backtest claimed.

Nothing on it is illustrative. Every level and premium is computed from bars that were
fetched; with no token it says **DEMO DATA** in three places and still renders end to end,
because a demo that cannot show the page working cannot prove the page works.

The page is **five tabs** — Command deck, Signals & tickets, Chart, Screener, Score — each
sized to fit one landscape screen at 1920×940 without scrolling. The verdict and the
numbers behind it sit on one status line above all five, so whatever tab is open, the tape
and the selected name are still on screen.

`python test_desk.py` runs the page through Streamlit's own AppTest and asserts on what
reached it — verdict strip, levels, all three scenario branches, disclaimer, and that a
ticket is built from a live option chain. Icon: **Tools → Desk render test**.

`python test_layout.py` is the one test that asks whether you can **see** it: a real
browser at 1920×940, every tab clicked, every overflow measured. AppTest cannot catch a
header that rendered correctly *underneath* Streamlit's own toolbar; this does. Icon:
**Tools → Screen fit test**.

## On the chart — `tradingview/`
| File | What it is |
|---|---|
| `AashishMomentum.pine` | The strategy: entry on the first expansion bar, ATR stop trailing from the high-water mark, EOD square-off. Backtestable on TradingView. |
| `AashishScreener.pine` | A **table on the chart** showing which of 20 names pass the same five gates right now — trend, VWAP, RVOL, squeeze, expansion — with a PASS count. |

The screener is **not** the scanner. TradingView caps a script at 40 `request.*` calls, so
it sees 20 names while the Python system sees the whole F&O list — and it computes none of
what a ticket needs: no option chain, no lot size, no premium, no charges, no S/R levels.
A green row means *worth opening the desk for*. It never means *place this*.

The live bar **repaints**: it is unfinished, so a row can turn green and back inside one
candle. Tick **confirmed bars only** to see closed candles alone.

`python test_pine.py` (Tools → Pine vs Python) checks the two halves still agree on every
number. Pine itself is compiled by TradingView, not here.

## The engine underneath
| File | Role |
|---|---|
| `rrg_engine.py` | RRG core - RS-Ratio/RS-Momentum, heading, velocity, distance, quadrant crossings, **own-trend**, signal dating, full-universe live data with a day cache |
| `rrg_strategy.py` | 9 rule-sets, walk-forward backtest, **trading profiles** (active/swing/positional), vol targeting, no-trade band, regime gate |
| `robustness.py` | Tries to **disprove** the edge: out-of-sample, cost sensitivity, regime, parameter stability |
| `trade_card.py` | Candidate -> order ticket: which option, size, entry/stop/T1/T2, exit contract |
| `journal.py` | Grades its own past calls, slices what works, prints KEEP/STOP lessons |
| `paper.py` · `broker.py` | The hands-free loop: take/mark/close, bar-by-bar trailing, market-minute timeouts, and the Fyers order layer beside it |
| `features.py` · `indicators.py` | Every candidate becomes one dict per bar: VWAP, RVOL, ATR, squeeze, expansion, R1/R2·S1/S2, continuation, breakout, structure |
| `hypothesis.py` | The ablation - each filter turned off in turn, so a filter has to earn its place |
| `desk.py` | The website (Streamlit): banner, ribbon, ticket, chart with levels, scenarios, paper score |
| `scanner.py` · `option_chain.py` · `chart_action.py` | OI buildup, PCR/Max-Pain/walls, support-resistance, the 60%-body rule |
| `charges.py` · `option_pnl.py` | Verified statutory rates, round-trip drag, breakeven move, DTE sweep |

**Deleted, on purpose:** `signal_engine.py`, `report.py`, `charts.py`, `app.py`, `rrg_app.py`,
`rrg_view.py`, `rrg.py`, `auto_trader.py`, `execution.py`, `risk_gate.py`. They were the
previous generation - a three-idea desk that included a **future**, and sizing that came
**out of the risk budget**. Both contradict decisions since made (options only; one lot,
fixed). Code that contradicts the doctrine does not sit quietly in a folder; it gets opened
by mistake at 9:20am.

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

## The standing frame — decisions, not defaults
| | |
|---|---|
| Instrument | **Options only.** Stock CE/PE. No futures. |
| Style | **Intraday**, 15-minute candles |
| Strike | **ATM** (delta ≈ 0.50) |
| Size | **1 lot, fixed.** The risk budget is a **veto**, not a sizer |
| Expiry | Near month; roll once the running series has **< 15 days** left |
| Entry | The **first expansion bar** — the bar a coil breaks |
| Exit | ATR stop, trailing from the high-water mark, **ratchet only**. Breakeven is a floor |
| Mode | Paper and live together; live only when armed |

Change them through `python configure.py` — it rewrites only the named keys and keeps a
backup. Hand-editing `config.py` is how the system silently reverted to SWING once.

## The auto-trader (paper-first, Fyers-linked)
```bash
python paper.py --session     # the loop: every candle, take / mark / trail / exit
python paper.py               # just the score against what the backtest claimed
```
`paper.py` runs the whole cycle and writes a paper record for every decision; when live is
armed, `broker.py` places the same order at Fyers beside it. A real order fires **only** if
`LIVE_TRADING=True` **and** no kill-switch file **and** a valid token **and** the risk gate
passed. Exits are managed bar by bar: stop, T1 (half off, stop to breakeven *if that is
higher than the trail*), T2, bar-count timeout, square-off.

**Kill switch:** create `STOP_TRADING.txt` (or the **STOP - Kill Switch** icon) → everything
halts. **You arm live trading; you own the outcome.**

## v2.1 — the derivatives picture completed
Added the pieces a futures-only scanner was missing:
- **`option_chain.py`** — PCR, **Max Pain**, Support/Resistance walls, **call/put-writing** detection,
  strike-wise OI ladder. Run: `python option_chain.py --dry-run`.
- **Volume confirmation** — buildup rows now flag `VOL✓` (OI up *with* rising volume = stronger).
- **F&O ban-list filter** — `BAN_LIST` in config; banned underlyings are skipped (no fresh positions allowed).

Still on the roadmap (say the word): rollover %, relative-strength vs sector, participant-wise (FII/DII) OI.

## Reconcile with your original (still worth doing)
Rebuilt from what the shortcuts revealed, not a byte-copy. Tell me and I'll merge:
your exact **universe**, **thresholds**, **futures vs option-chain (strike-wise) OI / PCR**,
and any **alerting** the original had.
