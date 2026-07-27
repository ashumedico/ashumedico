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

## 3. Momentum
**Idea:** ride strong acceleration, don't fade it.
- Expanding candle bodies in one direction; `continuation` shows 3–5 candles same way.
- Volume rising with price; OI **Long/Short Buildup** (fresh money, not covering).
- **Trade:** enter on the thrust or first micro-pause; trail; tight time-stop. Scalp R:R ok < 1.5.
- **Guard:** momentum into Max-Pain or a heavy wall exhausts — tighten.

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
Then require **3-lens confluence** (OI × option chain × chart action) before it becomes a plan.
Confidence 0–100 (`signal_engine.evaluate`): magnitude of agreement + number of lenses aligned.
Below ~60 confidence, watchlist only — don't force it.
