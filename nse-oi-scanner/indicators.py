"""
indicators.py  —  VWAP, RVOL, ATR, Supertrend, CCI. Candidates, not conclusions.

Asked whether EMA, CCI, VWAP and Supertrend should be added. Two things are worth saying
before any of them goes near a decision.

WHAT IS ACTUALLY DIFFERENT FROM WHAT WE ALREADY HAVE

  EMA        already the filter. abs_trend IS an EMA cross plus a price test.
  SUPERTREND an ATR band around a moving average - the same family as the EMA filter,
             lagging in the same way, wrong in the same conditions. Stacking it on top
             is one filter with extra steps, and every extra filter costs trades.
  CCI        an oscillator, so genuinely a different family from the trend filter, but
             noisy at 15 minutes.
  VWAP       the one clearly orthogonal member: volume-weighted, resets each session,
             and the price institutions measure their own fills against.
  RVOL       not asked for, and probably the most valuable of the set. A move on no
             volume is noise, and volume is independent of every price-based indicator
             here.

AND THE POINT THAT MATTERS MORE THAN ANY OF THEM

RRG looked exactly this reasonable. Tested, it cost 6.3% after costs for 141 extra
trades. So nothing here is wired into the live rule. Each is a function that computes a
number; whether any of them earns a place is for the walk-forward to say, on his data,
against the same baseline that killed the rotation.

    python indicators.py --demo
"""
import argparse


def _hlc(bars):
    return ([b[2] for b in bars], [b[3] for b in bars], [b[4] for b in bars])


def sma(v, n):
    out, s = [], 0.0
    for i, x in enumerate(v):
        s += x
        if i >= n:
            s -= v[i - n]
        out.append(s / min(i + 1, n))
    return out


def vwap_session(bars, dates):
    """Volume-weighted average price, RESET EVERY SESSION.

    The reset is the whole point. A VWAP running continuously across days is just a slow
    moving average with volume weights; the number traders actually watch is anchored to
    today's open, which is why it works as an intraday reference and why a cumulative
    version would quietly be measuring something else.

    bars: [[epoch, o, h, l, c, v], ...]   dates: one date string per bar.
    """
    out, cum_pv, cum_v, cur = [], 0.0, 0.0, None
    for b, d in zip(bars, dates):
        if d != cur:
            cum_pv, cum_v, cur = 0.0, 0.0, d
        typical = (b[2] + b[3] + b[4]) / 3.0
        vol = float(b[5] or 0)
        cum_pv += typical * vol
        cum_v += vol
        out.append(cum_pv / cum_v if cum_v else b[4])
    return out


def rvol(bars, n=20):
    """Volume against its own recent average. 1.0 is a normal bar, 2.0 is twice normal.

    Relative, not absolute, because absolute volume says more about the stock's size than
    about today - and the question is whether THIS move has participation behind it."""
    vols = [float(b[5] or 0) for b in bars]
    avg = sma(vols, n)
    return [(v / a if a else 0.0) for v, a in zip(vols, avg)]


def true_range(bars):
    highs, lows, closes = _hlc(bars)
    out = [highs[0] - lows[0]] if bars else []
    for i in range(1, len(bars)):
        out.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    return out


def atr(bars, n=14):
    tr = true_range(bars)
    if not tr:
        return []
    out = [tr[0]]
    for i in range(1, len(tr)):                     # Wilder smoothing
        out.append((out[-1] * (n - 1) + tr[i]) / n)
    return out


def supertrend(bars, n=10, mult=3.0):
    """Direction series: +1 uptrend, -1 downtrend.

    Included so the claim that it duplicates the EMA filter can be measured rather than
    asserted. If their agreement is high, adding it buys nothing but fewer trades."""
    if len(bars) < n + 2:
        return [0] * len(bars)
    a = atr(bars, n)
    highs, lows, closes = _hlc(bars)
    dirs, upper, lower = [], None, None
    d = 1
    for i in range(len(bars)):
        mid = (highs[i] + lows[i]) / 2.0
        u, l = mid + mult * a[i], mid - mult * a[i]
        upper = u if upper is None or closes[i - 1] > upper else min(u, upper)
        lower = l if lower is None or closes[i - 1] < lower else max(l, lower)
        if closes[i] > (upper if d < 0 else lower):
            d = 1 if closes[i] > upper or d > 0 else d
        if closes[i] > upper:
            d = 1
        elif closes[i] < lower:
            d = -1
        dirs.append(d)
    return dirs


def cci(bars, n=20):
    """Commodity Channel Index: how far price sits from its mean, in mean-deviation units."""
    highs, lows, closes = _hlc(bars)
    tp = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(len(bars))]
    ma = sma(tp, n)
    out = []
    for i in range(len(tp)):
        lo = max(0, i - n + 1)
        window = tp[lo:i + 1]
        md = sum(abs(x - ma[i]) for x in window) / len(window)
        out.append((tp[i] - ma[i]) / (0.015 * md) if md else 0.0)
    return out


def agreement(a, b):
    """Share of bars where two direction series say the same thing. High agreement means
    the second one is not adding information, it is repeating the first."""
    pairs = [(x, y) for x, y in zip(a, b) if x and y]
    if not pairs:
        return None
    return sum(1 for x, y in pairs if (x > 0) == (y > 0)) / len(pairs)


def _demo_bars(n=400, seed=5):
    import random
    random.seed(seed)
    px, out, day = 700.0, [], 0
    for i in range(n):
        if i % 25 == 0:
            day += 1
        o = px
        c = px * (1 + random.gauss(0.0004, 0.006))
        h, l = max(o, c) * 1.002, min(o, c) * 0.998
        v = abs(random.gauss(50000, 20000)) + 1000
        out.append([i, o, h, l, c, v])
        px = c
    dates = [f"2026-08-{(i // 25) % 28 + 1:02d}" for i in range(n)]
    return out, dates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.parse_args()
    bars, dates = _demo_bars()
    closes = [b[4] for b in bars]
    vw = vwap_session(bars, dates)
    rv = rvol(bars)
    st = supertrend(bars)
    cc = cci(bars)

    try:
        from rrg_engine import ema
    except Exception:
        def ema(v, n):
            k = 2.0 / (n + 1); out = [v[0]]
            for x in v[1:]:
                out.append(x * k + out[-1] * (1 - k))
            return out
    ef, es = ema(closes, 10), ema(closes, 30)
    ema_dir = [1 if (ef[i] > es[i] and closes[i] > es[i]) else
               (-1 if (ef[i] < es[i] and closes[i] < es[i]) else 0)
               for i in range(len(closes))]

    print(f"\n  {len(bars)} bars, {len(set(dates))} sessions   (synthetic - mechanics only)")
    print("  " + "-" * 62)
    print(f"  close        {closes[-1]:>10.2f}")
    print(f"  VWAP (today) {vw[-1]:>10.2f}   price {'above' if closes[-1] > vw[-1] else 'below'} VWAP")
    print(f"  RVOL         {rv[-1]:>10.2f}   ({'above' if rv[-1] > 1 else 'below'} normal volume)")
    print(f"  ATR(14)      {atr(bars)[-1]:>10.2f}")
    print(f"  CCI(20)      {cc[-1]:>10.1f}")
    print(f"  Supertrend   {st[-1]:>10}   EMA filter {ema_dir[-1]:>4}")
    print("  " + "-" * 62)

    ag = agreement(st, ema_dir)
    print(f"  Supertrend agrees with the EMA filter on {ag*100:.0f}% of bars")
    if ag and ag > 0.8:
        print("  -> mostly the same signal. Adding it would cut trades without adding")
        print("     information. Measure it on real data before believing either way.")
    vwap_dir = [1 if closes[i] > vw[i] else -1 for i in range(len(closes))]
    print(f"  VWAP agrees with the EMA filter on {agreement(vwap_dir, ema_dir)*100:.0f}% of bars")
    print("  -> lower agreement means it is carrying its own information, which is the")
    print("     only reason to add anything.\n")


if __name__ == "__main__":
    main()
