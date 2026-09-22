"""
test_card_math.py  —  every number on a ticket has to agree with every other one.

A ticket is a set of claims that are only useful if they are consistent: the stop is on
the losing side of the entry, the targets step away in order, the R:R printed is the R:R
you would actually get at the stated entry, and the option levels are derived from the
same entry as the stock levels.

None of that was true. The stop and both targets were computed from SPOT while the entry
was a limit somewhere else, so every figure that divides by risk was wrong by the gap
between them - on a worked example the card claimed R:R 1.5 while the real number at the
stated entry was 1.20. And "TP3" was computed a third way and landed BETWEEN TP1 and TP2:
a level labelled third target that was the second-furthest.

Numbers this wrong do not announce themselves. They look like numbers.

    python test_card_math.py
"""
import os
import random
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def cfg(bar_minutes=15):
    m = types.ModuleType("config")
    m.CAPITAL, m.RISK_PCT, m.LOTS_PER_TRADE = 200000, 0.005, 1
    m.BAR_MINUTES, m.RESOLUTION, m.HOLD_BARS = bar_minutes, "15", 10
    m.MIN_EXPIRY_DAYS, m.DEFAULT_LOT, m.LOT_SIZES = 15, 50, {}
    m.MAX_POSITIONS, m.OPTION_SPREAD_PCT = 1, 0.02
    sys.modules["config"] = m
    return m


def series(spot, n=60, vol=0.0035, drift=0.0005, seed=3):
    rnd = random.Random(seed)
    out = [float(spot)]
    for _ in range(n):
        out.append(out[-1] * (1 + rnd.gauss(drift, vol)))
    return out


def main():
    cfg()
    for m in ("trade_card",):
        sys.modules.pop(m, None)
    import trade_card as TC

    print("\n  TICKET ARITHMETIC")
    print("  " + "-" * 62)

    for spot, seed in ((5575.0, 3), (240.0, 11), (1420.0, 7)):
        closes = series(spot, seed=seed)
        for side, trend in (("LONG", 1.0), ("SHORT", -1.0)):
            d = 1 if side == "LONG" else -1
            p = {"name": "X", "symbol": "NSE:X-EQ", "close": closes[-1],
                 "abs_trend": trend, "abs_pct": 3.0 * trend}
            c = TC.build_card(p, closes, days_to_expiry=25, capital=200000,
                              lot=50, side=side)
            s, o = c["stock"], c["option"]
            e, R = s["entry_px"], s["risk_pts"]
            tag = f"{side} @{spot:.0f}"

            check(f"{tag}: stop is on the losing side of ENTRY",
                  (s["stop"] < e) if d > 0 else (s["stop"] > e),
                  f"entry {e} stop {s['stop']}")
            check(f"{tag}: targets step away in order",
                  (s["t1"] < s["t2"] < s["t3"]) if d > 0
                  else (s["t1"] > s["t2"] > s["t3"]),
                  f"{s['t1']} / {s['t2']} / {s['t3']}")
            # the claim that matters: the printed R:R is the one he would get
            for t, rr in ((s["t1"], s["rr1"]), (s["t2"], s["rr2"]), (s["t3"], s["rr3"])):
                real = abs(t - e) / R
                check(f"{tag}: R:R {rr} is real at {t}", abs(real - rr) < 0.02,
                      f"printed {rr}, actual {real:.2f}")
            check(f"{tag}: R equals the distance to the stop",
                  abs(R - abs(e - s["stop"])) < 0.01)

            # option levels must come off the SAME entry
            check(f"{tag}: option stop is below the premium",
                  o["stop"] < o["premium"], f"{o['stop']} vs {o['premium']}")
            check(f"{tag}: option targets step up in order",
                  o["premium"] < o["t1"] < o["t2"] < o["t3"],
                  f"{o['premium']} / {o['t1']} / {o['t2']} / {o['t3']}")
            check(f"{tag}: option is a {'PE' if d < 0 else 'CE'}",
                  o["type"] == ("PE" if d < 0 else "CE"))

    # ---- the lot band, both sides ----
    print("\n  LOT / CONTRACT VALUE")
    closes = series(5575.0)
    p = {"name": "X", "symbol": "NSE:X-EQ", "close": closes[-1],
         "abs_trend": 1.0, "abs_pct": 3.0}
    for lot, expect, why in ((18365, True, "freeze quantity - Rs 10 crore"),
                             (13, True, "old COFORGE bug - Rs 70k"),
                             (50, False, "sane")):
        z = TC.build_card(p, closes, days_to_expiry=25, capital=200000,
                          lot=lot)["size"]
        check(f"lot {lot} absurd={expect}", z["lot_absurd"] is expect,
              f"contract Rs {z['contract_value']:,} — {why}")

    # ---- SKIP must not print a tradeable plan ----
    print("\n  SKIP")
    p_flat = {"name": "X", "symbol": "NSE:X-EQ", "close": closes[-1],
              "abs_trend": -1.0, "abs_pct": -1.0}
    c = TC.build_card(p_flat, closes, days_to_expiry=25, capital=200000, lot=50)
    check("a long on a falling name is SKIPped", c["action"] == "SKIP", c["action"])
    check("SKIP still prices its levels from spot, not from nothing",
          c["stock"]["entry_px"] == c["spot"] and c["stock"]["entry"] is None,
          "no limit is offered, but the levels remain readable")

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the ticket agrees with itself\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
