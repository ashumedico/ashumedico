"""
test_volume_bubbles.py  —  does the overlay draw only what it measured?

The failure mode of a chart overlay is not a crash. It is a chart that looks complete: a
bubble on every candle, a colour on every bubble, and no way to tell which of them came
from data. So the checks here are about what is ABSENT - a bar with no norm draws nothing,
a session with no recorded OI state draws grey, and the legend counts both out loud.

    python test_volume_bubbles.py
"""
import os
import sys
import tempfile
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


def bar(day, hh, mm, v, c=100.0):
    t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
    return {"t": t.timestamp(), "o": c, "h": c + 1, "l": c - 1, "c": c, "v": v}


def test_legend_reaches_the_page():
    """The count is the honesty mechanism. Computing it and dropping it is the same
    failure as computing vega and discarding it - which is exactly what happened here
    one commit after that one was fixed."""
    src = open(os.path.join(HERE, "desk.py"), encoding="utf-8").read()
    check("the chart legend is rendered, not just attached to the figure",
          "_bubble_legend" in src and src.count("_chart(make_fig") >= 2
          and "st.caption(f\"volume · OI bubbles" in src)
    check("and no chart is drawn by a path that skips it",
          "st.plotly_chart(make_fig" not in src,
          "a direct plotly_chart(make_fig(...)) call would render the figure "
          "without its legend")
    # Inserting the helper above chart_window detached @st.dialog from it: the decorator
    # landed on the helper, so every chart opened a modal and the floating window stopped
    # being one. AppTest reported the page fine - only a real browser found it, when the
    # modal blocked the next tab click. Rendered and visible are different claims.
    i_dec = src.find('@st.dialog("Chart"')
    check("the chart dialog decorator sits on chart_window, not on the renderer",
          i_dec > 0 and src[i_dec:i_dec + 200].split("\n")[1].startswith("def chart_window"),
          src[i_dec:].split("\n")[1] if i_dec > 0 else "no @st.dialog found")
    check("and the figure renderer is a plain function",
          "@st.dialog" not in src[max(0, src.find("def _chart(") - 120):
                                  src.find("def _chart(")])


def main():
    import volume_bubbles as VB
    import oi_history as OH
    print("\n  VOLUME BUBBLES")
    print("  " + "-" * 62)

    d0 = date(2026, 7, 31)

    # ---- THE SHAPE THE ENGINE ACTUALLY SENDS -------------------------------
    # Every fixture below is built from epoch floats, and that is how this suite passed
    # while the real chart drew nothing at all: the engine hands dates through as ISO
    # strings, only the epoch shape was parsed, and every bar reported "no timestamp".
    # A test that feeds a shape production never sends is testing a different function.
    for shape in ("2025-01-20", "2025-01-20 09:15:00", "2025-01-20T09:15:00"):
        check(f"a bar timestamped {shape!r} is understood",
              VB._ts({"t": shape}) is not None, VB._ts({"t": shape}))
    check("and an epoch float still is", VB._ts({"t": 1737331200.0}) is not None)
    check("while an unparseable one is None, not today",
          VB._ts({"t": "not a date"}) is None)

    iso = [{"t": f"2025-01-{d:02d}", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000}
           for d in range(1, 12)]
    iso.append({"t": "2025-01-12", "o": 100, "h": 101, "l": 99, "c": 100, "v": 3000})
    res_iso = VB.bubbles(iso, intraday=False)
    check("and a whole series of ISO-dated bars produces bubbles",
          res_iso["measured"] > 0, f"{res_iso['measured']} of {res_iso['bars']}")

    # ---- the norm is bar-of-day, not a flat average ------------------------
    # Ten sessions where 9:15 trades 10,000 and 13:00 trades 1,000. A flat average over
    # all bars would sit near 5,500 - marking every morning as extraordinary and every
    # afternoon as dead, on a series where nothing unusual happened at all.
    bars = []
    for i in range(10, 0, -1):
        day = d0 - timedelta(days=i)
        bars += [bar(day, 9, 15, 10000), bar(day, 13, 0, 1000)]
    bars += [bar(d0, 9, 15, 10000), bar(d0, 13, 0, 1000)]

    r_open, _ = VB.volume_norm(bars, len(bars) - 2)
    r_noon, _ = VB.volume_norm(bars, len(bars) - 1)
    check("an ordinary morning measures as ordinary", r_open == 1.0, r_open)
    check("and an ordinary afternoon does too - the shape of the day is removed",
          r_noon == 1.0, r_noon)

    bars_busy = bars[:-2] + [bar(d0, 9, 15, 30000), bar(d0, 13, 0, 1000)]
    r_busy, note = VB.volume_norm(bars_busy, len(bars_busy) - 2)
    check("a genuinely busy morning stands out against mornings", r_busy == 3.0,
          f"{r_busy} {note}")

    # ---- no norm means no bubble, never a default one ----------------------
    thin = [bar(d0 - timedelta(days=1), 9, 15, 1000), bar(d0, 9, 15, 5000)]
    rt, nt = VB.volume_norm(thin, 1)
    check("too little history is UNKNOWN, not average", rt is None and "no norm" in nt,
          f"{rt} {nt}")
    res_thin = VB.bubbles(thin)
    check("and an unmeasurable bar draws NOTHING - not a default-sized bubble",
          res_thin["measured"] == 0 and not res_thin["bubbles"], res_thin["measured"])

    check("a missing ratio has no size at all", VB.size_of(None) is None)

    # A block deal prints thirty times the usual volume. Uncapped, that bubble becomes
    # the chart and hides the ordinary 2x day beside it - which is the one a trade gets
    # built on.
    check("an absurd print is capped, so it cannot become the chart",
          VB.size_of(30.0) == VB.size_of(VB.MAX_SCALE), VB.size_of(30.0))
    check("and an ordinary 2x is still visibly bigger than a 1x",
          VB.size_of(2.0) > VB.size_of(1.0))

    # ---- colour comes only from recorded OI --------------------------------
    res = VB.bubbles(bars)
    check("with nothing recorded, every bubble is uncoloured",
          res["uncoloured"] == res["measured"] and res["measured"] > 0,
          f"{res['uncoloured']}/{res['measured']}")
    check("and the legend SAYS so rather than letting grey read as neutral",
          "unknown" in VB.legend(res), VB.legend(res))

    states = {d0.isoformat(): "LONG BUILDUP"}
    res2 = VB.bubbles(bars, states)
    coloured = [b for b in res2["bubbles"] if b["state"]]
    check("a recorded session colours exactly its own candles",
          len(coloured) == 2 and all(b["state"] == "LONG BUILDUP" for b in coloured),
          len(coloured))
    check("a state nobody recorded stays unknown, it is not carried forward",
          res2["uncoloured"] == res2["measured"] - 2,
          f"{res2['uncoloured']}/{res2['measured']}")

    # THE DISTINCTION THE WHOLE OVERLAY EXISTS FOR. Buildup = a position opened.
    # Covering/unwinding = the same price direction from positions closing. Volume alone
    # cannot tell these apart, which is why this is coloured by OI and not by volume.
    check("BUILDUP is marked as opening a position",
          VB.BUILDUP["LONG BUILDUP"]["opening"] is True
          and VB.BUILDUP["SHORT BUILDUP"]["opening"] is True)
    check("and covering / unwinding are marked as closing one",
          VB.BUILDUP["SHORT COVERING"]["opening"] is False
          and VB.BUILDUP["LONG UNWINDING"]["opening"] is False)

    # ---- the recorder ------------------------------------------------------
    tmp = os.path.join(tempfile.mkdtemp(), "oi.json")
    n = OH.record({"ABC": "LONG BUILDUP", "XYZ": "SHORT BUILDUP"}, day=d0, path=tmp)
    check("the recorder writes one state per name per session", n == 2, n)
    got = OH.states_for("ABC", path=tmp)
    check("and reads back exactly what was written",
          got == {d0.isoformat(): "LONG BUILDUP"}, got)

    # A string the chart cannot interpret would sit in the file and colour a candle by
    # accident later. Cheapest place to refuse it is on the way in.
    n2 = OH.record({"BAD": "MASSIVE BUYING"}, day=d0, path=tmp)
    check("an uninterpretable state is refused at the door", n2 == 0
          and OH.states_for("BAD", path=tmp) == {}, n2)

    OH.record({"ABC": "SHORT COVERING"}, day=d0 + timedelta(days=2), path=tmp)
    gaps = OH.states_for("ABC", path=tmp)
    # The skipped day must stay absent. Filling it would make the chart most confident
    # about exactly the session nobody observed.
    check("a session nobody observed is left absent, not interpolated",
          (d0 + timedelta(days=1)).isoformat() not in gaps, sorted(gaps))

    sessions, first, last, err = OH.coverage(path=tmp)
    check("coverage reports what is genuinely known",
          sessions == 2 and first == d0.isoformat() and not err,
          f"{sessions} {first}..{last}")

    test_legend_reaches_the_page()

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - it draws what it measured, and counts what it did not\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

if __name__ == "__main__":
    raise SystemExit(main())
