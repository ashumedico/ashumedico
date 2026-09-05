"""
sectors.py  —  sector strength, and the momentum radar behind it.

Two things the reference deck shows that this system did not have:

  SECTOR HEATMAP   every sector index ranked, leader at the top, laggard at the bottom
  MOMENTUM RADAR   how many names are trending, and which ones just turned

Both are *context*. Neither is a trigger, and neither has been walk-forward tested - there
is no sector-index history in this system to test them against. They tell you where the
money is today; the entry still comes from the tested gates.

ON SYMBOL NAMES
The exact Fyers symbol for each sector index is not something to state from memory. So
every sector carries a list of candidate spellings, they are probed against the live feed
once, and whatever answers is what gets used. A sector that never resolves is reported as
unresolved - not dropped silently, and never drawn as 0.00%. A heatmap tile showing a flat
zero for a sector that simply failed to fetch is the exact lie this avoids.

    python sectors.py            # probe the feed and show what resolved
"""
import sys

# display name -> candidate Fyers symbols, most likely first
SECTORS = [
    ("NIFTY 50",       ["NSE:NIFTY50-INDEX"]),
    ("NIFTY BANK",     ["NSE:NIFTYBANK-INDEX"]),
    ("NIFTY IT",       ["NSE:NIFTYIT-INDEX"]),
    ("NIFTY AUTO",     ["NSE:NIFTYAUTO-INDEX"]),
    ("NIFTY PHARMA",   ["NSE:NIFTYPHARMA-INDEX"]),
    ("NIFTY FMCG",     ["NSE:NIFTYFMCG-INDEX"]),
    ("NIFTY METAL",    ["NSE:NIFTYMETAL-INDEX"]),
    ("NIFTY REALTY",   ["NSE:NIFTYREALTY-INDEX"]),
    ("NIFTY ENERGY",   ["NSE:NIFTYENERGY-INDEX"]),
    ("NIFTY MEDIA",    ["NSE:NIFTYMEDIA-INDEX"]),
    ("PSU BANK",       ["NSE:NIFTYPSUBANK-INDEX", "NSE:PSUBANK-INDEX"]),
    ("FIN SERVICES",   ["NSE:NIFTYFINSERVICE-INDEX", "NSE:FINNIFTY-INDEX"]),
    ("CONS DURABLE",   ["NSE:NIFTYCONSUMERDURABLES-INDEX", "NSE:NIFTYCONSRDURBL-INDEX"]),
    ("OIL & GAS",      ["NSE:NIFTYOILGAS-INDEX", "NSE:NIFTYOIL&GAS-INDEX"]),
]

_RESOLVED = None            # {display: symbol} once probed, so we probe once a session


def quotes(symbols):
    """LTP and change-% together. live_quote() only returns the price, and a heatmap
    without a change column is just a list of numbers."""
    out = {}
    if not symbols:
        return out
    try:
        import rrg_engine as E
        fy = E._fy()
        for i in range(0, len(symbols), 50):
            r = fy.quotes({"symbols": ",".join(symbols[i:i + 50])})
            for d in (r.get("d", []) if isinstance(r, dict) else []):
                v = d.get("v", {}) or {}
                if v.get("lp") is None:
                    continue
                out[d.get("n")] = {"ltp": float(v.get("lp") or 0),
                                   "chp": float(v.get("chp") or 0),
                                   "ch": float(v.get("ch") or 0)}
    except Exception:      # noqa - no feed / off hours; caller must handle {}
        pass
    return out


def resolve(force=False):
    """{display name: symbol that actually answered}. Probes once."""
    global _RESOLVED
    if _RESOLVED is not None and not force:
        return _RESOLVED
    cands = [s for _, syms in SECTORS for s in syms]
    got = quotes(cands)
    _RESOLVED = {}
    for name, syms in SECTORS:
        for s in syms:
            if s in got:
                _RESOLVED[name] = s
                break
    return _RESOLVED


def unresolved():
    r = resolve()
    return [n for n, _ in SECTORS if n not in r]


def heatmap():
    """Ranked sectors: [{name, symbol, pct, ltp, rank, tag}]. Empty when nothing resolved -
    an empty heatmap is a true statement; a heatmap of zeros is not."""
    r = resolve()
    if not r:
        return []
    q = quotes(list(r.values()))
    rows = []
    for name, sym in r.items():
        d = q.get(sym)
        if not d:
            continue
        rows.append({"name": name, "symbol": sym, "pct": round(d["chp"], 2),
                     "ltp": round(d["ltp"], 2)})
    rows.sort(key=lambda x: x["pct"], reverse=True)
    for i, row in enumerate(rows):
        row["rank"] = i + 1
        row["tag"] = "LEADER" if i == 0 else ("LAGGARD" if i == len(rows) - 1 else "")
    return rows


# ------------------------------------------------------------------- radar --
def _session_bars(bars, dates):
    """Only today's bars. Without dates there is no way to know where the session starts,
    and a 'day high' measured across three days is not a day high."""
    if not bars:
        return []
    if not dates or len(dates) < len(bars):
        return []
    tail = dates[-len(bars):]
    today = tail[-1]
    return [b for b, d in zip(bars, tail) if d == today]


def classify(bars, dates, feat=None, turn_pct=0.4):
    """One name -> one of UPTREND / DOWNTREND / DAY-HIGH REVERSAL / BOUNCING OFF LOW /
    FLAT, or None when it cannot be judged.

    The two turn states need intraday bars. On daily candles the question 'has it turned
    off the day high' has no answer, and None is the honest one.
    """
    sess = _session_bars(bars, dates)
    f = feat or {}
    trend = f.get("trend_struct")
    up = trend == "HH-HL"
    down = trend == "LH-LL"

    if len(sess) >= 4:
        highs = [b[2] for b in sess]
        lows = [b[3] for b in sess]
        px = sess[-1][4]
        hi, lo = max(highs), min(lows)
        n = len(sess)
        # LAST occurrence, because a level revisited later is what the price is turning
        # away from now - the first touch is history.
        hi_i = n - 1 - highs[::-1].index(hi)
        lo_i = n - 1 - lows[::-1].index(lo)
        off_high = 100.0 * (hi - px) / hi if hi else 0
        off_low = 100.0 * (px - lo) / lo if lo else 0
        half = (n - 1) / 2.0        # the extreme has to be in the latter half to be "just"

        # Which extreme came LAST decides the story. Asking "is it off the high" and "is
        # it off the low" independently makes every down-then-up day answer yes to both,
        # and the first question wins by position in the code rather than by the tape -
        # which is how a bounce got labelled a reversal.
        if hi_i > lo_i:
            if hi_i >= half and off_high >= turn_pct:
                return "DAY-HIGH REVERSAL"
        elif lo_i > hi_i:
            if lo_i >= half and off_low >= turn_pct:
                return "BOUNCING OFF LOW"
    if up:
        return "UPTREND"
    if down:
        return "DOWNTREND"
    if trend:
        return "FLAT"
    return None


def radar(points, bars_by_symbol, dates):
    """Counts plus the named example the reference badges show.

    'unjudged' is reported, not hidden: on daily bars every name lands there, and a radar
    that quietly shows 0/0/0 would look like a calm market instead of a missing input.
    """
    counts, examples, unjudged = {}, {}, 0
    for p in points or []:
        b = (bars_by_symbol or {}).get(p.get("symbol")) or []
        state = classify(b, dates, p.get("feat"))
        if state is None:
            unjudged += 1
            continue
        counts[state] = counts.get(state, 0) + 1
        # the example is the strongest mover in that state, so the badge names something
        # worth looking at rather than whichever name happened to be first
        cur = examples.get(state)
        if cur is None or abs(p.get("abs_pct") or 0) > abs(cur[1] or 0):
            examples[state] = (p.get("name"), p.get("abs_pct"))
    return {"counts": counts, "examples": examples, "unjudged": unjudged,
            "judged": sum(counts.values())}


# ------------------------------------------------------------ constituents --
def _returns(series):
    return [(series[i] / series[i - 1] - 1) for i in range(1, len(series))
            if series[i - 1]]


def _corr(a, b):
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / ((va * vb) ** 0.5)


def constituents(prices, min_corr=0.45, days=120):
    """Which sector each F&O name actually belongs to, MEASURED - not remembered.

    Writing out the constituents of fourteen sector indices from memory across two hundred
    names is exactly the kind of confident list that is wrong in a dozen places and shows
    it to nobody. So instead: pull each index's own history, correlate every stock's daily
    returns against every index, and assign the name to whichever index it actually tracks.

    Returns {sector: [{name, symbol, corr}]}, plus an "unclear" bucket for names that do
    not track anything strongly enough. A weak best-match is not a sector, it is a
    coincidence, and it is reported as unclear rather than filed under whatever number
    happened to be highest.
    """
    r = resolve()
    if not r or not prices:
        return {}, {}
    try:
        import rrg_engine as E
        idx_prices, _, _ = E.fetch_history(list(r.values()), days=days)
    except Exception:
        return {}, {}
    idx_rets = {name: _returns(idx_prices[sym])
                for name, sym in r.items()
                if idx_prices.get(sym) and len(idx_prices[sym]) > 20}
    if not idx_rets:
        return {}, {}

    out, unclear = {}, []
    for sym, closes in prices.items():
        if not closes or len(closes) < 25:
            continue
        nm = str(sym).split(":")[-1].replace("-EQ", "")
        sr = _returns(closes)
        best, best_c = None, 0.0
        for sec, ir in idx_rets.items():
            c = _corr(sr, ir)
            if c is not None and c > best_c:
                best, best_c = sec, c
        if best and best_c >= min_corr:
            out.setdefault(best, []).append({"name": nm, "symbol": sym,
                                             "corr": round(best_c, 2)})
        else:
            unclear.append({"name": nm, "symbol": sym,
                            "corr": round(best_c, 2) if best else None})
    for sec in out:
        out[sec].sort(key=lambda x: x["corr"], reverse=True)
    return out, unclear


def main():
    r = resolve()
    print(f"\n  SECTOR FEED PROBE")
    print("  " + "-" * 56)
    if not r:
        print("  Kuch bhi resolve nahi hua - token nahi hai ya market band hai.")
        print("  Heatmap khaali dikhega. Khaali sach hai; zero bhar dena jhooth hota.")
    for name, _ in SECTORS:
        sym = r.get(name)
        print(f"  {name:<16}{sym or '-- resolve nahi hua --'}")
    print("  " + "-" * 56)
    hm = heatmap()
    if hm:
        print(f"\n  HEATMAP  ({len(hm)} sector)")
        for row in hm:
            print(f"   #{row['rank']:<3}{row['name']:<16}{row['pct']:+.2f}%  {row['tag']}")
    print("\n  Ye context hai, trigger nahi. Iska backtest nahi hua.\n")
    return 0 if r else 1


if __name__ == "__main__":
    raise SystemExit(main())
