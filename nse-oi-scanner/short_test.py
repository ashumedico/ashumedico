"""
short_test.py  —  does the short book earn its place, or is it decoration?

Aashish asked for long AND short signals. The rule in this system is that nothing gets a
card until it has a number, so this measures the short book the same way the RRG was
measured - the ablation that got the RRG demoted at -6.3%.

Four arms, same data, same costs:

    LONG ONLY     what ships today
    SHORT ONLY    the short book alone
    BOTH          slots split between the two
    BOTH (broken) shorts ranked the way they used to be, as the control

The last arm is there on purpose. The short book was ranked descending by a bullishness
score, which put the STRONGEST name at the top of the short list. Every earlier read of
"shorts don't work here" was made through that, so it was a statement about a broken short
book rather than about shorting. Keeping the broken arm in the table is what makes the fix
measurable instead of asserted.

    python short_test.py --demo          # synthetic - mechanics only, NOT an edge
    python short_test.py --days 900      # live data (needs a Fyers token)

NOT financial advice.
"""
import argparse
import sys

import rrg_engine as E
import rrg_strategy as S

G, R, Y, D, X = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"


def _broken_rank_backtest(prices, bench, rule, params, **kw):
    """Run with the old descending short sort, by monkeypatching the sort back."""
    import builtins
    real = builtins.sorted
    state = {"n": 0}

    def patched(it, **k):
        # the short sort is the only ascending one in the entry block after the fix
        if k.get("key") is not None and "reverse" not in k:
            state["n"] += 1
            return real(it, key=k["key"], reverse=True)
        return real(it, **k)

    builtins.sorted = patched
    try:
        return S.backtest(prices, bench, rule, params, **kw)
    finally:
        builtins.sorted = real


def row(label, res, colour=""):
    if not res:
        print(f"  {label:<22}{Y}chala hi nahi (data kam){X}")
        return
    ret = res.get("total_return", res.get("return"))
    tr = res.get("trades", res.get("n_trades", 0))
    wr = res.get("win_rate")
    sh = res.get("sharpe")
    print(f"  {label:<22}{colour}{ret:+7.1f}%{X}   {tr:>4} trades"
          + (f"   {wr:.0f}% jeete" if wr is not None else "")
          + (f"   Sharpe {sh:.2f}" if sh is not None else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--cost-bps", type=int, default=35)
    ap.add_argument("--max-pos", type=int, default=8)
    a = ap.parse_args()

    if a.demo:
        print(f"\n  {Y}[DEMO] synthetic universe - mechanics only, NOT an edge.{X}")
        pts, prices, bench = E.demo_points()
        dates = getattr(E, "LAST_DATES", None)
    else:
        try:
            pts, prices, bench = E.live_points(tail=3)
            dates = getattr(E, "LAST_DATES", None)
        except Exception as e:      # noqa
            print(f"\n  {R}Live data nahi aaya: {e}{X}")
            print(f"  {D}Token ke bina yeh test nahi ho sakta. '1 - START DAY' chala.{X}\n")
            return 2

    rule, params, _ = S.load_best()
    kw = dict(start=60, step=5, max_pos=a.max_pos, hold_min=5,
              cost_bps=a.cost_bps, tail=3, win=10, mom_win=5)

    print(f"\n  SHORT BOOK - kya yeh apni jagah banata hai?")
    print(f"  {D}rule={rule}  ·  {len(prices)} naam  ·  {len(bench)} bars  ·  "
          f"{a.cost_bps}bps cost{X}")
    print("  " + "=" * 68)

    long_only = S.backtest(prices, bench, rule, params, side="long", **kw)
    short_only = S.backtest(prices, bench, rule, params, side="short", **kw)
    both = S.backtest(prices, bench, rule, params, side="both", **kw)
    broken = _broken_rank_backtest(prices, bench, rule, dict(params), side="both", **kw)

    row("LONG only", long_only, G)
    row("SHORT only", short_only)
    row("BOTH (fixed rank)", both)
    row("BOTH (old broken rank)", broken, D)
    print("  " + "=" * 68)

    if not (long_only and both):
        print(f"  {Y}Comparison nahi ho paya.{X}\n")
        return 1

    lr = long_only.get("total_return", long_only.get("return"))
    br = both.get("total_return", both.get("return"))
    sr = (short_only or {}).get("total_return", (short_only or {}).get("return"))
    delta = br - lr
    print(f"\n  Short jodne se: {G if delta > 0 else R}{delta:+.1f}%{X} "
          f"(LONG {lr:+.1f}% -> BOTH {br:+.1f}%)")
    if sr is not None:
        print(f"  Short akela    : {sr:+.1f}%")
    if broken:
        bkr = broken.get("total_return", broken.get("return"))
        print(f"  {D}Purana broken rank BOTH: {bkr:+.1f}%  "
              f"(farq sirf sort ka: {br - bkr:+.1f}%){X}")

    print()
    if delta > 2.0:
        print(f"  {G}>> Short book kuch add karta hai. Cards chhapo, par size wahi - 1 lot.{X}")
    elif delta > -1.0:
        print(f"  {Y}>> Farq shor ke andar hai. Ye 'kaam karta hai' nahi hai, "
              f"'saabit nahi hua' hai.{X}")
    else:
        print(f"  {R}>> Short book paisa khaata hai. RRG wali kahani - dikhao, "
              f"par trade mat karo.{X}")
    print(f"  {D}Ek backtest hypothesis hai, waada nahi. Ye chhota sample hai aur "
          f"in-sample hai.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
