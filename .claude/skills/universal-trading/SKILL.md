---
name: universal-trading
description: Aashish's universal trading operating system — the Fable-class 24/7 pipeline (Research → Scan → Signal → Trade Plan → Risk → Monitor) that unifies the NSE F&O OI scanner, chart-action confluence, RRG rotation, and option-chain analytics into one doctrine. Use for ANY trading task — scanning for setups, generating a CE/PE/futures idea, building a trade plan (entry · target · stop · invalidation), sizing risk, running the RRG, reading OI buildup, or producing the one-page signal desk. Trigger on "scan the market", "any trade today?", "which option", "build a trade plan", "size this", "run the RRG", "fresh longs/shorts", "signal desk". NOT financial advice — signals are inputs, the decision is Aashish's.
---

# Universal Trading — the Fable-class 24/7 Trader

One doctrine for every trading task. Modelled on the six-stage autonomous architecture
(**Research → Scan → Signal → Trade Plan → Risk → Monitor**) and wired to the real code in
`nse-oi-scanner/`. Nothing ships as "activity" — every stage must move a decision.

> **NOT financial advice.** Signals are inputs; the trade is Aashish's. Compliance never
> overrides risk. When live data isn't reachable (no Fyers/TradingView feed on this machine),
> say so and run `--dry-run` — never fabricate prices, OI, or levels (Directive 17).

Partner agent: **`@edge-seeker`** (systematic trading, backtests, risk sizing). Convene it to
stress-test any idea before it counts as done.

---

## THE PIPELINE (each stage → a module → an output)

| # | Stage | What it does | Module (`nse-oi-scanner/`) | Output |
|---|-------|--------------|----------------------------|--------|
| 1 | **Research** | Universe + context: full F&O list, market regime, OI buildup, PCR/Max-Pain/walls | `fno_universe.py`, `scanner.py`, `option_chain.py` | who's in play + bias |
| 2 | **Scan** | Buildup matrix from day-open OI; RRG rotation vs NIFTY × OI overlay | `scanner.py`, `rrg.py` | candidate names, leaders/laggards |
| 3 | **Signal** | Score each candidate across 5 setup archetypes + 3-layer confluence | `signal_engine.py`, `chart_action.py` | scored setups (0–100) |
| 4 | **Trade Plan** | Entry · Target · Stop · Invalidation + R:R + direction/TF/confidence | `signal_engine.py`, `charts.py` | 1 CE + 1 PE + 1 Future, annotated |
| 5 | **Risk** | Hard gate: size · exposure · drawdown · volatility · max-loss → PASS/BLOCK | `risk_gate.py` (+ `references/risk-gate.md`) | approved size or BLOCK |
| 6 | **Execute + Monitor** | Paper/live orders (Fyers), manage exits, one-page desk, auto-halt | `execution.py`, `auto_trader.py`, `report.py`, `alerts.py` | fills, blotter, live desk |

**One command runs the whole desk:** `python report.py --dry-run` (demo) or `python report.py`
(live) → the one-page HTML with buildup, option chain, the 3 ideas + charts, and the RRG.

**Automated execution** (`auto_trader.py`): the same pipeline, hands-free — **paper by default,
live only when armed.** A real order fires *only* if `LIVE_TRADING=True` **and** no kill-switch file
**and** a valid token **and** the risk gate passed. Kill switch = create `STOP_TRADING.txt`. Never
flip to live without a paper track record (Directive 12: pause on anything that touches money).

---

## STAGE 1 · RESEARCH — what's in play

- **Universe:** `fno_universe.fno_stocks()` — the full ~214 F&O list, self-updating from the
  Fyers/NSE symbol master (fallback list offline). Never trade a name in the **F&O ban list**.
- **Context bias:** option chain (`option_chain.analyse`) → **PCR** (>1.2 bullish, <0.7 bearish),
  **Max Pain** (where writers pin expiry), **Support/Resistance walls** (highest Put/Call OI),
  fresh **call/put writing**.
- **News/regime:** flag events (results, RBI, expiry day). No fresh positions into a known binary.

## STAGE 2 · SCAN — where the money is moving

- **OI buildup (from day-open, not last poll):** `scanner.classify(price%, oi%)` →
  **Long Buildup** (↑↑ bullish) · **Short Buildup** (↓↑ bearish) · **Short Covering** (↑↓ bullish) ·
  **Long Unwinding** (↓↓ bearish). Confirm with **rising volume** (`VOL✓`).
- **RRG rotation:** `rrg.py` plots all ~214 stocks vs NIFTY (Leading/Weakening/Lagging/Improving)
  **with OI overlay** on every dot (▲ buying / ▼ selling, solid = fresh money). The edge is the
  **confluence** (`rrg.confluence`): **Fresh Longs** = Leading/Improving + Long Buildup ·
  **Fresh Shorts** = Lagging/Weakening + Short Buildup.

## STAGE 3 · SIGNAL — score the setup

Detect and **score** (rank by probability), don't just spot. The five archetypes
(`references/setups.md` for detection logic):

| Setup | Trigger | Direction |
|-------|---------|-----------|
| **Breakout** | price breaks a key level with a 60%-body candle | with the break |
| **Pullback** | temporary pullback into support/resistance inside a trend | with the trend |
| **Momentum** | strong price acceleration (expanding bodies + volume) | with the thrust |
| **Trend continuation** | trend holds structure (HH-HL / LH-LL) and resumes | with the trend |
| **Reversal** | exhaustion + structure break at a wall | against the old trend |

**Confluence score** = 3 independent lenses must agree (`signal_engine.evaluate`):
OI buildup **×** option chain (PCR/Max-Pain/walls) **×** chart action
(trend + R1/R2 · S1/S2 + 60%-body breakout). Confidence 0–100; only act on agreement.

## STAGE 4 · TRADE PLAN — four numbers, always

Every idea carries all four or it doesn't exist:

- **Entry zone** — optimal range (at support for longs, resistance for shorts)
- **Target** — next structural level / wall (R:R must clear the risk)
- **Stop** — beyond the invalidating structure
- **Invalidation** — the price that says the thesis is wrong (flatten, no averaging)

Plus **Direction · Timeframe · Confidence · R:R** (reject R:R < 1.5 unless momentum-scalp).
`signal_engine.build_ideas` emits exactly **one CE, one PE, one Future**; `charts.py` renders each
with levels marked and the "why" on the chart.

## STAGE 5 · RISK — the gate that can say NO

The risk module **checks everything and can BLOCK any trade** — it is not advisory.
Run all five; **any FAIL → BLOCK** (full logic + formulae in `references/risk-gate.md`):

1. **Position size** — sized from *risk per trade* (default ≤1% of capital ÷ stop distance)
2. **Exposure limit** — total across open positions within cap; no over-concentration
3. **Drawdown control** — within the day/week drawdown threshold, else stand down
4. **Volatility check** — spread/VIX/ATR acceptable for the setup
5. **Max loss** — worst-case (incl. gap) will not breach the hard loss limit

`PASS → continue · FAIL → block.` Protecting capital beats catching every move.

## STAGE 6 · MONITOR — always on, honest

- **The desk:** `report.py` → one webpage (also `app.py` dashboard, `run_signals.bat` icon).
- **Cadence:** re-scan on `POLL_SECONDS`; alerts on strong buildups (`alerts.py`, config-gated).
- **Invalidate ruthlessly:** when an invalidation level breaks, the plan is dead — record it and move on.
- **Record:** log signals (`signals_YYYYMMDD.csv`) so the system learns; graduate repeat edges into this skill.

---

## OPERATING RULES (Fable-class)

1. **Confluence or nothing.** No single-lens trades. Price *and* OI *and* structure must agree.
2. **Four numbers or no trade.** Entry, Target, Stop, Invalidation — every time.
3. **Risk gate is a veto.** Stage 5 can kill a 95%-confidence idea. Let it.
4. **Impact, not activity.** More scans ≠ more edge. One A+ setup > ten B setups (Directive 4).
5. **Honesty on data (Directive 17).** No live feed → say it, run `--dry-run`, never invent numbers.
6. **Verify to 92% (Directive 3).** Before calling a plan "ready", stress it via `@edge-seeker`
   (Red-Team the thesis, the stop, the R:R). Ship only what survives.
7. **Divergence first (Directive 8).** For a market call, give the Obvious, the Contrarian, the 10x,
   then recommend one with reasoning.
8. **One next action (Directive 14).** End every trade brief with a single **Next:** line.

---

## QUICK INVOCATIONS

```bash
python report.py --dry-run                 # whole desk, one webpage (demo)
python scanner.py --dry-run                # OI buildup matrix
python signal_engine.py --dry-run          # 1 CE + 1 PE + 1 Future
python rrg.py --dry-run                    # full-universe RRG + fresh longs/shorts
python option_chain.py --dry-run           # PCR · Max Pain · walls
```
Live: drop `--dry-run` after a feed is connected (Fyers token, or TradingView-MCP on the PC).

**Provenance:** architecture adapted from the public "24/7 AI Trader · Fable 5" concept
(seb.ai) and fused with Aashish's own OI-buildup + option-chain + chart-action + RRG stack.
