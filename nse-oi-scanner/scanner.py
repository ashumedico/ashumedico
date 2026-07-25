"""
scanner.py  —  NSE F&O OI-Change Options Scanner (Fyers)  ·  v2 (hardened).

Fixes over v1:
  • OI-change is measured vs the DAY-OPEN baseline (real intraday buildup), not vs last poll.
  • Futures symbols (cash has no OI) — the universe now expects F&O instruments.
  • Market-hours guard (09:15-15:30 IST, Mon-Fri) unless --force.
  • Retries + backoff on API calls; token-expiry (auth error) detected -> tells you to re-login.
  • Every scan logged to scanner.log and appended to signals_YYYYMMDD.csv.
  • Optional Telegram alerts (see alerts.py / config).

    python fyers_auth.py            # each morning: token
    python scanner.py              # one scan
    python scanner.py --loop       # continuous
    python scanner.py --dry-run    # synthetic data, no Fyers/creds/market
    python scanner.py --force      # ignore market-hours guard

NOT financial advice. Signals are inputs; every trade decision is yours.
"""
import sys, os, json, time, csv, argparse, logging
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = SECRET_KEY = REDIRECT_URI = ""
        UNIVERSE = ["NSE:NIFTY25JULFUT", "NSE:RELIANCE25JULFUT", "NSE:HDFCBANK25JULFUT",
                    "NSE:INFY25JULFUT", "NSE:SBIN25JULFUT", "NSE:TATAMOTORS25JULFUT"]
        MIN_OI_CHANGE_PCT = 5.0; TOP_N = 15; POLL_SECONDS = 300
        TOKEN_FILE = "access_token.txt"; BASELINE_FILE = "oi_baseline.json"
        TELEGRAM_TOKEN = TELEGRAM_CHAT = ""
    config = _C()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.FileHandler("scanner.log"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("scanner")


# ---------- helpers ----------
def now_ist():
    return datetime.now(IST)

def is_market_open(t=None):
    t = t or now_ist()
    if t.weekday() >= 5:                      # Sat/Sun
        return False
    open_t = t.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = t.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= t <= close_t

def classify(price_chg, oi_chg):
    if oi_chg > 0:
        return "LONG BUILDUP" if price_chg >= 0 else "SHORT BUILDUP"
    return "SHORT COVERING" if price_chg >= 0 else "LONG UNWINDING"


# ---------- baseline (day-open OI reference) ----------
def load_baseline():
    if not os.path.exists(config.BASELINE_FILE):
        return None
    with open(config.BASELINE_FILE) as f:
        b = json.load(f)
    if b.get("date") != now_ist().strftime("%Y-%m-%d"):
        return None                          # stale -> new trading day
    return b["data"]

def save_baseline(data):
    with open(config.BASELINE_FILE, "w") as f:
        json.dump({"date": now_ist().strftime("%Y-%m-%d"), "data": data}, f, indent=2)


# ---------- data ----------
class AuthError(Exception):
    pass

def _with_retry(fn, tries=3, delay=1.5):
    last = None
    for i in range(tries):
        try:
            return fn()
        except AuthError:
            raise
        except Exception as e:                # noqa
            last = e
            log.warning(f"API call failed ({i+1}/{tries}): {e}")
            time.sleep(delay * (i + 1))
    raise last

def fetch_live():
    """LTP + OI for the universe via Fyers, with retry + auth detection."""
    from fyers_apiv3 import fyersModel
    if not os.path.exists(config.TOKEN_FILE):
        raise AuthError("No access token. Run:  python fyers_auth.py")
    token = open(config.TOKEN_FILE).read().strip()
    fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)

    out = {}
    for i in range(0, len(config.UNIVERSE), 50):
        chunk = config.UNIVERSE[i:i + 50]
        def call():
            r = fy.quotes({"symbols": ",".join(chunk)})
            if isinstance(r, dict) and r.get("s") == "error":
                msg = str(r.get("message", "")).lower()
                if "token" in msg or "auth" in msg or r.get("code") in (-16, -17, -8):
                    raise AuthError("Fyers token invalid/expired. Re-run: python fyers_auth.py")
                raise RuntimeError(r.get("message", r))
            return r
        r = _with_retry(call)
        for d in r.get("d", []):
            v = d.get("v", {})
            out[d.get("n")] = {"ltp": v.get("lp", 0), "oi": v.get("oi", 0)}
    if not any(x["oi"] for x in out.values()):
        log.warning("All OI values are 0 — are your UNIVERSE symbols FUTURES (not -EQ)?")
    return out

def fetch_dry():
    rnd = [(0.0, 0.0), (1.2, 8.0), (-0.9, 12.0), (2.1, -6.0), (-1.5, -9.0), (0.4, 3.0)]
    prev, curr = {}, {}
    for i, s in enumerate(config.UNIVERSE):
        bp, boi = 100 + i * 10, 100000 + i * 5000
        pc, oc = rnd[i % len(rnd)]
        prev[s] = {"ltp": bp, "oi": boi}
        curr[s] = {"ltp": round(bp * (1 + pc / 100), 2), "oi": int(boi * (1 + oc / 100))}
    return prev, curr


# ---------- scan ----------
def build_rows(baseline, curr, min_oi):
    rows = []
    for sym, now in curr.items():
        base = baseline.get(sym)
        if not base or not base.get("oi"):
            continue
        oi_chg = (now["oi"] - base["oi"]) / base["oi"] * 100
        px_chg = (now["ltp"] - base["ltp"]) / base["ltp"] * 100 if base["ltp"] else 0
        if abs(oi_chg) < min_oi:
            continue
        rows.append({"sym": sym.split(":")[-1], "px": round(px_chg, 2),
                     "oi": round(oi_chg, 2), "signal": classify(px_chg, oi_chg)})
    rows.sort(key=lambda r: abs(r["oi"]), reverse=True)
    return rows[:config.TOP_N]

def write_csv(rows):
    fn = f"signals_{now_ist().strftime('%Y%m%d')}.csv"
    new = not os.path.exists(fn)
    with open(fn, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "symbol", "price_pct", "oi_pct", "signal"])
        ts = now_ist().strftime("%H:%M:%S")
        for r in rows:
            w.writerow([ts, r["sym"], r["px"], r["oi"], r["signal"]])

def render(rows, dry):
    ts = now_ist().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  NSE F&O OI-CHANGE SCANNER  ·  {ts} IST  {'[DRY-RUN]' if dry else ''}")
    print("  " + "-" * 60)
    if not rows:
        print(f"  No names crossed the OI-change threshold (>= {config.MIN_OI_CHANGE_PCT}%).")
    else:
        print(f"  {'SYMBOL':<16}{'PRICE%':>8}{'OI%':>8}   SIGNAL")
        print("  " + "-" * 60)
        for r in rows:
            print(f"  {r['sym']:<16}{r['px']:>+7.1f}%{r['oi']:>+7.1f}%   {r['signal']}")
    print("  " + "-" * 60)

def scan(dry=False, min_oi=None):
    min_oi = config.MIN_OI_CHANGE_PCT if min_oi is None else min_oi
    if dry:
        baseline, curr = fetch_dry()
    else:
        curr = fetch_live()
        baseline = load_baseline()
        if baseline is None:                 # first scan of the day -> set the reference
            save_baseline(curr)
            log.info("Day-open OI baseline captured. Buildup measured from here on.")
            baseline = curr
    rows = build_rows(baseline, curr, min_oi)
    render(rows, dry)
    if not dry:
        write_csv(rows)
        try:
            from alerts import send_alerts
            send_alerts(rows, config)
        except Exception as e:               # noqa
            log.warning(f"Alert step skipped: {e}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore market-hours guard")
    args = ap.parse_args()

    try:
        if args.dry_run:
            scan(dry=True)
            return
        while True:
            if not args.force and not is_market_open():
                log.info("Market closed (09:15-15:30 IST, Mon-Fri). Waiting…")
            else:
                try:
                    scan(dry=False)
                except AuthError as e:
                    log.error(str(e))
                    if not args.loop:
                        sys.exit(1)
            if not args.loop:
                break
            time.sleep(config.POLL_SECONDS)
    except KeyboardInterrupt:
        log.info("Stopped by user. Bye.")


if __name__ == "__main__":
    main()
