"""
trade_card.py  —  turns an RRG candidate into an explicit ORDER TICKET.

The RRG tells you *what is rotating*. It never tells you what to buy, at what price, or
when to get out. This module closes that gap: one candidate in, a complete decision out.

Every card answers, with numbers:
    WHAT      stock + the exact option (CE/PE, strike, expiry) or the future
    BUY NOW?  ACT / WAIT-FOR-PULLBACK / SKIP  — and the limit price to use
    SIZE      quantity, straight from the risk gate (never from conviction)
    EXIT IF   hard stop  (thesis wrong -> out, no averaging)
    BOOK AT   T1 (take half) and T2 (take the rest)
    TRAIL     where the stop moves once T1 pays
    TIME OUT  dead-money stop, and the pre-expiry exit for options

Stops are volatility-scaled (not a flat %), because a 4% stop is noise on one stock and
a disaster on another. Vol comes from realised close-to-close deviation.

NOT financial advice. Signals are inputs; the decision is yours.
"""
import math
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 500000; RISK_PCT = 0.005
    config = _C()


# ---------------- volatility ----------------
def realised_vol(closes, n=20):
    """Volatility in PRICE terms, per BAR of whatever series is passed in.

    On daily closes this is daily vol. On 15-minute closes it is 15-minute vol - roughly
    a fifth of the daily number. Stops and targets want this bar-level figure, because
    they live on the same chart as the signal. Anything that reasons in CALENDAR time -
    option premium, time decay - must convert first via bar_to_daily_vol below, or it
    will price a month of time using five hours of movement."""
    if len(closes) < n + 2:
        return closes[-1] * 0.02 if closes else 0.0
    rets = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - n, len(closes))]
    m = sum(rets) / len(rets)
    sd = (sum((r - m) ** 2 for r in rets) / len(rets)) ** 0.5
    return closes[-1] * sd


def bar_to_daily_vol(vol_bar, bar_minutes=None):
    """Scale per-bar volatility up to per-day. Vol grows with the square root of time."""
    bm = float(bar_minutes if bar_minutes is not None
               else getattr(config, "BAR_MINUTES", SESSION_MINUTES))
    bars_per_day = max(SESSION_MINUTES / bm, 1.0)
    return vol_bar * (bars_per_day ** 0.5)


# ---------------- option selection ----------------
def strike_step(price):
    if price >= 20000: return 100
    if price >= 5000:  return 100
    if price >= 2000:  return 50
    if price >= 1000:  return 20
    if price >= 500:   return 10
    if price >= 100:   return 5
    return 2.5


def pick_strike(spot, direction, moneyness=None):
    """ATM by default, because the goal is catching momentum, not tracking a stock.

    Slightly in-the-money has a higher delta and is the right choice for a position you
    intend to hold. For a burst you want GAMMA - how fast delta grows as the move runs -
    and that peaks at the money. ATM also costs less, so the same rupees buy more
    contract, and it is where the volume is, which is where the spread is tightest.

    Set MONEYNESS in config to override.
    """
    moneyness = moneyness or getattr(config, "MONEYNESS", "ATM")
    step = strike_step(spot)
    atm = round(spot / step) * step
    if moneyness == "ATM":
        return atm
    if direction == "BULLISH":
        return atm - step if moneyness == "ITM1" else atm + step
    return atm + step if moneyness == "ITM1" else atm - step


def premium_estimate(spot, strike, direction, vol_daily, days_to_expiry=25):
    """Rough premium when a live chain isn't handy: intrinsic + time value.
    Live chain always wins — this only keeps the card usable off-hours."""
    intrinsic = max(0.0, (spot - strike) if direction == "BULLISH" else (strike - spot))
    sigma_t = vol_daily * math.sqrt(max(days_to_expiry, 1))
    time_value = 0.40 * sigma_t
    return round(max(intrinsic + time_value, spot * 0.002), 1)


def option_from_chain(chain, strike, direction):
    """Exact premium AND the exchange's tradeable symbol from a live chain.

    The symbol matters as much as the price: an order has to name a contract, and a
    symbol assembled by hand from strike and expiry is one typo away from a rejection or
    from a different contract entirely."""
    want = "CE" if direction == "BULLISH" else "PE"
    best = None
    for o in chain or []:
        if o.get("type") == want and o.get("strike") is not None:
            if best is None or abs(o["strike"] - strike) < abs(best["strike"] - strike):
                best = o
    if best and best.get("ltp"):
        return best["strike"], float(best["ltp"]), best.get("symbol")
    return None, None, None


# ---------------- the card ----------------
SESSION_MINUTES = 375           # 09:15 to 15:30


def hold_days(hold_bars=None, bar_minutes=None):
    """The intended hold, in trading days - whatever bar size the signal runs on.

    A hold of "10 bars" means ten months on a monthly chart and two and a half hours on a
    15-minute one. Every downstream rule that talks about time has to go through here,
    or the expiry rule silently assumes the bar size it was written for."""
    hb = float(hold_bars if hold_bars is not None else getattr(config, "HOLD_BARS", 10))
    bm = float(bar_minutes if bar_minutes is not None
               else getattr(config, "BAR_MINUTES", SESSION_MINUTES))
    return hb * bm / SESSION_MINUTES


def min_days_for_thesis(hold_bars=None, bar_minutes=None, daily_vol_pct=None,
                        spread_pct=None):
    """Which expiry the ticket should quote - chosen by arithmetic, not by feel.

    The intuition that a short hold wants a near expiry is wrong, and expensively so. A
    nearer option is cheaper and therefore more levered, but its decay per session is
    savage; a further one costs premium and gives that leverage back. Neither effect wins
    by default. What matters is the combination: how far must the STOCK move before the
    option has paid for its own decay and spread. That number has a minimum, and for a
    two-and-a-half-hour hold it sits nearer ten days than three - the 3-day answer this
    function used to give needs roughly twice the move to break even.

    Falls back to the old bound if the optimiser is unavailable, so a missing module
    degrades the answer rather than breaking the ticket.
    """
    hd = hold_days(hold_bars, bar_minutes)
    # An explicit floor set by the trader wins over the optimiser. His rule is 15 days:
    # if the running month has less than that left, roll to the next series. The sweep
    # puts the cheapest break-even at 10 days and 15 days at 0.16% against 0.15%, so the
    # rule costs essentially nothing - and a rule he can apply from the expiry date alone,
    # without re-running anything, is worth more than a hundredth of a percent.
    floor = getattr(config, "MIN_EXPIRY_DAYS", None)
    if floor:
        return int(floor)
    try:
        import option_pnl as OP
        rows = OP.dte_sweep(
            hold_days=hd,
            daily_vol=(daily_vol_pct if daily_vol_pct else 0.018),
            delta=0.60,
            spread_pct=(spread_pct if spread_pct is not None
                        else getattr(config, "OPTION_SPREAD_PCT", 0.02)))
        best = min(rows, key=lambda r: r["breakeven"])
        return max(3, int(best["dte"]))
    except Exception:
        return max(3, int(hd * 1.4) + 2)


def build_card(point, closes, chain=None, expiry_label=None, days_to_expiry=25,
               instrument="OPTION", capital=None, risk_pct=None, lot=None, side="LONG"):
    """point: an rrg_engine point dict. closes: that stock's close series.

    side="SHORT" builds the mirror: a PE, stop above, targets below, and the stretch test
    inverted. Everything derived from the stop distance follows automatically, which is
    the point of mirroring here rather than in the caller - a short card assembled at the
    display layer would get the option maths from the long path and quietly price a put
    off a call's stop.
    """
    capital = float(capital if capital is not None else getattr(config, "CAPITAL", 500000))
    risk_pct = float(risk_pct if risk_pct is not None else getattr(config, "RISK_PCT", 0.005))
    spot = float(point.get("close") or closes[-1])
    short = str(side).upper() == "SHORT"
    direction = "BEARISH" if short else "BULLISH"
    vol = realised_vol(closes) or spot * 0.02
    sgn = -1.0 if short else 1.0

    # ---- entry FIRST, then everything measured from it --------------------------
    # This used to run the other way round: the stop and both targets were built off
    # SPOT, and then the entry was set somewhere else - a limit above spot when chasing,
    # a limit below it when waiting for a pullback. So the R printed on the card was not
    # the R the trade would actually have. On one worked example the card claimed
    # R:R 1.5 while the real figure from the stated entry was 1.20. Every number that
    # divides by risk was wrong by the gap between spot and the limit.
    #
    # Now the entry is decided first and the stop, all three targets and the R:R are
    # measured from THAT price. If he enters where the card says, the numbers are his.
    raw_stretch = (spot - (sum(closes[-10:]) / 10)) / vol if len(closes) >= 10 else 0
    stretch = raw_stretch * sgn
    trend = point.get("abs_trend", 0)
    if (trend >= 0) if short else (trend <= 0):
        action = "SKIP"
        entry_note = ("own trend is not down — rotation alone is not enough" if short
                      else "own trend is not up — rotation alone is not enough")
        limit_px = None
    elif stretch > 2.2:
        action = "WAIT FOR PULLBACK"
        limit_px = round(spot + sgn * 0.8 * vol, 2)
        entry_note = (f"extended {stretch:.1f}x vol "
                      f"{'below' if short else 'above'} its 10-day mean — "
                      f"{'offer' if short else 'bid'} {limit_px}, don't chase")
    else:
        action = "BUY PE NOW" if short else "BUY NOW"
        limit_px = round(spot * (0.998 if short else 1.002), 2)
        entry_note = (f"in range ({stretch:+.1f}x vol from mean) — "
                      f"{'sell down to' if short else 'buy up to'} {limit_px}")

    # A price is a price. Leaving this as a raw float made entry_px and spot differ
    # in the 12th decimal, which is invisible on screen and breaks every equality
    # test that tries to check the two agree.
    entry_px = round(limit_px if limit_px is not None else spot, 2)

    # Targets as multiples of R, so their ORDER is guaranteed by arithmetic instead of
    # by hoping two different formulas happen to sort. The old card computed T1/T2 from
    # vol and T3 from R, and T3 landed BETWEEN T1 and T2 - a level labelled "third
    # target" that was the second-furthest.
    risk_pts = 2.0 * vol
    stop_px = round(entry_px - sgn * risk_pts, 2)
    t1_px = round(entry_px + sgn * 1.5 * risk_pts, 2)
    t2_px = round(entry_px + sgn * 3.0 * risk_pts, 2)
    t3_px = round(entry_px + sgn * 4.0 * risk_pts, 2)
    risk_pts = max(risk_pts, 1e-9)
    rr1, rr2, rr3 = 1.5, 3.0, 4.0

    card = {
        "name": point["name"], "symbol": point.get("symbol"),
        "action": action, "entry_note": entry_note,
        "quadrant": point.get("quadrant"), "confidence_bits": {
            "rotation": point.get("quadrant"),
            "crossed_in": point.get("crossed"),
            "distance": point.get("distance"),
            "velocity": point.get("velocity"),
            "own_trend": point.get("abs_trend"),
            "oi": point.get("signal"),
        },
        "spot": round(spot, 2), "vol_daily": round(vol, 2),
        # Every one of these is measured from `entry`, not from spot.
        "stock": {"entry": limit_px, "entry_px": entry_px, "stop": stop_px,
                  "t1": t1_px, "t2": t2_px, "t3": t3_px, "risk_pts": round(risk_pts, 2),
                  "rr1": rr1, "rr2": rr2, "rr3": rr3},
        "instrument": instrument,
        "rules": [],
    }

    # ---- the option leg ----
    if instrument == "OPTION":
        strike = pick_strike(spot, direction)
        ch_strike, ch_prem, ch_sym = option_from_chain(chain, strike, direction)
        # Sanity-gate the chain before trusting it. A slightly-in-the-money call is worth
        # its intrinsic plus a few percent of spot; a quote approaching the share price
        # itself means the lookup landed on a deep-ITM strike, a stale print, or another
        # instrument. Multiplied by a lot size that becomes a ticket claiming one lot
        # costs more than the entire account - which is what it printed live, so the
        # chain is checked rather than believed.
        prem_reject = None
        if ch_strike is not None and ch_prem is not None:
            # A put's intrinsic is strike-minus-spot, not spot-minus-strike. Using the
            # call formula for a PE makes every in-the-money put look absurdly overpriced
            # and would get every real quote rejected as fake.
            intrinsic = (max(0.0, ch_strike - spot) if short
                         else max(0.0, spot - ch_strike))
            if ch_prem <= 0 or ch_prem > intrinsic + 0.25 * spot:
                prem_reject = (f"chain quoted {ch_strike:g}{'PE' if short else 'CE'} at "
                               f"{ch_prem} against spot {spot:.1f} (intrinsic "
                               f"{intrinsic:.1f}) - not a real slightly-ITM premium; "
                               f"estimated instead")
        if ch_strike is not None and ch_prem is not None and prem_reject is None:
            strike, premium = ch_strike, ch_prem
            prem_src = "live chain"
        else:
            # premium_estimate reasons in CALENDAR days, so it needs daily vol - handing
            # it the 15-minute figure would price a month of time value off five hours
            # of movement and understate the premium several-fold
            premium = premium_estimate(spot, strike, direction,
                                       bar_to_daily_vol(vol), days_to_expiry)
            prem_src = "estimated"
        # refuse an expiry too close to carry the trade
        need_days = min_days_for_thesis()
        expiry_warning = None
        if days_to_expiry < need_days:
            expiry_warning = (f"expiry only {days_to_expiry}d away but this thesis needs "
                              f"~{need_days}d - roll to the next series")
        # Delta follows the strike actually chosen: ~0.5 at the money, ~0.6 one strike in.
        delta = 0.50 if getattr(config, "MONEYNESS", "ATM") == "ATM" else 0.60
        # Distances, not signed differences: the premium of a put rises as the stock
        # falls, so the same formula serves both sides once the direction is taken out.
        # Measured from the ENTRY, like every stock level above. Using spot here would
        # reintroduce the same mismatch on the option leg: a premium stop derived from a
        # price he is not entering at.
        opt_stop = round(max(premium - delta * abs(entry_px - stop_px), premium * 0.55), 1)
        opt_t1   = round(premium + delta * abs(t1_px - entry_px), 1)
        opt_t2   = round(premium + delta * abs(t2_px - entry_px), 1)
        opt_t3   = round(premium + delta * abs(t3_px - entry_px), 1)
        card["option"] = {
            "type": "CE" if direction == "BULLISH" else "PE",
            "strike": strike, "expiry": expiry_label or "current",
            "premium": premium, "premium_source": prem_src,
            "stop": opt_stop, "t1": opt_t1, "t2": opt_t2, "t3": opt_t3,
            "max_loss_per_unit": round(premium - opt_stop, 1),
            "days_to_expiry": days_to_expiry,
            "expiry_warning": expiry_warning,
            "premium_reject": prem_reject,
            "tradingsymbol": ch_sym,
            # the raw inputs behind the money figures, so a wrong number can be pinned to
            # its source instead of guessed at from the total
            "raw": {"spot": round(spot, 2), "wanted_strike": strike,
                    "chain_strike": ch_strike, "chain_ltp": ch_prem},
        }
        risk_per_unit = max(premium - opt_stop, 1e-9)
    else:
        risk_per_unit = risk_pts

    # ---- size ----
    # He buys ONE lot. That is the decision, not an output - so quantity is not derived
    # from the risk budget any more. Deriving it was wrong twice over: it could suggest
    # two or three lots on a cheap name, which is a quarter of the account in a levered
    # instrument, and when the arithmetic said "zero lots" it printed an unbuyable
    # quantity instead of the trade he would actually place.
    #
    # The risk rule now does the job it is good at: not sizing the trade, but telling him
    # whether the trade he is going to place anyway is inside his own limit.
    budget = capital * risk_pct
    units = int(budget / risk_per_unit) if risk_per_unit > 0 else 0
    # Real F&O lot size. Options/futures trade only in whole lots, so a wrong lot makes
    # the quantity unbuyable and the risk figure meaningless. Prefer the live option
    # chain (authoritative), then a config override, then the Fyers symbol master, and
    # only then a generic fallback.
    chain_lot = int(lot) if lot else None
    if not lot:
        lot = getattr(config, "LOT_SIZES", {}).get(point["name"])
    try:
        from fno_universe import lot_sizes
        master_lot = lot_sizes().get(point["name"])
    except Exception:
        master_lot = None
    lot = int(lot or master_lot or getattr(config, "DEFAULT_LOT", 1) or 1)
    rule_lots = max(0, units // max(lot, 1))       # what the risk budget alone would allow
    lots = int(getattr(config, "LOTS_PER_TRADE", 1) or 1)
    # Sanity-check the lot itself, two ways.
    # 1) Every NSE F&O contract is sized to roughly Rs 5-10 lakh of underlying. Far below
    #    that means the lot came from the wrong place and the quantity is fiction.
    # 2) If the live chain and the symbol master disagree, one of them is stale - a split
    #    revises the lot (COFORGE went 75 -> 375 on a 5:1). Trade the chain, but say so.
    # The band has to be checked from BOTH sides. It only ever tested "too small", which
    # is the failure that happened first (COFORGE at 13). The freeze-quantity bug fails the
    # other way - PERSISTENT came back as lot 18,365, a Rs 102 CRORE contract - and a
    # one-sided check waved it straight through to a button.
    contract_value = round(spot * lot)
    lot_warning = None
    lot_absurd = False
    if contract_value < 200000:
        lot_absurd = True
        lot_warning = (f"lot {lot} gives a contract value of only Rs {contract_value:,} - "
                       f"NSE F&O contracts are ~Rs 5-10 lakh, so verify the lot before you order")
    elif contract_value > 2000000:
        lot_absurd = True
        lot_warning = (f"lot {lot} gives a contract value of Rs {contract_value:,} - "
                       f"NSE F&O contracts are ~Rs 5-10 lakh, so this lot is wrong "
                       f"(freeze quantity reads like this). Do NOT order on it.")
    elif contract_value > 1200000:
        # Not absurd, but above the band. Worth saying out loud rather than silently
        # sizing on it - a name can run past its lot revision, and a wrong lot looks
        # exactly like this on the way up.
        lot_warning = (f"lot {lot} gives a contract value of Rs {contract_value:,} - "
                       f"above the usual Rs 5-10 lakh band. Check the lot before ordering.")
    elif chain_lot and master_lot and chain_lot != master_lot:
        lot_warning = (f"lot mismatch: live chain says {chain_lot}, symbol master says "
                       f"{master_lot} - using {chain_lot}; a recent split may have revised it")
    card["size"] = {"risk_budget": round(budget), "lot": lot, "lots": lots,
                    "qty": lots * max(lot, 1),
                    "risk_per_unit": round(risk_per_unit, 2),
                    # the fixed size vs what his own risk rule would have allowed
                    "rule_lots": rule_lots,
                    "too_big": rule_lots < lots,
                    "one_lot_risk": round(risk_per_unit * lot),
                    "contract_value": contract_value,
                    "lot_absurd": lot_absurd,
                    "lot_warning": lot_warning}

    # ---- can he actually pay for it? ----
    # Risk sizing answers "how much am I willing to lose". On a small account a second
    # question bites first: the cash to buy ONE lot. F&O lots do not get smaller to suit
    # the account, so this is a hard yes/no - and printing a quantity he cannot fund is
    # the same class of lie as printing a wrong lot.
    if card.get("option"):
        o = card["option"]
        cost_per_lot = round(o["premium"] * lot)
        risk_per_lot = round((o["premium"] - o["stop"]) * lot)
        card["size"].update({
            "cost_per_lot": cost_per_lot,
            "cost_pct": round(100 * cost_per_lot / capital, 1) if capital else None,
            "risk_per_lot": risk_per_lot,
            "risk_pct_of_capital": round(100 * risk_per_lot / capital, 1) if capital else None,
            "affordable_lots": int(capital // cost_per_lot) if cost_per_lot else 0,
        })
        # Cross-check the outlay against the contract it controls. SEBI sizes a stock
        # F&O lot so the contract is worth Rs 5-10 lakh, and a short-dated slightly-ITM
        # call costs a few percent of that - roughly Rs 20,000-40,000 per lot. An outlay
        # approaching the contract's own value means premium or lot is wrong, and this
        # catches the wrong-LOT case that the premium check alone cannot see.
        if contract_value and cost_per_lot > 0.20 * contract_value:
            card["size"]["cost_warning"] = (
                f"one lot costs Rs {cost_per_lot:,} against a contract worth Rs "
                f"{contract_value:,} - {100*cost_per_lot/contract_value:.0f}% of the "
                f"underlying. A real short-dated call is 3-5%; premium or lot is wrong.")
        if cost_per_lot > capital:
            card["size"]["afford_note"] = (
                f"one lot costs Rs {cost_per_lot:,} - more than your entire Rs "
                f"{int(capital):,} capital. This name is not tradeable for you.")
        elif cost_per_lot > 0.5 * capital:
            card["size"]["afford_note"] = (
                f"one lot costs Rs {cost_per_lot:,} = {card['size']['cost_pct']}% of capital. "
                f"That is one position and no room for a second.")

    # ---- the exit contract: mechanical, decided BEFORE entry ----
    o = card.get("option")
    card["rules"] = [
        ("EXIT IF (hard stop)",
         f"stock closes below {stop_px}" + (f"  |  or premium hits {o['stop']}" if o else "")),
        ("BOOK HALF at T1",
         f"stock {t1_px}" + (f"  |  premium {o['t1']}" if o else "") + f"   (R:R {rr1})"),
        ("TRAIL the rest",
         "move stop to breakeven the moment T1 fills; then trail 2x daily vol below the high"),
        ("BOOK REST at T2",
         f"stock {t2_px}" + (f"  |  premium {o['t2']}" if o else "") + f"   (R:R {rr2})"),
        ("INVALIDATE (rotation)",
         "exit next open if RRG crosses into Weakening/Lagging or the own-trend flips down"),
        ("TIME OUT", _timeout_rule()),
    ]
    if o:
        card["rules"].append(("EXPIRY RULE",
                             "square off 3 sessions before expiry, or roll to next series — "
                             "never hold a long option into the theta cliff"))
    return card


def _timeout_rule(hold_bars=None, bar_minutes=None):
    """Dead money is a cost - but "10 sessions" is meaningless on a 15-minute chart.
    State the timeout in the unit the trade is actually measured in."""
    hb = int(hold_bars if hold_bars is not None else getattr(config, "HOLD_BARS", 10))
    d = hold_days(hb, bar_minutes)
    if d < 1:
        return (f"if T1 hasn't printed in {hb} bars (~{d*375/60:.1f} hrs), close it — "
                f"an intraday thesis that needs a second day was wrong about the day")
    return (f"if T1 hasn't printed in {hb} bars (~{d:.0f} sessions), close it — "
            f"dead money is a cost")


def render(card):
    c = card
    print("\n" + "=" * 66)
    print(f"  {c['action']}   {c['name']}    spot {c['spot']}   [{c['quadrant']}]")
    print("=" * 66)
    print(f"  {c['entry_note']}")
    if c.get("option"):
        o = c["option"]
        print(f"\n  BUY   {c['name']} {o['strike']} {o['type']} ({o['expiry']})"
              f"   premium ~{o['premium']} [{o['premium_source']}]")
        print(f"  QTY   {c['size']['qty']}  ({c['size']['lots']} lot x {c['size']['lot']})"
              f"   risk budget Rs {c['size']['risk_budget']}")
        if o.get("expiry_warning"):
            print(f"  WARN  {o['expiry_warning']}")
        if c["size"].get("lot_warning"):
            print(f"  WARN  {c['size']['lot_warning']}")
    else:
        s = c["stock"]
        print(f"\n  BUY   {c['name']} @ {s['entry']}   QTY {c['size']['qty']}")
    print()
    for label, rule in c["rules"]:
        print(f"  {label:<22} {rule}")
    print("=" * 66)
    print("  NOT financial advice. Decided before entry; follow it without renegotiating.")
    print("=" * 66 + "\n")


if __name__ == "__main__":
    import rrg_engine as E, rrg_strategy as S
    pts, prices, _ = E.demo_points()
    sel = S.select(pts, max_pos=3)
    if not sel["longs"]:
        print("  no candidates in the demo universe right now")
    for p in sel["longs"]:
        closes = prices[p["symbol"]]
        render(build_card(p, closes, expiry_label="26AUG"))
