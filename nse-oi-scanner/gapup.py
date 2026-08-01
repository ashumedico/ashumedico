"""
gapup.py  —  the Chartink screen, rebuilt here so it runs on the same bars as everything
else and can be argued with.

THE FILTER, exactly as it is written on Chartink (futures segment):

    Daily Close      >  1 day ago Sma(1 day ago Close, 20)
    Daily Open       >  1 day ago Close * 1.01
    Daily Open       <  1 day ago Close * 1.02
    [0] 15 minute Close > Daily Open           <- DISABLED there, disabled here

It is one idea in three clauses: the name is **above its 20-day mean** (trend), it
**gapped up between 1% and 2%** this morning (interest, not a moonshot), and - if the
fourth clause is switched on - it is **still above its own opening price** (the gap has
not been sold into). The band matters more than it looks: below 1% is noise, above 2% is
a name that has already made its move before he can get filled.

ON "1 DAY AGO SMA(1 DAY AGO CLOSE, 20)"
Chartink's phrasing is precise and easy to get wrong. It is the 20-period average of the
closes **ending yesterday** - today's close is compared against a mean it is not part of.
Averaging today in would let a big up-day drag its own benchmark up and quietly weaken
the test. So the window here is closes[-21:-1], never closes[-20:].

WHAT THIS IS NOT
It is a **screen**, not an edge. Nothing in this file has been walk-forward tested on his
data, and the last untested thing that reached the main window (RRG) cost -6.3% after
costs. A name passing here means *worth opening the ticket for*. It never means *place
this*. Anything that says otherwise on screen is a bug.

    python gapup.py --demo
"""

DEFAULTS = {
    "sma_len": 20,
    "gap_min": 1.01,      # Daily Open > prev Close * this
    "gap_max": 1.02,      # Daily Open < prev Close * this
    "use_intraday_gate": False,   # the [0] 15-minute clause, off exactly as he has it
}


def sma(values, n):
    """Mean of the last n values, or None when there are not n of them.

    None, not zero, and not a shorter mean: a 6-day average called a 20-day average is a
    different test wearing the same name, and it passes when it should not be asked."""
    if not values or len(values) < n:
        return None
    tail = values[-n:]
    return sum(tail) / float(n)


def daily_row(bars, sma_len=20):
    """One name's numbers for today, from its DAILY candles.

    bars: [[epoch, open, high, low, close, volume], ...] oldest first. Fyers' last daily
    candle during market hours is the running session - its open is final, its close is
    the LTP - which is exactly what "Daily Close" means on a live screener.
    """
    if not bars or len(bars) < sma_len + 2:
        return None
    closes = [float(b[4]) for b in bars]
    today, prev = bars[-1], bars[-2]
    return {
        "open": float(today[1]),
        "close": float(today[4]),
        "high": float(today[2]),
        "low": float(today[3]),
        "prev_close": float(prev[4]),
        # the average ENDING YESTERDAY - today is not in its own benchmark
        "sma_prev": sma(closes[:-1], sma_len),
        "bars": len(bars),
    }


def passes(row, cfg=None, last_intraday=None):
    """(bool, [clause dicts]) - every clause named, with the numbers that decided it.

    The clause list is the point. A screen that answers only yes/no cannot be argued with,
    and a filter he cannot argue with is one he has to take on faith.
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    if not row or row.get("sma_prev") is None:
        return False, [{"clause": "history", "ok": False,
                        "detail": f"needs {cfg['sma_len'] + 2} daily bars, "
                                  f"has {row.get('bars', 0) if row else 0}"}]

    pc, op, cl = row["prev_close"], row["open"], row["close"]
    lo_gap, hi_gap = pc * cfg["gap_min"], pc * cfg["gap_max"]
    gap_pct = (op / pc - 1.0) * 100.0 if pc else 0.0

    out = [
        {"clause": f"Close > SMA{cfg['sma_len']} (ending yesterday)",
         "ok": cl > row["sma_prev"],
         "detail": f"{cl:.2f} vs {row['sma_prev']:.2f}"},
        {"clause": f"Open > prev Close x {cfg['gap_min']}",
         "ok": op > lo_gap,
         "detail": f"{op:.2f} vs {lo_gap:.2f}  (gap {gap_pct:+.2f}%)"},
        {"clause": f"Open < prev Close x {cfg['gap_max']}",
         "ok": op < hi_gap,
         "detail": f"{op:.2f} vs {hi_gap:.2f}"},
    ]
    if cfg["use_intraday_gate"]:
        # [0] 15 minute Close > Daily Open - the latest intraday bar, not the day's close.
        # Unknown is never a pass: with no intraday bar this clause FAILS rather than
        # being skipped, because "I could not check" and "it checked out" are not the
        # same claim and only one of them should let a name through.
        out.append({
            "clause": "[0] 15-min Close > Daily Open",
            "ok": last_intraday is not None and float(last_intraday) > op,
            "detail": (f"{float(last_intraday):.2f} vs {op:.2f}"
                       if last_intraday is not None else "no intraday bar — not checked"),
        })
    return all(c["ok"] for c in out), out


def scan(daily_bars, points=None, cfg=None, last_intraday=None):
    """Every F&O name against the filter. Returns rows for the ones that pass.

    daily_bars:    {symbol: [daily candles]}
    points:        the scan's own points, for the name and today's percent move
    last_intraday: {symbol: latest 15-minute close}, only read when the gate is on
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    by_sym = {p["symbol"]: p for p in (points or [])}
    rows = []
    for sym, bars in (daily_bars or {}).items():
        row = daily_row(bars, cfg["sma_len"])
        ok, clauses = passes(row, cfg, (last_intraday or {}).get(sym))
        if not ok:
            continue
        p = by_sym.get(sym) or {}
        pc = row["prev_close"]
        rows.append({
            "name": p.get("name") or sym.split(":")[-1].replace("-EQ", ""),
            "symbol": sym,
            "open": round(row["open"], 2),
            "prev_close": round(pc, 2),
            "gap_pct": round((row["open"] / pc - 1.0) * 100.0, 2) if pc else None,
            "close": round(row["close"], 2),
            "from_open_pct": round((row["close"] / row["open"] - 1.0) * 100.0, 2)
                             if row["open"] else None,
            f"sma{cfg['sma_len']}": round(row["sma_prev"], 2),
            "above_sma_pct": round((row["close"] / row["sma_prev"] - 1.0) * 100.0, 2),
            "clauses": clauses,
        })
    # Held the gap best first. The gap is the entry condition; what the name did with it
    # afterwards is the only new information the morning has produced.
    rows.sort(key=lambda r: (r["from_open_pct"] is None, -(r["from_open_pct"] or 0)))
    return rows


def near_misses(daily_bars, points=None, cfg=None, last_intraday=None, top=8):
    """Names that failed EXACTLY ONE clause, and which one.

    This is the answer to "why is your list different from Chartink's". Two screens with
    the same rules disagree at the BAND EDGES, because a gap of 0.98% and a gap of 1.02%
    are the same event and land on opposite sides of a threshold - and the two feeds do
    not agree to the paisa on what yesterday's close was (Chartink adjusts for corporate
    actions on its own schedule; Fyers returns its own continuous series). A name missing
    from one list is usually not a bug, it is a number differing in the third decimal.

    So instead of a shorter list, this shows the ones that came closest and the exact
    figure that kept them out. Then a disagreement can be checked instead of argued.
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    by_sym = {p["symbol"]: p for p in (points or [])}
    out = []
    for sym, bars in (daily_bars or {}).items():
        row = daily_row(bars, cfg["sma_len"])
        if not row:
            continue
        ok, clauses = passes(row, cfg, (last_intraday or {}).get(sym))
        if ok:
            continue
        failed = [c for c in clauses if not c["ok"]]
        if len(failed) != 1:
            continue
        p = by_sym.get(sym) or {}
        pc = row["prev_close"]
        gap = (row["open"] / pc - 1.0) * 100.0 if pc else 0.0
        clause = failed[0]["clause"]
        # HOW BADLY it missed has to be measured on the clause that actually failed.
        # Reporting the gap's distance from the band for a name that failed the SMA test
        # sorts the list by a number that had nothing to do with the rejection - it looks
        # like an answer and ranks by noise.
        if "SMA" in clause:
            miss = abs(row["close"] / row["sma_prev"] - 1.0) * 100.0
        elif "15-min" in clause:
            miss = 0.0          # a gate that could not be evaluated has no distance
        else:
            miss = min(abs(gap - (cfg["gap_min"] - 1) * 100),
                       abs(gap - (cfg["gap_max"] - 1) * 100))
        out.append({
            "name": p.get("name") or sym.split(":")[-1].replace("-EQ", ""),
            "failed": clause,
            "detail": failed[0]["detail"],
            "gap_pct": round(gap, 2),
            "missed_by_pct": round(miss, 2),
        })
    out.sort(key=lambda r: r["missed_by_pct"])
    return out[:top]


def explain(symbols, cfg=None, days=90):
    """Print every number for named symbols, live. The tool for a disagreement.

    `python gapup.py --explain BAJAJFINSV TORNTPHARM` prints what this system believes
    yesterday's close, today's open and the 20-day mean are for each name, and which
    clause decided it. Paste the same names into Chartink and the difference stops being
    "the lists are different" and becomes "your prev close is 2029.10, mine is 2027.55".
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    import rrg_engine as E
    syms = [s if ":" in s else f"NSE:{s.upper()}-EQ" for s in symbols]
    E.fetch_history(syms, resolution="D", days=days)
    bars = E.LAST_BARS or {}
    print(f"\n  GAP-UP, clause by clause  (SMA{cfg['sma_len']}, band "
          f"{cfg['gap_min']:g}-{cfg['gap_max']:g})")
    print("  " + "-" * 70)
    for s in syms:
        nm = s.split(":")[-1].replace("-EQ", "")
        b = bars.get(s)
        if not b:
            print(f"  {nm:14s} no daily bars came back for this symbol")
            continue
        row = daily_row(b, cfg["sma_len"])
        if not row:
            print(f"  {nm:14s} only {len(b)} daily bars - needs {cfg['sma_len'] + 2}")
            continue
        ok, clauses = passes(row, cfg)
        gap = (row["open"] / row["prev_close"] - 1) * 100
        print(f"  {nm:14s} {'PASS' if ok else 'fail'}   prev close {row['prev_close']:.2f}"
              f" · open {row['open']:.2f} (gap {gap:+.2f}%) · close {row['close']:.2f}"
              f" · sma {row['sma_prev']:.2f}")
        for c in clauses:
            print(f"       {'ok ' if c['ok'] else '>> '} {c['clause']:44s} {c['detail']}")
    print()


def _demo():
    """A hand-built set where each name fails exactly one clause, so the output is
    readable as a test rather than as a list."""
    import random
    rnd = random.Random(7)

    def series(base, n=40, drift=0.002):
        out = [base]
        for _ in range(n):
            out.append(out[-1] * (1 + rnd.gauss(drift, 0.01)))
        return out

    def bars_from(closes, last_open):
        b = [[i, c, c * 1.01, c * 0.99, c, 1000] for i, c in enumerate(closes[:-1])]
        b.append([len(closes), last_open, max(last_open, closes[-1]) * 1.005,
                  min(last_open, closes[-1]) * 0.995, closes[-1], 1500])
        return b

    out = {}
    c = series(500)
    out["NSE:PASSES-EQ"] = bars_from(c + [c[-1] * 1.02], c[-1] * 1.015)     # in band
    out["NSE:TOOBIG-EQ"] = bars_from(c + [c[-1] * 1.05], c[-1] * 1.045)     # gap > 2%
    out["NSE:TOOSMALL-EQ"] = bars_from(c + [c[-1] * 1.004], c[-1] * 1.003)  # gap < 1%
    d = [500 - i * 3 for i in range(41)]                                    # below SMA
    out["NSE:BELOWSMA-EQ"] = bars_from(d + [d[-1] * 1.015], d[-1] * 1.015)
    out["NSE:SHORTHIST-EQ"] = [[i, 100, 101, 99, 100, 10] for i in range(5)]
    return out


if __name__ == "__main__":
    import sys
    if "--explain" in sys.argv:
        i = sys.argv.index("--explain")
        names = [a for a in sys.argv[i + 1:] if not a.startswith("--")]
        if not names:
            print("  usage: python gapup.py --explain BAJAJFINSV TORNTPHARM ...")
            raise SystemExit(2)
        explain(names)
    elif "--demo" in sys.argv:
        db = _demo()
        print("\n  GAP-UP SCREEN (demo)\n  " + "-" * 58)
        for sym, bars in db.items():
            row = daily_row(bars)
            ok, cls = passes(row)
            print(f"  {sym.split(':')[-1]:14s} {'PASS' if ok else 'fail'}")
            for c in cls:
                print(f"      {'ok ' if c['ok'] else '   '} {c['clause']:42s} {c['detail']}")
        print()
        for r in scan(db):
            print("  passes:", r["name"], r["gap_pct"], "%")
        print()
    else:
        print(__doc__)
