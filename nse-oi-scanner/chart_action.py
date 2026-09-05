"""
chart_action.py  —  the "Chart Action Analyzer" layer (Chartonix-style), in code.

Turns a candle series into the same read a chartist gives a screenshot:
  • TREND        — primary + secondary  (e.g. "Bullish + Sideways")
  • RESISTANCE   — R1, R2  (pivot swing-highs above price = the ceilings)
  • SUPPORT      — S1, S2  (pivot swing-lows below price = the floors)
  • CONTINUATION — are the last 3-5 candles pushing one way?
  • BREAKOUT     — 60%-body rule: did price close through a level with conviction?

No live feed needed to develop: fetch_dry() builds a realistic OHLC series.
Live uses Fyers history() (fetch_candles). NOT financial advice.
"""
import os, math

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = ""; TOKEN_FILE = "access_token.txt"
    config = _C()


# ---------- pivots / levels ----------
def _pivots(candles, left=2, right=2):
    """Return (highs, lows) pivot indices: a bar higher/lower than `left`+`right` neighbours."""
    highs, lows = [], []
    n = len(candles)
    for i in range(left, n - right):
        h = candles[i]["h"]; l = candles[i]["l"]
        if all(candles[j]["h"] <= h for j in range(i - left, i)) and \
           all(candles[i + 1 + j]["h"] <= h for j in range(right)):
            highs.append(i)
        if all(candles[j]["l"] >= l for j in range(i - left, i)) and \
           all(candles[i + 1 + j]["l"] >= l for j in range(right)):
            lows.append(i)
    return highs, lows


def _cluster(levels, tol):
    """Merge nearby price levels into representative bands (mean of each cluster)."""
    if not levels:
        return []
    levels = sorted(levels)
    bands, cur = [], [levels[0]]
    for x in levels[1:]:
        if abs(x - cur[-1]) <= tol:
            cur.append(x)
        else:
            bands.append(sum(cur) / len(cur)); cur = [x]
    bands.append(sum(cur) / len(cur))
    return bands


def support_resistance(candles):
    """Two nearest resistances above and two supports below the last close."""
    close = candles[-1]["c"]
    rng = max(c["h"] for c in candles) - min(c["l"] for c in candles)
    tol = rng * 0.008 or close * 0.002              # cluster tolerance ~0.8% of range
    hi_idx, lo_idx = _pivots(candles)
    highs = _cluster([candles[i]["h"] for i in hi_idx], tol)
    lows = _cluster([candles[i]["l"] for i in lo_idx], tol)

    res = sorted(h for h in highs if h > close)              # ceilings above
    sup = sorted((l for l in lows if l < close), reverse=True)  # floors below
    step = max(tol * 4, close * 0.004)                        # synthetic spacing if a side is thin
    R1 = round(res[0], 1) if len(res) > 0 else round(close + step, 1)
    R2 = round(res[1], 1) if len(res) > 1 else round(R1 + step, 1)
    S1 = round(sup[0], 1) if len(sup) > 0 else round(close - step, 1)
    S2 = round(sup[1], 1) if len(sup) > 1 else round(S1 - step, 1)
    return {"R1": R1, "R2": R2, "S1": S1, "S2": S2}


# ---------- trend ----------
def _slope_pct(vals):
    """Least-squares slope of a series, normalised to % of mean."""
    n = len(vals); xs = list(range(n))
    mx = sum(xs) / n; my = sum(vals) / n
    num = sum((xs[i] - mx) * (vals[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n)) or 1
    slope = num / den
    return slope / (my or 1) * 100 * n                       # % move across the window


def trend(candles):
    """Primary trend over the whole window + secondary read of the recent tail."""
    closes = [c["c"] for c in candles]
    start = closes[0]
    hi = max(candles, key=lambda c: c["h"]); lo = min(candles, key=lambda c: c["l"])
    hi_i = candles.index(hi); lo_i = candles.index(lo)
    up_amp = (hi["h"] - start) / start * 100          # how far it rallied off the start
    dn_amp = (start - lo["l"]) / start * 100          # how far it fell off the start

    # PRIMARY = the dominant impulse: a big rally with its low BEFORE its high is an
    # uptrend (now maybe pulling back); mirror for downtrend. Else genuinely sideways.
    if up_amp > 1.2 and up_amp >= dn_amp and lo_i <= hi_i:
        primary = "Bullish"
    elif dn_amp > 1.2 and dn_amp > up_amp and hi_i <= lo_i:
        primary = "Bearish"
    else:
        primary = "Sideways"

    tail = _slope_pct(closes[-5:]) if len(closes) >= 5 else 0
    full = _slope_pct(closes)
    secondary = "Bullish" if tail > 1.2 else "Bearish" if tail < -1.2 else "Sideways"
    # structure: higher-highs & higher-lows?
    hi_idx, lo_idx = _pivots(candles)
    hh = len(hi_idx) >= 2 and candles[hi_idx[-1]]["h"] > candles[hi_idx[0]]["h"]
    ll = len(lo_idx) >= 2 and candles[lo_idx[-1]]["l"] < candles[lo_idx[0]]["l"]
    if primary == secondary:
        combined = primary
    else:
        combined = f"{primary} + {secondary}"
    structure = "HH-HL" if (hh and not ll) else "LH-LL" if (ll and not hh) else "range"
    return {"primary": primary, "secondary": secondary, "combined": combined,
            "structure": structure, "slope_pct": round(full, 2), "tail_pct": round(tail, 2)}


# ---------- continuation + 60% body breakout ----------
def continuation(candles, n=5):
    """How many of the last n candles share one direction (green/red run)."""
    tail = candles[-n:]
    ups = sum(1 for c in tail if c["c"] >= c["o"])
    downs = len(tail) - ups
    if ups >= 3:   return {"dir": "up", "count": ups, "of": len(tail)}
    if downs >= 3: return {"dir": "down", "count": downs, "of": len(tail)}
    return {"dir": "mixed", "count": max(ups, downs), "of": len(tail)}


def body_breakout(candle, level, min_body=0.60):
    """60% rule: did this candle close THROUGH `level` with body >= 60% of its range?"""
    rng = candle["h"] - candle["l"]
    if rng <= 0:
        return None
    body = abs(candle["c"] - candle["o"]) / rng
    if body < min_body:
        return None
    if candle["o"] < level <= candle["c"]:
        return {"dir": "up", "body_pct": round(body * 100)}
    if candle["o"] > level >= candle["c"]:
        return {"dir": "down", "body_pct": round(body * 100)}
    return None


def analyse(candles):
    """Full chart-action read for one instrument. `candles`: list of {o,h,l,c,v}."""
    sr = support_resistance(candles)
    tr = trend(candles)
    cont = continuation(candles)
    last = candles[-1]
    # test a 60%-body breakout of the nearest level in the direction of travel
    brk = None
    for lvl_name in ("R1", "S1"):
        b = body_breakout(last, sr[lvl_name])
        if b:
            brk = {"level": lvl_name, "price": sr[lvl_name], **b}
            break
    return {"close": last["c"], "levels": sr, "trend": tr,
            "continuation": cont, "breakout": brk, "candles": candles}


# ---------- data ----------
def fetch_candles(symbol, resolution="15", days=5):
    """Live OHLC via Fyers history(). Returns list of {t,o,h,l,c,v}."""
    from fyers_apiv3 import fyersModel
    from datetime import datetime, timedelta, timezone
    IST = timezone(timedelta(hours=5, minutes=30))
    token = open(config.TOKEN_FILE).read().strip()
    fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)
    # Fyers rejects 1D/1W/1M requests spanning >366 days (use rrg_engine.fetch_history,
    # which chunks, when you need more than a year of daily bars).
    if resolution in ("D", "1D", "W", "1W", "M", "1M"):
        days = min(days, 360)
    to = datetime.now(IST); frm = to - timedelta(days=days)
    r = fy.history({"symbol": symbol, "resolution": resolution, "date_format": "1",
                    "range_from": frm.strftime("%Y-%m-%d"), "range_to": to.strftime("%Y-%m-%d"),
                    "cont_flag": "1"})
    if not isinstance(r, dict) or r.get("s") != "ok":
        raise RuntimeError(f"history error: {r}")
    return [{"t": c[0], "o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]}
            for c in r.get("candles", [])]


def fetch_dry(symbol="NSE:NIFTY50-INDEX", base=24200.0, shape="bull_flag"):
    """Deterministic synthetic OHLC so charts render with no live feed.
    shape: 'bull_flag' (up then consolidate), 'bear' (down), 'range' (sideways)."""
    candles = []
    price = base
    # scripted % moves per candle for each archetype (reproducible, no randomness)
    # each archetype: build structure (highs/lows), then END on a pullback/consolidation
    # so entry sits mid-range with room to the target and a defined stop (clean R:R).
    # zig-zag up/down to seed swing highs (R1/R2) and lows (S1/S2), then END the
    # series at the setup: bull pulls back to SUPPORT, bear bounces to RESISTANCE.
    scripts = {
        # rally (swing highs) -> pullback to support -> small bounce = buy-the-dip
        "bull_flag": [0.6, 0.7, -0.3, 0.5, 0.8, -0.35, 0.6, 0.7, -0.4, -0.5,
                      -0.5, -0.45, -0.4, -0.3, 0.15, 0.1, -0.05, 0.2, 0.15, 0.25],
        # decline (swing lows) -> bounce to resistance -> small stall = sell-the-bounce
        "bear":      [-0.6, -0.7, 0.3, -0.5, -0.8, 0.35, -0.6, -0.7, 0.4, 0.5,
                      0.5, 0.45, 0.4, 0.3, -0.15, -0.1, 0.05, -0.2, -0.15, -0.25],
        # even oscillation between floor and ceiling = no edge (excluded)
        "range":     [0.5, 0.4, -0.45, -0.5, 0.5, 0.45, -0.5, -0.45, 0.5, 0.4,
                      -0.45, -0.5, 0.5, 0.45, -0.5, -0.45, 0.5, 0.4, -0.45, -0.4],
    }
    seq = scripts.get(shape, scripts["bull_flag"])
    for i, mv in enumerate(seq):
        o = price
        c = o * (1 + mv / 100)
        span = abs(c - o)
        h = max(o, c) + span * 0.6 + o * 0.0008
        l = min(o, c) - span * 0.6 - o * 0.0008
        candles.append({"t": i, "o": round(o, 1), "h": round(h, 1),
                        "l": round(l, 1), "c": round(c, 1), "v": 100000 + i * 3000})
        price = c
    return candles


def render(symbol, a):
    tr = a["trend"]; sr = a["levels"]; cont = a["continuation"]
    print(f"\n  CHART ACTION  ·  {symbol}   close {a['close']}")
    print("  " + "-" * 54)
    print(f"  Trend ......... {tr['combined']}   ({tr['structure']}, {tr['slope_pct']:+}% window)")
    print(f"  Resistance .... R1 {sr['R1']}   R2 {sr['R2']}")
    print(f"  Support ....... S1 {sr['S1']}   S2 {sr['S2']}")
    print(f"  Continuation .. {cont['count']}/{cont['of']} candles {cont['dir']}")
    if a["breakout"]:
        b = a["breakout"]
        print(f"  BREAKOUT ...... {b['dir']} through {b['level']} {b['price']} "
              f"(body {b['body_pct']}% ≥ 60%)")
    print("  " + "-" * 54)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="NSE:NIFTY50-INDEX")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shape", default="bull_flag")
    args = ap.parse_args()
    candles = fetch_dry(args.symbol, shape=args.shape) if args.dry_run else fetch_candles(args.symbol)
    render(args.symbol + (" [DRY]" if args.dry_run else ""), analyse(candles))


if __name__ == "__main__":
    main()
