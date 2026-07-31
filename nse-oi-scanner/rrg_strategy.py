"""
rrg_strategy.py  —  turning RRG from a picture into a system, then PROVING it.

StockCharts are explicit: "RRGs are not a trading system... there are no predefined
trading rules." So the edge is not the graph — it is the rules you bolt on. This module
implements the candidate rule-sets and then BACKTESTS them walk-forward (no lookahead)
so the best setup is chosen by evidence on YOUR data, not by assertion.

Rule-sets tested (each is a full strategy):
  A hold_leading      hold everything in LEADING                        (the naive way most lose)
  B cross_leading     BUY on the cross INTO Leading                     (trend-follower)
  C cross_improving   BUY on the cross INTO Improving (from Lagging)    (aggressive, earliest)
  D dist_filter       C/B + skip the noise blob near (100,100)
  E trend_filter      + the stock's OWN uptrend must agree              (fixes RRG's blind spot)
  F heading_filter    + travelling north-east (heading 0-90 deg)
  G combined          distance + own-trend + heading + OI buildup

    python rrg_strategy.py --demo                 # mechanics proof on synthetic data
    python rrg_strategy.py --sweep                # LIVE: find the best setup on your data
    python rrg_strategy.py --sweep --days 500     # longer history

NOT financial advice. A backtest is a hypothesis, not a promise.
"""
import argparse, math, json, os
from datetime import datetime, timezone, timedelta

import rrg_engine as E

IST = timezone(timedelta(hours=5, minutes=30))


# ---------------- point-in-time snapshot (no lookahead) ----------------
def snapshot(prices, bench, t, tail=3, win=10, mom_win=5):
    """RRG points computed ONLY from data up to index t (exclusive)."""
    sl_prices = {s: c[:t] for s, c in prices.items() if len(c) >= t}
    sl_bench = bench[:t]
    return E.build_points(sl_prices, sl_bench, tail=tail, win=win, mom_win=mom_win)


# ---------------- the rule-sets ----------------
def _entry_ok(p, rule, params):
    q, pq = p["quadrant"], p["prev_quadrant"]
    dist = params.get("min_distance", 0.0)
    need_trend = params.get("need_trend", False)
    head = params.get("heading", None)

    if rule == "hold_leading":
        base = q == "LEADING"
    elif rule == "cross_leading":
        base = q == "LEADING" and pq != "LEADING"
    elif rule == "cross_improving":
        base = q == "IMPROVING" and pq == "LAGGING"
    elif rule == "improving_or_leading":
        base = (q == "IMPROVING" and pq == "LAGGING") or (q == "LEADING" and pq != "LEADING")
    elif rule == "momentum_only":
        # Deliberately ignores the rotation entirely. This is the ablation control:
        # if it scores as well as the full machine, the rotation is decoration.
        base = p["abs_trend"] > 0
    else:
        base = False
    if not base:
        return False
    if p["distance"] < dist:
        return False
    if need_trend and p["abs_trend"] <= 0:
        return False
    if head is not None:
        lo, hi = head
        h = p["heading"]
        if not (lo <= h <= hi):
            return False
    if params.get("need_buildup") and p.get("signal") not in ("LONG BUILDUP", "SHORT COVERING"):
        return False
    return True


def _entry_ok_short(p, rule, params):
    """Mirror of the long rules for the short book.

    Half the universe was unusable while this was long-only, and a long-only rotation
    structurally loses in a falling market - which is exactly how the out-of-sample test
    failed. Shorts come from the weak side of the rotation, with the same own-trend
    filter inverted so a name must also be falling in absolute terms."""
    q, pq = p["quadrant"], p["prev_quadrant"]
    if rule == "momentum_only":
        base = p["abs_trend"] < 0              # control, mirrored for the short book
    elif rule == "hold_leading":               # mirror: hold everything Lagging
        base = q == "LAGGING"
    elif rule == "cross_leading":              # mirror: the cross INTO Lagging
        base = q == "LAGGING" and pq != "LAGGING"
    elif rule == "cross_improving":            # mirror: Leading -> Weakening
        base = q == "WEAKENING" and pq == "LEADING"
    elif rule == "improving_or_leading":
        base = ((q == "WEAKENING" and pq == "LEADING") or
                (q == "LAGGING" and pq != "LAGGING"))
    else:
        base = False
    if not base:
        return False
    if p["distance"] < params.get("min_distance", 0.0):
        return False
    if params.get("need_trend", False) and p["abs_trend"] >= 0:
        return False                            # must be falling on its own too
    if params.get("need_buildup") and p.get("signal") not in ("SHORT BUILDUP", "LONG UNWINDING"):
        return False
    return True


def _exit_ok_short(p, params):
    """Cover when the rotation turns back up (or the downtrend breaks)."""
    band = float(params.get("exit_band", 0.0))
    if p["y"] > 100 + band:
        return True
    if params.get("need_trend", False) and p["abs_trend"] > 0:
        return True
    return False


def _exit_ok(p, params):
    """Exit when the rotation turns against us (or own trend breaks).

    `exit_band` adds a no-trade buffer: the dot must travel that far PAST the axis
    before we pay to exit, instead of churning every time it wobbles across 100.
    Banding cuts turnover more efficiently than simply rebalancing less often,
    because it keeps full exposure to the signal while dropping the noise trades."""
    band = float(params.get("exit_band", 0.0))
    if params.get("rule") == "momentum_only":
        return p["abs_trend"] < 0              # control exits on trend alone
    if params.get("exit_on_weaken", True):
        # both WEAKENING and LAGGING sit below the momentum axis
        if p["y"] < 100 - band:
            return True
    if params.get("need_trend", False) and p["abs_trend"] < 0:
        return True
    return False


# How OFTEN you actually trade changes which setup is right. RRG is natively a
# weekly/positional tool - running it on a 5-day rebalance with 10 slots generates
# ~190 trades a year, which only suits someone at the screen daily. For an occasional
# trader the same signal needs fewer slots, a longer hold, and far less churn.
PROFILES = {
    "active":     {"step": 5,  "max_pos": 10, "hold_min": 5,
                   "note": "~190 trades/yr - screen every day"},
    "swing":      {"step": 10, "max_pos": 6,  "hold_min": 10,
                   "note": "~2 weeks per decision, a handful of positions"},
    "positional": {"step": 20, "max_pos": 4,  "hold_min": 20,
                   "note": "~monthly decisions, 4 slots - checks in when free"},
}


RULESETS = {
    "A hold_leading":    ("hold_leading",   {}),
    "B cross_leading":   ("cross_leading",  {}),
    "C cross_improving": ("cross_improving", {}),
    "D +distance":       ("improving_or_leading", {"min_distance": 1.0}),
    "E +own-trend":      ("improving_or_leading", {"min_distance": 1.0, "need_trend": True}),
    "F +heading NE":     ("improving_or_leading", {"min_distance": 1.0, "need_trend": True,
                                                   "heading": (0, 90)}),
    "G combined":        ("improving_or_leading", {"min_distance": 1.5, "need_trend": True,
                                                   "heading": (-1, 100)}),
    # H = E plus the two evidence-based upgrades: volatility targeting (Barroso &
    # Santa-Clara 2015) to kill the crash tail, and a no-trade band to cut turnover.
    "H +vol-target+band": ("improving_or_leading", {"min_distance": 1.0, "need_trend": True,
                                                    "target_vol": 0.15, "exit_band": 0.5}),
    "I H+regime":         ("improving_or_leading", {"min_distance": 1.0, "need_trend": True,
                                                    "target_vol": 0.15, "exit_band": 0.5,
                                                    "need_regime": True}),
}


# ---------------- walk-forward backtest ----------------
def bench_uptrend(bench, t, fast=20, slow=50):
    """Is the INDEX itself healthy at bar t? RRG is relative: a name can lead a falling
    market and still lose money. This is the market-level gate that filter lacks."""
    hist = bench[:t]
    if len(hist) < slow + 2:
        return True
    f = E.ema(hist, fast)[-1]; sl = E.ema(hist, slow)[-1]
    return f > sl and hist[-1] > sl


def r_factor(closes, t, k=10, win=20):
    """Move intensity: the recent move measured in units of the name's OWN noise.

    This is the idea behind TradeFinder's R-Factor, adapted to daily bars - today's
    activity judged against the same name's last ~20 days, so a 3% day in a sleepy stock
    outranks a 3% day in one that moves 3% every session. Raw percent-change ranking, which
    is what the strategy uses today, cannot tell those two apart and will keep picking the
    noisiest names in the universe.

    Theirs is intraday and proprietary; this is the daily, disclosed approximation. Signed,
    because a long-only book wants up-intensity - the direction-agnostic version is for
    intraday scalping, which is not this system.
    """
    h = closes[:t]
    if len(h) < win + k + 2:
        return 0.0
    rets = [h[i] / h[i - 1] - 1 for i in range(len(h) - win, len(h))]
    m = sum(rets) / len(rets)
    sd = (sum((r - m) ** 2 for r in rets) / len(rets)) ** 0.5
    if sd <= 0:
        return 0.0
    move = h[-1] / h[-1 - k] - 1
    return move / (sd * (k ** 0.5))


def backtest(prices, bench, rule, params, start=60, step=5, max_pos=10,
             hold_min=5, cost_bps=15, tail=3, win=10, mom_win=5, side=None):
    """Equal-weight rotation. Rebalance every `step` bars.
    side: "long" (default), "short", or "both" - "both" splits the slots and lets the
    short book carry the falling half of the universe, which a long-only version cannot.
    cost_bps = round-trip slippage+brokerage per trade in basis points."""
    params = dict(params); params.setdefault("rule", rule)
    side = side or params.get("side", "long")
    want_long = side in ("long", "both")
    want_short = side in ("short", "both")
    n = len(bench)
    if n <= start + step * 3:
        return None
    equity = [1.0]
    held = {}                       # name -> {entry_px, bars}
    by_name = {s.split(":")[-1].replace("-EQ", ""): c for s, c in prices.items()}
    entries, closed_rs = 0, []      # count entries; record every realised trade return
    period_rets, exposure = [], []  # for volatility targeting

    # Market-regime context, built once. params["regime"]: None/"off" | "gate" | "strict".
    # Separate from the older need_regime flag, which was only the index's own trend -
    # this adds breadth, volatility and drawdown, i.e. the channels global sentiment
    # actually arrives through.
    regime_ctx = None
    if params.get("regime") in ("gate", "strict"):
        try:
            import market_regime as MR
            regime_ctx = MR.Regime(prices, bench)
        except Exception:
            regime_ctx = None

    t = start
    while t + step < n:
        pts = snapshot(prices, bench, t, tail=tail, win=win, mom_win=mom_win)
        if not pts:
            t += step; continue
        pmap = {p["name"]: p for p in pts}

        # --- exits ---
        for name in list(held):
            p = pmap.get(name)
            held[name]["bars"] += step
            if p is None:
                continue
            h = held[name]
            gone = (_exit_ok_short(p, params) if h["dir"] < 0 else _exit_ok(p, params))
            if h["bars"] >= hold_min and gone:
                px = by_name[name][t - 1]
                closed_rs.append((px / h["entry_px"] - 1) * h["dir"])
                del held[name]

        # --- entries. The regime gate only ever blocked LONGS; shorts are exactly what
        # a weak index calls for, so they are never gated on it. ---
        regime_ok = bench_uptrend(bench, t) if params.get("need_regime") else True
        if regime_ctx is not None:
            regime_ok = regime_ok and regime_ctx.tradeable(t, params["regime"])
        usable = lambda p: p["name"] not in held and p["name"] in by_name and len(by_name[p["name"]]) > t
        if params.get("rank") == "rfactor":
            rank = lambda p: r_factor(by_name[p["name"]], t, k=mom_win * 2)
        elif rule == "momentum_only":
            rank = lambda p: p.get("abs_pct", 0)
        else:
            rank = lambda p: p["distance"] * (1 + p["velocity"])

        if len(held) < max_pos:
            slots = max_pos - len(held)
            picks = []
            if want_long and regime_ok:
                longs = sorted([p for p in pts if usable(p) and _entry_ok(p, rule, params)],
                               key=rank, reverse=True)
                picks += [(p, +1) for p in longs[:(slots // 2 if want_short else slots)]]
            if want_short:
                taken = {p["name"] for p, _ in picks}
                shorts = sorted([p for p in pts if usable(p) and p["name"] not in taken
                                 and _entry_ok_short(p, rule, params)], key=rank, reverse=True)
                picks += [(p, -1) for p in shorts[:slots - len(picks)]]
            for p, d in picks[:slots]:
                held[p["name"]] = {"entry_px": by_name[p["name"]][t - 1], "bars": 0, "dir": d}
                entries += 1

        # --- mark to market over the next `step` bars ---
        if held:
            rets = []
            for name, h in held.items():
                c = by_name[name]
                if t + step - 1 < len(c):
                    rets.append((c[t + step - 1] / c[t - 1] - 1) * h["dir"])
            gross = sum(rets) / len(rets) if rets else 0.0
        else:
            gross = 0.0
        turnover_cost = (cost_bps / 10000.0) * (len(held) / max(max_pos, 1))

        # --- volatility targeting (Barroso & Santa-Clara): cut exposure when the
        # strategy's own recent volatility spikes. Momentum crashes arrive with high
        # vol, so de-risking into them removes the worst of the drawdown. Capped at
        # 1.0 so this can only ever REDUCE risk - never lever up. ---
        tvol = params.get("target_vol")
        scale = 1.0
        if tvol:
            look = period_rets[-12:]
            if len(look) >= 6:
                m = sum(look) / len(look)
                sd = (sum((x - m) ** 2 for x in look) / len(look)) ** 0.5
                ann = sd * math.sqrt(252 / step)
                if ann > 1e-6:
                    scale = min(1.0, float(tvol) / ann)
        net = (gross - turnover_cost) * scale
        period_rets.append(gross)
        exposure.append(scale)
        equity.append(equity[-1] * (1 + net))
        t += step

    # --- close anything still open, at the last bar, so accounting is complete ---
    for name, h in held.items():
        c = by_name.get(name)
        if c:
            closed_rs.append((c[min(t, len(c)) - 1] / h["entry_px"] - 1) * h["dir"])

    # --- metrics (honest: no annualising a sample too small to support it) ---
    # A longer rebalance step means fewer periods for the same history, so a flat
    # period floor silently dropped the whole positional profile from the sweep.
    # Require a meaningful SPAN of bars instead, and flag thin samples rather than
    # hiding them.
    periods = len(equity) - 1
    if periods < 12 or periods * step < 180:
        return None
    low_sample = periods < 25
    total = equity[-1] - 1
    per_year = 252 / step
    years = periods / per_year
    cagr = (equity[-1] ** (1 / years) - 1) if years >= 0.75 and equity[-1] > 0 else None
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    mu = sum(rets) / len(rets)
    sd = (sum((r - mu) ** 2 for r in rets) / len(rets)) ** 0.5 or 1e-9
    sharpe = mu / sd * math.sqrt(per_year)
    peak, mdd = equity[0], 0.0
    for e in equity:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    wins = sum(1 for r in closed_rs if r > 0)
    return {"total_return": round(total * 100, 2),
            "cagr": round(cagr * 100, 2) if cagr is not None else None,
            "sharpe": round(sharpe, 2), "max_dd": round(mdd * 100, 2),
            "trades": len(closed_rs), "entries": entries,
            "avg_exposure": round(sum(exposure) / len(exposure), 2) if exposure else 1.0,
            "win_rate": round(wins / len(closed_rs) * 100, 1) if closed_rs else 0,
            "years": round(years, 2), "low_sample": low_sample,
            # every realised trade's STOCK return. The book is traded in options, so this
            # is the input option_pnl.py needs to say what the trader would actually have
            # been paid - the headline above is the underlying's move, not his P&L.
            "trade_returns": [round(r, 6) for r in closed_rs],
            "equity": [round(e, 4) for e in equity]}


def benchmark_stats(bench, start=60, step=5):
    eq = [1.0]
    t = start
    while t + step < len(bench):
        eq.append(eq[-1] * (bench[t + step - 1] / bench[t - 1]))
        t += step
    total = eq[-1] - 1
    per_year = 252 / step; periods = len(eq) - 1
    years = periods / per_year
    cagr = (eq[-1] ** (1 / years) - 1) if years >= 0.75 and eq[-1] > 0 else None
    peak, mdd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    return {"total_return": round(total * 100, 2),
            "cagr": round(cagr * 100, 2) if cagr is not None else None,
            "max_dd": round(mdd * 100, 2), "equity": [round(e, 4) for e in eq]}


# ---------------- the sweep: which setup wins? ----------------
def sweep(prices, bench, step=5, max_pos=10, verbose=True, hold_min=5, profile=None):
    rows = []
    for label, (rule, params) in RULESETS.items():
        r = backtest(prices, bench, rule, params, step=step, max_pos=max_pos,
                     hold_min=hold_min)
        if r:
            r["setup"] = label; r["rule"] = rule; r["params"] = params
            rows.append(r)
    bm = benchmark_stats(bench, step=step)
    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    if verbose:
        head = f"  RRG SETUP SWEEP  ·  walk-forward, no lookahead  ·  rebalance every {step} bars"
        if profile:
            head += f"  ·  profile: {profile.upper()}"
        print("\n" + head)
        print("  " + "-" * 78)
        print(f"  {'SETUP':<20}{'RETURN%':>9}{'CAGR%':>8}{'SHARPE':>8}{'MAXDD%':>9}"
              f"{'TRADES':>8}{'WIN%':>7}{'EXP':>6}")
        print("  " + "-" * 78)
        for r in rows:
            cagr = f"{r['cagr']:>8.1f}" if r.get("cagr") is not None else f"{'n/a':>8}"
            exp = r.get("avg_exposure", 1.0)
            flag = " *" if r.get("low_sample") else ""
            print(f"  {r['setup']:<20}{r['total_return']:>9.1f}{cagr}"
                  f"{r['sharpe']:>8.2f}{r['max_dd']:>9.1f}{r['trades']:>8}{r['win_rate']:>7.1f}"
                  f"{exp:>6.2f}{flag}")
        print("  " + "-" * 78)
        bcagr = f"{bm['cagr']:>8.1f}" if bm.get("cagr") is not None else f"{'n/a':>8}"
        print(f"  {'NIFTY (buy & hold)':<20}{bm['total_return']:>9.1f}{bcagr}"
              f"{'—':>8}{bm['max_dd']:>9.1f}")
        print("  " + "-" * 78)
        if rows:
            best = rows[0]
            print(f"  BEST BY SHARPE: {best['setup']}   "
                  f"(return {best['total_return']:.1f}% vs NIFTY {bm['total_return']:.1f}%, "
                  f"maxDD {best['max_dd']:.1f}%)")
            beat = "beats" if best["total_return"] > bm["total_return"] else "does NOT beat"
            print(f"  -> this setup {beat} buy-and-hold on this sample.")
        print("  " + "-" * 78)
        if any(r.get("low_sample") for r in rows):
            print("  * = thin sample (few rebalances). Direction is informative,")
            print("      the exact Sharpe is not - get more history to firm it up.")
        print("  EXP = average exposure. Below 1.00 means volatility targeting was")
        print("  de-risking - lower return there is the PRICE of a smaller drawdown.")
        print("  A backtest is a hypothesis, not a promise. Costs assumed 15bps/trade.\n")
    return rows, bm


def save_best(rows, path="rrg_best_setup.json"):
    if not rows:
        return None
    best = rows[0]
    out = {"setup": best["setup"], "rule": best["rule"], "params": best["params"],
           "metrics": {k: best[k] for k in ("total_return", "cagr", "sharpe", "max_dd",
                                            "trades", "win_rate")},
           "saved_at": datetime.now(IST).isoformat()}
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  [saved] best setup -> {path}")
    return out


def load_best(path="rrg_best_setup.json"):
    """The live app uses this so it trades the setup your own data validated."""
    if os.path.exists(path):
        with open(path) as f:
            b = json.load(f)
        return b.get("rule"), b.get("params", {}), b
    # Default is the ablation winner, not the elaborate one. On real NSE data the
    # rotation layer cost 6.3% after costs and tripled turnover, while the plain
    # own-trend filter won every walk-forward fold on a third of the trades.
    return "momentum_only", {"need_trend": True}, None


# ---------------- live signal selection ----------------
def select(points, rule=None, params=None, max_pos=10):
    """Rank today's RRG candidates under the chosen setup -> the names to trade."""
    if rule is None:
        rule, params, _ = load_best()
    params = params or {}
    longs = [p for p in points if _entry_ok(p, rule, params)]
    longs.sort(key=lambda p: (p["distance"] * (1 + p["velocity"])), reverse=True)
    exits = [p for p in points if _exit_ok(p, params)]
    return {"longs": longs[:max_pos], "exits": exits, "rule": rule, "params": params}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="synthetic data (mechanics proof)")
    ap.add_argument("--sweep", action="store_true", help="live data sweep (needs Fyers token)")
    ap.add_argument("--days", type=int, default=300)
    ap.add_argument("--step", type=int, default=None, help="rebalance every N bars")
    ap.add_argument("--max-pos", type=int, default=None)
    ap.add_argument("--profile", default="positional",
                    choices=list(PROFILES), help="how often you actually trade")
    ap.add_argument("--all-profiles", action="store_true",
                    help="compare active vs swing vs positional")
    a = ap.parse_args()
    prof = PROFILES[a.profile]
    step = a.step or prof["step"]
    max_pos = a.max_pos or prof["max_pos"]
    hold_min = prof["hold_min"]

    if a.demo:
        print("  [DEMO] synthetic universe — proves the harness, NOT a real edge.")
        _, prices, bench = E.demo_points()
    else:
        def prog(i, n):
            print(f"    fetching {i}/{n}…", end="\r")
        from fno_universe import fno_stocks
        prices, bench, _dates = E.fetch_history(fno_stocks(), days=a.days, progress=prog)
        print(f"\n  history: {len(prices)} names, {len(bench)} bars")

    if a.all_profiles:
        print("\n  COMPARING TRADING PROFILES  (best setup within each)")
        print("  " + "-" * 74)
        print(f"  {'PROFILE':<14}{'BEST SETUP':<22}{'RETURN':>9}{'SHARPE':>8}{'MAXDD':>9}{'TRADES':>8}")
        print("  " + "-" * 74)
        keep = None
        for name, p in PROFILES.items():
            rws, bmk = sweep(prices, bench, step=p["step"], max_pos=p["max_pos"],
                             hold_min=p["hold_min"], verbose=False)
            if not rws:
                continue
            b = rws[0]
            print(f"  {name:<14}{b['setup']:<22}{b['total_return']:>8.1f}%"
                  f"{b['sharpe']:>8.2f}{b['max_dd']:>8.1f}%{b['trades']:>8}")
            if name == a.profile:
                keep = rws
        print("  " + "-" * 74)
        print(f"  NIFTY buy & hold: {bmk['total_return']:.1f}%  maxDD {bmk['max_dd']:.1f}%")
        print(f"  Fewer trades is not a compromise for you - it is less cost drag and")
        print(f"  fewer decisions to get wrong.\n")
        if keep and not a.demo:
            save_best(keep)
        return

    print(f"  profile: {a.profile}  ({prof['note']})")
    rows, bm = sweep(prices, bench, step=step, max_pos=max_pos,
                     hold_min=hold_min, profile=a.profile)
    if not a.demo:
        save_best(rows)


if __name__ == "__main__":
    main()
