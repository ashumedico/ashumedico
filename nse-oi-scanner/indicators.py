"""
indicators.py  —  the five numbers that earn their place. Nothing else.

WHAT IS HERE

  VWAP     volume-weighted, resets every session, the price institutions measure their
           own fills against. Carries information the trend filter does not.
  RVOL     volume against the name's own norm. A move without participation is noise,
           and volume is independent of every price indicator here.
  ATR      the unit everything else is measured in. "Five rupees from resistance" means
           nothing until you know what the name moves in a bar.
  SQUEEZE  range compression - the closest measurable thing to "before the move".
  EXPANSION the bar a coil starts to break. The entry bar, not the fifth bar of a move.

WHAT WAS DELETED, AND WHY

  SUPERTREND  agreed with the existing EMA filter on 91% of bars. Same family, lagging
              the same way, wrong in the same conditions. It bought fewer trades and no
              information.
  CCI         never earned a test, and an oscillator at 15 minutes is mostly noise.

Keeping an indicator nobody acts on is not free. It is one more number on a screen that
has to be read fast, and one more thing that looks like it was considered.

ON "GETTING IN BEFORE THE MOVE"

Nobody does that - it is prediction. What is real is that expansion follows contraction:
ranges narrow, volume dries up, then it breaks. squeeze() measures the coil and
expansion() marks the bar it starts to release. Neither says anything about DIRECTION,
and neither must be read as if it did.

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

    The reset is the whole point. A VWAP running across days is just a slow moving
    average with volume weights; the number traders actually watch is anchored to today's
    open, which is why it works intraday and why a cumulative version would quietly be
    measuring something else.

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
    """Volume against its own recent average. 1.0 is normal, 2.0 is twice normal.

    Relative, not absolute: absolute volume says more about the stock's size than about
    today, and the question is whether THIS move has participation behind it."""
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


def squeeze(bars, short=6, long=30):
    """Range compression: recent true range against its own longer norm.

    A value near 0.5 means the last few bars are half as wide as normal - a coil. Says
    nothing about direction; direction still comes from the trend filter."""
    tr = true_range(bars)
    if len(tr) < long + 2:
        return [1.0] * len(bars)
    s_ma, l_ma = sma(tr, short), sma(tr, long)
    return [(s_ma[i] / l_ma[i] if l_ma[i] else 1.0) for i in range(len(tr))]


def expansion(bars, short=6, long=30, coil=0.7):
    """True on the bar a coil starts to break: it was compressed, and this bar is wider
    than the recent norm. This is the entry bar - the point of the whole exercise."""
    sq = squeeze(bars, short, long)
    tr = true_range(bars)
    l_ma = sma(tr, long)
    out = [False] * len(bars)
    for i in range(1, len(bars)):
        out[i] = sq[i - 1] < coil and tr[i] > l_ma[i]
    return out


def agreement(a, b):
    """Share of bars where two direction series agree. High agreement means the second
    one is repeating the first, not adding to it."""
    pairs = [(x, y) for x, y in zip(a, b) if x and y]
    if not pairs:
        return None
    return sum(1 for x, y in pairs if (x > 0) == (y > 0)) / len(pairs)


def _demo_bars(n=400, seed=5):
    """Synthetic bars with a deliberate coil-then-break around bar 300, so the squeeze
    and expansion logic is exercised rather than merely executed."""
    import random
    random.seed(seed)
    px, out = 700.0, []
    for i in range(n):
        vol_mult = 0.25 if 280 <= i < 300 else (2.5 if 300 <= i < 315 else 1.0)
        o = px
        c = px * (1 + random.gauss(0.0004, 0.006 * vol_mult))
        h, l = max(o, c) * (1 + 0.002 * vol_mult), min(o, c) * (1 - 0.002 * vol_mult)
        v = abs(random.gauss(50000, 20000)) * vol_mult + 1000
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
    vw, rv, sq, ex = (vwap_session(bars, dates), rvol(bars),
                      squeeze(bars), expansion(bars))

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
    print(f"  RVOL         {rv[-1]:>10.2f}")
    print(f"  ATR(14)      {atr(bars)[-1]:>10.2f}")
    print(f"  squeeze      {sq[-1]:>10.2f}   (below 0.70 = coiling)")
    print("  " + "-" * 62)

    fires = [i for i, e in enumerate(ex) if e]
    print(f"  expansion fired on {len(fires)} of {len(bars)} bars"
          f"   ({100*len(fires)/len(bars):.1f}%)")
    print(f"  a coil was planted at bars 280-300, breaking from 300:")
    near = [i for i in fires if 295 <= i <= 320]
    print(f"    fired at {near[:6]}{' ...' if len(near) > 6 else ''}"
          if near else "    *** did not fire on the planted break ***")
    print(f"  squeeze at bar 299 (deep in the coil): {sq[299]:.2f}")
    print(f"  squeeze at bar 320 (after the break):  {sq[320]:.2f}")
    print("  " + "-" * 62)
    print(f"  VWAP agrees with the EMA filter on {agreement([1 if closes[i] > vw[i] else -1 for i in range(len(closes))], ema_dir)*100:.0f}% of bars")
    print("  -> lower agreement means it carries its own information, which is the only")
    print("     reason to keep anything.\n")


if __name__ == "__main__":
    main()
