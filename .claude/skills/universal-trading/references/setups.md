# Setup archetypes — detection logic

The Signal Engine flags five high-probability setups. Each maps to concrete, testable
conditions on the candle series (`chart_action.analyse`) and the OI/option-chain context.
Score = how many conditions fire × confluence with OI + walls.

## 1. Breakout
**Idea:** price breaks a level that has held, with conviction.
- Price closes **through R1/S1** (a clustered pivot level from `support_resistance`).
- Breakout candle **body ≥ 60%** of its range (`body_breakout`, the 60%-body rule).
- Volume expands on the break; OI shows **fresh buildup** in the break direction.
- **Trade:** enter on break/retest; target R2/S2 (measured move); stop back inside the range.
- **Trap to avoid:** low-volume break into a Call/Put wall = likely fade.

## 2. Pullback
**Idea:** buy the dip in an uptrend / sell the bounce in a downtrend.
- Primary trend Bullish (HH-HL) or Bearish (LH-LL) from `trend()`.
- Price pulls back **into S1** (long) or **into R1** (short) — the `_near` proximity check.
- Momentum of the pullback is fading (shrinking counter-trend bodies).
- **Trade:** enter at the level; stop beyond S2/R2; target prior swing / R2 / S2. Best R:R setup.

## 3. Momentum  ← **the one this system actually trades**
**Idea:** be in on the bar the move starts, not the bar everyone can see it.
- **Squeeze then expansion** (`indicators.squeeze`, `indicators.expansion`): the name was coiled
  on the *previous* bar (short-window TR ÷ long-window TR below the coil threshold) and *this*
  bar is wider than the long-window norm. Using this bar for both would be asking the break to
  have happened before it happened.
- `continuation` counts **up-candles in a row** for a long — a run of down candles is
  continuation too, and it is the opposite trade.
- Volume rising with price (`rvol` above its minimum); price above session **VWAP**.
- OI **Long/Short Buildup** if visible — context, not a gate (no historical OI series to test it).
- **Trade:** enter on the **first expansion bar**. Stop at entry − mult × ATR, then **trail from
  the high-water mark, ratchet only**. Tight bar-count timeout — dead money is a cost.
- **Guard:** momentum into Max-Pain or a heavy wall exhausts — tighten.
- **Not a thing:** "enter before momentum starts." Nobody does that. The first expansion bar is
  the earliest honest entry, and that is what this marks.

## 4. Trend continuation
**Idea:** the trend holds structure and resumes after a pause/consolidation.
- Structure intact (`structure` = HH-HL or LH-LL), no lower-low (up) / higher-high (down).
- Consolidation near a prior breakout level (old resistance = new support).
- OI buildup persists in the trend direction; RRG shows the name **Leading/Improving** (up) or
  **Lagging/Weakening** (down).
- **Trade:** enter on resumption; target the next measured leg; stop under the consolidation.

## 5. Reversal
**Idea:** a turn, not a continuation — the hardest, needs the most confirmation.
- Exhaustion at a **wall** (highest Call OI for a top, highest Put OI for a bottom).
- Structure break: first HH broken in a downtrend / first LL broken in an uptrend.
- OI flips: fresh **Short Covering** at a bottom / **Long Unwinding** at a top, then opposite buildup.
- Divergence (price new extreme, momentum not).
- **Trade:** enter only after the structure break confirms; wide-ish stop beyond the extreme;
  target the mean (Max Pain) then the opposite wall. Never anticipate — confirm.

---

### Scoring
For a candidate, count fired conditions per archetype and take the best-fitting setup.
Then require **3-lens confluence** (trend × volume × structure) before it becomes a plan —
`features.passes` is the gate, and a **missing feature is a fail, never a pass**. Below
rough agreement across the three, watchlist only — don't force it.

An archetype that has never been walk-forward tested is **NOT TESTED**, which is neither a
pass nor a fail, and must be reported as neither. OI buildup is permanently in that
category here: there is no historical open-interest series in this system to test it with.
