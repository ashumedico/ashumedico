"""
test_option_quality.py  —  the option has to earn the order too.

Until this shipped, selection was entirely stock-level: trend, VWAP, RVOL, squeeze,
expansion. The option was chosen afterwards — ATM, current expiry — and priced. It was
never judged. For a BUYER that is the wrong way round, because the contract IS the trade:
a perfect read on the name, expressed through a strike nobody can exit at a fair price,
loses money for reasons that have nothing to do with the read.

Three things pinned here, each from a number this system was previously inventing:

  1. The bid-ask is MEASURED from the chain, not the OPTION_SPREAD_PCT = 0.02 constant
     that was applied to every strike on every name.
  2. Implied vol is SOLVED from the market price. It appeared nowhere in this codebase
     before — a grep returned nothing — and it is the first thing a professional buyer
     screens on.
  3. The stock-to-option translation cannot return impossible numbers. A long option
     cannot lose more than the premium, and a hold longer than the expiry is not a
     pessimistic trade, it is an incoherent one.

    python test_option_quality.py
"""
import os
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


def cfg():
    m = types.ModuleType("config")
    m.CAPITAL, m.RISK_PCT, m.LOTS_PER_TRADE = 200000, 0.005, 1
    m.BAR_MINUTES, m.RESOLUTION, m.HOLD_BARS = 375, "D", 10
    m.MIN_EXPIRY_DAYS, m.DEFAULT_LOT, m.LOT_SIZES = 15, 50, {}
    m.MAX_POSITIONS, m.OPTION_SPREAD_PCT = 1, 0.02
    m.MAX_SPREAD_PCT, m.MIN_OPTION_OI = 0.05, 500
    m.MIN_OPTION_VOLUME, m.MAX_IV_TO_REALISED = 100, 2.0
    sys.modules["config"] = m
    return m


def series(spot=1000.0, n=60, vol=0.012, seed=3):
    import random
    rnd = random.Random(seed)
    out = [spot]
    for _ in range(n):
        out.append(out[-1] * (1 + rnd.gauss(0.0005, vol)))
    return out


def main():
    C = cfg()
    for m in ("trade_card", "option_metrics", "option_pnl"):
        sys.modules.pop(m, None)
    import trade_card as TC
    import option_pnl as OP

    print("\n  OPTION QUALITY")
    print("  " + "-" * 62)

    closes = series()
    spot = closes[-1]
    K = round(spot / 50) * 50

    # The "good" contract is priced FAIRLY - Black-Scholes at the volatility this series
    # actually realised - rather than at a premium picked by hand. A hand-picked 38.0
    # implied 50% vol against a 24% realised, so the reference contract failed its own
    # IV gate and the test was asserting on a strike no buyer should take.
    import option_metrics as OM
    _rv = OM.realised_vol_annual(closes, window=20, bars_per_year=252)
    FAIR = round(OM.price(spot, K, OM.years_to_expiry(25), _rv, "CE"), 1)

    def row(**kw):
        base = {"strike": K, "type": "CE", "ltp": FAIR,
                "bid": round(FAIR * 0.99, 2), "ask": round(FAIR * 1.01, 2),
                "oi": 9000, "volume": 4200, "symbol": "NSE:X-CE"}
        base.update(kw)
        return base

    # ---- 1. spread is measured, not assumed ---------------------------------
    q, f = TC.option_quality(row(), spot, 25, "CE", closes, C)
    check("a chain with bid/ask gives a MEASURED spread", q["spread_src"] == "measured",
          f"{q['spread_pct'] * 100:.2f}%")
    q2, _ = TC.option_quality(row(bid=None, ask=None), spot, 25, "CE", closes, C)
    check("no bid/ask falls back to the estimate AND says so",
          q2["spread_src"].startswith("assumed"), q2["spread_src"])
    check("the fallback is not silently treated as measured",
          q2["spread_pct"] == C.OPTION_SPREAD_PCT)

    wide = row(bid=round(FAIR * 0.80, 2), ask=round(FAIR * 1.20, 2))
    q3, f3 = TC.option_quality(wide, spot, 25, "CE", closes, C)
    check("a wide measured spread BLOCKS the ticket",
          any("bid-ask" in x for x in f3), f"{q3['spread_pct'] * 100:.1f}%")
    # an ASSUMED spread must never block - blocking on a number we made up would
    # reject good strikes for a reason that does not exist
    q4, f4 = TC.option_quality(row(bid=None, ask=None), spot, 25, "CE", closes, C)
    check("an ASSUMED spread never blocks", not any("bid-ask" in x for x in f4),
          "refusing a trade on an invented number is worse than not checking")

    # ---- 2. liquidity floors -------------------------------------------------
    _, f5 = TC.option_quality(row(oi=120), spot, 25, "CE", closes, C)
    check("thin open interest blocks", any("open interest" in x for x in f5))
    _, f6 = TC.option_quality(row(volume=9), spot, 25, "CE", closes, C)
    check("open interest without VOLUME blocks", any("contracts traded" in x for x in f6),
          "OI with no volume is somebody stuck, not a market you can exit")

    # ---- 3. implied volatility ----------------------------------------------
    check("implied vol is solved from the quote", q["iv"] is not None, f"{q['iv']}")
    check("realised vol is computed from the same closes", q["rv"] is not None,
          f"{q['rv']}")
    check("greeks come with it", all(q.get(k) is not None
                                     for k in ("delta", "theta_day", "gamma", "vega_1pct")),
          f"delta {q['delta']}, theta/day {q['theta_day']}")
    check("theta is negative — it is what a long option gives up", q["theta_day"] < 0)
    check("a call's delta is positive", q["delta"] > 0)
    # priced as a PUT - handing a put the call's premium can put it below its own
    # intrinsic, which correctly yields no implied vol and would have tested nothing
    fair_pe = round(OM.price(spot, K, OM.years_to_expiry(25), _rv, "PE"), 1)
    qp, _ = TC.option_quality(row(type="PE", ltp=fair_pe,
                                  bid=round(fair_pe * 0.99, 2),
                                  ask=round(fair_pe * 1.01, 2)),
                              spot, 25, "PE", closes, C)
    check("a put's delta is negative", (qp["delta"] or 0) < 0, str(qp["delta"]))

    # an unsolvable quote must yield None, never a default
    q7, _ = TC.option_quality(row(ltp=0.0), spot, 25, "CE", closes, C)
    check("an unpriced strike has no implied vol, not a made-up one",
          q7["iv"] is None and q7["vol"]["verdict"] == "unknown")

    # ---- 4. the stock->option translation cannot be impossible ---------------
    # A 30% adverse move at high leverage used to come out below -100%: a loss larger
    # than the money that was ever at risk.
    o_rs, meta = OP.translate([-0.30, -0.50], premium_pct=0.02, delta=0.5,
                              spread_pct=0.02, days_to_expiry=15, hold_days=2)
    check("a long option cannot lose more than the premium", min(o_rs) >= -1.0,
          f"worst {min(o_rs):.2f}")
    check("and the floor is exactly -100%, not -99% or -101%",
          abs(min(o_rs) + 1.0) < 1e-9)

    _, meta2 = OP.translate([0.01], premium_pct=0.02, delta=0.5, spread_pct=0.02,
                            days_to_expiry=15, hold_days=20)
    check("a hold longer than the expiry is refused, not priced",
          bool(meta2.get("invalid")), (meta2.get("invalid") or "")[:60])
    check("the refusal names both numbers",
          "20.0" in (meta2.get("invalid") or "") and "15.0" in (meta2.get("invalid") or ""))

    _, meta3 = OP.translate([0.01], premium_pct=0.02, delta=0.5, spread_pct=0.02,
                            days_to_expiry=15, hold_days=2)
    check("a hold that fits is not refused", not meta3.get("invalid"))

    # ---- 5. the card carries all of it, and blocks on it ---------------------
    p = {"name": "X", "symbol": "NSE:X-EQ", "close": spot,
         "abs_trend": 1.0, "abs_pct": 3.0}
    good_chain = [row()]
    bad_chain = [row(oi=50, volume=3, bid=round(FAIR * 0.75, 2),
                     ask=round(FAIR * 1.25, 2), ltp=FAIR * 2.2)]
    cg = TC.build_card(p, closes, chain=good_chain, days_to_expiry=25,
                       capital=200000, lot=50)
    cb = TC.build_card(p, closes, chain=bad_chain, days_to_expiry=25,
                       capital=200000, lot=50)
    check("a good contract produces no quality failures",
          cg["option"]["quality_fails"] == [], str(cg["option"]["quality_fails"])[:70])
    check("a bad contract produces them", len(cb["option"]["quality_fails"]) >= 3,
          f"{len(cb['option']['quality_fails'])} gates failed")
    check("theta reaches the ticket in RUPEES, not in greek",
          cg["option"].get("theta_rs_day") is not None,
          f"Rs {cg['option'].get('theta_rs_day')}/day per lot")
    check("and the weekend cost is stated separately",
          abs(cg["option"].get("theta_rs_weekend", 0)
              - cg["option"]["theta_rs_day"] * 3) <= 2,
          f"Rs {cg['option'].get('theta_rs_weekend')} over a weekend — "
          f"decay does not stop on Saturday")

    # no chain at all -> gates NOT EVALUATED, and it says so
    cn = TC.build_card(p, closes, days_to_expiry=25, capital=200000, lot=50)
    check("with no chain the gates are reported as not evaluated",
          cn["option"].get("quality") is None and cn["option"].get("quality_note"),
          "not checked is not the same as passed")
    check("and no quality failure is invented from nothing",
          cn["option"]["quality_fails"] == [])

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the contract is judged, not just priced\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
