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
    """Daily volatility in PRICE terms (a practical ATR proxy from closes)."""
    if len(closes) < n + 2:
        return closes[-1] * 0.02 if closes else 0.0
    rets = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - n, len(closes))]
    m = sum(rets) / len(rets)
    sd = (sum((r - m) ** 2 for r in rets) / len(rets)) ** 0.5
    return closes[-1] * sd


# ---------------- option selection ----------------
def strike_step(price):
    if price >= 20000: return 100
    if price >= 5000:  return 100
    if price >= 2000:  return 50
    if price >= 1000:  return 20
    if price >= 500:   return 10
    if price >= 100:   return 5
    return 2.5


def pick_strike(spot, direction, moneyness="ITM1"):
    """Slightly IN-the-money is the sweet spot for a swing: delta ~0.6 so it tracks the
    stock, and far less of the premium is pure time-decay than an OTM lottery ticket."""
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
    """Exact premium from a live Fyers chain, if we have one."""
    want = "CE" if direction == "BULLISH" else "PE"
    best = None
    for o in chain or []:
        if o.get("type") == want and o.get("strike") is not None:
            if best is None or abs(o["strike"] - strike) < abs(best["strike"] - strike):
                best = o
    if best and best.get("ltp"):
        return best["strike"], float(best["ltp"])
    return None, None


# ---------------- the card ----------------
def min_days_for_thesis(hold_bars=20):
    """A target that needs weeks cannot be bought on an option expiring in days.
    Require the expiry to outlast the intended hold with room to spare."""
    return int(hold_bars * 1.4) + 5


def build_card(point, closes, chain=None, expiry_label=None, days_to_expiry=25,
               instrument="OPTION", capital=None, risk_pct=None, lot=None):
    """point: an rrg_engine point dict. closes: that stock's close series."""
    capital = float(capital if capital is not None else getattr(config, "CAPITAL", 500000))
    risk_pct = float(risk_pct if risk_pct is not None else getattr(config, "RISK_PCT", 0.005))
    spot = float(point.get("close") or closes[-1])
    direction = "BULLISH"                      # RRG longs; short book is a separate mode
    vol = realised_vol(closes) or spot * 0.02

    # ---- stock-level structure: stop 2x daily vol, targets at 3x and 6x ----
    stop_px   = round(spot - 2.0 * vol, 2)
    t1_px     = round(spot + 3.0 * vol, 2)
    t2_px     = round(spot + 6.0 * vol, 2)
    risk_pts  = max(spot - stop_px, 1e-9)
    rr1 = round((t1_px - spot) / risk_pts, 2)
    rr2 = round((t2_px - spot) / risk_pts, 2)

    # ---- entry timing: chase or wait? ----
    # extended = already far above the fast mean -> waiting for a pullback beats chasing
    stretch = (spot - (sum(closes[-10:]) / 10)) / vol if len(closes) >= 10 else 0
    if point.get("abs_trend", 0) <= 0:
        action, entry_note = "SKIP", "own trend is not up — rotation alone is not enough"
        limit_px = None
    elif stretch > 2.2:
        action = "WAIT FOR PULLBACK"
        limit_px = round(spot - 0.8 * vol, 2)
        entry_note = f"extended {stretch:.1f}x vol above its 10-day mean — bid {limit_px}, don't chase"
    else:
        action = "BUY NOW"
        limit_px = round(spot * 1.002, 2)      # small buffer so a market-ish limit fills
        entry_note = f"in range ({stretch:+.1f}x vol from mean) — buy up to {limit_px}"

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
        "stock": {"entry": limit_px, "stop": stop_px, "t1": t1_px, "t2": t2_px,
                  "rr1": rr1, "rr2": rr2},
        "instrument": instrument,
        "rules": [],
    }

    # ---- the option leg ----
    if instrument == "OPTION":
        strike = pick_strike(spot, direction, "ITM1")
        ch_strike, ch_prem = option_from_chain(chain, strike, direction)
        if ch_strike:
            strike, premium = ch_strike, ch_prem
            prem_src = "live chain"
        else:
            premium = premium_estimate(spot, strike, direction, vol, days_to_expiry)
            prem_src = "estimated"
        # refuse an expiry too close to carry the trade
        need_days = min_days_for_thesis()
        expiry_warning = None
        if days_to_expiry < need_days:
            expiry_warning = (f"expiry only {days_to_expiry}d away but this thesis needs "
                              f"~{need_days}d - roll to the next series")
        delta = 0.60                            # slightly-ITM working assumption
        opt_stop = round(max(premium - delta * (spot - stop_px), premium * 0.55), 1)
        opt_t1   = round(premium + delta * (t1_px - spot), 1)
        opt_t2   = round(premium + delta * (t2_px - spot), 1)
        card["option"] = {
            "type": "CE" if direction == "BULLISH" else "PE",
            "strike": strike, "expiry": expiry_label or "current",
            "premium": premium, "premium_source": prem_src,
            "stop": opt_stop, "t1": opt_t1, "t2": opt_t2,
            "max_loss_per_unit": round(premium - opt_stop, 1),
            "days_to_expiry": days_to_expiry,
            "expiry_warning": expiry_warning,
        }
        risk_per_unit = max(premium - opt_stop, 1e-9)
    else:
        risk_per_unit = risk_pts

    # ---- size from risk, not from feelings ----
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
    lots = max(0, units // max(lot, 1))
    # Sanity-check the lot itself, two ways.
    # 1) Every NSE F&O contract is sized to roughly Rs 5-10 lakh of underlying. Far below
    #    that means the lot came from the wrong place and the quantity is fiction.
    # 2) If the live chain and the symbol master disagree, one of them is stale - a split
    #    revises the lot (COFORGE went 75 -> 375 on a 5:1). Trade the chain, but say so.
    contract_value = round(spot * lot)
    lot_warning = None
    if contract_value < 200000:
        lot_warning = (f"lot {lot} gives a contract value of only Rs {contract_value:,} - "
                       f"NSE F&O contracts are ~Rs 5-10 lakh, so verify the lot before you order")
    elif chain_lot and master_lot and chain_lot != master_lot:
        lot_warning = (f"lot mismatch: live chain says {chain_lot}, symbol master says "
                       f"{master_lot} - using {chain_lot}; a recent split may have revised it")
    card["size"] = {"risk_budget": round(budget), "lot": lot, "lots": lots,
                    "qty": lots * max(lot, 1),
                    "risk_per_unit": round(risk_per_unit, 2),
                    # if one lot already risks more than the budget, say so instead of
                    # quietly printing qty 0 or an un-tradeable number
                    "too_big": lots < 1,
                    "one_lot_risk": round(risk_per_unit * lot),
                    "contract_value": contract_value,
                    "lot_warning": lot_warning}

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
        ("TIME OUT",
         "if it hasn't cleared T1 in 10 sessions, close it — dead money is a cost"),
    ]
    if o:
        card["rules"].append(("EXPIRY RULE",
                             "square off 3 sessions before expiry, or roll to next series — "
                             "never hold a long option into the theta cliff"))
    return card


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
