"""
broker.py  —  places REAL orders in the Fyers account. Read this before arming it.

Aashish asked for live and paper to run together, and to skip the balance check because
he manages funding himself. That is his account and his call, so this does exactly that.
What it will not do is place an order it cannot describe afterwards.

Every order is written to orders.jsonl BEFORE it is sent and again with the broker's
reply, so a rejection, a partial fill or a wrong contract can be reconstructed from the
file rather than remembered. An order that is sent but not logged is an order nobody can
audit, and on a bad day that is the only record there is.

THREE THINGS STOP AN ORDER, and none of them are about balance:

  1. LIVE_TRADING must be True in config.py. Absent or False, this prints the order and
     places nothing. That is the default.
  2. STOP_TRADING.txt in this folder halts everything, instantly, no restart needed.
  3. The contract must come from the exchange's own chain. A symbol assembled by hand
     from strike and expiry is one character away from a different contract.

    python broker.py --status          # is live armed? is the kill switch on?
    python broker.py --arm             # turn LIVE_TRADING on (asks first)
    python broker.py --disarm

NOT financial advice. Live orders risk real money.
"""
import os, json, argparse
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
ORDER_LOG = "orders.jsonl"
KILL_FILE = "STOP_TRADING.txt"

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = ""; TOKEN_FILE = "access_token.txt"
    config = _C()


def now():
    return datetime.now(IST)


def killed():
    return os.path.exists(KILL_FILE)


def armed():
    return bool(getattr(config, "LIVE_TRADING", False))


def _log(rec):
    rec["at"] = now().isoformat()
    with open(ORDER_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _client():
    from fyers_apiv3 import fyersModel
    try:
        import rrg_engine
        rrg_engine._quiet_fyers()
    except Exception:
        pass
    token = open(config.TOKEN_FILE).read().strip()
    return fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)


def place(symbol, qty, side, kind="MARKET", limit_price=0.0, tag="", product=None):
    """Send one order. side: 'BUY' or 'SELL'.

    Returns (ok, detail). Never raises on a broker rejection - a rejection is information
    the caller has to act on, not an exception to unwind through.
    """
    product = product or getattr(config, "PRODUCT_TYPE", "MARGIN")
    req = {
        "symbol": symbol,
        "qty": int(qty),
        "type": 1 if kind == "LIMIT" else 2,        # 1 limit, 2 market
        "side": 1 if side == "BUY" else -1,
        "productType": product,                     # MARGIN carries; INTRADAY auto-squares
        "limitPrice": float(limit_price) if kind == "LIMIT" else 0.0,
        "stopPrice": 0.0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }

    if not symbol:
        _log({"event": "blocked", "why": "no tradeable symbol", "tag": tag})
        return False, "no tradeable symbol - the chain did not supply one"
    if killed():
        _log({"event": "blocked", "why": "kill switch", "req": req, "tag": tag})
        return False, f"{KILL_FILE} mojood hai - sab kuch ruka hua hai"
    if not armed():
        _log({"event": "dry", "req": req, "tag": tag})
        return False, "LIVE_TRADING off - order bheja nahi, sirf log kiya"

    _log({"event": "sending", "req": req, "tag": tag})
    try:
        r = _client().place_order(req)
    except Exception as e:      # noqa
        _log({"event": "error", "req": req, "error": str(e)[:300], "tag": tag})
        return False, f"order gaya hi nahi: {e}"
    _log({"event": "reply", "req": req, "reply": r, "tag": tag})
    ok = isinstance(r, dict) and r.get("s") == "ok"
    return ok, (r.get("id") if ok else str(r)[:300])


def buy(symbol, qty, limit_price=None, tag=""):
    return (place(symbol, qty, "BUY", "LIMIT", limit_price, tag) if limit_price
            else place(symbol, qty, "BUY", "MARKET", tag=tag))


def sell(symbol, qty, tag=""):
    """Exits go to market. A limit exit that does not fill is not an exit - it is a
    position you believe is closed and is not."""
    return place(symbol, qty, "SELL", "MARKET", tag=tag)


def find_contract(underlying, strike, opt_type="CE", month=None):
    """Resolve a spoken instruction - "SONACOMS 750 CE August" - to the exchange's own
    symbol, plus its live premium and lot.

    Nothing here is constructed. The symbol, the premium and the lot all come from the
    chain, because a hand-built symbol that is one character wrong is either a rejected
    order or a different contract, and both are discovered after the money moves.
    """
    import option_chain as oc
    sym = underlying if ":" in underlying else f"NSE:{underlying.upper()}-EQ"
    oc.fetch_live(sym)                                  # populates the expiry list
    exps = oc.expiries(0)
    if not exps:
        return None, "koi expiry nahi mili - naam sahi hai?"
    pick = exps[0]
    if month:
        # Accept how a person actually says it: AUG, August, aug, or 8.
        m = str(month).strip().upper()
        MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        if m.isdigit() and 1 <= int(m) <= 12:
            m = MONTHS[int(m) - 1]
        else:
            m = m[:3]
        match = [e for e in exps if m in e[0].upper()]
        if not match:
            have = ", ".join(f"{e[0]} ({e[1]}d)" for e in exps)
            return None, f"'{month}' expiry nahi mili. Available: {have}"
        pick = match[0]
    chain, _spot = oc.fetch_live(sym, timestamp=pick[2])
    want = [c for c in chain if c["type"] == opt_type.upper()]
    if not want:
        return None, f"chain mein koi {opt_type} nahi mila"
    hit = min(want, key=lambda c: abs((c["strike"] or 0) - float(strike)))
    if abs((hit["strike"] or 0) - float(strike)) > 0.01:
        near = ", ".join(str(c["strike"]) for c in sorted(
            want, key=lambda c: abs((c["strike"] or 0) - float(strike)))[:5])
        return None, f"strike {strike} chain mein nahi hai. Paas ke: {near}"
    return {"symbol": hit["symbol"], "strike": hit["strike"], "type": opt_type.upper(),
            "premium": hit["ltp"], "lot": oc.LAST_LOT,
            "expiry": pick[0], "days": pick[1]}, None


def order_interactive(underlying, strike, opt_type, month, lots, side):
    """Place one named order after showing exactly what it costs. The confirmation is not
    ceremony: the premium and the lot are the two numbers that have been wrong before, and
    this is the last point at which a wrong one is free to catch."""
    c, err = find_contract(underlying, strike, opt_type, month)
    if err:
        print(f"\n  {err}\n")
        return
    lot = int(c["lot"] or 0)
    qty = lot * int(lots)
    cost = (c["premium"] or 0) * qty
    print(f"\n  {'=' * 60}")
    print(f"  {side}  {c['symbol']}")
    print(f"  {'=' * 60}")
    print(f"  strike      {c['strike']:g} {c['type']}      expiry {c['expiry']} "
          f"({c['days']} din baaki)")
    print(f"  premium     {c['premium']}")
    print(f"  quantity    {qty}   ({lots} lot x {lot})")
    print(f"  LAGEGA      Rs {cost:,.0f}")
    cap = float(getattr(config, "CAPITAL", 0) or 0)
    if cap:
        print(f"  capital ka  {100 * cost / cap:.1f}%")
    try:
        import charges as CH
        d = CH.round_trip(c["premium"] or 0, qty)
        print(f"  charges     Rs {d['total']:,.0f} round trip ({d['pct_of_premium']*100:.2f}%)")
    except Exception:
        pass
    print(f"  {'=' * 60}")
    if not armed():
        print("  LIVE_TRADING off hai - ye order jayega nahi.")
        print("  Chalu karna ho:  python broker.py --arm\n")
        return
    if killed():
        print(f"  {KILL_FILE} mojood hai - sab kuch ruka hua hai.\n")
        return
    if input(f"  Bhej doon? 'HAAN' likh: ").strip() != "HAAN":
        print("  Nahi bheja.\n")
        return
    ok, detail = (buy(c["symbol"], qty, tag="manual") if side == "BUY"
                  else sell(c["symbol"], qty, tag="manual"))
    print(f"\n  {'[OK] order id ' + str(detail) if ok else '[X] ' + str(detail)}")
    print(f"  {ORDER_LOG} mein likh diya.\n")


def status():
    print(f"\n  LIVE TRADING : {'ARMED - real orders' if armed() else 'off (safe)'}")
    print(f"  KILL SWITCH  : {'ON - everything halted' if killed() else 'off'}")
    print(f"  PRODUCT      : {getattr(config, 'PRODUCT_TYPE', 'MARGIN')}"
          f"   {'(carries overnight)' if getattr(config, 'PRODUCT_TYPE', 'MARGIN') == 'MARGIN' else '(auto square-off 3:20)'}")
    print(f"  ORDER LOG    : {ORDER_LOG}"
          f" ({sum(1 for _ in open(ORDER_LOG)) if os.path.exists(ORDER_LOG) else 0} lines)")
    if armed() and not killed():
        print(f"\n  Real paise lag rahe hain. Rokna ho toh is folder mein "
              f"{KILL_FILE} bana de.")
    print()


def _set_live(on):
    import re, shutil
    if not os.path.exists("config.py"):
        print("  config.py nahi mila."); return
    shutil.copy("config.py", f"config.py.bak-{now():%Y%m%d-%H%M%S}")
    s = open("config.py").read()
    line = f"LIVE_TRADING = {'True' if on else 'False'}"
    s = (re.sub(r"^LIVE_TRADING\s*=.*$", line, s, count=1, flags=re.M)
         if re.search(r"^LIVE_TRADING\s*=", s, re.M) else s.rstrip("\n") + f"\n{line}\n")
    open("config.py", "w").write(s)
    print(f"  LIVE_TRADING = {on}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--arm", action="store_true")
    ap.add_argument("--disarm", action="store_true")
    ap.add_argument("--buy", metavar="NAME", help='underlying, e.g. SONACOMS')
    ap.add_argument("--sell", metavar="NAME")
    ap.add_argument("--strike", type=float)
    ap.add_argument("--type", default="CE", choices=["CE", "PE", "ce", "pe"])
    ap.add_argument("--month", help="expiry month, e.g. AUG (default: nearest)")
    ap.add_argument("--lots", type=int, default=1)
    a = ap.parse_args()

    if a.buy or a.sell:
        if a.strike is None:
            print("  --strike chahiye. Jaise:  --buy SONACOMS --strike 750 --month AUG")
            return
        order_interactive(a.buy or a.sell, a.strike, a.type, a.month, a.lots,
                          "BUY" if a.buy else "SELL")
        return
    if a.arm:
        print("\n  LIVE_TRADING on karne ja raha hoon. Iske baad system tere Fyers")
        print("  account mein ASLI order lagayega, apne aap, bina pooche.")
        if input("  Likh 'HAAN' agar samajh gaya: ").strip() != "HAAN":
            print("  Kuch nahi badla.\n"); return
        _set_live(True)
    elif a.disarm:
        _set_live(False)
    status()


if __name__ == "__main__":
    main()
