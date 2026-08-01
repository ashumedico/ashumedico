"""
test_gapup.py  —  the Chartink screen has to mean here what it means there.

Four ways a rewritten screener quietly stops being the same screener:

  1. The SMA window slides. "1 day ago Sma(1 day ago Close, 20)" is the mean of the
     closes ENDING YESTERDAY. Use closes[-20:] instead of closes[-21:-1] and today's
     close is inside its own benchmark - a big up-day then drags up the very line it is
     being measured against, and the test weakens exactly when it should bite.
  2. The band boundary flips. Chartink's ">" is strict. A name opening at exactly
     prev_close * 1.01 does NOT pass, and an implementation using >= lets in the whole
     edge of the distribution.
  3. A clause that cannot be evaluated gets skipped instead of failed. "I could not
     check" and "it checked out" are different claims; only one may let a name through.
  4. Not enough history is treated as a pass because the mean came back as something.

    python test_gapup.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gapup as G

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def bars(closes, last_open=None):
    """Daily candles from a close series; the last candle's open can be forced."""
    b = [[i, c, c * 1.01, c * 0.99, c, 1000] for i, c in enumerate(closes)]
    if last_open is not None:
        b[-1][1] = last_open
    return b


def main():
    print("\n  GAP-UP SCREEN")
    print("  " + "-" * 62)

    # ---- 1. the SMA window ---------------------------------------------------
    # 20 closes of 100, then a close of 200. The mean ENDING YESTERDAY is 100.
    # A mean that included today would be ~104.8 - both are above nothing, so the
    # window is tested directly rather than through the verdict.
    flat = [100.0] * 21 + [200.0]
    row = G.daily_row(bars(flat), sma_len=20)
    check("SMA is the mean ending YESTERDAY, not including today",
          abs(row["sma_prev"] - 100.0) < 1e-9, f"got {row['sma_prev']}")
    check("today's close is the one being compared", row["close"] == 200.0)

    # ---- 2. the band, at its exact edges --------------------------------------
    base = [100.0] * 25
    for open_px, want, why in ((101.0, False, "exactly 1.01x - Chartink's > is strict"),
                               (101.5, True, "inside the band"),
                               (102.0, False, "exactly 1.02x - < is strict"),
                               (101.999, True, "a hair inside"),
                               (100.9, False, "gap too small"),
                               (103.0, False, "gap too big")):
        b = bars(base + [open_px * 1.001], last_open=open_px)
        ok, _ = G.passes(G.daily_row(b))
        check(f"open {open_px} -> {'pass' if want else 'fail'}", ok is want, why)

    # ---- 3. the trend clause has to be able to fail ---------------------------
    falling = [200.0 - i * 4 for i in range(25)]
    b = bars(falling, last_open=falling[-2] * 1.015)
    b[-1][4] = falling[-2] * 1.016                    # gapped up, still under the mean
    ok, cls = G.passes(G.daily_row(b))
    check("a name below its own 20-day mean fails even on a perfect gap", not ok,
          next(c["detail"] for c in cls if "SMA" in c["clause"]))

    # ---- 4. the intraday gate -------------------------------------------------
    b = bars([100.0] * 25 + [101.6], last_open=101.5)
    cfg = {"use_intraday_gate": True}
    ok, cls = G.passes(G.daily_row(b), cfg, last_intraday=102.0)
    check("gate ON, holding above the open -> passes", ok)
    ok, cls = G.passes(G.daily_row(b), cfg, last_intraday=101.0)
    check("gate ON, sold below the open -> fails", not ok)
    ok, cls = G.passes(G.daily_row(b), cfg, last_intraday=None)
    check("gate ON with NO intraday bar -> fails, is not skipped", not ok,
          next(c["detail"] for c in cls if "15-min" in c["clause"]))
    ok, _ = G.passes(G.daily_row(b), {"use_intraday_gate": False}, last_intraday=None)
    check("gate OFF (as he has it) -> the same name passes", ok)

    # ---- 5. not enough history is a failure with a reason ---------------------
    short = bars([100.0] * 8, last_open=101.5)
    check("too little history yields no row", G.daily_row(short) is None)
    ok, cls = G.passes(G.daily_row(short))
    check("and it fails rather than passing on a partial mean", not ok,
          cls[0]["detail"])

    # ---- 6. every clause is named, always -------------------------------------
    ok, cls = G.passes(G.daily_row(bars([100.0] * 25 + [101.6], last_open=101.5)))
    check("three clauses when the gate is off", len(cls) == 3)
    check("each clause carries the numbers that decided it",
          all(c.get("detail") and "clause" in c and "ok" in c for c in cls))

    # ---- 7. scan: naming, sorting, and who is left out -----------------------
    db = {
        "NSE:HELD-EQ":  bars([100.0] * 25 + [103.0], last_open=101.5),   # +1.48% from open
        "NSE:FADED-EQ": bars([100.0] * 25 + [101.0], last_open=101.5),   # -0.49% from open
        "NSE:OUT-EQ":   bars([100.0] * 25 + [105.0], last_open=104.0),   # gap too big
    }
    pts = [{"symbol": "NSE:HELD-EQ", "name": "HELD"},
           {"symbol": "NSE:FADED-EQ", "name": "FADED"}]
    rows = G.scan(db, pts)
    check("only the names inside the band are returned",
          [r["name"] for r in rows] == ["HELD", "FADED"],
          str([r["name"] for r in rows]))
    check("held-the-gap ranks above faded-the-gap",
          rows[0]["from_open_pct"] > rows[1]["from_open_pct"],
          f"{rows[0]['from_open_pct']}% then {rows[1]['from_open_pct']}%")
    check("a symbol with no point still gets a readable name",
          G.scan({"NSE:NOPOINT-EQ": db["NSE:HELD-EQ"]}, [])[0]["name"] == "NOPOINT")
    check("the gap percent is reported, not just the verdict",
          abs(rows[0]["gap_pct"] - 1.5) < 0.01, f"{rows[0]['gap_pct']}%")

    # ---- 8. near misses: the tool for "why is your list different" -----------
    # A near-miss list is only useful if "how badly it missed" is measured on the clause
    # that actually failed. Ranking a name that failed the SMA test by how far its GAP
    # was from the band sorts the list by a number that had nothing to do with the
    # rejection - it looks like an answer and orders by noise.
    db2 = {
        "NSE:JUSTUNDER-EQ": bars([100.0] * 25 + [101.5], last_open=100.95),  # gap 0.95%
        "NSE:JUSTOVER-EQ":  bars([100.0] * 25 + [102.5], last_open=102.1),   # gap 2.10%
        "NSE:WAYOFF-EQ":    bars([100.0] * 25 + [106.0], last_open=105.0),   # gap 5.00%
        # gapped perfectly, but sits 8% under its own 20-day mean
        "NSE:UNDERSMA-EQ":  bars([100.0] * 25 + [92.0], last_open=101.5),
    }
    nm = G.near_misses(db2, [])
    names = [r["name"] for r in nm]
    check("near misses lists only single-clause failures",
          set(names) == {"JUSTUNDER", "JUSTOVER", "WAYOFF", "UNDERSMA"}, str(names))
    check("the closest miss ranks first", names[0] == "JUSTUNDER",
          f"{names[0]} missed by {nm[0]['missed_by_pct']}%")
    under = next(r for r in nm if r["name"] == "UNDERSMA")
    check("an SMA failure is measured against the MEAN, not against the band",
          abs(under["missed_by_pct"] - 8.0) < 0.5,
          f"{under['missed_by_pct']}% below the mean, gap was {under['gap_pct']}%")
    check("and it names the clause that actually failed",
          "SMA" in under["failed"], under["failed"])
    check("a name that passes is never a near miss",
          "PASSES" not in names)
    two_bad = G.near_misses({"NSE:TWO-EQ": bars([100.0] * 25 + [92.0],
                                                last_open=105.0)}, [])
    check("failing two clauses is not a near miss", two_bad == [],
          "below the mean AND outside the band — that is not 'nearly'")

    # ---- 9. the exchange quote decides, and a conflict is never hidden -------
    # Three of the four clauses are two numbers: today's OPEN and YESTERDAY'S CLOSE. A
    # daily candle is a derived view of both, and two paise on prev_close moves a name
    # across a 1% threshold. So the published quote wins - and when it disagrees with the
    # candle by more than rounding, that is a corporate action, not noise, and it has to
    # be said rather than silently resolved.
    cand = bars([100.0] * 25 + [101.6], last_open=100.5)      # candle: gap 0.50% -> fails
    q = {"prev_close": 100.0, "open": 101.5, "ltp": 101.6}    # quote:  gap 1.50% -> passes
    plain = G.daily_row(cand)
    withq = G.daily_row(cand, quote=q)
    check("without a quote the candle is used",
          plain["open"] == 100.5 and plain["source"] == "daily candles")
    check("with a quote, the exchange's open and prev close win",
          withq["open"] == 101.5 and withq["prev_close"] == 100.0
          and withq["source"] == "exchange quote")
    check("and that flips the verdict, which is the whole point",
          G.passes(plain)[0] is False and G.passes(withq)[0] is True)
    check("the mean still comes from the candles — there is no quote for an average",
          abs(withq["sma_prev"] - plain["sma_prev"]) < 1e-9)
    check("no conflict flagged when the two agree", withq["prev_close_conflict"] is None,
          "candle prev close is 100.0 and so is the quote")

    # ---- a corporate action is REPAIRED, not just announced -------------------
    # History at 200 and a quote at 100 is a 1:2 split the history has not applied.
    # Leaving it there would compare today's adjusted price against twenty unadjusted
    # closes: every name would read 50% below its own mean and drop off the screen for a
    # reason that has nothing to do with the market. The disagreement IS the factor, so
    # the series is rescaled by it.
    split_bars = bars([200.0] * 25 + [101.6], last_open=100.5)
    raw = G.daily_row(split_bars)
    split = G.daily_row(split_bars,
                        quote={"prev_close": 100.0, "open": 101.5, "ltp": 101.6})
    check("without the repair the split would fail the SMA clause",
          G.passes(raw)[0] is False and abs(raw["sma_prev"] - 200.0) < 1e-9,
          f"mean {raw['sma_prev']:.2f} against a price of 101.60")
    check("the mean is rescaled onto the quote's basis",
          abs(split["sma_prev"] - 100.0) < 1e-9, f"{split['sma_prev']:.2f}")
    check("the factor is the disagreement itself", split["adjusted_by"] == 0.5)
    check("and the name then passes, as it should",
          G.passes(split)[0] is True)
    check("the repair is stated, not silent", bool(split["prev_close_conflict"]))
    check("and it names both numbers and the factor",
          all(x in (split["prev_close_conflict"] or "")
              for x in ("100.00", "200.00", "0.5000")),
          (split["prev_close_conflict"] or "")[:70])
    check("no rescale when the two agree", "adjusted_by" not in withq)

    # a quote with no prev_close is not a quote for this purpose
    half = G.daily_row(cand, quote={"open": 101.5, "ltp": 101.6})
    check("a quote missing prev_close is ignored rather than half-applied",
          half["open"] == 100.5 and half["source"] == "daily candles",
          "using its open with the candle's prev close would invent a third gap")

    # and it must flow all the way through scan()
    sc = G.scan({"NSE:Q-EQ": cand}, [], None, None, {"NSE:Q-EQ": q})
    check("scan() applies quotes too", len(sc) == 1 and sc[0]["src"] == "exchange quote",
          str([r["name"] for r in sc]))
    check("scan() without quotes leaves the name out", G.scan({"NSE:Q-EQ": cand}, []) == [])

    # ---- 10. an empty universe is an answer, not a crash ---------------------
    check("no bars at all -> empty list", G.scan({}, []) == [])
    check("None -> empty list", G.scan(None, None) == [])

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the screen means here what it means on Chartink\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
