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


def _exit_ok(p, params):
    """Exit when the rotation turns against us (or own trend breaks)."""
    if p["quadrant"] in ("WEAKENING", "LAGGING") and params.get("exit_on_weaken", True):
        return True
    if params.get("need_trend", False) and p["abs_trend"] < 0:
        return True
    return False


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
}


# ---------------- walk-forward backtest ----------------
def backtest(prices, bench, rule, params, start=60, step=5, max_pos=10,
             hold_min=5, cost_bps=15, tail=3, win=10, mom_win=5):
    """Equal-weight long-only rotation. Rebalance every `step` bars.
    cost_bps = round-trip slippage+brokerage per trade in basis points."""
    n = len(bench)
    if n <= start + step * 3:
        return None
    equity = [1.0]
    held = {}                       # name -> {entry_px, bars}
    by_name = {s.split(":")[-1].replace("-EQ", ""): c for s, c in prices.items()}
    entries, closed_rs = 0, []      # count entries; record every realised trade return

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
            if held[name]["bars"] >= hold_min and _exit_ok(p, params):
                px = by_name[name][t - 1]
                closed_rs.append(px / held[name]["entry_px"] - 1)
                del held[name]

        # --- entries ---
        if len(held) < max_pos:
            cands = [p for p in pts if _entry_ok(p, rule, params) and p["name"] not in held
                     and p["name"] in by_name and len(by_name[p["name"]]) > t]
            cands.sort(key=lambda p: (p["distance"] * (1 + p["velocity"])), reverse=True)
            for p in cands[:max_pos - len(held)]:
                held[p["name"]] = {"entry_px": by_name[p["name"]][t - 1], "bars": 0}
                entries += 1

        # --- mark to market over the next `step` bars ---
        if held:
            rets = []
            for name, h in held.items():
                c = by_name[name]
                if t + step - 1 < len(c):
                    rets.append(c[t + step - 1] / c[t - 1] - 1)
            gross = sum(rets) / len(rets) if rets else 0.0
        else:
            gross = 0.0
        turnover_cost = (cost_bps / 10000.0) * (len(held) / max(max_pos, 1))
        equity.append(equity[-1] * (1 + gross - turnover_cost))
        t += step

    # --- close anything still open, at the last bar, so accounting is complete ---
    for name, h in held.items():
        c = by_name.get(name)
        if c:
            closed_rs.append(c[min(t, len(c)) - 1] / h["entry_px"] - 1)

    # --- metrics (honest: no annualising a sample too small to support it) ---
    MIN_PERIODS = 20
    periods = len(equity) - 1
    if periods < MIN_PERIODS:
        return None
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
            "win_rate": round(wins / len(closed_rs) * 100, 1) if closed_rs else 0,
            "years": round(years, 2), "equity": [round(e, 4) for e in equity]}


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
def sweep(prices, bench, step=5, max_pos=10, verbose=True):
    rows = []
    for label, (rule, params) in RULESETS.items():
        r = backtest(prices, bench, rule, params, step=step, max_pos=max_pos)
        if r:
            r["setup"] = label; r["rule"] = rule; r["params"] = params
            rows.append(r)
    bm = benchmark_stats(bench, step=step)
    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    if verbose:
        print(f"\n  RRG SETUP SWEEP  ·  walk-forward, no lookahead  ·  rebalance every {step} bars")
        print("  " + "-" * 78)
        print(f"  {'SETUP':<20}{'RETURN%':>9}{'CAGR%':>8}{'SHARPE':>8}{'MAXDD%':>9}{'TRADES':>8}{'WIN%':>7}")
        print("  " + "-" * 78)
        for r in rows:
            cagr = f"{r['cagr']:>8.1f}" if r.get("cagr") is not None else f"{'n/a':>8}"
            print(f"  {r['setup']:<20}{r['total_return']:>9.1f}{cagr}"
                  f"{r['sharpe']:>8.2f}{r['max_dd']:>9.1f}{r['trades']:>8}{r['win_rate']:>7.1f}")
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
    # sensible default until a sweep has been run: the evidence-based combined filter
    return "improving_or_leading", {"min_distance": 1.0, "need_trend": True}, None


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
    ap.add_argument("--step", type=int, default=5, help="rebalance every N bars")
    ap.add_argument("--max-pos", type=int, default=10)
    a = ap.parse_args()

    if a.demo:
        print("  [DEMO] synthetic universe — proves the harness, NOT a real edge.")
        _, prices, bench = E.demo_points()
    else:
        def prog(i, n):
            print(f"    fetching {i}/{n}…", end="\r")
        from fno_universe import fno_stocks
        prices, bench, _dates = E.fetch_history(fno_stocks(), days=a.days, progress=prog)
        print(f"\n  history: {len(prices)} names, {len(bench)} bars")

    rows, bm = sweep(prices, bench, step=a.step, max_pos=a.max_pos)
    if not a.demo:
        save_best(rows)


if __name__ == "__main__":
    main()
