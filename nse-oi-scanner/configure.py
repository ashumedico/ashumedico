"""
configure.py  —  change the trading settings without opening config.py by hand.

config.py holds credentials. Editing it by hand at 11pm to change one number is how a
client id gets mangled, so this rewrites ONLY the named settings, leaves every other line
byte-for-byte alone, and keeps a timestamped backup.

    python configure.py                          # show what is set now
    python configure.py --capital 50000          # the money actually in the account
    python configure.py --hold-days 10           # how long a trade is meant to run
    python configure.py --risk-pct 5             # percent of capital risked per trade

CAPITAL is the one that matters most: every quantity, every stop and every "can I afford
this" answer is computed from it. A default left at 5,00,000 on a 50,000 account sizes
every trade ten times too big.

NOT financial advice.
"""
import os, re, shutil, argparse
from datetime import datetime

CFG = "config.py"

# key -> (python literal formatter, human description)
KEYS = {
    "CAPITAL":       (lambda v: str(int(v)),      "money in the account (Rs)"),
    "RISK_PCT":      (lambda v: str(round(v, 4)), "fraction of capital risked per trade"),
    "HOLD_BARS":     (lambda v: str(int(v)),      "BARS a trade runs (bar size below)"),
    "MAX_POSITIONS":  (lambda v: str(int(v)),     "how many trades may be open at once"),
    "LOTS_PER_TRADE": (lambda v: str(int(v)),     "lots bought per trade (you buy 1)"),
    "RESOLUTION":    (lambda v: repr(str(v)),     "candle the signal runs on ('D' or '15')"),
    "BAR_MINUTES":   (lambda v: str(int(v)),      "minutes in one bar (375 = one session)"),
    "MIN_EXPIRY_DAYS": (lambda v: str(int(v)),    "expiry must have this many days left"),
    "LOT_SIZES":     (lambda v: str(v),           "pinned lot sizes that beat the parser"),
    "TARGET_RUPEES": (lambda v: str(int(v)),      "book and exit at this NET profit (0 = off)"),
    "WATCH_SECONDS": (lambda v: str(int(v)),      "how often to check stops while holding"),
    "PRICE_MIN":     (lambda v: str(int(v)),      "ignore names cheaper than this (0 = off)"),
    "PRICE_MAX":     (lambda v: str(int(v)),      "ignore names dearer than this (0 = off)"),
}

# Credentials. Same safe writer, different door: these are strings, they are never
# accepted as command-line arguments, and they never reach a log line.
CRED_KEYS = ("CLIENT_ID", "SECRET_KEY", "REDIRECT_URI", "TELEGRAM_TOKEN", "TELEGRAM_CHAT")


def write_credentials(values):
    """values: {KEY: 'string'}. Only CRED_KEYS are honoured; anything else is ignored."""
    updates = {k: repr(str(v)) for k, v in (values or {}).items()
               if k in CRED_KEYS and str(v).strip() != ""}
    return write(updates) if updates else True


def read_credentials():
    """What is set now, for pre-filling a form. Returns raw strings."""
    if not os.path.exists(CFG):
        return {}
    text = open(CFG).read()
    out = {}
    for k in CRED_KEYS:
        m = re.search(rf"^{k}\s*=\s*[\"']([^\"']*)[\"']", text, re.M)
        if m:
            out[k] = m.group(1)
    return out

# The bar size decides everything downstream - trend, volatility, stops, how long a
# "10 bar hold" actually is, and therefore which expiry is correct. Setting it in one
# place stops the two halves from disagreeing.
MODES = {
    "intraday": {"RESOLUTION": "15", "BAR_MINUTES": 15,  "HOLD_BARS": 10,
                 "MIN_EXPIRY_DAYS": 15},
    "swing":    {"RESOLUTION": "D",  "BAR_MINUTES": 375, "HOLD_BARS": 10,
                 "MIN_EXPIRY_DAYS": 30},
}


def read_current():
    if not os.path.exists(CFG):
        return {}
    text = open(CFG).read()
    out = {}
    for k in KEYS:
        m = re.search(rf"^{k}\s*=\s*([^\n#]+)", text, re.M)
        if m:
            out[k] = m.group(1).strip()
    return out


def write(updates):
    """Rewrite only the given keys. Anything not named here is untouched."""
    if not os.path.exists(CFG):
        print(f"  {CFG} not found. Run this from the scanner folder.")
        return False
    text = open(CFG).read()
    # Second-resolution names collide: the launcher writes credentials and settings back
    # to back, both land in the same second, and the second copy silently overwrites the
    # only record of what the file looked like before either. A backup that can be
    # overwritten by the very next write is not a backup.
    stamp = f"{CFG}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    backup, n = stamp, 1
    while os.path.exists(backup):
        backup = f"{stamp}-{n}"
        n += 1
    shutil.copy(CFG, backup)
    for k, val in updates.items():
        line = f"{k} = {val}"
        if re.search(rf"^{k}\s*=", text, re.M):
            text = re.sub(rf"^{k}\s*=[^\n]*", line, text, count=1, flags=re.M)
        else:
            text = text.rstrip("\n") + f"\n{line}\n"
    open(CFG, "w").write(text)
    print(f"  backup -> {backup}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, help="rupees actually in the account")
    ap.add_argument("--risk-pct", type=float, help="percent of capital risked per trade, e.g. 5")
    ap.add_argument("--hold-days", type=int, help="sessions a trade is meant to run")
    ap.add_argument("--max-positions", type=int,
                    help="how many trades may be open at once (1 = one at a time)")
    ap.add_argument("--lots-per-trade", type=int, help="lots per trade (you buy 1)")
    ap.add_argument("--mode", choices=sorted(MODES),
                    help="intraday (15-min bars) or swing (daily bars)")
    ap.add_argument("--bar-minutes", type=int, help="minutes per bar, if not using --mode")
    ap.add_argument("--min-expiry-days", type=int,
                    help="roll to next month when the running one has fewer days left")
    ap.add_argument("--set-lot", action="append", metavar="NAME=LOT",
                    help="pin a lot size permanently, e.g. --set-lot SONACOMS=1225")
    ap.add_argument("--target-rupees", type=int,
                    help="book and exit at this NET profit, e.g. 500 (0 = off)")
    ap.add_argument("--watch-seconds", type=int,
                    help="how often to check stops/targets while a position is open")
    ap.add_argument("--secret", action="store_true",
                    help="update SECRET_KEY (asks for it - never pass it on the command line)")
    a = ap.parse_args()

    updates = {}
    if a.mode:
        for k, v in MODES[a.mode].items():
            updates[k] = KEYS[k][0](v)
    if a.bar_minutes is not None:
        updates["BAR_MINUTES"] = KEYS["BAR_MINUTES"][0](a.bar_minutes)
    if a.capital is not None:
        updates["CAPITAL"] = KEYS["CAPITAL"][0](a.capital)
    if a.risk_pct is not None:
        updates["RISK_PCT"] = KEYS["RISK_PCT"][0](a.risk_pct / 100.0)
    if a.hold_days is not None:
        updates["HOLD_BARS"] = KEYS["HOLD_BARS"][0](a.hold_days)
    if a.max_positions is not None:
        updates["MAX_POSITIONS"] = KEYS["MAX_POSITIONS"][0](a.max_positions)
    if a.lots_per_trade is not None:
        updates["LOTS_PER_TRADE"] = KEYS["LOTS_PER_TRADE"][0](a.lots_per_trade)
    if a.min_expiry_days is not None:
        updates["MIN_EXPIRY_DAYS"] = KEYS["MIN_EXPIRY_DAYS"][0](a.min_expiry_days)
    if a.target_rupees is not None:
        updates["TARGET_RUPEES"] = KEYS["TARGET_RUPEES"][0](a.target_rupees)
    if a.watch_seconds is not None:
        updates["WATCH_SECONDS"] = KEYS["WATCH_SECONDS"][0](a.watch_seconds)

    # Secret is prompted, never taken as an argument: a command line ends up in shell
    # history, in scrollback, and in any screenshot of the window.
    if a.secret:
        val = input("  Naya SECRET_KEY paste kar: ").strip()
        if not val:
            print("  Kuch nahi likha - kuch nahi badla.")
            return
        if not write({"SECRET_KEY": repr(val)}):
            return
        print("  SECRET_KEY update ho gaya. Ab dobara login kar: python fyers_auth.py")
        return

    # A pinned lot beats anything parsed. The parser has been wrong twice, and this
    # number is checkable in seconds on NSE - so let it be stated once and stay stated.
    if a.set_lot:
        import ast
        cur_txt = open(CFG).read() if os.path.exists(CFG) else ""
        m = re.search(r"^LOT_SIZES\s*=\s*(\{.*?\})", cur_txt, re.M | re.S)
        d = {}
        if m:
            try:
                d = ast.literal_eval(m.group(1))
            except Exception:
                d = {}
        for pair in a.set_lot:
            if "=" in pair:
                k, v = pair.split("=", 1)
                d[k.strip().upper()] = int(v)
        updates["LOT_SIZES"] = repr(d)

    if updates and not write(updates):
        return

    cur = read_current()
    print("\n  CURRENT SETTINGS")
    print("  " + "-" * 52)
    for k, (_fmt, desc) in KEYS.items():
        val = cur.get(k, "(not set - using the built-in default)")
        print(f"  {k:<14} {val:<14} {desc}")
    # What these settings mean together, so a mismatched pair is visible immediately
    try:
        import trade_card as TC
        hb = float(cur.get("HOLD_BARS", 10))
        bm = float(cur.get("BAR_MINUTES", 375))
        hd = TC.hold_days(hb, bm)
        span = (f"{hd*375/60:.1f} ghante" if hd < 1 else f"{hd:.0f} trading din")
        print(f"\n  -> ek trade ka intended hold: {span}"
              f"   (expiry kam se kam {TC.min_days_for_thesis(hb, bm)} din door)")
    except Exception:
        pass
    cap = float(cur.get("CAPITAL", 0) or 0)
    risk = float(cur.get("RISK_PCT", 0) or 0)
    if cap and risk:
        print(f"  -> risk budget per trade: Rs {cap * risk:,.0f}")
        if cap * risk < 3000:
            print("     Note: most F&O option lots risk far more than this per lot, so"
                  "\n     nearly every card will come back as 'one lot is too big'."
                  "\n     On a small account the honest fix is a larger RISK_PCT, not a"
                  "\n     smaller lot - lots are fixed by the exchange.")
    print()


if __name__ == "__main__":
    main()
