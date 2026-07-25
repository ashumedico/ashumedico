"""
scanner.py  —  NSE F&O OI-Change Options Scanner (Fyers).
Equivalent of your old  run_scanner.bat.

Classifies each F&O underlying by the classic price + open-interest matrix:

    Price UP   + OI UP    = LONG BUILDUP        (bullish, fresh longs)
    Price DOWN + OI UP    = SHORT BUILDUP       (bearish, fresh shorts)
    Price UP   + OI DOWN  = SHORT COVERING      (bullish, shorts exiting)
    Price DOWN + OI DOWN  = LONG UNWINDING      (bearish, longs exiting)

Run:
    python fyers_auth.py          # once each morning (token)
    python scanner.py             # single scan
    python scanner.py --loop      # re-scan every POLL_SECONDS
    python scanner.py --dry-run   # synthetic data, no Fyers needed (test the flow)

NOT financial advice. Signals are inputs; every trade decision is yours.
"""
import sys, os, json, time, argparse

try:
    import config
except ImportError:
    class _C:  # dry-run fallback so the file runs without config.py
        UNIVERSE = ["NSE:NIFTY50-INDEX", "NSE:RELIANCE-EQ", "NSE:HDFCBANK-EQ",
                    "NSE:INFY-EQ", "NSE:SBIN-EQ", "NSE:TATAMOTORS-EQ"]
        MIN_OI_CHANGE_PCT = 5.0; TOP_N = 15; POLL_SECONDS = 300
        TOKEN_FILE = "access_token.txt"; SNAPSHOT_FILE = "oi_snapshot.json"
    config = _C()


def classify(price_chg, oi_chg):
    if oi_chg > 0:
        return "LONG BUILDUP" if price_chg > 0 else "SHORT BUILDUP"
    else:
        return "SHORT COVERING" if price_chg > 0 else "LONG UNWINDING"


def load_snapshot():
    if os.path.exists(config.SNAPSHOT_FILE):
        with open(config.SNAPSHOT_FILE) as f:
            return json.load(f)
    return {}


def save_snapshot(snap):
    with open(config.SNAPSHOT_FILE, "w") as f:
        json.dump(snap, f, indent=2)


def fetch_live():
    """Fetch LTP + OI for the universe via Fyers. Returns {symbol: {'ltp':x,'oi':y}}."""
    from fyers_apiv3 import fyersModel
    if not os.path.exists(config.TOKEN_FILE):
        sys.exit("!! No access token. Run:  python fyers_auth.py")
    token = open(config.TOKEN_FILE).read().strip()
    fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)
    out = {}
    # Fyers quotes accepts up to 50 symbols per call
    for i in range(0, len(config.UNIVERSE), 50):
        chunk = config.UNIVERSE[i:i + 50]
        resp = fy.quotes({"symbols": ",".join(chunk)})
        for d in resp.get("d", []):
            v = d.get("v", {})
            out[d.get("n")] = {"ltp": v.get("lp", 0), "oi": v.get("oi", 0)}
    return out


def fetch_dry():
    """Synthetic data so the pipeline runs with no Fyers/creds/market."""
    import random
    rnd = [(0.0, 0.0), (1.2, 8.0), (-0.9, 12.0), (2.1, -6.0), (-1.5, -9.0), (0.4, 3.0)]
    prev, curr = {}, {}
    for i, s in enumerate(config.UNIVERSE):
        base_p, base_oi = 100 + i * 10, 100000 + i * 5000
        pc, oc = rnd[i % len(rnd)]
        prev[s] = {"ltp": base_p, "oi": base_oi}
        curr[s] = {"ltp": round(base_p * (1 + pc / 100), 2),
                   "oi": int(base_oi * (1 + oc / 100))}
    return prev, curr


def scan(dry=False):
    if dry:
        prev, curr = fetch_dry()
    else:
        prev, curr = load_snapshot(), fetch_live()

    rows = []
    for sym, now in curr.items():
        old = prev.get(sym)
        if not old or not old.get("oi"):
            continue
        oi_chg = (now["oi"] - old["oi"]) / old["oi"] * 100
        px_chg = (now["ltp"] - old["ltp"]) / old["ltp"] * 100 if old["ltp"] else 0
        if abs(oi_chg) < config.MIN_OI_CHANGE_PCT:
            continue
        rows.append({"sym": sym.split(":")[-1], "px": px_chg, "oi": oi_chg,
                     "signal": classify(px_chg, oi_chg)})

    rows.sort(key=lambda r: abs(r["oi"]), reverse=True)
    rows = rows[:config.TOP_N]

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  NSE F&O OI-CHANGE SCANNER  ·  {ts}  {'[DRY-RUN]' if dry else ''}")
    print("  " + "-" * 58)
    if not rows:
        print("  No names crossed the OI-change threshold "
              f"(>= {config.MIN_OI_CHANGE_PCT}%).")
    else:
        print(f"  {'SYMBOL':<14}{'PRICE%':>8}{'OI%':>8}   SIGNAL")
        print("  " + "-" * 58)
        for r in rows:
            print(f"  {r['sym']:<14}{r['px']:>+7.1f}%{r['oi']:>+7.1f}%   {r['signal']}")
    print("  " + "-" * 58)

    if not dry:
        save_snapshot(curr)  # this scan becomes the baseline for the next
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="re-scan every POLL_SECONDS")
    ap.add_argument("--dry-run", action="store_true", help="synthetic data, no Fyers")
    args = ap.parse_args()

    if args.loop and not args.dry_run:
        while True:
            scan(dry=False)
            time.sleep(config.POLL_SECONDS)
    else:
        scan(dry=args.dry_run)


if __name__ == "__main__":
    main()
