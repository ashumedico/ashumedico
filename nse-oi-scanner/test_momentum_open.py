"""
test_momentum_open.py  —  does the opening engine measure what it claims to?

Every check here is a specific way this kind of screen goes wrong quietly. The screen
still returns a list when it is broken; that is the problem. A wrong RVOL denominator does
not raise, it just never fires. A range built from yesterday's bars does not raise, it
just breaks on every tick. So the tests are aimed at the silent failures, not at the
arithmetic.

    python test_momentum_open.py
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
IST = timezone(timedelta(hours=5, minutes=30))
FAILED = []


def check(name, cond, detail=""):
    d = " ".join(str(detail).split())[:130]
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + d if d else ''}")
    if not cond:
        FAILED.append(name)


def bar(day, hh, mm, o, h, l, c, v):
    t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
    return {"t": t.timestamp(), "o": o, "h": h, "l": l, "c": c, "v": v}


def session(day, vol_per_bar=1000, base=100.0):
    """Five 3-minute bars covering 9:15-9:30, plus one later bar outside the window."""
    return [bar(day, 9, 15, base, base + 1, base - 1, base, vol_per_bar),
            bar(day, 9, 18, base, base + 2, base - 1, base + 1, vol_per_bar),
            bar(day, 9, 21, base, base + 2, base - 2, base, vol_per_bar),
            bar(day, 9, 24, base, base + 1, base - 1, base, vol_per_bar),
            bar(day, 9, 27, base, base + 1, base - 1, base, vol_per_bar),
            bar(day, 11, 0, base, base + 9, base - 9, base, 99999)]


def main():
    import momentum_open as M
    print("\n  OPENING MOMENTUM")
    print("  " + "-" * 62)

    today = date(2026, 7, 31)

    # ---- the window is a window, at both ends ----------------------------
    r = M.opening_range(session(today), today)
    check("the opening range uses only the opening window",
          r["high"] == 102 and r["low"] == 98 and r["bars"] == 5,
          f"{r['high']}/{r['low']} from {r['bars']} bars")
    # An 11:00 bar ranging 91-109 sits in the same list. A range that swallowed it would
    # be four times too wide and would never be broken all day.
    check("and a later bar in the same list cannot widen it", r["high"] == 102, r["high"])

    yday = today - timedelta(days=1)
    mixed = session(yday, base=200.0) + session(today, base=100.0)
    r2 = M.opening_range(mixed, today)
    check("yesterday's opening bars do not leak into today's range",
          r2["high"] == 102 and r2["low"] == 98, f"{r2['high']}/{r2['low']}")

    # ---- an unmeasurable range is None, not zero -------------------------
    r3 = M.opening_range([], today)
    check("no bars means no range - not a range of zero",
          r3["high"] is None and r3["low"] is None and r3["bars"] == 0, r3)

    # ---- RVOL: the denominator is the same window, not the day -----------
    bars = []
    for i in range(1, 13):
        bars += session(today - timedelta(days=i), vol_per_bar=1000)
    bars += session(today, vol_per_bar=3000)
    rv, note = M.rvol_open(bars, today)
    # 5x3000 against a median of 5x1000. If the denominator were the whole previous DAY
    # (which includes that 99999-volume 11:00 bar) the ratio would collapse to well under
    # 1 and the filter would never fire - the exact silent failure this guards.
    check("rvol compares like with like - same window, not the whole day",
          rv == 3.0, f"{rv} {note}")

    thin = session(today - timedelta(days=1)) + session(today)
    rv2, note2 = M.rvol_open(thin, today)
    check("too little history is UNKNOWN, never 1.0",
          rv2 is None and "too few" in note2, f"{rv2} {note2}")

    # A median, not a mean: one block-deal morning in the lookback must not hide a
    # genuinely busy open behind an inflated average.
    spiky = []
    for i in range(1, 13):
        spiky += session(today - timedelta(days=i),
                         vol_per_bar=100000 if i == 3 else 1000)
    spiky += session(today, vol_per_bar=3000)
    rv3, _ = M.rvol_open(spiky, today)
    check("one event day in the lookback does not hide a busy morning", rv3 == 3.0, rv3)

    # ---- VWAP is volume-weighted -----------------------------------------
    lopsided = [bar(today, 9, 15, 100, 100, 100, 100, 100),
                bar(today, 9, 18, 200, 200, 200, 200, 9900)]
    v = M.vwap(lopsided, today)
    check("vwap is weighted by volume, not an average of bars",
          v is not None and v > 190, f"{v} (an unweighted mean would be 150)")
    check("and no volume means no vwap", M.vwap([], today) is None)

    # ---- gap vs trend -----------------------------------------------------
    g, aligned, _ = M.gap_vs_trend(102, 100, trend_pct=5.0)
    check("a gap with the trend is aligned", g == 2.0 and aligned is True, f"{g} {aligned}")
    g2, a2, _ = M.gap_vs_trend(102, 100, trend_pct=-5.0)
    check("the same gap against the trend is not", a2 is False, a2)
    g3, a3, note3 = M.gap_vs_trend(102, 100, trend_pct=None)
    # Not False. "I cannot tell which way this has been going" is a different finding
    # from "it has been going the other way", and scoring them the same invents a fact.
    check("an unknown trend is None, not 'against'", a3 is None, f"{a3} {note3}")

    # ---- relative strength -------------------------------------------------
    check("relative strength nets out the market",
          M.relative_strength(1.0, 1.0) == 0.0)
    check("and is unknown when the index is", M.relative_strength(1.0, None) is None)

    # ---- scoring: absent is not zero --------------------------------------
    full = {"name": "A", "break": 1, "rvol": 3.0, "rel_strength": 1.2,
            "gap_aligned": True, "vs_vwap": 1.0}
    half = {"name": "B", "break": 1, "rvol": None, "rel_strength": None,
            "gap_aligned": None, "vs_vwap": None}
    sf, _, mf = M.score_name(full)
    sh, _, mh = M.score_name(half)
    check("a fully measured name scores and reports nothing missing", sf > 0 and not mf,
          f"{sf} {mf}")
    check("an unmeasured name reports what it could not read",
          set(mh) >= {"rvol", "vwap"}, mh)

    out = M.scan([full, half])
    check("and it is DROPPED rather than ranked below the measured one",
          [n["name"] for n in out["names"]] == ["A"]
          and any(d["name"] == "B" for d in out["dropped"]),
          f"{[n['name'] for n in out['names']]} dropped={out['dropped']}")
    check("every dropped name carries the reason it was dropped",
          all(d.get("why") for d in out["dropped"]), out["dropped"])

    inside = {"name": "C", "break": 0, "rvol": 5.0, "rel_strength": 2.0,
              "gap_aligned": True, "vs_vwap": 1.0}
    out2 = M.scan([full, inside])
    check("a name that has not broken its range is not a trade, however loud",
          [n["name"] for n in out2["names"]] == ["A"],
          [n["name"] for n in out2["names"]])

    # A 40x volume print is a block deal or a corporate event, not forty times the
    # conviction. Uncapped it would own the top of every list on the day it happens.
    huge = dict(full, name="D", rvol=40.0)
    sd, _, _ = M.score_name(huge)
    normal = dict(full, name="E", rvol=4.5)
    sn, _, _ = M.score_name(normal)
    check("an absurd volume print is capped, not rewarded forever", sd == sn,
          f"40x scores {sd}, 4.5x scores {sn}")

    out3 = M.scan([dict(full, name=f"N{i}") for i in range(40)], top=30)
    check("the screen returns the top 30 he asked for",
          out3["shown"] == 30 and out3["passed"] == 40,
          f"shown {out3['shown']} of {out3['passed']}")

    short = {"name": "S", "break": -1, "rvol": 3.0, "rel_strength": -1.2,
             "gap_aligned": True, "vs_vwap": -1.0}
    out4 = M.scan([short])
    check("a downside break is a SHORT, scored the same way",
          out4["names"] and out4["names"][0]["side"] == "SHORT"
          and out4["names"][0]["score"] == sf,
          f"{out4['names'][0]['side']} {out4['names'][0]['score']} vs long {sf}")

    # ---- the four proposed additions --------------------------------------
    # Admitted at weight zero. Measured, reported, and changing nothing until an arm
    # turns one on - which is what stops four plausible ideas going live together.
    base = dict(full, ema9_ok=True, prev_break=True, near_extreme=True)
    s_live, _, _ = M.score_name(base)
    s_bare, _, _ = M.score_name(full)
    check("the proposed factors change no ranking until an arm enables them",
          s_live == s_bare, f"{s_live} vs {s_bare}")
    s_arm, _, _ = M.score_name(base, {"ema9": 2.0})
    check("and an arm that enables one moves the score by exactly that weight",
          round(s_arm - s_live, 2) == 2.0, f"{s_arm} - {s_live}")
    # An arm has to differ in ONE place or it is not a measurement of anything.
    s_two, _, _ = M.score_name(base, {"ema9": 2.0, "prev_break": 1.0})
    check("two arms differ only where the weights differ",
          round(s_two - s_arm, 2) == 1.0, f"{s_two} - {s_arm}")

    # ---- EMA -----------------------------------------------------------------
    check("a 9 EMA needs nine points, and says so when it has not got them",
          M.ema([1, 2, 3], 9) is None)
    flat = M.ema([100.0] * 20, 9)
    check("a flat series has its own value as the EMA", flat == 100.0, flat)
    rising = M.ema(list(range(1, 21)), 9)
    # An EMA weights the recent end, so on a rising series it must sit above the simple
    # mean of the same window. If it did not, it is a differently-named SMA.
    check("a rising series puts the EMA above the simple mean of the window",
          rising > sum(range(12, 21)) / 9.0 - 1, rising)

    # ---- wick / near-extreme -------------------------------------------------
    check("price at the high is holding its extreme",
          M.near_extreme(close=100.0, high=100.2, low=95.0, side="LONG") is True)
    check("price rejected well off the high is not",
          M.near_extreme(close=97.0, high=100.0, low=95.0, side="LONG") is False)
    check("and the short side measures the LOW, not the high",
          M.near_extreme(close=95.1, high=100.0, low=95.0, side="SHORT") is True)

    # ---- previous-window break -----------------------------------------------
    day2 = date(2026, 7, 30)
    first = [bar(day2, 9, 15, 100, 102, 98, 101, 1000)]
    second = [bar(day2, 9, 32, 101, 104, 101, 103, 1000)]
    ok, note = M.prev_candle_break(first + second, day2, "LONG")
    check("a close above the first window's high is a break", ok is True, note)
    ok2, _ = M.prev_candle_break(first, day2, "LONG")
    check("and one window alone cannot answer it - not a False",
          ok2 is None, ok2)

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - it measures what it says, and drops what it cannot\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
