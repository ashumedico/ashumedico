"""
test_sectors.py  —  sector membership is measured, and measured things can be checked.

Writing out which of two hundred F&O names sits in which of fourteen sector indices, from
memory, produces a list that is wrong in a dozen places and shows it to nobody. So the
system correlates each stock against each index and assigns what it finds.

That is only better if it is right. This builds three synthetic indices, three stocks that
track each one, and one that tracks nothing, then checks that every stock lands where it
belongs and the loner is left out rather than filed under whichever number was highest.

    python test_sectors.py
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def build(n=160, seed=11):
    rnd = random.Random(seed)
    idx = {}
    for name in ("NIFTY BANK", "NIFTY IT", "NIFTY PHARMA"):
        px, ser = 100.0, []
        for _ in range(n):
            px *= 1 + rnd.gauss(0.0003, 0.010)
            ser.append(px)
        idx[name] = ser

    prices, truth = {}, {}
    for sec, ser in idx.items():
        for k in range(3):
            px, out = 100.0, []
            for t in range(n):
                mkt = (ser[t] / ser[t - 1] - 1) if t else 0.0
                px *= 1 + 0.95 * mkt + rnd.gauss(0, 0.004)
                out.append(px)
            sym = f"NSE:{sec.split()[-1]}{k}-EQ"
            prices[sym] = out
            truth[sym] = sec
    px, out = 100.0, []
    for _ in range(n):
        px *= 1 + rnd.gauss(0, 0.015)
        out.append(px)
    prices["NSE:LONER-EQ"] = out
    return idx, prices, truth


def main():
    import sectors as S
    import rrg_engine as E

    idx, prices, truth = build()
    S._RESOLVED = {k: f"NSE:{k.replace(' ', '')}-INDEX" for k in idx}
    real_fetch = E.fetch_history
    E.fetch_history = lambda syms, **kw: (
        {f"NSE:{k.replace(' ', '')}-INDEX": v for k, v in idx.items()}, [], [])

    print("\n  SECTOR MEMBERSHIP  (measured, not remembered)")
    print("  " + "-" * 62)
    try:
        cmap, unclear = S.constituents(prices)
        placed = sum(len(v) for v in cmap.values())
        for sec in sorted(cmap):
            names = ", ".join("%s(r=%s)" % (m["name"], m["corr"]) for m in cmap[sec])
            print(f"   {sec:<14} {names}")
        print(f"   {'unclear':<14} "
              + ", ".join(u["name"] for u in unclear or []))

        check("every tracking stock was placed", placed == 9, f"{placed}/9 placed")
        wrong = [m["name"] for sec, ms in cmap.items() for m in ms
                 if truth.get(m["symbol"]) != sec]
        check("and placed in the right sector", not wrong, f"wrong: {wrong}")
        check("the uncorrelated name is left unclear",
              any(u["name"] == "LONER" for u in unclear or []),
              "a weak best-match is a coincidence, not a sector")
        check("correlations are reported so they can be doubted",
              all(m.get("corr") is not None for ms in cmap.values() for m in ms))

        # nothing to measure -> nothing claimed
        empty_map, _ = S.constituents({})
        check("no prices -> no assignments invented", empty_map == {})
        S._RESOLVED = {}
        none_map, _ = S.constituents(prices)
        check("no resolved indices -> no assignments invented", none_map == {})
    finally:
        E.fetch_history = real_fetch
        S._RESOLVED = None

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
