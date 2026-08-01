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


# Fyers order types. SL and SL_LIMIT are what make a stop REST AT THE EXCHANGE, which is
# a different animal from the trailing stop the session loop computes: that one lives in a
# running Python process and dies with the window. A resting SL-M survives a closed laptop,
# a dropped connection and a power cut. It cannot trail - the exchange has no opinion about
# your high-water mark - so the two are complements, not substitutes.
ORDER_TYPE = {"LIMIT": 1, "MARKET": 2, "SL": 3, "SL_LIMIT": 4}


def place(symbol, qty, side, kind="MARKET", limit_price=0.0, tag="", product=None,
          stop_price=0.0):
    """Send one order. side: 'BUY' or 'SELL'. kind: MARKET | LIMIT | SL | SL_LIMIT.

    Returns (ok, detail). Never raises on a broker rejection - a rejection is information
    the caller has to act on, not an exception to unwind through.
    """
    product = product or getattr(config, "PRODUCT_TYPE", "MARGIN")
    kind = str(kind).upper()
    if kind not in ORDER_TYPE:
        return False, f"unknown order kind {kind!r} - use {'/'.join(ORDER_TYPE)}"
    req = {
        "symbol": symbol,
        "qty": int(qty),
        "type": ORDER_TYPE[kind],
        "side": 1 if side == "BUY" else -1,
        "productType": product,                     # MARGIN carries; INTRADAY auto-squares
        "limitPrice": float(limit_price) if kind in ("LIMIT", "SL_LIMIT") else 0.0,
        "stopPrice": float(stop_price) if kind in ("SL", "SL_LIMIT") else 0.0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }
    # A stop order with no trigger is a market order wearing a disguise - it would fire
    # instantly and look like the stop had been hit.
    if kind in ("SL", "SL_LIMIT") and not req["stopPrice"]:
        return False, "stop order needs a trigger price - refusing to send it without one"

    if not symbol:
        _log({"event": "blocked", "why": "no tradeable symbol", "tag": tag})
        return False, "no tradeable symbol - the chain did not supply one"
    if killed():
        _log({"event": "blocked", "why": "kill switch", "req": req, "tag": tag})
        return False, f"{KILL_FILE} mojood hai - sab kuch ruka hua hai"
    if not armed():
        _log({"event": "dry", "req": req, "tag": tag})
        return False, "LIVE_TRADING off - order bheja nahi, sirf log kiya"

    # THE FOURTH GATE: the drawdown halt. DAY_DD, WEEK_DD and MAX_LOSS sat in config.py
    # from the beginning and were enforced nowhere - three settings that read like a
    # safety net and did nothing. They are checked here because this is the single point
    # every live order passes through; a limit enforced at the display layer is a limit
    # any other caller walks around.
    #
    # ENTRIES ONLY. A halt must never trap him inside a position: the point of standing
    # down is to be FLAT, and a rule that blocks the sell is not a risk limit, it is a
    # trap. So a BUY is gated and a SELL is not.
    if side == "BUY":
        try:
            import risk_limits as RL
            allowed, why = RL.gate()
        except Exception as e:      # noqa
            # The gate itself failing must not silently open it. Say so and refuse.
            allowed, why = False, f"risk limit check failed ({str(e)[:100]}) - refusing"
        if not allowed:
            _log({"event": "blocked", "why": "risk limit", "detail": why,
                  "req": req, "tag": tag})
            return False, f"RISK HALT - {why}"

    _log({"event": "sending", "req": req, "tag": tag})
    try:
        r = _client().place_order(req)
    except Exception as e:      # noqa
        _log({"event": "error", "req": req, "error": str(e)[:300], "tag": tag})
        return False, f"order gaya hi nahi: {e}"
    _log({"event": "reply", "req": req, "reply": r, "tag": tag})
    ok = isinstance(r, dict) and r.get("s") == "ok"
    return ok, (r.get("id") if ok else explain_rejection(r))


# Broker rejections arrive as a code and a sentence of API English. The ones that recur
# have a specific fix, and pairing them saves rediscovering it under time pressure.
REJECTIONS = {
    -50: ("IP whitelist",
          "Fyers app mein IP whitelisting on hai. myapi.fyers.in -> apni app edit kar ->\n"
          "     jo IP error mein likha hai wo whitelist mein daal. Ghar ka IP badalta\n"
          "     rehta hai, toh router restart ke baad dobara daalna pad sakta hai."),
    -15: ("token", "Token invalid ho gaya. Fyers app ki settings badalne se - jaise IP\n"
                   "     whitelist add karne se - purane token revoke ho jaate hain.\n"
                   "     '1 - Fyers Login' chala ke naya le le."),
    -392: ("market band", "Market band hai ya us contract mein trading nahi ho rahi."),
    -201: ("margin", "Broker ne margin ki wajah se roka - funds check kar."),
}

# Fyers reuses -99 for almost any order rejection, so the code alone is not the diagnosis.
# Mapping it to "token expired" told him to log in again when the account simply had no
# funds - a wrong explanation is worse than none, because it sends him somewhere useless.
# The message text is what actually distinguishes these.
BY_MESSAGE = [
    ("margin shortfall", "margin",
     "Account mein paisa nahi hai. Message mein likha hai kitna chahiye aur kitna hai.\n"
     "     Funds daal ke dobara chala."),
    ("insufficient", "margin", "Funds kam hain - message mein amount likha hai."),
    ("valid token", "token",
     "Token invalid. Fyers app ki settings badalne se purane token revoke ho jaate hain.\n"
     "     '1 - Fyers Login' chala."),
    ("whitelisted ip", "IP whitelist",
     "myapi.fyers.in -> app edit -> jo IP message mein hai wo whitelist mein daal."),
    ("market is closed", "market band", "Market band hai."),
    ("rms", "risk", "Broker ke RMS ne roka - message padh, wahi wajah likhi hai."),
]


def explain_rejection(r):
    """Turn the broker's reply into something actionable."""
    if not isinstance(r, dict):
        return str(r)[:300]
    code = r.get("code")
    msg = str(r.get("message") or r)[:250]
    low = msg.lower()
    # message first - it is specific where the code is not
    for needle, label, hint in BY_MESSAGE:
        if needle in low:
            return f"{msg}\n  -> [{label}] {hint}"
    hint = REJECTIONS.get(code)
    if hint:
        return f"{msg}\n  -> [{hint[0]}] {hint[1]}"
    return f"{msg}  (code {code})"


def buy(symbol, qty, limit_price=None, tag=""):
    return (place(symbol, qty, "BUY", "LIMIT", limit_price, tag) if limit_price
            else place(symbol, qty, "BUY", "MARKET", tag=tag))


def stop_loss(symbol, qty, trigger, tag="", limit_price=None):
    """A SELL stop that RESTS AT THE EXCHANGE for an already-open long option.

    This is the one protection that does not depend on this program still running. The
    session loop's trailing stop is better while the machine is on - it ratchets - and
    worthless the moment the window closes. Place both: the trail for the good case, this
    for the case where nobody is watching.

    SL-M by default. A limit price turns it into SL-L, which can go unfilled in a fast
    move - the thing a stop exists to survive.
    """
    kind = "SL_LIMIT" if limit_price else "SL"
    return place(symbol, qty, "SELL", kind=kind, stop_price=trigger,
                 limit_price=limit_price or 0.0, tag=tag or "stop")


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
    # A dead token, a wrong name, a closed market - the chain call fails in several
    # ordinary ways, and a Python traceback tells the trader none of them. Catch it and
    # say what happened.
    try:
        oc.fetch_live(sym)                              # populates the expiry list
    except Exception as e:      # noqa
        msg = str(e)
        for code, (label, hint) in REJECTIONS.items():
            if f"'code': {code}" in msg or f'"code": {code}' in msg:
                return None, f"[{label}] {hint}"
        return None, f"chain nahi mila: {msg[:200]}"
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
    # Lot, from the chain if it gave one, else the symbol master. Never zero: a ticket
    # showing quantity 0 reads as an answer and is not, and the next step after reading it
    # is arming live trading.
    lot, lot_src = oc.LAST_LOT, "chain"
    if not lot:
        lot = (getattr(config, "LOT_SIZES", {}) or {}).get(underlying.upper())
        lot_src = "config"
    if not lot:
        try:
            from fno_universe import lot_sizes
            lot = lot_sizes().get(underlying.upper())
            lot_src = "symbol master"
        except Exception:
            lot = None
    if not lot:
        return None, (f"{underlying} ka lot size kahin nahi mila - na chain mein, na "
                      f"master mein. Chain ke fields the: {', '.join(oc.LAST_FIELDS[:12])}."
                      f"\n  Bina lot ke quantity nikal hi nahi sakti. "
                      f"'10 - Lot Audit' chala ke master theek kar.")
    return {"symbol": hit["symbol"], "strike": hit["strike"], "type": opt_type.upper(),
            "premium": hit["ltp"], "lot": int(lot), "lot_source": lot_src,
            "spot": _spot, "expiry": pick[0], "days": pick[1]}, None


def order_interactive(underlying, strike, opt_type, month, lots, side, lot_override=None):
    """Place one named order after showing exactly what it costs. The confirmation is not
    ceremony: the premium and the lot are the two numbers that have been wrong before, and
    this is the last point at which a wrong one is free to catch."""
    c, err = find_contract(underlying, strike, opt_type, month)
    if err:
        print(f"\n  {err}\n")
        return
    # An explicit lot beats every guessed one. The symbol master has been wrong twice now
    # - 13 for COFORGE, 4595 for SONACOMS against a real 1225 - and the number is checkable
    # in ten seconds on NSE or in the broker's own order window.
    if lot_override:
        c["lot"], c["lot_source"] = int(lot_override), "tera diya hua"
    lot = int(c["lot"] or 0)
    qty = lot * int(lots)
    cost = (c["premium"] or 0) * qty
    if qty <= 0 or not c.get("premium"):
        print(f"\n  Quantity {qty}, premium {c.get('premium')} - ye ticket nahi hai.")
        print("  Kuch bhejne se pehle lot aur premium dono chahiye.\n")
        return
    print(f"\n  {'=' * 60}")
    print(f"  {side}  {c['symbol']}")
    print(f"  {'=' * 60}")
    print(f"  strike      {c['strike']:g} {c['type']}      expiry {c['expiry']} "
          f"({c['days']} din baaki)")
    print(f"  premium     {c['premium']}")
    print(f"  quantity    {qty}   ({lots} lot x {lot})"
          f"   [lot {c.get('lot_source', '?')} se]")
    print(f"  LAGEGA      Rs {cost:,.0f}")
    cap = float(getattr(config, "CAPITAL", 0) or 0)
    if cap:
        print(f"  capital ka  {100 * cost / cap:.1f}%")
    # The broker's own number, beside the one about to be spent. The exchange rejects on
    # margin, not on what config.py believes the capital to be, and finding that out from
    # a rejection wastes the entry.
    bal = available_balance()
    if bal is not None:
        short = cost - bal
        print(f"  account mein Rs {bal:,.0f}"
              + (f"   {'-' * 3} Rs {short:,.0f} kam pad sakta hai" if short > 0 else "   (kaafi hai)"))
    try:
        import charges as CH
        d = CH.round_trip(c["premium"] or 0, qty)
        print(f"  charges     Rs {d['total']:,.0f} round trip ({d['pct_of_premium']*100:.2f}%)")
    except Exception:
        pass
    # The same guard the ticket builder has, which this path was missing. SEBI sizes a
    # single-stock contract to Rs 5-10 lakh and a short-dated call costs a few percent of
    # it. A lot that puts the contract far outside that band is a parsing error, and it
    # arrives here as a plausible-looking rupee figure.
    spot = c.get("spot") or 0
    contract = spot * lot
    problems = []
    # Band is Rs 5-10 lakh at review; prices drift between six-monthly revisions, so the
    # check allows well outside it before complaining. Rs 34 lakh is not drift.
    if contract and not (200000 <= contract <= 2000000):
        problems.append(f"contract value Rs {contract:,.0f} (spot {spot:g} x lot {lot}) - "
                        f"NSE stock F&O contracts are Rs 5-10 lakh")
    if contract and cost > 0.20 * contract:
        problems.append(f"premium is {100*cost/contract:.0f}% of the contract - a real "
                        f"short-dated call is 3-5%")
    if cap and cost > 0.5 * cap:
        problems.append(f"one lot is {100*cost/cap:.0f}% of your capital")
    for w in problems:
        print(f"  !! {w}")
    if problems:
        print(f"  {'=' * 60}")
        print("  Ye numbers galat lag rahe hain. Bhejne se pehle Fyers app mein")
        print("  is contract ka lot khud dekh le - '10 - Lot Audit' bhi chala sakta hai.")
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


def public_ip():
    """The IP Fyers will see. Shown before an order is ever tried, because the whitelist
    has to contain this exact address and hunting for it belongs to the tool, not the
    trader. Home connections change it, so it is read fresh every time."""
    import urllib.request
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                ip = r.read().decode().strip()
                if ip and len(ip) < 40:
                    return ip
        except Exception:
            continue
    return None


def funds():
    """What the account actually has. Read from the broker, not assumed.

    Fyers returns a list of limits with numeric ids and titles; the titles are what the
    broker itself calls them, so they are printed as given rather than renamed here.
    Anything unrecognised is shown raw - a funds display that quietly drops a row is
    worse than one that shows a row you have to read.
    """
    try:
        r = _client().funds()
    except Exception as e:      # noqa
        return None, f"funds nahi mile: {e}"
    if not isinstance(r, dict) or r.get("s") != "ok":
        return None, explain_rejection(r if isinstance(r, dict) else {"message": str(r)})
    rows = r.get("fund_limit") or []
    out = []
    for f in rows:
        title = str(f.get("title") or f.get("id") or "?")
        val = f.get("equityAmount", f.get("equity_amount", f.get("balance")))
        if val is None:
            val = f.get("commodityAmount", 0)
        try:
            out.append((title, float(val)))
        except Exception:
            out.append((title, 0.0))
    return out, None


def available_balance():
    rows, err = funds()
    if err or not rows:
        return None
    for title, val in rows:
        if "available" in title.lower():
            return val
    return rows[0][1] if rows else None


def status():
    ip = public_ip()
    print(f"\n  TERA IP      : {ip or 'pata nahi chala (internet?)'}"
          f"{'   <- yahi Fyers whitelist mein daalna hai' if ip else ''}")
    print(f"  LIVE TRADING : {'ARMED - real orders' if armed() else 'off (safe)'}")
    print(f"  KILL SWITCH  : {'ON - everything halted' if killed() else 'off'}")
    print(f"  PRODUCT      : {getattr(config, 'PRODUCT_TYPE', 'MARGIN')}"
          f"   {'(carries overnight)' if getattr(config, 'PRODUCT_TYPE', 'MARGIN') == 'MARGIN' else '(auto square-off 3:20)'}")
    print(f"  ORDER LOG    : {ORDER_LOG}"
          f" ({sum(1 for _ in open(ORDER_LOG)) if os.path.exists(ORDER_LOG) else 0} lines)")
    if armed() and not killed():
        print(f"\n  Real paise lag rahe hain. Rokna ho toh is folder mein "
              f"{KILL_FILE} bana de.")
    print()


def _reload_config():
    """Re-read config.py after writing it.

    The module is already in memory, so a freshly written LIVE_TRADING is invisible until
    it is reloaded - which had --arm print "LIVE_TRADING = True" and then, one line later,
    "LIVE TRADING : off (safe)". A status display that can disagree with the file it just
    wrote is worse than none: it can also claim off while armed."""
    global config
    try:
        import importlib
        config = importlib.reload(config)
    except Exception:
        pass


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
    _reload_config()
    print(f"  config.py mein likha: LIVE_TRADING = {on}")
    print(f"  dobara padh ke confirm: armed() = {armed()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--arm", action="store_true")
    ap.add_argument("--disarm", action="store_true")
    ap.add_argument("--funds", action="store_true", help="account mein kitna paisa hai")
    ap.add_argument("--buy", metavar="NAME", help='underlying, e.g. SONACOMS')
    ap.add_argument("--sell", metavar="NAME")
    ap.add_argument("--strike", type=float)
    ap.add_argument("--type", default="CE", choices=["CE", "PE", "ce", "pe"])
    ap.add_argument("--month", help="expiry month, e.g. AUG (default: nearest)")
    ap.add_argument("--lots", type=int, default=1)
    ap.add_argument("--lot", type=int,
                    help="override the lot size for this order (see it on NSE/Zerodha)")
    a = ap.parse_args()

    if a.funds:
        rows, err = funds()
        if err:
            print(f"\n  {err}\n")
            return
        print("\n  FUNDS")
        print("  " + "-" * 46)
        for title, val in rows:
            mark = "  <-- yahi trade ke liye hai" if "available" in title.lower() else ""
            print(f"  {title:<30} Rs {val:>10,.2f}{mark}")
        print("  " + "-" * 46 + "\n")
        return

    if a.buy or a.sell:
        if a.strike is None:
            print("  --strike chahiye. Jaise:  --buy SONACOMS --strike 750 --month AUG")
            return
        order_interactive(a.buy or a.sell, a.strike, a.type, a.month, a.lots,
                          "BUY" if a.buy else "SELL", lot_override=a.lot)
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
