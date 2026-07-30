"""
hypothesis.py  —  which component actually earns its place?

Every test so far bundled several ideas together and asked "does the bundle work". That
question cannot tell you WHICH part works, and it hides the possibility that one plain
component is doing all the work while the elaborate parts add noise.

Across every run, one thing helped consistently: the own-trend filter - the stock must
be rising in absolute terms. Not the quadrants, not the heading, not the tails. So:

    H1  The edge is absolute momentum, and RRG contributes nothing.

This runs an ABLATION - each component alone and in combination - against two baselines
that must be beaten before any of it deserves capital:

    B1  NIFTY buy & hold           doing nothing at all
    B2  classic 12-1 momentum      the most documented equity anomaly there is
                                   (rank by 12-month return skipping the last month)

If the elaborate strategy cannot beat B2, the elaborate strategy is not worth running.
Most systems fail this test, which is exactly why it belongs here.

Everything is judged by multi-fold walk-forward - each fold chooses on its own past and
trades blind - because that is the only measure that has not lied to us yet.

    python hypothesis.py --days 900 --profile swing
    python hypothesis.py --demo

NOT financial advice.
"""
import argparse, statistics, sys
from datetime import datetime, timezone, timedelta

import rrg_engine as E
import rrg_strategy as S

IST = timezone(timedelta(hours=5, minutes=30))
REPORT = "hypothesis_report.txt"


class _Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8"); self.out = sys.stdout

    def write(self, s):
        self.out.write(s); self.f.write(s)

    def flush(self):
        self.out.flush(); self.f.flush()


# ---------------- the plain baseline everything must beat ----------------
def momentum_12_1(prices, bench, start=60, step=10, max_pos=6, cost_bps=15,
                  look=250, skip=21):
    """Classic cross-sectional momentum: rank by return over `look` bars excluding the
    most recent `skip` (the one-month reversal), hold the top N, rebalance every step.

    No RRG, no quadrants, no filters. This is the honest yardstick."""
    by_name = {s.split(":")[-1].replace("-EQ", ""): c for s, c in prices.items()}
    n = len(bench)
    equity, held = [1.0], []
    entries = 0
    t = max(start, look + skip + 1)
    while t + step < n:
        scores = []
        for nm, c in by_name.items():
            if len(c) > t and t - look - skip >= 0:
                a, b = c[t - look - skip], c[t - skip]
                if a > 0:
                    scores.append((b / a - 1, nm))
        scores.sort(reverse=True)
        new = [nm for _, nm in scores[:max_pos]]
        entries += len(set(new) - set(held))
        held = new
        rets = [by_name[nm][t + step - 1] / by_name[nm][t - 1] - 1
                for nm in held if t + step - 1 < len(by_name[nm])]
        gross = sum(rets) / len(rets) if rets else 0.0
        equity.append(equity[-1] * (1 + gross - cost_bps / 10000.0))
        t += step

    periods = len(equity) - 1
    if periods < 12:
        return None
    total = equity[-1] - 1
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    mu = sum(rets) / len(rets)
    sd = (sum((r - mu) ** 2 for r in rets) / len(rets)) ** 0.5 or 1e-9
    peak, mdd = equity[0], 0.0
    for e in equity:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    return {"total_return": round(total * 100, 2),
            "sharpe": round(mu / sd * (252 / step) ** 0.5, 2),
            "max_dd": round(mdd * 100, 2), "trades": entries,
            "setup": "B2 momentum 12-1"}


# ---------------- the ablation ----------------
# Each entry isolates one claim. "rrg_off" means quadrant logic is bypassed entirely:
# candidates are ranked purely on their own trend, so if that scores as well as the full
# machine, the machine is decoration.
ABLATIONS = {
    "RRG only (no own-trend)":    ("improving_or_leading", {"min_distance": 1.0}),
    "own-trend only (no RRG)":    ("momentum_only",        {"need_trend": True}),
    "RRG + own-trend":            ("improving_or_leading", {"min_distance": 1.0,
                                                            "need_trend": True}),
    "RRG + own-trend + vol/band": ("improving_or_leading", {"min_distance": 1.0,
                                                            "need_trend": True,
                                                            "target_vol": 0.15,
                                                            "exit_band": 0.5}),
    "own-trend + vol/band":       ("momentum_only",        {"need_trend": True,
                                                            "target_vol": 0.15,
                                                            "exit_band": 0.5}),
}


def walk_folds(prices, bench, rule, params, step, max_pos, folds=3, side="long",
               cost_bps=15):
    """Walk-forward for a FIXED rule - no per-fold selection, because the point here is
    to measure one component, not to pick a winner."""
    n = len(bench)
    need = 60 + 12 * step
    max_folds = n // need - 1
    if max_folds < 2:
        return None
    folds = min(folds, max_folds)
    seg = n // (folds + 1)
    outs = []
    for k in range(1, folds + 1):
        a, b = seg * k - 60, min(seg * (k + 1), n)
        p_te = {s: c[a:b] for s, c in prices.items() if len(c) >= b}
        r = S.backtest(p_te, bench[a:b], rule, params, step=step, max_pos=max_pos,
                       side=side, cost_bps=cost_bps)
        if r:
            outs.append(r)
    if not outs:
        return None
    rets = [r["total_return"] for r in outs]
    return {"folds": len(outs), "wins": sum(1 for x in rets if x > 0),
            "avg": round(sum(rets) / len(rets), 2),
            "median": round(statistics.median(rets), 2),
            "sharpe": round(sum(r["sharpe"] for r in outs) / len(outs), 2),
            "max_dd": round(min(r["max_dd"] for r in outs), 2),
            "trades": sum(r["trades"] for r in outs)}


def baselines_per_fold(prices, bench, step, max_pos, folds=3):
    """B1 and B2 measured inside the same fold windows the ablation uses.

    Comparing a whole-period total against a per-fold average is meaningless - the
    period is roughly four times longer. Everything must be measured on the same
    windows or the verdict is an artefact of arithmetic."""
    n = len(bench)
    need = 60 + 12 * step
    max_folds = n // need - 1
    if max_folds < 2:
        return None, None
    folds = min(folds, max_folds)
    seg = n // (folds + 1)
    b1s, b2s = [], []
    for k in range(1, folds + 1):
        a, b = seg * k - 60, min(seg * (k + 1), n)
        p_te = {s2: c[a:b] for s2, c in prices.items() if len(c) >= b}
        bm = S.benchmark_stats(bench[a:b], step=step)
        if bm:
            b1s.append(bm["total_return"])
        m = momentum_12_1(p_te, bench[a:b], step=step, max_pos=max_pos)
        if m:
            b2s.append(m["total_return"])
    return (round(sum(b1s) / len(b1s), 2) if b1s else None,
            round(sum(b2s) / len(b2s), 2) if b2s else None)


def main():
    sys.stdout = _Tee(REPORT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--days", type=int, default=900)
    ap.add_argument("--profile", default="swing", choices=list(S.PROFILES))
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--save", action="store_true",
                    help="make the winning component set the live setup")
    a = ap.parse_args()
    prof = S.PROFILES[a.profile]
    step, max_pos = prof["step"], prof["max_pos"]

    print("=" * 78)
    print("  HYPOTHESIS TEST  —  which part actually earns its place?")
    print(f"  profile: {a.profile.upper()}  ({prof['note']})")
    print("=" * 78)

    if a.demo:
        print("  [DEMO] synthetic data — mechanics only, not a real edge.")
        _, prices, bench = E.demo_points(n_bars=max(400, int(a.days * 0.69)))
    else:
        def prog(i, n):
            print(f"    fetching {i}/{n}...", end="\r")
        from fno_universe import fno_stocks
        prices, bench, _d = E.fetch_history(fno_stocks(), days=a.days, progress=prog)
        print(f"\n  history: {len(prices)} names, {len(bench)} bars")

    # ---- baselines ----
    print("\n  BASELINES — beat these or the machinery is pointless")
    print("  " + "-" * 74)
    bm = S.benchmark_stats(bench, step=step)
    print(f"  {'B1 NIFTY buy & hold':<32}{bm['total_return']:>9.1f}%"
          f"{'—':>9}{bm['max_dd']:>9.1f}%")
    b2 = momentum_12_1(prices, bench, step=step, max_pos=max_pos)
    if b2:
        print(f"  {'B2 classic 12-1 momentum':<32}{b2['total_return']:>9.1f}%"
              f"{b2['sharpe']:>9.2f}{b2['max_dd']:>9.1f}%{b2['trades']:>8}")
    else:
        print("  B2 needs more history to compute.")
    print("  " + "-" * 74)

    # ---- ablation, walk-forward ----
    print(f"\n  ABLATION — walk-forward, each fold traded blind ({a.folds} folds)")
    print("  " + "-" * 74)
    print(f"  {'COMPONENT':<30}{'@15bps':>9}{'@35bps':>9}{'WINS':>7}"
          f"{'SHARPE':>8}{'MAXDD':>9}{'TRADES':>8}")
    print("  " + "-" * 74)
    scored = []
    for label, (rule, params) in ABLATIONS.items():
        w = walk_folds(prices, bench, rule, params, step, max_pos, a.folds, cost_bps=15)
        w35 = walk_folds(prices, bench, rule, params, step, max_pos, a.folds, cost_bps=35)
        if not w:
            print(f"  {label:<30}{'(not enough history)':>34}")
            continue
        w["avg35"] = w35["avg"] if w35 else w["avg"]
        scored.append((label, w))
        print(f"  {label:<30}{w['avg']:>8.1f}%{w['avg35']:>8.1f}%{w['wins']:>4}/{w['folds']:<2}"
              f"{w['sharpe']:>8.2f}{w['max_dd']:>9.1f}%{w['trades']:>8}")
    b1_f, b2_f = baselines_per_fold(prices, bench, step, max_pos, a.folds)
    if b1_f is not None:
        print(f"  {'B1 NIFTY (same folds)':<30}{b1_f:>8.1f}%{b1_f:>8.1f}%{'—':>7}")
    if b2_f is not None:
        print(f"  {'B2 12-1 momentum (same folds)':<30}{b2_f:>8.1f}%{'':>8}{'—':>7}")
    print("  " + "-" * 74)
    print("  @35bps is the realistic column. Compare components THERE - a variant with")
    print("  three times the turnover has to earn that cost back before it counts.")
    print("  Baselines are measured on the SAME fold windows, so every number here is")
    print("  a per-fold average and directly comparable.")

    # ---- the verdict ----
    print("\n" + "=" * 78)
    print("  WHAT THIS SETTLES")
    print("=" * 78)
    if not scored:
        print("  Not enough history to separate the components. Fetch more --days.")
        print("=" * 78 + "\n"); return

    scored.sort(key=lambda x: x[1].get("avg35", x[1]["avg"]), reverse=True)
    best_label, best = scored[0]
    rrg_only = dict(scored).get("RRG only (no own-trend)")
    mom_only = dict(scored).get("own-trend only (no RRG)")
    full = dict(scored).get("RRG + own-trend")

    print(f"  Best component set : {best_label}   avg OOS {best['avg']:+.1f}%")
    best35 = best.get("avg35", best["avg"])
    if b2_f is not None:
        print(f"  vs 12-1 momentum (same folds, {b2_f:+.1f}%): "
              f"{'BEATS it' if best35 > b2_f else 'does NOT beat it'}")
    if b1_f is not None:
        verdict = "BEATS it" if best35 > b1_f else "does NOT beat it"
        print(f"  vs NIFTY buy & hold (same folds, {b1_f:+.1f}%): {verdict}")
        if best35 <= b1_f:
            print("     >> Doing nothing would have paid more. That is the real benchmark,")
            print("        and this system does not clear it on this data.")
    if mom_only and full:
        gain = full.get("avg35", full["avg"]) - mom_only.get("avg35", mom_only["avg"])
        raw_gain = full["avg"] - mom_only["avg"]
        print(f"\n  H1 - does RRG add anything on top of plain momentum?")
        print(f"     own-trend only : {mom_only.get('avg35'):+.1f}% at 35bps "
              f"({mom_only['trades']} trades)")
        print(f"     RRG + own-trend: {full.get('avg35'):+.1f}% at 35bps "
              f"({full['trades']} trades)")
        print(f"     RRG contributes {gain:+.1f}% after costs "
              f"(+{raw_gain:.1f}% before) for {full['trades'] - mom_only['trades']} extra trades")
        if gain <= 0:
            print("     >> H1 CONFIRMED. RRG adds nothing - it is decoration. Drop it,")
            print("        keep the momentum filter, and the system gets simpler AND better.")
        elif gain < 2:
            print("     >> RRG adds almost nothing. Not worth the complexity it costs.")
        else:
            print("     >> RRG does add something. Keep it, but it is the smaller half.")
    if rrg_only:
        print(f"\n  RRG alone (no momentum filter): {rrg_only['avg']:+.1f}% "
              f"- {'loses money' if rrg_only['avg'] < 0 else 'weak'}")
    if all(w["avg"] <= 0 for _, w in scored):
        print("\n  >> NOTHING here has a positive out-of-sample edge. Do not trade any of it.")
        print("     The infrastructure stays useful; this particular signal family does not.")
    if a.save and not a.demo:
        import json
        rule, params = dict(ABLATIONS)[best_label]
        with open("rrg_best_setup.json", "w") as f:
            json.dump({"setup": best_label, "rule": rule, "params": params,
                       "metrics": {"total_return": best.get("avg35", best["avg"]),
                                   "sharpe": best["sharpe"], "max_dd": best["max_dd"],
                                   "trades": best["trades"],
                                   "win_rate": round(best["wins"] / best["folds"] * 100, 1)},
                       "chosen_by": "walk-forward ablation at 35bps",
                       "saved_at": datetime.now(IST).isoformat()}, f, indent=2)
        print(f"\n  [saved] '{best_label}' is now the live setup (rrg_best_setup.json).")
        print("          checkin.py and the app will trade THIS from now on.")
    print(f"\n  Saved to: {REPORT}")
    print("  A backtest is a hypothesis, not a promise.")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
