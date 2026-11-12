"""
market_regime.py  —  is the MARKET worth trading today, before asking which stock?

The strategy picks the strongest name in the universe. That is a relative question, and a
relative answer is worthless in the wrong tape: the strongest name in a falling market
still loses money. This module answers the prior question - what regime are we in - using
only what is already on disk (daily closes), so it costs nothing extra to compute and can
be walk-forward tested like any other rule.

Global sentiment is not fetched from a news feed. It arrives in the tape, and these are the
channels it arrives through:

  TREND      the index's own trend        - the tape's direction
  BREADTH    % of the universe in own-trend - is the move carried by many names or four
  VOL        index realised vol vs its own norm - momentum dies when vol spikes
  DRAWDOWN   how far the index is off its recent high - risk-off shows up here first
  VIX        India VIX vs its own norm (optional) - the price of fear, if we have it

Every measure at bar t uses ONLY bars before t. That is not a style choice: a regime filter
with lookahead would flatter every backtest it touches, which is exactly the trap that
made RRG look profitable.

    python market_regime.py --demo        # see it on synthetic data
    python market_regime.py               # today's regime from your cached history

NOT financial advice.
"""
import argparse

try:
    from rrg_engine import ema
except Exception:                                   # standalone fallback
    def ema(v, n):
        if not v:
            return []
        k = 2.0 / (n + 1)
        out = [v[0]]
        for x in v[1:]:
            out.append(x * k + out[-1] * (1 - k))
        return out


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return 0.0
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def _realised_vol(closes, win):
    if len(closes) < win + 2:
        return 0.0
    rets = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - win, len(closes))]
    m = sum(rets) / len(rets)
    return (sum((r - m) ** 2 for r in rets) / len(rets)) ** 0.5


def breadth_series(prices, fast=20, slow=50):
    """Share of the universe in its own uptrend, at every bar.

    Precomputed in one pass. Computing this inside the backtest loop instead would be
    O(names x bars) per rebalance and would quietly make a sweep unrunnable.
    """
    if not prices:
        return []
    T = max(len(v) for v in prices.values())
    up = [0] * T
    tot = [0] * T
    for series in prices.values():
        n = len(series)
        if n < slow + 2:
            continue
        f, s = ema(series, fast), ema(series, slow)
        off = T - n                                  # right-align short series
        for i in range(slow, n):
            t = i + off
            tot[t] += 1
            if f[i] > s[i] and series[i] > s[i]:
                up[t] += 1
    return [(up[t] / tot[t]) if tot[t] else None for t in range(T)]


def to_daily(series, dates):
    """Collapse intraday bars to one close per session (the last bar of each date)."""
    if not dates or len(dates) != len(series):
        return series
    out, cur = [], None
    for v, d in zip(series, dates):
        if d != cur:
            out.append(v)
            cur = d
        else:
            out[-1] = v
    return out


class Regime:
    """Precomputed regime context. Build once, query at any bar.

    REGIME IS ALWAYS MEASURED ON DAILY BARS, whatever the signal runs on. This is not a
    convenience: the windows here mean things - a 50-period trend, a 60-period drawdown,
    a 120-period volatility norm. On a 15-minute chart those are two days, two days and a
    week, which is not a regime, it is noise wearing a regime's name. Pass `dates` (one
    per bar, as fetch_history returns) and intraday input is folded to sessions first.

    When folding, a query at intraday bar t is answered from the last COMPLETED session.
    Today's daily close is not knowable while today is still trading, and using it would
    put tomorrow's information into today's decision.
    """

    def __init__(self, prices, bench, vix=None, fast=20, slow=50,
                 vol_win=20, dd_win=60, norm_win=120, dates=None):
        self.map = None
        if dates and len(dates) == len(bench):
            daily_bench = to_daily(bench, dates)
            if len(daily_bench) < len(bench):          # input really was intraday
                # bar t -> index of the last session that had already CLOSED at bar t
                seen, idx = {}, []
                order = []
                for d in dates:
                    if d not in seen:
                        seen[d] = len(order)
                        order.append(d)
                    idx.append(seen[d])
                self.map = [i - 1 for i in idx]        # -1 = today's session excluded
                bench = daily_bench
                prices = {k: to_daily(v, dates) for k, v in prices.items()
                          if len(v) == len(dates)}
                if vix:
                    vix = to_daily(vix, dates)
        self.bench = bench
        self.vix = vix
        self.fast, self.slow = fast, slow
        self.vol_win, self.dd_win, self.norm_win = vol_win, dd_win, norm_win
        self.breadth = breadth_series(prices, fast, slow)
        self.ef = ema(bench, fast)
        self.es = ema(bench, slow)

    def _t(self, t):
        """Translate a caller's bar index into this object's (possibly daily) index."""
        if self.map is None:
            return t
        i = max(0, min(t, len(self.map)) - 1)
        return max(0, self.map[i] + 1)                 # +1 = exclusive end, as elsewhere

    # ---- individual channels, each strictly backward-looking ----
    def trend_ok(self, t):
        if t < self.slow + 2:
            return None
        return self.ef[t - 1] > self.es[t - 1] and self.bench[t - 1] > self.es[t - 1]

    def breadth_at(self, t):
        if t < 1 or t - 1 >= len(self.breadth):
            return None
        return self.breadth[t - 1]

    def breadth_ok(self, t, floor=0.40):
        b = self.breadth_at(t)
        return None if b is None else b >= floor

    def vol_ratio(self, t):
        """Index vol now vs its own recent norm. >1 means an unusually noisy tape."""
        hist = self.bench[:t]
        if len(hist) < self.norm_win + self.vol_win + 2:
            return None
        now = _realised_vol(hist, self.vol_win)
        past = [_realised_vol(hist[:i], self.vol_win)
                for i in range(len(hist) - self.norm_win, len(hist), 5)]
        med = _median([p for p in past if p])
        return (now / med) if med else None

    def vol_ok(self, t, cap=1.6):
        r = self.vol_ratio(t)
        return None if r is None else r <= cap

    def drawdown(self, t):
        hist = self.bench[:t]
        if len(hist) < self.dd_win:
            return None
        peak = max(hist[-self.dd_win:])
        return (peak - hist[-1]) / peak if peak else None

    def drawdown_ok(self, t, cap=0.07):
        d = self.drawdown(t)
        return None if d is None else d <= cap

    def vix_ok(self, t, cap=1.35):
        if not self.vix or t < self.norm_win:
            return None
        hist = self.vix[:t]
        med = _median(hist[-self.norm_win:])
        return (hist[-1] <= cap * med) if med else None

    # ---- the verdict ----
    def at(self, t, floor=0.40, vol_cap=1.6, dd_cap=0.07, vix_cap=1.35):
        t = self._t(t)
        checks = {
            "trend": self.trend_ok(t),
            "breadth": self.breadth_ok(t, floor),
            "vol": self.vol_ok(t, vol_cap),
            "drawdown": self.drawdown_ok(t, dd_cap),
            "vix": self.vix_ok(t, vix_cap),
        }
        have = {k: v for k, v in checks.items() if v is not None}
        if not have:
            # Not enough history to judge. Say so rather than defaulting to RISK-OFF,
            # which would silently stop the strategy trading on every short series.
            return {"state": "UNKNOWN", "passed": 0, "of": 0, "checks": checks,
                    "breadth": self.breadth_at(t), "reasons": ["not enough history"]}
        passed = sum(1 for v in have.values() if v)
        n = len(have)
        if passed == n:
            state = "RISK-ON"
        elif passed <= n // 2:
            state = "RISK-OFF"
        else:
            state = "NEUTRAL"
        reasons = [f"{k} {'ok' if v else 'FAIL'}" for k, v in have.items()]
        return {"state": state, "passed": passed, "of": n, "checks": checks,
                "breadth": self.breadth_at(t), "vol_ratio": self.vol_ratio(t),
                "drawdown": self.drawdown(t), "reasons": reasons}

    def tradeable(self, t, mode="gate", **kw):
        """mode: off = ignore regime | gate = block RISK-OFF | strict = only RISK-ON."""
        if mode in (None, "off", False):
            return True
        r = self.at(t, **kw)
        if r["state"] == "UNKNOWN":
            return True
        if mode == "strict":
            return r["state"] == "RISK-ON"
        return r["state"] != "RISK-OFF"


def render(r):
    col = {"RISK-ON": "risk-on", "NEUTRAL": "neutral",
           "RISK-OFF": "RISK-OFF", "UNKNOWN": "unknown"}[r["state"]]
    print(f"\n  MARKET REGIME : {col}   ({r['passed']}/{r['of']} checks passed)")
    print("  " + "-" * 54)
    for k, v in r["checks"].items():
        mark = "-" if v is None else ("ok" if v else "FAIL")
        extra = ""
        if k == "breadth" and r.get("breadth") is not None:
            extra = f"  ({r['breadth']*100:.0f}% of names in own-trend)"
        if k == "vol" and r.get("vol_ratio"):
            extra = f"  ({r['vol_ratio']:.2f}x normal)"
        if k == "drawdown" and r.get("drawdown") is not None:
            extra = f"  ({r['drawdown']*100:.1f}% off the high)"
        print(f"    {k:<10} {mark}{extra}")
    print("  " + "-" * 54)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    import rrg_engine as E
    if a.demo:
        _pts, prices, bench = E.demo_points()
    else:
        prices, bench, _dates = E.fetch_history(
            __import__("fno_universe").fno_stocks(), days=400)
    reg = Regime(prices, bench)
    render(reg.at(len(bench)))
    print(f"  tradeable (gate)  : {reg.tradeable(len(bench), 'gate')}")
    print(f"  tradeable (strict): {reg.tradeable(len(bench), 'strict')}\n")


if __name__ == "__main__":
    main()
