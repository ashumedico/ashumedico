"""
option_chain.py  —  the piece the futures-only scanner was missing.

For any F&O underlying it pulls the Fyers option chain and computes what actually
moves derivatives:
  • PCR  (Put/Call OI ratio)          -> bias
  • Max Pain                          -> where writers want expiry to land
  • Support / Resistance              -> highest Put-OI / Call-OI strikes (the walls)
  • Call-writing / Put-writing        -> where fresh option OI is being sold
  • ATM +/- N strike-wise OI ladder

    python option_chain.py NSE:NIFTY50-INDEX          # live (needs token)
    python option_chain.py --dry-run                  # synthetic chain, no Fyers

NOT financial advice. Signals are inputs; the decision is yours.
"""
import sys, os, argparse
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = ""; TOKEN_FILE = "access_token.txt"; OC_STRIKES = 10
    config = _C()


LAST_EXPIRIES = []      # tradeable expiries from the most recent live chain
LAST_LOT = None         # real lot size from the most recent live chain
LAST_EPOCH = None       # expiry epoch the most recent chain actually belongs to


def expiries(min_days=0):
    """Tradeable expiries from the last live chain as (label, days_away, epoch),
    nearest first. Fyers hands back epochs; days-away is what a trade decision needs."""
    out, today = [], datetime.now(IST).date()
    for e in LAST_EXPIRIES or []:
        ep = e.get("expiry")
        try:
            d = datetime.fromtimestamp(int(ep), IST).date()
        except Exception:
            continue
        days = (d - today).days
        if days >= min_days:
            out.append((e.get("date") or d.strftime("%d%b").upper(), days, str(ep)))
    return sorted(out, key=lambda t: t[1])


def pick_expiry(min_days):
    """First expiry that outlasts the thesis. If none does, return the furthest one
    available and let the caller warn — silently buying a dying option is the bug."""
    ok = expiries(min_days)
    if ok:
        return ok[0]
    allx = expiries(-3650)
    return allx[-1] if allx else (None, None, None)


def analyse(chain, spot):
    """chain: list of {strike, type('CE'/'PE'), oi, ltp, oi_chg}. Returns metrics dict."""
    ce = {c["strike"]: c for c in chain if c["type"] == "CE"}
    pe = {c["strike"]: c for c in chain if c["type"] == "PE"}
    strikes = sorted(set(ce) | set(pe))
    tot_ce = sum(c["oi"] for c in ce.values())
    tot_pe = sum(c["oi"] for c in pe.values())
    pcr = round(tot_pe / tot_ce, 2) if tot_ce else 0

    # walls
    resistance = max(ce.values(), key=lambda c: c["oi"])["strike"] if ce else None
    support    = max(pe.values(), key=lambda c: c["oi"])["strike"] if pe else None

    # max pain: strike E minimising total intrinsic payout to option buyers
    def pain(E):
        p = 0
        for K in strikes:
            if K in ce: p += ce[K]["oi"] * max(0, E - K)
            if K in pe: p += pe[K]["oi"] * max(0, K - E)
        return p
    max_pain = min(strikes, key=pain) if strikes else None

    # writing: biggest positive OI change on the sell side
    call_writing = max((c for c in ce.values() if c.get("oi_chg", 0) > 0),
                       key=lambda c: c.get("oi_chg", 0), default=None)
    put_writing  = max((c for c in pe.values() if c.get("oi_chg", 0) > 0),
                       key=lambda c: c.get("oi_chg", 0), default=None)

    if pcr >= 1.2:   bias = "BULLISH (put writers in control)"
    elif pcr <= 0.7: bias = "BEARISH (call writers in control)"
    else:            bias = "NEUTRAL / range-bound"

    return {"spot": spot, "pcr": pcr, "max_pain": max_pain, "support": support,
            "resistance": resistance, "bias": bias,
            "tot_ce": tot_ce, "tot_pe": tot_pe,
            "call_writing": call_writing, "put_writing": put_writing,
            "ce": ce, "pe": pe, "strikes": strikes}


def fetch_live(symbol, timestamp=""):
    """timestamp: expiry epoch (from expiries()). Empty string = the nearest expiry,
    which is Fyers' default and is exactly the one you must NOT trade near expiry."""
    from fyers_apiv3 import fyersModel
    global LAST_EXPIRIES, LAST_LOT, LAST_EPOCH
    if not os.path.exists(config.TOKEN_FILE):
        raise RuntimeError("No token. Run: python fyers_auth.py")
    token = open(config.TOKEN_FILE).read().strip()
    fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)
    r = fy.optionchain({"symbol": symbol, "strikecount": getattr(config, "OC_STRIKES", 10),
                        "timestamp": str(timestamp or "")})
    if not isinstance(r, dict) or r.get("s") != "ok":
        raise RuntimeError(f"optionchain error: {r}")
    d = r["data"]
    spot = d.get("expiryData", [{}]) and d.get("underlyingValue") or 0
    # Fyers returns the tradeable expiries and the real lot size. Both matter: an option
    # expiring in days cannot carry a multi-week target, and a wrong lot makes the
    # quantity unbuyable.
    LAST_EXPIRIES = d.get("expiryData", []) or []
    LAST_EPOCH = str(timestamp) if timestamp else (
        str(LAST_EXPIRIES[0].get("expiry")) if LAST_EXPIRIES else None)
    for o in d.get("optionsChain", []):
        if o.get("option_type") in ("CE", "PE") and o.get("lot_size"):
            LAST_LOT = int(o["lot_size"]); break
    chain = []
    for o in d.get("optionsChain", []):
        ot = o.get("option_type")
        if ot not in ("CE", "PE"):
            continue
        chain.append({"strike": o.get("strike_price"), "type": ot,
                      "oi": o.get("oi", 0), "ltp": o.get("ltp", 0),
                      "oi_chg": o.get("oichng", 0)})
    return chain, spot or d.get("underlyingValue", 0)


def tradeable_chain(symbol, min_days):
    """The chain you can actually trade: the first expiry that outlasts `min_days`.

    Fyers' default chain is the NEAREST expiry. Run that in the last week of a series and
    every ticket quotes an option that dies before the target can print. So: read the
    expiry list, choose one with room, then re-fetch that series so the premium shown is
    the one he would really pay. Returns (chain, label, days_to_expiry, lot_size).
    """
    chain, _ = fetch_live(symbol)
    lbl, days, ep = pick_expiry(min_days)
    if ep and str(ep) != str(LAST_EPOCH):
        chain, _ = fetch_live(symbol, timestamp=ep)
    return chain, lbl, days, LAST_LOT


def fetch_dry(symbol="NSE:NIFTY50-INDEX", spot=24200):
    step = 100 if spot > 5000 else 50 if spot > 1000 else 10
    atm = round(spot / step) * step
    chain = []
    for i in range(-6, 7):
        K = atm + i * step
        # puts pile up below spot (support), calls above (resistance)
        ce_oi = max(2000, int(90000 * (1 - abs(i - 2) / 8)))
        pe_oi = max(2000, int(95000 * (1 - abs(i + 2) / 8)))
        chain.append({"strike": K, "type": "CE", "oi": ce_oi, "ltp": max(1, 200 - i * 30), "oi_chg": (i - 1) * 1500})
        chain.append({"strike": K, "type": "PE", "oi": pe_oi, "ltp": max(1, 200 + i * 30), "oi_chg": (-i + 1) * 1600})
    return chain, spot


def render(sym, m):
    print(f"\n  OPTION CHAIN  ·  {sym}   spot {m['spot']}")
    print("  " + "-" * 54)
    print(f"  PCR .............. {m['pcr']}   -> {m['bias']}")
    print(f"  Max Pain ......... {m['max_pain']}")
    print(f"  Support (Put wall) {m['support']}     Resistance (Call wall) {m['resistance']}")
    if m["call_writing"]:
        print(f"  Fresh CALL writing at {m['call_writing']['strike']}  (+{m['call_writing']['oi_chg']:,} OI)  -> resistance building")
    if m["put_writing"]:
        print(f"  Fresh PUT  writing at {m['put_writing']['strike']}  (+{m['put_writing']['oi_chg']:,} OI)  -> support building")
    print("  " + "-" * 54)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="NSE:NIFTY50-INDEX")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    chain, spot = fetch_dry(a.symbol) if a.dry_run else fetch_live(a.symbol)
    render(a.symbol + (" [DRY]" if a.dry_run else ""), analyse(chain, spot))


if __name__ == "__main__":
    main()
