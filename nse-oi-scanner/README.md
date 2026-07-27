# NSE F&O OI-Change Options Scanner (Fyers) — v2

Version-controlled, hardened rebuild of the scanner that used to live only on your PC at
`C:\claude\`. Now in git: backed up, diff-able, improvable.

> **Not financial advice.** Signals are inputs; every trade decision is yours (`@edge-seeker`).

## The signal engine
Price × open-interest matrix, measured **from the day's opening OI** (real intraday buildup):

| Price | OI | Signal |
|---|---|---|
| ↑ | ↑ | **Long Buildup** (bullish) |
| ↓ | ↑ | **Short Buildup** (bearish) |
| ↑ | ↓ | **Short Covering** (bullish) |
| ↓ | ↓ | **Long Unwinding** (bearish) |

## What v2 fixed (critical review of the first rebuild)
1. **OI baseline** — now vs **day-open OI**, not vs the last 5-min poll (which was noise).
2. **Futures symbols** — cash `-EQ` has no OI; the universe now uses `...FUT` symbols.
3. **Market-hours guard** — only scans 09:15–15:30 IST, Mon–Fri (override with `--force`).
4. **Token expiry** — a Fyers auth error is caught and tells you to re-login instead of crashing.
5. **Retries + backoff** on every API call.
6. **History + logging** — `scanner.log` + a daily `signals_YYYYMMDD.csv`.
7. **Optional Telegram alerts** on strong buildups (`alerts.py`, config-gated).

## Setup
```bash
pip install -r requirements.txt
copy config.example.py config.py     # add Fyers keys + your FUT universe
```

## Desktop icons (Windows)
Double-click **`install.bat`** once → it **replaces old icons** and drops 4 fresh ones:
- **NSE OI Scanner** → `run_scanner.bat` (console, live loop)
- **Fyers Login** → `run_login.bat` (daily token)
- **OI Scanner Board** → `run_dashboard.bat` (Streamlit → localhost:8501)
- **Trade Signals + RRG** → `run_signals.bat` (1 CE + 1 PE + 1 Future, 3 annotated charts + RRG)

## Run
```bash
python fyers_auth.py         # each morning: today's token
python scanner.py            # one scan
python scanner.py --loop     # continuous (every POLL_SECONDS)
python scanner.py --dry-run  # synthetic data, no Fyers needed
streamlit run app.py         # dashboard at http://localhost:8501
```

## Files
| File | Role |
|---|---|
| `scanner.py` | hardened OI-change scanner (console) |
| `option_chain.py` | PCR · Max Pain · S/R walls · call/put-writing |
| `chart_action.py` | trend · R1/R2 · S1/S2 · continuation · 60%-body breakout |
| `signal_engine.py` | 3-layer confluence → 1 CE + 1 PE + 1 Future |
| `charts.py` | annotated candlestick chart per idea (levels + why) |
| `rrg.py` | Relative Rotation Graph (leading/lagging vs NIFTY) |
| `app.py` | Streamlit dashboard (localhost:8501) |
| `fyers_auth.py` | daily Fyers token refresh |
| `alerts.py` | optional Telegram push |
| `config.example.py` | copy → `config.py` (git-ignored) |
| `install.bat` / `create_desktop_shortcuts.ps1` | desktop icons (4, auto-refreshed) |
| `run_*.bat` | Windows launchers your shortcuts point to |

## v3.0 — Chart-Action revalidation + RRG (the "Chartonix" layer)
Your scanner now gives OI buildup **and** cross-checks it before recommending a trade —
exactly what you asked: revalidate the signals against chart action, then give **one CE,
one PE, one Future** with **3 annotated charts** that mark the levels and justify each trade.

**Three independent lenses must agree (confluence):**
1. **OI buildup** (`scanner.py`) — long/short buildup, covering, unwinding
2. **Option chain** (`option_chain.py`) — PCR, Max Pain, support/resistance walls, writing
3. **Chart action** (`chart_action.py`) — trend (e.g. *Bullish + Sideways*), **R1/R2 & S1/S2**,
   3–5 candle continuation, **60%-body breakout rule**

`signal_engine.py` fuses them into a 0–100 confidence score and emits **exactly 1 CE + 1 PE +
1 Future** (entry / stop / target / R:R + the *why*). `charts.py` renders one annotated
candlestick per idea — levels marked, entry/stop/target bands, a direction arrow and a
"WHY THIS TRADE" box.

```bash
python signal_engine.py --dry-run   # the 3 ideas in the console
python charts.py --dry-run          # writes charts/signal_{CE,PE,FUT}_*.png
python signal_engine.py             # live (needs Fyers token)
```

### RRG — Relative Rotation Graph (`rrg.py`) — **full F&O universe × OI buildup**
The StockCharts-style **2×2 rotation** of **all ~214 F&O stocks** vs NIFTY
(**Leading · Weakening · Lagging · Improving**), with a second layer the standard RRG
doesn't have — **OI buildup overlaid on every dot**:

- **Position** = price rotation (RS-Ratio x, RS-Momentum y)
- **Marker** = fresh-money direction: **▲ solid** long buildup (fresh buying) · **▲ hollow**
  short covering · **▼ solid** short buildup (fresh selling) · **▼ hollow** long unwinding
- **Confluence picks** = where price and OI agree:
  **Fresh longs** (Leading/Improving + long buildup) · **Fresh shorts** (Lagging/Weakening + short buildup)

The universe is **self-updating** (`fno_universe.py` pulls the live Fyers symbol master, so
new F&O inclusions appear automatically; a built-in fallback list keeps it working offline).

```bash
python fno_universe.py              # refresh + count the F&O stock list
python rrg.py --dry-run             # ~190-name synthetic universe -> charts/rrg.png
python rrg.py --expiry 26JUL        # live: full universe + OI overlay (Fyers token)
```

Both are also wired into the **dashboard** (`app.py`).

### Everything in one webpage (`report.py`)
One self-contained HTML page — no server, no internet — with the OI buildup table, option-chain
context, all **three ideas + their charts**, and the **RRG**. Charts are embedded, so it's a single
file you can open by double-click or email to yourself.

```bash
python report.py --dry-run          # demo -> report.html (opens in your browser)
python report.py                    # live (needs Fyers token)
```

The **Signal Desk (1 page)** desktop icon (`run_signals.bat`) builds and opens this page for you.

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
