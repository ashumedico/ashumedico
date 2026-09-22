"""
test_rfactor.py  —  an ablation arm only means something if it changes ONE thing.

TradeFinder's R-Factor is described as the intensity of momentum AND volatility: today's
activity against the name's own last ~20 days. Ours read close-to-close only, so a
2-sigma move on half the usual volume and a 2-sigma move on triple volume with a range
three times normal scored identically. For an option BUYER that is the whole trade —
premium is paid for movement, and a move without participation is the one that stalls and
bleeds theta.

The composite version folds volume and range in. The property that makes it TESTABLE
rather than merely different is that its multiplier is **centred on 1.0**: at normal
volume and normal range it reduces to the price-only version. So the two arms diverge
only where activity is abnormal, and the ablation measures *the addition* instead of
comparing two unrelated rankings and calling the difference evidence.

That is the trap this file guards. A variant that changes several things at once produces
a number that attributes nothing — which is how a system ends up with twenty features and
an edge of unknown origin.

    python test_rfactor.py
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def make(n=80, seed=5, drift=0.001, vol=0.012):
    rnd = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * (1 + rnd.gauss(drift, vol)))
    bars = [[i, c, c * 1.005, c * 0.995, c, 100000] for i, c in enumerate(closes)]
    return closes, bars


def main():
    import rrg_strategy as S

    print("\n  R-FACTOR")
    print("  " + "-" * 62)

    closes, bars = make()
    t = len(bars)
    base = S.r_factor(closes, t, k=10)
    check("the price-only factor scores a trending name positively", base > 0,
          f"{base:+.3f}")

    # ---- the property that makes the arm a measurement ----------------------
    full = S.r_factor_full(bars, t, k=10)
    check("at NORMAL volume and range the composite reduces to the control",
          abs(full / base - 1.0) < 0.05, f"ratio {full / base:.3f}")

    hot = [r[:] for r in bars]
    hot[-1][5] = 300000                       # 3x volume
    hot[-1][2] = hot[-1][4] * 1.03            # and a much wider range
    hot[-1][3] = hot[-1][4] * 0.97
    fh = S.r_factor_full(hot, t, k=10)
    check("a move on 3x volume with a wide range scores higher", fh > base * 1.5,
          f"ratio {fh / base:.2f}")

    cold = [r[:] for r in bars]
    cold[-1][5] = 50000                       # half the usual volume
    fc = S.r_factor_full(cold, t, k=10)
    check("the SAME move on half the volume scores lower", fc < base,
          f"ratio {fc / base:.2f} — participation is what pays for the premium")

    # ---- bounded: one freak print must not dominate the universe ------------
    freak = [r[:] for r in bars]
    freak[-1][5] = 100000 * 500               # 500x volume
    freak[-1][2] = freak[-1][4] * 5
    freak[-1][3] = freak[-1][4] * 0.2
    ff = S.r_factor_full(freak, t, k=10)
    check("ratios are capped, so one freak bar cannot dominate the ranking",
          ff <= base * 2.05, f"ratio {ff / base:.2f} against a designed ceiling of 2.0")

    # ---- direction is preserved --------------------------------------------
    # A deterministic decline over the LAST k bars. Using a negative drift over the whole
    # series was not enough: r_factor measures the move over the last k bars, and a noisy
    # downtrend can still be up across those ten - so the test was asserting on a series
    # that happened not to be falling where the factor actually looks.
    dn_closes, dn_bars = make()
    for i in range(1, 12):
        dn_bars[-i][4] = dn_bars[-12][4] * (1 - 0.02 * (12 - i))
        dn_bars[-i][1] = dn_bars[-i][4]
        dn_bars[-i][2] = dn_bars[-i][4] * 1.005
        dn_bars[-i][3] = dn_bars[-i][4] * 0.995
    dn = S.r_factor_full(dn_bars, len(dn_bars), k=10)
    check("a falling name scores negative — the factor stays signed", dn < 0,
          f"{dn:+.3f}; the direction-agnostic version is for scalping, not this book")

    # ---- refusals -----------------------------------------------------------
    check("too little history returns 0.0, not a partial score",
          S.r_factor_full(bars[:12], 12, k=10) == 0.0)
    check("no bars returns 0.0 rather than raising", S.r_factor_full(None, 50) == 0.0)
    check("zero volume history does not divide by zero",
          isinstance(S.r_factor_full([[i, 100, 101, 99, 100, 0] for i in range(60)],
                                     60, k=10), float))

    # ---- and it is NOT in the live selector ---------------------------------
    src = open(os.path.join(HERE, "rrg_strategy.py")).read()
    check("the composite is reachable as an ablation arm", "rfactor_full" in src)
    hyp = open(os.path.join(HERE, "hypothesis.py")).read()
    check("...and has arms defined for it", hyp.count("rfactor_full") >= 2)
    check("NOT ENABLED — an untested factor stays out of the live selector",
          "NOT ENABLED" in src,
          "this is the rung the -6.3% RRG skipped")

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the arm changes exactly one thing\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
