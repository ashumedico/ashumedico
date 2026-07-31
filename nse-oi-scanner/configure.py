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
    "MAX_POSITIONS": (lambda v: str(int(v)),      "how many trades may be open at once"),
    "RESOLUTION":    (lambda v: repr(str(v)),     "candle the signal runs on ('D' or '15')"),
    "BAR_MINUTES":   (lambda v: str(int(v)),      "minutes in one bar (375 = one session)"),
}

# The bar size decides everything downstream - trend, volatility, stops, how long a
# "10 bar hold" actually is, and therefore which expiry is correct. Setting it in one
# place stops the two halves from disagreeing.
MODES = {
    "intraday": {"RESOLUTION": "15", "BAR_MINUTES": 15,  "HOLD_BARS": 10},
    "swing":    {"RESOLUTION": "D",  "BAR_MINUTES": 375, "HOLD_BARS": 10},
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
    backup = f"{CFG}.bak-{datetime.now():%Y%m%d-%H%M%S}"
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
    ap.add_argument("--mode", choices=sorted(MODES),
                    help="intraday (15-min bars) or swing (daily bars)")
    ap.add_argument("--bar-minutes", type=int, help="minutes per bar, if not using --mode")
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
