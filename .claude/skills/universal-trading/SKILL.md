---
name: universal-trading
description: Aashish's universal trading operating system — the Fable-class 24/7 pipeline (Scan → Signal → Trade Plan → Risk → Monitor) wired to the NSE F&O options stack in nse-oi-scanner/. Use for ANY trading task — scanning for setups, picking an ATM CE/PE, building a trade plan (entry · target · stop · invalidation), sizing, reading OI buildup or the option chain, running the paper/live session, or opening the desk. Trigger on "scan the market", "any trade today?", "which option", "build a trade plan", "size this", "fresh longs", "check-in", "paper", "desk". NOT financial advice — signals are inputs, the decision is Aashish's.
---

# Universal Trading — the Fable-class 24/7 Trader

One doctrine for every trading task: **Scan → Signal → Trade Plan → Risk → Monitor**, running
as a loop that never fully stops. Wired to the real code in `nse-oi-scanner/`.

> **NOT financial advice.** Signals are inputs; the trade is Aashish's. When live data isn't
> reachable, say so and run the demo path — never fabricate prices, OI, lots, or levels
> (Directive 17).

Partner agent: **`@edge-seeker`**. Convene it to try to *disprove* an idea before it counts as done.

---

## THE STANDING FRAME (his rules, not defaults)

These are decisions Aashish has already made. They are not tunable by inference.

| | |
|---|---|
| **Instrument** | **Options only, BOUGHT only.** LONG = **buy CE**. SHORT = **buy PE**. Never *sell* an option — writing is a margin position with open-ended risk and it is not what this system does. Max loss is always the premium. |
| **Style** | **Intraday**, 15-minute candles. Carry only when he says so. |
| **Strike** | **ATM** (delta ≈ 0.50). Gamma is the point; deep ITM is a slower proxy for the stock. |
| **Size** | **1 lot. Fixed.** Quantity is a decision, never an output of the risk budget. |
| **Short book** | Built and mirrored; **display only** until `TRADE_SHORTS=True`. The edge is unmeasured on his data. |
| **Expiry** | Near month. Roll to the next series once the running one has **< 15 days** left. |
| **Entry** | The **first expansion bar** — the bar a coil breaks. Not the fifth bar of a move. |
| **Exit** | ATR stop, **trailing from the high-water mark, ratchet only**. Breakeven is a *floor*, never an overwrite of a stop that already trailed higher. |
| **Mode** | **Paper and live at the same time**, always. Paper is the scorecard; live is armed separately. |
| **Capital** | `config.CAPITAL`. One trade at a time unless told otherwise. |

Changing any of these is a conversation, not a code change.

---

## THE PIPELINE (each stage → a module → an output)

| # | Stage | What it does | Module (`nse-oi-scanner/`) | Output |
|---|-------|--------------|----------------------------|--------|
| 1 | **Scan** | Universe + regime + what moved: F&O list, market state, day-open OI buildup | `fno_universe.py`, `market_regime.py`, `scanner.py` | tradeable? + candidate names |
| 2 | **Signal** | Features per name per bar → the five setup archetypes | `features.py`, `indicators.py`, `chart_action.py`, `rrg_strategy.py` | scored, gated candidates |
| 3 | **Trade Plan** | Contract, entry, stop, T1/T2, invalidation, R:R, cost | `trade_card.py`, `option_chain.py`, `charges.py`, `option_pnl.py` | one ticket, priced |
| 4 | **Risk** | Five checks, any FAIL → BLOCK | `references/risk-gate.md`, `trade_card.py`, `broker.py` | approved or blocked |
| 5 | **Monitor** | Paper + live, bar-by-bar trail, timeout, square-off, score | `paper.py`, `checkin.py`, `desk.py` | fills, blotter, P&L vs backtest |

**Daily commands** — the same four icons in `AASHISH TRADING OS`:

```bash
python fyers_auth.py          # 1 - START DAY : token, lot check, check-in
python checkin.py             # 2 - CHECK-IN  : what to hold / book / buy
streamlit run desk.py         # 3 - DESK      : the website
python paper.py --session     # 4 - PAPER LIVE: every candle, hands-free
```

Live orders fire **only** when `LIVE_TRADING=True` **and** `STOP_TRADING.txt` is absent
**and** the token is valid **and** the risk gate passed. Kill switch: create `STOP_TRADING.txt`.

---

## STAGE 1 · SCAN — is the tape worth trading, and who is in play

- **Universe:** `fno_universe.fno_stocks()` — the live F&O list with **lot sizes parsed from the
  symbol master by data shape**, not a fixed column (that bug once produced a 13-lot COFORGE).
  Never trade a name in the ban list.
- **Regime:** `market_regime.Regime` — breadth · trend · vol · drawdown, answered from the last
  **closed** session, and folded to daily when the feed is intraday. RISK-OFF is not a veto by
  itself; it is a size-down.
- **OI buildup** (from day-open, not last poll): `scanner.classify(price%, oi%)` →
  Long Buildup ↑↑ · Short Buildup ↓↑ · Short Covering ↑↓ · Long Unwinding ↓↓.
  **Displayed and journalled, never backtested** — there is no historical OI series in this
  system, so anything claiming to have tested buildup is claiming the impossible.
- **Option-chain context:** `option_chain.analyse` → PCR, Max Pain, the Call/Put walls.

### Fundamental watchlists (`watchlist.py`)

When a fundamental idea sheet arrives — Q1 results, sector triggers, guidance — run it
through `python watchlist.py` **before discussing any of it as a trade**:

1. **Options exist only on F&O names.** Most small caps are not in F&O at all. Of the Q1
   FY27 sheet, **4 of 39** were tradeable as options. A thesis on a name with no option
   chain is a cash trade or nothing, and saying so first saves the whole conversation.
2. **Membership comes from the live symbol master, never from memory.** The F&O list is
   revised twice a year. If the master could not be fetched, say the answer is off a stale
   snapshot rather than delivering it confidently.
3. **Never guess a ticker.** Fuzzy matching once paired "ICICI Pru AMC" with **ICICIPRULI**
   — a different company — and missed **AUBANK** entirely. A near-miss is not a bad row on
   a screen; it is an order in the wrong stock. Unknown ticker → say unknown, ask.
4. **A fundamental trigger does not time a 15-minute expansion bar.** It is a **bias** that
   can narrow the universe. It is displayed, tagged, and never sized on.
5. **NOT TESTED, permanently.** There is no point-in-time fundamentals data here, so
   "trade only watchlist names" cannot be walk-forward tested — the same category as OI
   buildup. Not passed, not failed.
6. **Guidance and results are binary events.** No fresh positions into one.

## STAGE 2 · SIGNAL — score the setup

`features.at()` produces one dict per name per bar, computed **strictly from bars before the
decision bar**. A missing feature is a **fail**, never a pass (`features.passes`).

The features that survived: **VWAP** (above/below, session-reset) · **RVOL** (own norm) ·
**ATR** · **squeeze** (short TR ÷ long TR) · **expansion** (was coiled, this bar is wide) ·
**R1/R2 · S1/S2** with room-to-resistance in ATRs · **continuation** (up-candles in a row, not
"some continuation" — a run of down candles is continuation too, and it is the opposite trade) ·
**breakout** (60%-body rule) · **trend structure** (HH-HL / LH-LL).

Deleted on purpose: **Supertrend** (agreed 91% with the EMA filter — a second vote from the
same voter) and **CCI**. **RRG rotation** measured **-6.3% after costs** in walk-forward and is
therefore **context on the desk, not a trigger**. Own-trend momentum is what the walk-forward kept.

The five archetypes (detection logic in `references/setups.md`):

| Setup | Trigger | Direction |
|-------|---------|-----------|
| **Breakout** | closes through a level with a 60%-body candle | with the break |
| **Pullback** | pullback into S1 (long) / R1 (short) inside a trend | with the trend |
| **Momentum** | the first expansion bar out of a coil, RVOL confirming | with the thrust |
| **Trend continuation** | structure intact, resumes after a pause | with the trend |
| **Reversal** | exhaustion at a wall + structure break | against the old trend |

**Never enable an untested filter.** The RRG is the standing precedent. NOT TESTED and
FAILED are different verdicts and must be reported differently.

## STAGE 3 · TRADE PLAN — four numbers, and what it costs

Every idea carries all four or it does not exist:

- **Entry zone** — the expansion bar's range, not a wish
- **Target** — T1 / T2 at ATR multiples, T1 books half and raises the stop to breakeven *if that
  is higher than the trail*
- **Stop** — entry − mult × ATR, trailing from the high-water mark
- **Invalidation** — the price that says the thesis is wrong. Flatten. No averaging.

Plus **Direction · Timeframe · Confidence · R:R** (reject R:R < 1.5 unless it is a momentum scalp).

**The contract is real or there is no ticket.** `option_chain.tradeable_chain()` supplies the
`symbol`, the strike and the **lot size from the chain itself**. Cross-check before quoting a
number: a lot that implies a contract value outside the SEBI band (**stock F&O ₹5–10 lakh**,
index ₹15–20 lakh) is wrong — check it against NSE and the broker, do not defend it.
Refuse to emit a zero-quantity ticket.

**Cost is part of the plan** (`charges.py`, verified rates in `references/nse-options-mechanics.md`):
STT 0.15% sell-side, exchange ₹35.03/lakh, SEBI 0.0001%, stamp 0.003% buy-side, GST 18%,
brokerage ₹20/order. `option_pnl.breakeven_move()` says how far the stock must move before the
trade is even.

## STAGE 4 · RISK — the gate that can say NO

Five checks. **Any FAIL → BLOCK** (full logic in `references/risk-gate.md`):

```
RISK CHECK  →  Position size · Exposure · Drawdown · Volatility · Max loss
              PASS → continue        FAIL → block
```

1. **Position size** — **fixed at `LOTS_PER_TRADE` (1).** The risk budget is a **veto**, not a
   sizer: if one lot costs more than the trade is allowed to lose, the answer is *no trade*, not
   *nine lots*. (That bug once proposed ₹2.46L of premium on ₹2L of capital.)
2. **Exposure** — total deployed within cap; one position at a time by default.
3. **Drawdown** — inside the day/week limit, else stand down. No revenge trades.
4. **Volatility** — spread not blown out, IV not spiking into a binary, expiry-day gamma respected.
5. **Max loss** — for buying, max loss *is* the premium; the premium must fit the cap.

Protecting capital beats catching every move. Log every BLOCK — the blocks are data too.

## STAGE 5 · MONITOR — always on, honest

- **The loop:** `paper.py --session` polls every `WATCH_SECONDS`, marks open trades, ratchets the
  trail bar by bar, honours the **bar-based** timeout, and squares off at `SQUAREOFF`.
- **Time is counted in market minutes**, not wall-clock: Fri 15:00 → Mon 09:45 is 60 minutes, not
  four thousand. A timeout in calendar days fires every weekend.
- **Live beside paper:** the same decision writes a paper record and, when armed, a real order.
- **Score:** `desk.py` shows realised P&L against what the backtest claimed, with a binomial band —
  a small sample inside the band is *neither proof nor problem*.
- **Record:** every signal is journalled so the system can be graded later.

---

## OPERATING RULES (Fable-class)

1. **Confluence or nothing.** Trend *and* volume *and* structure. No single-lens trades.
2. **Four numbers or no trade.** Entry, Target, Stop, Invalidation — every time.
3. **The risk gate is a veto.** It can kill a 95%-confidence idea. Let it.
4. **Never enable an untested filter.** RRG −6.3% is the precedent.
5. **Say NOT TESTED when it is not tested.** It is not the same as passed, and not the same as failed.
6. **Check the number, don't defend it.** If a lot, a premium or an expiry looks wrong to him, it
   probably is — go to NSE and the broker before arguing.
7. **Honesty on data (Directive 17).** No feed → say it, run demo, never invent.
8. **Verify to 92% (Directive 3).** Stress via `@edge-seeker` before calling anything ready.
9. **One next action (Directive 14).** End every trade brief with a single **Next:** line.

---

---

## LESSONS THAT COST SOMETHING (add to this list, never trim it)

Each of these was a real failure in this codebase. They are here because the same shape
recurs, and recognising the shape is faster than rediscovering the bug.

1. **Two implementations of one rule will disagree, and you find out live.**
   The backtest ranked candidates one way and the live selector another - weeks of
   trading a strategy nobody had tested. Later the card backtest recomputed `abs_trend`
   in an "obviously equivalent" shorter form; replacing it with the real `build_points`
   moved the result from −₹446 to +₹997. **Call the function. Never restate it.**
   `paper.step()` is now the single exit contract, shared by the live loop and the
   backtest.

2. **A statistical tie-break will pick the wrong column by construction.**
   The lot parser chose "the column with the most distinct values". Freeze quantity has
   the same *shape* as lot size but is nearly unique, while lot sizes repeat - so that
   rule prefers freeze **every time**. MCX came back as 31,181 when its lot is 25.
   Fixed by an **economic** test: price × lot must land near a ₹5-10 lakh contract.
   Same trap, smaller: sector "drivers" weighted move × correlation, and a 9% move at
   r=0.30 still outranked 3% at r=0.85. **Correlation must gate before it weights.**

3. **A poisoned cache never heals itself.** Freeze quantities pass every plausibility
   check - numeric, varied, in range. Version the cache filename; that is the only thing
   that guarantees the bad file is not read again.

4. **A swallowed exception turns one fault into two hundred identical lines.**
   `except: lot = None` made an expired token, a rate limit and a bad symbol print the
   same message across the whole universe. Show the first error verbatim, and cap
   fan-out API calls - a broken parse otherwise becomes hundreds of throttled requests.

5. **Say which failure it was.** "The chain gave nothing" and "the chain gave a lot the
   band rejects" are different facts; the second is the case where the *band* is wrong.

6. **Mirror at the source, not at the display layer.** The short book gets its stop,
   targets, put intrinsic and premium from `build_card(side="SHORT")`. Assembling a
   short card in the UI would have priced a put off a call's stop. Every
   direction-bearing comparison flips: `px <= stop` stops out a fresh put instantly, and
   a put's high-water mark is its *lowest* print.

7. **Fix the class, not the instance - even when it is unreachable.** The put-marking
   bug sat behind `TRADE_SHORTS=False`. A flag is one keystroke from real money.

8. **The backtest must obey the same constraints as the account.** `PRODUCT_TYPE` is
   INTRADAY, so the live engine flattens at 15:15 - a backtest that carried overnight
   scored trades the account could never have held. Detect intraday from **BAR_MINUTES**
   (what the engine itself asks), not from "do any dates repeat"; a cycling date series
   satisfies that and squares off every bar.

9. **Prove no-lookahead by experiment.** Asserting "we sliced with `[:t]`" is not proof.
   Poison every bar after a cut with noise; the run must be identical to the last rupee.

10. **A control that does nothing is worse than no control**, because it gets trusted.
    The price band was wired into the actual universe filter the same hour the field
    appeared.

11. **Never offer a source that cannot answer.** StockCharts covers US/Canada, not NSE -
    linking it would be a dead link dressed as a feature.

12. **Say what cannot be tested.** OI buildup and fundamental watchlists have no
    historical series here, so they are permanently NOT TESTED - not passed, not failed.
    Sector strength and the scorecard *weighting* are the same.

13. **Empty is an answer. Zero is a different claim.** An empty heatmap means "no data";
    0.00% means "did not move". Never render the second when you have the first.

14. **Screenshot the UI instead of assuming it.** That is what caught the wordmark being
    clipped - a glow renders above the cap height and the container silently cuts it.

15. **A one-press order button is one stray scroll-click from a position he did not
    choose.** Every order control on the desk ARMS on the first press, shows the exact
    request, and fires on the second - disarming itself after 20 seconds. That is not
    overriding "trade live"; it is how an order ticket works everywhere, and it costs one
    click for the only thing that cannot be undone.

16. **A stop with no trigger is a market order in disguise** - it fires instantly and
    looks exactly like the stop being hit. `place()` refuses it.

17. **A resting exchange stop and a trailing stop are complements, not substitutes.**
    The session loop's trail ratchets and dies with the window; an SL-M resting at Fyers
    survives a closed laptop and cannot trail. Place both.

18. **A guard defeated by its own placeholder is worse than no guard.** The order button
    checked `payload.get("symbol")` and the caller passed `sym or "-"` for display -
    `"-"` is truthy, so the guard read as protection on screen and never fired. Check the
    placeholder too, and never let display formatting reach a safety test.

19. **Sanity bands must be checked from BOTH sides.** The contract-value check only
    tested "too small" (COFORGE at 13). The freeze-quantity bug fails the other way -
    PERSISTENT at lot 18,365 is a ₹102 CRORE contract - and a one-sided check waved it
    straight through to a live order button. An absurd quantity now blocks every button
    on that ticket.

20. **Design hierarchy is a safety feature.** Three equal buttons in a half-width column
    wrapped "CANCEL" onto three lines and crushed the confirm sheet at the exact moment
    it had to be readable. One number, one primary action, everything else quieter and
    full width.

21. **Measure every level from the ENTRY, never from spot.** The card set its stop and
    targets off spot while the entry was a limit somewhere else, so every figure that
    divides by risk was wrong by the gap between them - it printed R:R 1.5 where the real
    number at the stated entry was 1.20. If he enters where the card says, the numbers
    have to be his.

22. **Derive ordered things from one formula.** T1 and T2 came from vol, T3 from R, and
    T3 landed BETWEEN them - a level labelled "third target" that was second-furthest.
    All three are R-multiples now (1.5R / 3R / 4R), so their order is arithmetic rather
    than luck.

23. **Wrong numbers do not announce themselves. They look like numbers.** Consistency is
    testable even when correctness is not: stop on the losing side of entry, targets
    stepping away in order, printed R:R equal to actual R:R, option levels off the same
    entry as the stock levels. `test_card_math.py` asserts all of it on three price
    scales and both directions.

24. **Language: the chat is Hinglish, the product is English.** Code, commits, the
    website and any MLR/UCPMP content stay English. A half-translated screen reads as
    careless.

25. **A guard firing on every single item is not a guard, it is a missing input.** Every
    order button on every ticket was permanently greyed out, and the guard was right:
    there was no contract to send. The desk called `build_card()` with **no chain at
    all**, so `option_from_chain()` searched nothing and the tradeable symbol came back
    None - for every name, always. Three buttons x twelve tickets of correct behaviour
    over a hole. When a check never passes for anything, stop auditing the check and go
    find what was never supplied.

26. **A disabled control has to say which of its reasons it is.** Kill switch on, no
    token, no F&O series, absurd quantity - four different problems, four different
    fixes, and one identical grey button. The button now carries the reason it is dead.

27. **Fetch the chain and the lot size comes with it.** The live option chain carries the
    exchange's own lot - the one number the symbol-master parser keeps confusing with
    freeze quantity. Fetching contracts for the ticket fixed the quantity as a side
    effect, which is what happens when data comes from where it is authoritative.

28. **Screens are sized in screens, not in pixels.** A 21-inch desktop is ~1900x950. The
    page was capped at 1500px wide and ran 6000px tall: a fifth of the width thrown away
    and paid for in scroll, so the ticket and the evidence for it could never be visible
    together. Five tabs, each measured against 940px of viewport in the browser, full
    width, margins shrunk - and the type size left alone. On a trading screen you shrink
    the margins, never the numbers.

29. **A "row" of Streamlit metrics beside tall HTML is not a row.** Six `st.metric`s next
    to a 2rem wordmark stacked, grew the row to the tallest child, and pushed the scan
    button off the right edge. Things that must sit on one line belong in one element
    whose CSS knows they are on a line together. The screenshot found it; the code
    review before it did not.

30. **Measure the layout, do not eyeball it.** "Looks about right" cost three rounds.
    Printing each tab's `scrollHeight` against the viewport turned it into arithmetic:
    signals 2124 → 1537 → 1242 → 1143 → fits, and at each step the number said which
    change had actually paid. `test_layout.py` keeps it honest, and it subtracts the
    demo-only banners **out loud** rather than quietly - an adjusted number that hides
    its adjustment is the same lie as a wrong one.

31. **Ask the DOM which element is expensive.** Guessing which block to cut wasted two
    rounds; enumerating every child's height took one query and found a three-line
    caption costing 45px on a tab that was 29px over. The most expensive thing on the
    page is rarely the thing that looks big.

32. **A demo that cannot exercise a path cannot prove that path.** The synthetic market
    opened every session at exactly the previous close (`o = prev`), so no name could
    ever gap - and the new gap screen printed "nothing passes" on it, which reads as an
    observation and was an impossibility. Empty results have to be checked against
    whether the data COULD have produced a non-empty one. The demo gaps now, and the
    screen states how many names gapped at all beside its own count.

33. **A rewritten screener must mean what the original meant.** Four ways it silently
    stops: the SMA window slides (Chartink's `Sma(1 day ago Close, 20)` ends YESTERDAY -
    include today and a big up-day drags up its own benchmark); the strict `>` becomes
    `>=` at a band edge; a clause that cannot be evaluated gets skipped instead of
    failed; too little history passes on a partial mean. `test_gapup.py` pins all four.

34. **A screen is not an edge, and the screen has to say so.** The gap filter is his,
    not tested here, and it lives in its own tab rather than intersecting the signal
    book - crossing them would produce a list that is neither, with the authority of
    both. Thresholds go in the sidebar, not the source: a number he has to ask me to
    change is a number he will stop questioning.

35. **"Why is your list different?" is answered with numbers, not with an argument.**
    Two screens running identical rules disagree at the BAND EDGES - a 0.98% gap and a
    1.02% gap are the same event on opposite sides of a threshold, and two feeds do not
    agree to the paisa on yesterday's close. So the tab shows **near misses** (failed
    exactly one clause, and by how much) and `gapup.py --explain NAME` prints this
    system's prev close, open, mean and every verdict. The question becomes *whose
    previous close is right*, which is answerable.

36. **Measure "how close" on the clause that failed.** The first near-miss list ranked a
    name that failed the SMA test by how far its GAP was from the band - a number with
    nothing to do with the rejection. It looked like an answer and sorted by noise.

---

## REFERENCES

- `references/setups.md` — the five archetypes, condition by condition
- `references/risk-gate.md` — the five checks, formulae, config keys
- `references/nse-options-mechanics.md` — lot sizes, SEBI bands, verified charges, with sources
- `references/rrg-profitable-setup.md` — what the walk-forward kept, and what it threw away
- `tradingview/AashishMomentum.pine` — the same rules on a chart, bar by bar, arguable

**Provenance:** the five-stage architecture follows the public "24/7 AI Trader · Fable 5"
concept, fused with Aashish's own OI-buildup + option-chain + chart-action stack and cut down
to what survived his walk-forward.
