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

    # ---- 8. an empty universe is an answer, not a crash ----------------------
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
