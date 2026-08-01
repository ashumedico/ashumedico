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

    # The banner and the ribbon are ONE line now - a verdict pill followed by the numbers
    # that justify it. Two stacked blocks cost 115px above every one of the five tabs.
    r = html(at, 'class="verdict')
    check("status verdict rendered", bool(r), r[0][:90] if r else "missing")
    check("the verdict is a verdict, not a label",
          bool(r) and ("Trend Identified" in r[0] or "No trend" in r[0]
                       or "Partial" in r[0]))
    check("the numbers behind it are on the same line", bool(r) and "SPOT" in r[0])
    check("HUD frame is on the strip", bool(r) and "hud" in r[0])
    check("selected name carries a targeting reticle", bool(r) and "reticle" in r[0])

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

    # ---- the floating chart window ----
    src = open(DESK).read()
    check("tables open the chart on row click",
          src.count("clickable(") >= 4,
          f"{src.count('clickable(') - 1} tables wired")
    check("trade cards have their own chart button", 'chart_window(nm)' in src)
    check("one chart builder, used by page and popup alike",
          src.count("def make_fig") == 1 and src.count("make_fig(") >= 3,
          f"{src.count('make_fig(') - 1} call sites")

    # The chart builder is a pure function - test it directly rather than through the UI.
    # One namespace for globals AND locals: with two, the functions defined here get the
    # first dict as their globals and cannot see each other - make_fig would not find
    # touches, which is exactly what happened.
    ns = {"st": None, "__name__": "_deskfns"}
    exec(compile(src[src.index("def touches("):src.index("@st.dialog")], DESK, "exec"),
         ns, ns)
    bars_ = [[i, 100 + i, 102 + i, 98 + i, 101 + i, 1000] for i in range(40)]
    feat = {"r1": 130.0, "r2": 140.0, "s1": 95.0, "s2": 90.0, "atr": 2.0}
    plan = [("STOP", 96.0, "#FF2D8A"), ("T1", 125.0, "#00E5FF")]
    fig = ns["make_fig"]("X", [b[4] for b in bars_], bars_, ["d"] * 40, feat, plan)
    shapes = getattr(fig.layout, "shapes", ()) or ()
    check("chart draws all four levels plus the trade plan",
          len(shapes) == 6, f"{len(shapes)} lines (4 levels + 2 plan)")
    texts = " ".join(str(a.text) for a in (getattr(fig.layout, "annotations", ()) or ()))
    check("levels are named on the chart",
          all(k in texts for k in ("R1", "R2", "S1", "S2", "STOP", "T1")))
    check("levels carry their touch count", "x" in texts)

    # ---- the palette: three neons on black, and nothing else ----
    # A stray colour is not a cosmetic slip. Every colour on this page is a claim - blue
    # says up, pink says down, green says look here - so a fourth one is a claim nobody
    # can read. This catches an old hex creeping back in through a copied line.
    import re as _re
    hexes = set(h.upper() for h in _re.findall(r"#[0-9a-fA-F]{6}", src))
    OLD = {"#3FB950", "#56D364", "#F85149", "#FF7B72", "#D29922", "#E3B341",
           "#58A6FF", "#0D2B18", "#3D1519", "#0B0F14", "#161B22"}
    check("no pre-neon colours left", not (hexes & OLD), f"{sorted(hexes & OLD)}")

    def _hue(h):
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        if max(r, g, b) < 60:
            return "black"                      # surfaces
        if b >= r and b >= g:
            return "blue"
        if g > r and g > b:
            return "green"
        if r >= g and r >= b:
            return "pink"
        return "other"
    fams = {}
    for h in hexes:
        fams.setdefault(_hue(h), []).append(h)
    check("only black, blue, green and pink are used",
          not (set(fams) - {"black", "blue", "green", "pink"}),
          f"{ {k: len(v) for k, v in sorted(fams.items())} }")

    # up must never be pink and down must never be blue - the swap he asked for is the
    # whole point, and getting it backwards is worse than not doing it
    check("candles: up is blue, down is pink",
          'increasing_line_color="#00E5FF"' in src
          and 'decreasing_line_color="#FF2D8A"' in src)
    rule = src.split(".disclaim {", 1)[-1].split("}", 1)[0]
    check("the disclaimer bar is pink, not red",
          "#FF2D8A" in rule and "#FF8FC5" in rule, rule[:70].replace("\n", " "))

    # ---- sector drivers ----
    # The two-column heatmap cannot render in demo (no sector feed), so the function
    # behind it is tested directly rather than left to be discovered live.
    ns2 = {"st": None, "__name__": "_deskfns2"}
    # slice from the CONSTANT, not the def - drivers() reads DRIVER_MIN_R, and starting
    # at "def" leaves it undefined in the exec namespace
    exec(compile(src[src.index("DRIVER_MIN_R ="):src.index("# --- end of sector helpers ---")],
                 DESK, "exec"), ns2, ns2)
    cmap = {"NIFTY IT": [{"name": "A", "corr": 0.9}, {"name": "B", "corr": 0.3},
                         {"name": "C", "corr": 0.8}, {"name": "D", "corr": 0.85}]}
    by = {"A": {"abs_pct": 2.0}, "B": {"abs_pct": 9.0},
          "C": {"abs_pct": -4.0}, "D": {"abs_pct": 3.0}}
    up = ns2["drivers"]("NIFTY IT", +1, cmap, by)
    check("drivers only lists names moving WITH the sector",
          [d["name"] for d in up] == ["D", "A"],
          f"{[d['name'] for d in up]}")
    check("a big move in a name that barely tracks the sector does not lead",
          "B" not in [d["name"] for d in up],
          "B moved 9% at r=0.3 - that is B's story, not the sector's")
    dn = ns2["drivers"]("NIFTY IT", -1, cmap, by)
    check("the declining side lists the fallers", [d["name"] for d in dn] == ["C"])
    check("an unknown sector yields nothing, not an error",
          ns2["drivers"]("NOPE", +1, cmap, by) == [])

    # ---- the page is in English ----
    # The chat is Hinglish; the website is not. A half-translated screen is worse than
    # either language on its own - the reader stops trusting that the words were chosen
    # rather than left over. This scans the strings that reach the page.
    import re as _re
    HINGLISH = _re.compile(
        r"\b(nahi|naam|hai|hoon|kar(o|na|ke)?|chala(o|na)?|jeete|khaali|khule|"
        r"mein|kya|koi|abhi|purani|sabse|pehle|dekh|bata|jhooth|matlab|wo|ye|"
        r"raha|rahe|aaya|aaj|upar|neeche|haan|thoda|zyada)\b", _re.I)
    # "band" is deliberately NOT in that list: price band, confidence band and the F&O
    # band are all English here, and a checker that cries wolf gets switched off.
    lit = _re.findall(r'"([^"\n]{14,})"', src) + _re.findall(r"'([^'\n]{14,})'", src)
    # skip code-ish literals: selectors, css, module paths, keys
    def _uiish(t):
        if any(x in t for x in ("data-testid", "px", "rgba(", "#", "<", "/", "_", "=")):
            return False
        return " " in t
    leftovers = sorted({t for t in lit if _uiish(t) and HINGLISH.search(t)})
    check("no Hinglish left on the page", not leftovers,
          "; ".join(leftovers[:3])[:160] if leftovers else "")

    # a source that cannot show NSE names must not be offered as one
    # StockCharts covers US/Canada, not NSE India. Offering it would be a dead link
    # dressed as a feature - so it must not appear in the link list.
    links_block = src.split("EXTERNAL_CHARTS = [", 1)[-1].split("]", 1)[0].lower()
    check("no chart source that cannot carry NSE names",
          "EXTERNAL_CHARTS = [" in src and "stockcharts" not in links_block)
    check("external links are offered for what we cannot draw",
          "tradingview.com" in src.lower())

    # ---- the dead-button bug -------------------------------------------------
    # Every order button on every ticket was permanently greyed out, and the cause was
    # not in the button: the ticket called build_card() with NO CHAIN, so there was no
    # tradeable symbol to send and the guard did its job on nothing. A ticket that can
    # be ordered has to be built from a chain.
    tickets = src.split("def signal_block", 1)[-1]
    check("the ticket builds its card from a live option chain",
          "chain=ch" in tickets and "chain_for(" in tickets)
    check("the ticket takes the real lot size from that chain", "lot=chlot" in tickets)
    check("a dead button says WHY it is dead", "no_contract_why" in src)
    # and the disabled state must be reachable rather than theoretical: DEMO has no token
    caps = [c.value for c in at.caption]
    check("in DEMO the buttons explain the missing token, not just 'no contract'",
          any("No contract" in c and "token" in c for c in caps),
          next((c[:90] for c in caps if "No contract" in c), "no such caption"))

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the page renders, and every branch of it was exercised\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
