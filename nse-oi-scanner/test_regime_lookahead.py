"""
Prove the regime filter cannot see the future.

A regime gate that peeks even one bar ahead will improve every backtest it is added to,
which is indistinguishable from a real edge until real money is on it. So this does not
argue about the code - it re-runs the regime with the future physically deleted and
demands the identical answer.

    python test_regime_lookahead.py
"""
import sys
sys.path.insert(0, ".")
import rrg_engine as E
import market_regime as MR

_pts, prices, bench = E.demo_points()
T = len(bench)

full = MR.Regime(prices, bench)

bars = [t for t in range(80, T, 7)]
mismatch = []
for t in bars:
    # the same bar, computed in a world where nothing after t-1 exists at all
    truncated = MR.Regime({k: v[:t] for k, v in prices.items()}, bench[:t])
    a = full.at(t)
    b = truncated.at(t)
    same = (a["state"] == b["state"] and a["passed"] == b["passed"]
            and a["checks"] == b["checks"])
    if not same:
        mismatch.append((t, a["state"], b["state"], a["checks"], b["checks"]))

print(f"  regime evaluated at {len(bars)} bars, each recomputed with the future deleted")
if mismatch:
    print(f"  *** LOOKAHEAD DETECTED at {len(mismatch)} bars ***")
    for t, s1, s2, c1, c2 in mismatch[:5]:
        print(f"    bar {t}: full-series says {s1}, truncated says {s2}")
        print(f"           {c1}\n           {c2}")
    sys.exit(1)
print("  identical at every bar - the gate uses no information from the future")

# and the states it actually produces, so a gate that is always-on cannot hide
states = {}
for t in bars:
    states[full.at(t)["state"]] = states.get(full.at(t)["state"], 0) + 1
print(f"  states across the sample: {states}")
if len(states) == 1:
    print("  NOTE: only one state occurs here - on this data the gate never changes"
          "\n        anything, so it can neither help nor hurt. Judge it on real data.")
