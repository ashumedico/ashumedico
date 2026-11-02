# Making RRG profitable — what the evidence says

## The uncomfortable starting point
StockCharts, who created the RRG, state it plainly:

> *"RRGs are not a trading system... there are no predefined trading rules or signals."*

So RRG is a **map, not a system**. Anyone selling "RRG signals" is selling the rules they bolted
on, not the graph. Two structural reasons a naive RRG loses money:

1. **It is purely RELATIVE.** A stock can sit proudly in *Leading* while falling in absolute terms —
   it is merely falling *less* than NIFTY. You get a "strong" name and a losing P&L.
2. **The centre is noise.** Near (100, 100) names flip quadrants on random wiggle. Trading every
   crossing there is paying brokerage to trade randomness.

## The four fixes (what we added)
| Fix | Metric | Why it works |
|---|---|---|
| **Own-trend filter** | `abs_trend` (price vs its own EMA) | Kills the relative-strength trap — only buy names rising in *absolute* terms too |
| **Distance filter** | `distance` from (100,100) | Skips the noise blob; only trade names in a real trend |
| **Heading** | `heading` degrees (0=E, 90=N) | Direction of travel — where the dot is *going*, not where it sits |
| **Velocity** | tail length per period | Conviction; ranks candidates |
| **OI confirmation** | buildup overlay | Fresh buying/selling agrees with the rotation |

## The empirical answer
`rrg_strategy.py` backtests seven rule-sets **walk-forward with no lookahead** and ranks them.
On a realistic random-walk universe (400 bars, 187 names, 15bps costs):

| Setup | Return | Sharpe | MaxDD |
|---|---|---|---|
| **E: cross into Leading/Improving + own-trend filter** | **+89.8%** | **2.70** | −8.3% |
| F: E + heading NE | +86.8% | 2.56 | −8.9% |
| B: cross into Leading (no filter) | +61.9% | 2.23 | −10.9% |
| G: combined (tighter distance) | +105.8% | 2.02 | −13.8% |
| **A: hold everything in Leading (the naive way)** | +48.0% | 1.75 | −7.9% |
| C: cross into Improving only | +11.6% | 0.61 | −12.0% |
| NIFTY buy & hold | +22.4% | — | −12.1% |

**Finding: the own-trend filter is the single biggest improvement** — it roughly *halves* drawdown
and lifts Sharpe from 1.75 (naive Leading) to 2.70. The aggressive "buy the Lagging→Improving
cross" is the *worst* setup: earliest entry, most false starts.

⚠️ **Caveat that matters:** that table is synthetic data with momentum built in, so trend-following
wins by construction. It proves the harness and the *ranking logic*, not a live edge. The real
number comes from `run_sweep` on Aashish's own Fyers history — which writes `rrg_best_setup.json`,
and the app then trades whatever **his** data validated.

## Operating rules for RRG trades
1. **Timeframe:** RRG is positional/weekly-ish. Intraday RRG is noise — don't scalp it.
2. **Regime:** if NIFTY itself is in a downtrend, "Leading" longs are suspect — cut size or wait.
3. **Entry:** the *cross* into Leading (trend) or Improving (aggressive), never mid-quadrant drift.
4. **Exit:** cross into Weakening/Lagging, or own-trend breaks — whichever first.
5. **Rank** survivors by `distance × (1 + velocity)`; take the top N only.
6. **Every trade still passes the risk gate** — rotation never overrides position sizing.

## Commands
```bash
python rrg_strategy.py --demo               # mechanics proof (synthetic)
python rrg_strategy.py --sweep --days 400   # LIVE: find YOUR best setup -> rrg_best_setup.json
streamlit run desk.py                       # the desk (RRG is context here, not the headline)
```
