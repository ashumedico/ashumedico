"""
robustness.py  —  is the edge real, or did one lucky stretch flatter it?

A single backtest number is the easiest way to fool yourself. The sweep said
"E +own-trend, +22.3% vs NIFTY 5.4%". Before trusting that with money, four questions
have to be answered, and each one can kill the idea:

  1. OUT-OF-SAMPLE   Pick the setup on the first half. Does it still work on the
                     second half, which it never saw? This is the real test.
  2. COST SENSITIVITY At what brokerage+slippage does the edge die? 300 trades makes
                     this the single biggest fragility - F&O costs are not 15bps.
  3. REGIME GATE      RRG is relative. Does blocking entries while the index itself is
                     unhealthy improve the drawdown?
  4. PARAMETER        Does it only work at one magic setting (overfit), or across a
     STABILITY        range? A real edge is a plateau, not a spike.

    python robustness.py                 # full suite on live data
    python robustness.py --demo          # synthetic (mechanics only)
    python robustness.py --days 500

NOT financial advice. This is the test that tries to DISPROVE the edge.
"""
import argparse, statistics, sys
from datetime import datetime, timezone, timedelta

import rrg_engine as E
import rrg_strategy as S

IST = timezone(timedelta(hours=5, minutes=30))
REPORT = "robustness_report.txt"


class _Tee:
    """Mirror everything to a file. The most important verdict was scrolling off the
    top of the console, which is a bad place to keep a conclusion."""
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush(); self.f.flush()


def _slice(prices, bench, a, b):
    return {s: c[a:b] for s, c in prices.items() if len(c) >= b}, bench[a:b]


def _fmt(r):
    if not r:
        return "  (sample too small)"
    cagr = f"{r['cagr']:>7.1f}" if r.get("cagr") is not None else f"{'n/a':>7}"
    return (f"{r['total_return']:>8.1f}%{cagr}%{r['sharpe']:>8.2f}"
            f"{r['max_dd']:>9.1f}%{r['trades']:>8}{r['win_rate']:>7.1f}%")


# ---------------- 1. out-of-sample ----------------
def out_of_sample(prices, bench, step=5, max_pos=10):
    n = len(bench)
    mid = n // 2
    print("\n  1) OUT-OF-SAMPLE  — choose on the first half, verify on the unseen second half")
    print("  " + "-" * 74)
    print(f"  {'SETUP':<20}{'RETURN':>9}{'CAGR':>8}{'SHARPE':>8}{'MAXDD':>10}{'TRADES':>8}{'WIN':>8}")
    print("  " + "-" * 74)

    p1, b1 = _slice(prices, bench, 0, mid)
    p2, b2 = _slice(prices, bench, mid - 60, n)      # carry 60 bars so indicators are warm

    in_rows = []
    for label, (rule, params) in S.RULESETS.items():
        r = S.backtest(p1, b1, rule, params, step=step, max_pos=max_pos)
        if r:
            in_rows.append((label, rule, params, r))
    if not in_rows:
        # Each HALF must survive the warmup and still hold a meaningful span, so the
        # requirement is (warmup + span) per half - not a bar count for the whole run.
        # The earlier formula under-stated it and produced "you have 400, need 240"
        # immediately followed by a failure.
        need_bars = (60 + max(180, 12 * step)) * 2
        print(f"  NOT ENOUGH HISTORY to split at this cadence.")
        print(f"  A {step}-bar rebalance needs ~{need_bars} bars to test out-of-sample;")
        print(f"  you have {n}. Re-run with:  --days {int(need_bars * 1.5)}")
        print("  Until then the headline number is UNVALIDATED - do not size it up.")
        return None
    in_rows.sort(key=lambda x: x[3]["sharpe"], reverse=True)
    best_label, rule, params, in_r = in_rows[0]

    print(f"  IN-SAMPLE  (1st half)")
    print(f"  {best_label:<20}{_fmt(in_r)}")
    out_r = S.backtest(p2, b2, rule, params, step=step, max_pos=max_pos)
    print(f"  OUT-OF-SAMPLE  (2nd half, never seen)")
    print(f"  {best_label:<20}{_fmt(out_r)}")

    bm2 = S.benchmark_stats(b2, step=step)
    bm_cagr = f"{bm2['cagr']:>7.1f}%" if bm2.get("cagr") is not None else f"{'n/a':>8}"
    print(f"  {'NIFTY (2nd half)':<20}{bm2['total_return']:>8.1f}%{bm_cagr}"
          f"{'—':>8}{bm2['max_dd']:>9.1f}%")
    print("  " + "-" * 74)
    if in_r and in_r.get("trades", 0) < 40:
        print(f"  NOTE: only {in_r['trades']} trades in-sample - a high Sharpe on this few")
        print("        trades is fragile. Treat the out-of-sample line as the real answer.")
    if not out_r:
        print("  VERDICT: second half too short to judge. Get more history.")
    elif out_r["sharpe"] > 0.3 and out_r["total_return"] > bm2["total_return"]:
        print(f"  VERDICT: HOLDS UP. '{best_label}' survived unseen data and still beat NIFTY.")
    elif out_r["total_return"] > 0:
        print(f"  VERDICT: WEAKER out-of-sample — positive but no longer clearly beating NIFTY.")
        print("           Treat the headline number as optimistic.")
    else:
        print(f"  VERDICT: FAILS out-of-sample. The first-half result was likely luck.")
        print("           Do NOT size this up.")
    return {"setup": best_label, "rule": rule, "params": params,
            "in_sample": in_r, "out_sample": out_r, "bench_out": bm2}


# ---------------- 1b. multi-fold walk-forward ----------------
def walkforward(prices, bench, step=5, max_pos=10, folds=4, side="long"):
    """The honest test. A single 50/50 split can itself be luck, so this repeats it.

    For each fold: pick the best setup on everything BEFORE the fold, then trade the
    fold blind. Nothing is ever chosen using the data it is judged on. The question is
    not "did it win once" but "how often does it win on data it has never seen".
    """
    n = len(bench)
    warm = 60
    need_per_seg = warm + 12 * step
    # Use as many folds as the history actually supports rather than failing outright:
    # a longer rebalance eats history fast, so a fixed fold count silently rules out
    # exactly the cadence being tested.
    max_folds = n // need_per_seg - 1
    if max_folds < 2:
        print(f"\n  1b) WALK-FORWARD - need ~{need_per_seg * 3} bars for even 2 folds "
              f"at a {step}-bar rebalance; have {n}.")
        print("      Test at a faster cadence (--profile swing) or fetch more history.")
        return None
    if max_folds < folds:
        print(f"\n  [history allows {max_folds} folds, not {folds} - using {max_folds}]")
        folds = max_folds
    seg = n // (folds + 1)

    print(f"\n  1b) WALK-FORWARD  — {folds} folds, each traded blind ({side} book)")
    print("  " + "-" * 74)
    print(f"  {'FOLD':<6}{'CHOSEN ON TRAIN':<22}{'OOS RET':>9}{'SHARPE':>8}"
          f"{'MAXDD':>9}{'NIFTY':>8}{'TRADES':>8}")
    print("  " + "-" * 74)

    results = []
    skipped_folds = []
    for k in range(1, folds + 1):
        tr_end = seg * k
        if tr_end < need_per_seg * 2:
            # training window too short to choose a setup from - say so, do not drop it
            skipped_folds.append(k)
            continue
        te_a, te_b = tr_end - warm, min(seg * (k + 1), n)
        p_tr, b_tr = _slice(prices, bench, 0, tr_end)
        p_te, b_te = _slice(prices, bench, te_a, te_b)

        best = None
        for label, (rule, params) in S.RULESETS.items():
            r = S.backtest(p_tr, b_tr, rule, params, step=step, max_pos=max_pos, side=side)
            if r and (best is None or r["sharpe"] > best[3]["sharpe"]):
                best = (label, rule, params, r)
        if not best:
            skipped_folds.append(k)
            continue
        label, rule, params, _ = best
        oos = S.backtest(p_te, b_te, rule, params, step=step, max_pos=max_pos, side=side)
        bm = S.benchmark_stats(b_te, step=step)
        if not oos:
            print(f"  {k:<6}{label:<22}{'(fold too short)':>34}")
            continue
        results.append({"fold": k, "setup": label, "oos": oos, "bench": bm})
        print(f"  {k:<6}{label:<22}{oos['total_return']:>8.1f}%{oos['sharpe']:>8.2f}"
              f"{oos['max_dd']:>8.1f}%{bm['total_return']:>7.1f}%{oos['trades']:>8}")

    print("  " + "-" * 74)
    if skipped_folds:
        print(f"  (folds {skipped_folds} skipped - training window too short to choose from)")
    if not results:
        return None
    rets = [r["oos"]["total_return"] for r in results]
    beats = sum(1 for r in results if r["oos"]["total_return"] > r["bench"]["total_return"])
    wins = sum(1 for x in rets if x > 0)
    avg = sum(rets) / len(rets)
    print(f"  {wins}/{len(results)} folds positive · {beats}/{len(results)} beat NIFTY · "
          f"average OOS {avg:+.1f}% · median {statistics.median(rets):+.1f}%")
    if len(results) < 2:
        print("  >> INCONCLUSIVE. Only one fold completed - that is a single coin flip,")
        print("     not evidence. Fetch more history or test a faster cadence.")
    elif wins == len(results) and beats >= len(results) - 1:
        print("  >> CONSISTENT. Wins on data it never saw, fold after fold.")
    elif wins >= len(results) * 0.6 and avg > 0:
        print("  >> MIXED but positive. A real but unreliable edge - keep size small.")
    else:
        print("  >> NOT AN EDGE. It does not survive unseen data repeatedly.")
    return {"results": results, "wins": wins, "beats": beats, "avg": avg,
            "folds": len(results)}


# ---------------- 2. cost sensitivity ----------------
def cost_sensitivity(prices, bench, rule, params, step=5, max_pos=10):
    print("\n  2) COST SENSITIVITY  — where does the edge die?")
    print("  " + "-" * 62)
    print(f"  {'COST (bps/trade)':<20}{'RETURN':>10}{'SHARPE':>9}{'MAXDD':>10}")
    print("  " + "-" * 62)
    rows = []
    for bps in (5, 15, 25, 35, 50, 75):
        r = S.backtest(prices, bench, rule, params, step=step, max_pos=max_pos, cost_bps=bps)
        if r:
            rows.append((bps, r))
            tag = "   <- realistic F&O" if bps in (25, 35) else ""
            print(f"  {bps:<20}{r['total_return']:>9.1f}%{r['sharpe']:>9.2f}"
                  f"{r['max_dd']:>9.1f}%{tag}")
    print("  " + "-" * 62)
    dead = next((bps for bps, r in rows if r["total_return"] <= 0), None)
    if dead:
        print(f"  Edge turns NEGATIVE at ~{dead}bps per trade.")
    else:
        print("  Edge survives every cost level tested.")
    real = next((r for bps, r in rows if bps == 35), None)
    if real:
        print(f"  At a realistic 35bps: {real['total_return']:.1f}% "
              f"(Sharpe {real['sharpe']:.2f}) — plan on this, not the headline.")
    return rows


# ---------------- 3. regime gate ----------------
def regime_test(prices, bench, rule, params, step=5, max_pos=10):
    print("\n  3) MARKET REGIME GATE  — block longs when the index itself is weak?")
    print("  " + "-" * 68)
    print(f"  {'VARIANT':<24}{'RETURN':>9}{'SHARPE':>9}{'MAXDD':>10}{'TRADES':>9}")
    print("  " + "-" * 68)
    off = S.backtest(prices, bench, rule, params, step=step, max_pos=max_pos)
    on_params = dict(params); on_params["need_regime"] = True
    on = S.backtest(prices, bench, rule, on_params, step=step, max_pos=max_pos)
    for label, r in (("regime gate OFF", off), ("regime gate ON", on)):
        if r:
            print(f"  {label:<24}{r['total_return']:>8.1f}%{r['sharpe']:>9.2f}"
                  f"{r['max_dd']:>9.1f}%{r['trades']:>9}")
    print("  " + "-" * 68)
    if off and on:
        if on["sharpe"] > off["sharpe"] and on["max_dd"] > off["max_dd"]:
            print("  Gate HELPS on both risk and return — turn it on (need_regime: true).")
        elif on["max_dd"] > off["max_dd"]:
            print("  Gate cuts the drawdown but costs return — worth it if you hate pain.")
        else:
            print("  Gate does not help on this sample — leave it off, revisit in a bear phase.")
    return {"off": off, "on": on}


# ---------------- 4. parameter stability ----------------
def param_stability(prices, bench, rule, params, step=5, max_pos=10):
    print("\n  4) PARAMETER STABILITY  — a real edge is a plateau, not a spike")
    print("  " + "-" * 68)
    results = []
    print(f"  {'VARIATION':<28}{'RETURN':>10}{'SHARPE':>9}")
    print("  " + "-" * 68)
    grid = [("rebalance 3 bars", {"step": 3}), ("rebalance 5 bars", {"step": 5}),
            ("rebalance 10 bars", {"step": 10}),
            ("max 5 positions", {"max_pos": 5}), ("max 10 positions", {"max_pos": 10}),
            ("max 15 positions", {"max_pos": 15}),
            ("RS window 8", {"win": 8}), ("RS window 10", {"win": 10}),
            ("RS window 14", {"win": 14})]
    for label, over in grid:
        kw = {"step": step, "max_pos": max_pos}
        kw.update(over)
        r = S.backtest(prices, bench, rule, params, **kw)
        if r:
            results.append(r["sharpe"])
            print(f"  {label:<28}{r['total_return']:>9.1f}%{r['sharpe']:>9.2f}")
    print("  " + "-" * 68)
    if len(results) >= 4:
        pos = sum(1 for x in results if x > 0)
        print(f"  Sharpe across {len(results)} variations: "
              f"median {statistics.median(results):.2f}, "
              f"range {min(results):.2f} to {max(results):.2f}, "
              f"{pos}/{len(results)} positive.")
        if pos == len(results) and min(results) > 0.2:
            print("  STABLE — works across every setting tried, not just one. Good sign.")
        elif pos >= len(results) * 0.7:
            print("  MOSTLY STABLE — a few settings fail; avoid the extremes.")
        else:
            print("  FRAGILE — only some settings work. Likely overfit; do not trust the best one.")
    return results


def main():
    sys.stdout = _Tee(REPORT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--step", type=int, default=None)
    ap.add_argument("--max-pos", type=int, default=None)
    ap.add_argument("--profile", default="positional", choices=list(S.PROFILES),
                    help="test at the cadence you actually trade")
    ap.add_argument("--folds", type=int, default=4,
                    help="walk-forward folds - more folds, harder to fool")
    a = ap.parse_args()
    prof = S.PROFILES[a.profile]
    a.step = a.step or prof["step"]
    a.max_pos = a.max_pos or prof["max_pos"]

    print("=" * 76)
    print("  ROBUSTNESS SUITE  —  trying to DISPROVE the edge")
    print(f"  profile: {a.profile.upper()}  ({prof['note']})")
    print("=" * 76)

    if a.demo:
        print("  [DEMO] synthetic data — mechanics only, not a real edge.")
        _, prices, bench = E.demo_points(n_bars=max(400, int(a.days * 0.69)))
    else:
        def prog(i, n):
            print(f"    fetching {i}/{n}…", end="\r")
        from fno_universe import fno_stocks
        prices, bench, _d = E.fetch_history(fno_stocks(), days=a.days, progress=prog)
        print(f"\n  history: {len(prices)} names, {len(bench)} bars")

    oos = out_of_sample(prices, bench, a.step, a.max_pos)
    if oos:
        rule, params = oos["rule"], oos["params"]
    else:
        # The single split could not run, but the remaining tests still inform. Pick the
        # best full-sample setup for them and label it honestly as in-sample.
        rows, _bm = S.sweep(prices, bench, step=a.step, max_pos=a.max_pos, verbose=False)
        if not rows:
            print("  Not enough history for any test. Re-run with more --days.")
            return
        rule, params = rows[0]["rule"], rows[0]["params"]
        oos = {"setup": rows[0]["setup"] + " (in-sample only)", "rule": rule,
               "params": params, "in_sample": rows[0], "out_sample": None, "bench_out": {}}
        print(f"\n  Continuing with '{rows[0]['setup']}' chosen IN-SAMPLE - the tests below")
        print("  are informative but not independent validation.")
    wf_long = walkforward(prices, bench, a.step, a.max_pos, folds=a.folds, side="long")
    wf_both = walkforward(prices, bench, a.step, a.max_pos, folds=a.folds, side="both")

    cost_rows = cost_sensitivity(prices, bench, rule, params, a.step, a.max_pos)
    real35 = next((r for bps, r in cost_rows if bps == 35), None)
    regime_test(prices, bench, rule, params, a.step, a.max_pos)
    stab = param_stability(prices, bench, rule, params, a.step, a.max_pos)

    # ---- the bottom line, repeated LAST so it cannot scroll away ----
    print("\n" + "=" * 76)
    print("  BOTTOM LINE")
    print("=" * 76)
    o = oos.get("out_sample"); i = oos.get("in_sample"); bmk = oos.get("bench_out", {})
    print(f"  Setup tested      : {oos['setup']}   (profile {a.profile})")
    if i:
        print(f"  In-sample         : {i['total_return']:+.1f}%  Sharpe {i['sharpe']:.2f}  "
              f"maxDD {i['max_dd']:.1f}%  ({i['trades']} trades)")
    if o:
        print(f"  OUT-OF-SAMPLE     : {o['total_return']:+.1f}%  Sharpe {o['sharpe']:.2f}  "
              f"maxDD {o['max_dd']:.1f}%  ({o['trades']} trades)")
        print(f"  NIFTY same period : {bmk.get('total_return', 0):+.1f}%  "
              f"maxDD {bmk.get('max_dd', 0):.1f}%")
        if o["sharpe"] > 0.3 and o["total_return"] > bmk.get("total_return", 0):
            print("\n  >> HOLDS UP. Survived data it never saw, and still beat the index.")
            print("     Next: paper-trade it for a few weeks before sizing up.")
        elif o["total_return"] > 0:
            print("\n  >> WEAKER out-of-sample. Positive, but no longer clearly beating NIFTY.")
            print("     Treat the headline as optimistic; keep size small.")
        else:
            print("\n  >> FAILS out-of-sample. The headline was likely luck.")
            print("     Do NOT put money behind this setup.")
    for tag, wf in (("long only", wf_long), ("long+short", wf_both)):
        if wf:
            print(f"\n  WALK-FORWARD ({tag}): {wf['wins']}/{wf['folds']} folds positive, "
                  f"{wf['beats']}/{wf['folds']} beat NIFTY, avg {wf['avg']:+.1f}%")
    if wf_long or wf_both:
        best_wf = max([w for w in (wf_long, wf_both) if w], key=lambda w: w["avg"])
        print("  ^ this is the number that matters. One split can be luck; several cannot.")
    if real35:
        print(f"\n  At realistic 35bps costs: {real35['total_return']:+.1f}%  "
              f"(Sharpe {real35['sharpe']:.2f})  <- plan on this, not the headline")
    if stab:
        pos = sum(1 for x in stab if x > 0)
        print(f"  Parameter stability     : {pos}/{len(stab)} variations positive, "
              f"median Sharpe {statistics.median(stab):.2f}")
    print(f"\n  Full run saved to: {REPORT}")
    print("  A backtest is a hypothesis, not a promise.")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
