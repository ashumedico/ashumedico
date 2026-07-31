"""
test_desk.py  —  proof that the website renders, not just that it imports.

A dashboard is the one file that can be completely broken while every unit test passes:
Streamlit swallows nothing, but nobody runs it in CI, so a typo in a level name or a None
where a float was expected shows up at 9:20am on a Monday instead of here.

This runs desk.py the way a browser session runs it, through Streamlit's own AppTest, and
asserts on what actually reached the page: the banner, the ribbon, the levels, all three
scenario branches, and the disclaimer. It runs in DEMO mode, which is now a full synthetic
OHLCV path - if the demo could not produce bars, the test could not tell a working page
from a page that renders only its headings.

    python test_desk.py            (or: pytest test_desk.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.join(HERE, "desk.py")

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def html(at, fragment):
    """Markdown blocks that carry a fragment, ignoring the <style> block that contains
    every class name and would otherwise make each of these checks pass trivially."""
    return [m.value for m in at.markdown
            if fragment in m.value and "<style>" not in m.value]


def main():
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        print("  SKIP  streamlit not installed - pip install streamlit plotly")
        return 0

    print("\n  DESK  (demo mode, synthetic bars)")
    print("  " + "-" * 62)
    at = AppTest.from_file(DESK, default_timeout=600).run()

    check("script raises nothing", not at.exception,
          "; ".join(str(e.value)[:120] for e in at.exception))
    check("demo mode is announced",
          any("DEMO" in w.value for w in at.warning))

    b = html(at, 'class="banner')
    check("status banner rendered", bool(b), b[0][:90] if b else "missing")
    check("banner states a verdict",
          bool(b) and ("Trend Identified" in b[0] or "Koi trend nahi" in b[0]
                       or "Partial" in b[0]))

    r = html(at, 'class="ribbon"')
    check("ribbon rendered with the name", bool(r) and "Spot" in r[0])

    s = html(at, "SCENARIO ANALYSIS")
    check("scenario strip names the rules used",
          bool(s) and "60% body breakout" in s[0])

    d = html(at, "disclaim")
    check("disclaimer pinned", bool(d) and "NOT FINANCIAL ADVICE" in d[0])

    # Levels only exist if the feature layer ran end to end on the demo bars.
    scen = [x for x in at.radio if x.label == "Scenario"]
    check("levels computed (scenario control present)", bool(scen))

    if scen:
        for opt in ("Bullish", "Sideways", "Bearish"):
            a2 = scen[0].set_value(opt).run()
            texts = ([x.value for x in a2.success] + [x.value for x in a2.error] +
                     [x.value for x in a2.info])
            body = " ".join(texts)
            check(f"scenario {opt} renders", not a2.exception and bool(body))
            if opt == "Bullish":
                check("bullish states an invalidation", "invalidation" in body)
            if opt == "Bearish":
                check("bearish says exit, not entry",
                      "long-only" in body or "exit" in body)
            scen = [x for x in a2.radio if x.label == "Scenario"] or scen

    check("mauke table rendered", len(at.dataframe) >= 1)
    check("metrics rendered", len(at.metric) >= 4, f"{len(at.metric)} metrics")

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the page renders, and every branch of it was exercised\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
