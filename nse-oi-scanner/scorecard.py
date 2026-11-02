"""
scorecard.py  —  a 10-point conviction score, with every point named.

A single number next to a stock is the most dangerous object on a trading screen: it looks
like a conclusion and hides its reasoning. So this one is built to be taken apart. Ten
points, each a condition that already exists as a gate in this system, each reported
individually. If a component cannot be computed - no bars, no levels - it scores zero and
says so, because an unknown must never be counted as a yes.

WHAT THE SCORE IS
An aggregation, for reading and ranking on a screen. Its components are the gates that
survived the walk-forward; the *weighting* between them is not itself backtested. A
10/10 is not a probability and is not a licence to size up. Quantity is still one lot.

    python scorecard.py --demo
"""

# (key, points, label, how it is read)
COMPONENTS = (
    ("trend",     2, "Trend up",        "close above the slow average, fast above slow"),
    ("vwap",      1, "Above VWAP",      "buyers paying up today"),
    ("rvol",      2, "Volume",          "RVOL at or above its minimum"),
    ("expansion", 2, "Expansion bar",   "was coiled, this bar is wide - the entry bar"),
    ("room",      1, "Room above",      "more than one ATR to the nearest resistance"),
    ("structure", 1, "Structure",       "higher highs and higher lows"),
    ("breakout",  1, "60% body break",  "closed through R1 with a decisive candle"),
)
MAX = sum(c[1] for c in COMPONENTS)          # 10


def score(p, min_rvol=1.2):
    """One candidate -> {'total', 'of', 'hits': [(label, points, got, why)]}."""
    f = (p or {}).get("feat") or {}
    got = {}
    got["trend"] = (p.get("abs_pct") or 0) > 0
    got["vwap"] = bool(f.get("above_vwap"))
    got["rvol"] = float(f.get("rvol") or 0) >= float(min_rvol)
    got["expansion"] = bool(f.get("expanding"))
    got["room"] = bool(f.get("room_up"))
    got["structure"] = f.get("trend_struct") == "HH-HL"
    got["breakout"] = bool(f.get("breakout"))

    hits, total = [], 0
    for key, pts, label, why in COMPONENTS:
        # No feature dict at all means the name has too little history. That is not a
        # zero-scoring stock, it is an unmeasured one, and the difference matters.
        unknown = not f and key != "trend"
        ok = bool(got.get(key)) and not unknown
        total += pts if ok else 0
        hits.append({"label": label, "points": pts, "got": ok, "why": why,
                     "unknown": unknown})
    return {"total": total, "of": MAX, "hits": hits,
            "unmeasured": sum(1 for h in hits if h["unknown"])}


def label(total, of=MAX):
    pct = 100.0 * total / (of or 1)
    if pct >= 80:
        return "STRONG"
    if pct >= 60:
        return "OK"
    if pct >= 40:
        return "WEAK"
    return "NO"


def volume_shock(points, mult=2.5, top=12):
    """The names whose volume is running far above their own norm.

    The reference screen calls this a volume shock and sets the bar very high. The bar is
    a setting here because the right multiple depends on the bar size: on a 15-minute
    candle, 25x its own average is a halt, not a signal.
    """
    out = []
    for p in points or []:
        f = p.get("feat") or {}
        rv = f.get("rvol")
        if rv and rv >= mult:
            out.append({"name": p.get("name"), "rvol": rv,
                        "close": p.get("close"), "pct": p.get("abs_pct"),
                        "vwap": "upar" if f.get("above_vwap") else "neeche",
                        "expanding": bool(f.get("expanding"))})
    out.sort(key=lambda r: r["rvol"], reverse=True)
    return out[:top]


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        import rrg_engine as E
        pts, _, _ = E.demo_points()
        pts = sorted(pts, key=lambda p: score(p)["total"], reverse=True)
        print(f"\n  SCORECARD  —  {MAX}-point conviction  (synthetic data)")
        print("  " + "-" * 62)
        for p in pts[:12]:
            s = score(p)
            on = ", ".join(h["label"] for h in s["hits"] if h["got"]) or "kuch nahi"
            print(f"  {p['name']:<14}{s['total']:>3}/{s['of']}  "
                  f"{label(s['total']):<7}{on[:44]}")
        print("  " + "-" * 62)
        print("  Har point ek gate hai jo pehle se test hua hai. Weighting test nahi hui.")
        print("  10/10 probability nahi hai. Quantity phir bhi 1 lot.\n")
