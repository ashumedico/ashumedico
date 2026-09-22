"""
option_metrics.py  —  what an option is actually worth, and what it costs to hold.

Until now every option number in this system was a constant standing in for a
calculation. Delta was 0.50, or 0.60 one strike in. The bid-ask was
`OPTION_SPREAD_PCT = 0.02`, the same 2% for a Rs 12 premium on an illiquid name and a
Rs 300 premium on RELIANCE. Implied volatility appeared nowhere at all - a grep across
the whole codebase returned nothing. The premium estimate was `intrinsic + 0.4*sigma*sqrt(T)`,
which is a reasonable sketch and is not a price.

That is fine for a system that trades stocks. It is not fine for one that buys options,
because for a BUYER those constants are the trade:

  - Buying a 1.5% move when implied volatility sits far above what the stock has actually
    been doing means paying for a move larger than the one being forecast. The direction
    can be right and the trade still loses.
  - Theta is charged every day whether the thesis works or not, and it is not linear -
    it accelerates into expiry.
  - The spread is paid twice, on the premium, and single-stock options in India are not
    NIFTY: a 4% round trip on an illiquid strike eats a whole day's expected move.

This module computes all of it: Black-Scholes price, the four greeks that matter to a
buyer, implied volatility solved from the market price, and the comparison that tells a
buyer whether he is being charged fairly.

ASSUMPTIONS, STATED
  - European exercise. NSE stock options are American, so this slightly under-prices deep
    ITM puts. Immaterial for the slightly-ITM/ATM strikes this system buys.
  - No dividend. For holds measured in days, on names not going ex-dividend, this is
    smaller than the bid-ask. It is NOT safe across an ex-date - that is what the event
    blackout is for.
  - r defaults to 6.5% (Indian short rate). Its effect on a 2-week option is tiny.

    python option_metrics.py --selftest
"""
import math

R_DEFAULT = 0.065          # Indian short rate; effect on a 2-week option is negligible
SQRT_2PI = math.sqrt(2.0 * math.pi)


def _n_pdf(x):
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _n_cdf(x):
    """Standard normal CDF via erf - exact enough that the solver converges cleanly."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1_d2(spot, strike, t_years, sigma, r):
    if t_years <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return None, None
    v = sigma * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t_years) / v
    return d1, d1 - v


def price(spot, strike, t_years, sigma, kind="CE", r=R_DEFAULT):
    """Black-Scholes premium. `kind` is CE or PE."""
    call = str(kind).upper() != "PE"
    if t_years <= 0:                      # at expiry an option is worth its intrinsic
        return max(0.0, (spot - strike) if call else (strike - spot))
    d1, d2 = _d1_d2(spot, strike, t_years, sigma, r)
    if d1 is None:
        return max(0.0, (spot - strike) if call else (strike - spot))
    disc = math.exp(-r * t_years)
    if call:
        return spot * _n_cdf(d1) - strike * disc * _n_cdf(d2)
    return strike * disc * _n_cdf(-d2) - spot * _n_cdf(-d1)


def greeks(spot, strike, t_years, sigma, kind="CE", r=R_DEFAULT):
    """delta, gamma, theta_per_day, vega_per_1pct — in the units a trader reads.

    theta is PER DAY and NEGATIVE for a long option: it is what the position gives up
    each day if nothing happens. vega is per ONE percentage point of implied vol, not per
    1.00 of it, because nobody thinks in whole units of volatility.
    """
    call = str(kind).upper() != "PE"
    d1, d2 = _d1_d2(spot, strike, t_years, sigma, r)
    if d1 is None:
        return {"delta": 1.0 if (call and spot > strike) else
                         (-1.0 if (not call and spot < strike) else 0.0),
                "gamma": 0.0, "theta_day": 0.0, "vega_1pct": 0.0}
    sq = math.sqrt(t_years)
    pdf = _n_pdf(d1)
    disc = math.exp(-r * t_years)
    delta = _n_cdf(d1) if call else _n_cdf(d1) - 1.0
    gamma = pdf / (spot * sigma * sq)
    theta_year = (-spot * pdf * sigma / (2 * sq)
                  - r * strike * disc * (_n_cdf(d2) if call else -_n_cdf(-d2)))
    vega = spot * pdf * sq
    return {"delta": round(delta, 4), "gamma": round(gamma, 6),
            "theta_day": round(theta_year / 365.0, 4),
            "vega_1pct": round(vega / 100.0, 4)}


def implied_vol(market_price, spot, strike, t_years, kind="CE", r=R_DEFAULT,
                lo=0.01, hi=5.0, tol=1e-6, iters=100):
    """Solve for the volatility the market is charging. None when it cannot be solved.

    None, never a default. A quote below intrinsic, a stale print, or a strike with no
    trade has no implied volatility, and inventing one would put a fabricated number in
    the column a buyer is supposed to judge the trade by.

    Bisection rather than Newton: vega collapses on deep ITM/OTM strikes and Newton walks
    off to nonsense there. Bisection is slower and always lands.
    """
    if market_price is None or market_price <= 0 or t_years <= 0:
        return None
    call = str(kind).upper() != "PE"
    intrinsic = max(0.0, (spot - strike) if call else (strike - spot))
    if market_price < intrinsic - 1e-9:
        return None                       # below intrinsic: not a real premium
    # bracket must contain the answer, or there is nothing to bisect
    if price(spot, strike, t_years, lo, kind, r) > market_price:
        return None                       # cheaper than a 1% vol option - stale quote
    if price(spot, strike, t_years, hi, kind, r) < market_price:
        return None                       # richer than a 500% vol option - not credible
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        p = price(spot, strike, t_years, mid, kind, r)
        if abs(p - market_price) < tol:
            return round(mid, 6)
        if p > market_price:
            hi = mid
        else:
            lo = mid
    return round(0.5 * (lo + hi), 6)


def realised_vol_annual(closes, window=20, bars_per_year=252):
    """Annualised realised volatility from close-to-close log returns.

    The comparison IV needs. `bars_per_year` must match the bar size of `closes` - 252 for
    daily. Handing it 15-minute closes with 252 would understate realised vol by an order
    of magnitude and make every option look expensive.
    """
    if not closes or len(closes) < window + 1:
        return None
    rets = []
    for a, b in zip(closes[-(window + 1):-1], closes[-window:]):
        if a and b and a > 0 and b > 0:
            rets.append(math.log(b / a))
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(bars_per_year), 6)


def vol_verdict(iv, rv):
    """Is the buyer paying up, or being paid to wait?

    IV RANK is the number every professional buyer screens on - where today's implied vol
    sits within its OWN past year. This system has never recorded implied vol, so there is
    no year of it to rank against, and printing a rank computed from three days of history
    would be a fabricated percentile.

    What IS computable from day one is IV against the stock's own REALISED volatility -
    the variance risk premium. It answers the buyer's actual question: am I paying for
    more movement than this name has been delivering? `iv_history.py` starts accumulating
    the series so a true rank becomes available with time rather than being faked now.
    """
    if iv is None or not rv:
        return {"ratio": None, "verdict": "unknown",
                "note": "no implied vol could be solved from this quote"}
    ratio = iv / rv
    if ratio >= 1.5:
        v, note = "EXPENSIVE", ("implied vol is far above what this name has actually "
                                "been doing — a buyer is paying for a move bigger than "
                                "the one being forecast")
    elif ratio >= 1.15:
        v, note = "rich", "implied above realised — the usual state; size accordingly"
    elif ratio >= 0.85:
        v, note = "fair", "implied is close to realised"
    else:
        v, note = "CHEAP", ("implied vol is below realised — options are cheap relative "
                            "to how this name has been moving, which is a buyer's edge")
    return {"ratio": round(ratio, 2), "verdict": v, "note": note}


def years_to_expiry(days, calendar=True):
    """Days to expiry as a year fraction. Calendar days, because theta is charged on
    weekends too - an option held over a Friday-to-Monday loses three days of value, not
    one, and that is exactly the leak a buyer feels and cannot explain."""
    return max(float(days), 0.0) / (365.0 if calendar else 252.0)


# ---------------------------------------------------------------- selftest --
def _selftest():
    ok = True

    def chk(name, cond, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
        ok = ok and cond

    print("\n  OPTION METRICS")
    print("  " + "-" * 62)

    # A textbook case: S=100 K=100 T=1 sigma=20% r=0 -> call ~ 7.966
    p = price(100, 100, 1.0, 0.20, "CE", r=0.0)
    chk("Black-Scholes ATM call matches the textbook", abs(p - 7.9656) < 0.01, f"{p:.4f}")

    # put-call parity: C - P = S - K*e^(-rT)
    c = price(100, 95, 0.5, 0.25, "CE", r=0.065)
    pu = price(100, 95, 0.5, 0.25, "PE", r=0.065)
    parity = 100 - 95 * math.exp(-0.065 * 0.5)
    chk("put-call parity holds", abs((c - pu) - parity) < 1e-6,
        f"C-P={c - pu:.6f} vs S-Ke^-rT={parity:.6f}")

    # implied vol round-trips
    mkt = price(1000, 1000, 30 / 365, 0.32, "CE")
    iv = implied_vol(mkt, 1000, 1000, 30 / 365, "CE")
    chk("implied vol recovers the vol it was priced with", abs(iv - 0.32) < 1e-3,
        f"{iv:.4f} from a price of {mkt:.2f}")

    chk("a quote below intrinsic has no implied vol",
        implied_vol(1.0, 1000, 900, 30 / 365, "CE") is None,
        "100 intrinsic, quoted at 1 - not a real premium")
    chk("a zero quote has no implied vol",
        implied_vol(0, 1000, 1000, 30 / 365, "CE") is None)

    g = greeks(1000, 1000, 30 / 365, 0.32, "CE")
    chk("ATM call delta is near 0.5", 0.5 < g["delta"] < 0.60, str(g["delta"]))
    chk("theta is NEGATIVE for a long option", g["theta_day"] < 0,
        f"{g['theta_day']} per day")
    chk("gamma is positive", g["gamma"] > 0)
    chk("vega is positive", g["vega_1pct"] > 0)

    gp = greeks(1000, 1000, 30 / 365, 0.32, "PE")
    chk("ATM put delta is near -0.5", -0.60 < gp["delta"] < -0.40, str(gp["delta"]))

    # theta accelerates into expiry - the whole reason MIN_EXPIRY_DAYS exists
    far = greeks(1000, 1000, 60 / 365, 0.32, "CE")["theta_day"]
    near = greeks(1000, 1000, 3 / 365, 0.32, "CE")["theta_day"]
    chk("theta accelerates as expiry approaches", abs(near) > abs(far) * 3,
        f"{abs(near):.2f}/day at 3 DTE vs {abs(far):.2f}/day at 60 DTE")

    rv = realised_vol_annual([100 * (1.01 ** i) for i in range(30)])
    chk("a steady drift has near-zero realised vol", rv is not None and rv < 0.01,
        f"{rv}")
    chk("too little history gives None, not zero",
        realised_vol_annual([100, 101, 102]) is None,
        "a fabricated vol would make every option look cheap")

    v = vol_verdict(0.60, 0.30)
    chk("IV at twice realised reads EXPENSIVE", v["verdict"] == "EXPENSIVE", str(v["ratio"]))
    v = vol_verdict(0.20, 0.30)
    chk("IV below realised reads CHEAP", v["verdict"] == "CHEAP", str(v["ratio"]))
    chk("no IV yields 'unknown', never a default",
        vol_verdict(None, 0.30)["verdict"] == "unknown")

    chk("expiry uses CALENDAR days — theta is charged over the weekend",
        abs(years_to_expiry(365) - 1.0) < 1e-9)

    print("  " + "-" * 62)
    print("  all good\n" if ok else "  FAILURES ABOVE\n")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print(__doc__)
