"""
selftest.py  —  before the engine trades, prove every link in the chain works.

A trading loop that starts on a stale token, an expired series or a wrong lot does not
crash. It runs, quietly, and produces confident nonsense until money is lost. This checks
each link once, out loud, and refuses to report a link it could not actually test.

    python selftest.py                # the full check
    python selftest.py --quiet        # exit code only (0 = go, 1 = don't)

Every line is one of:
    OK        tested, and it passed
    FAIL      tested, and it failed - the engine should not start
    SKIP      could not be tested from here, and is NOT being counted as passed

NOT financial advice.
"""
import sys
import time

G, R, Y, B, D, X = ("\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[90m", "\033[0m")

RESULTS = []


def line(label, status, detail=""):
    col = {"OK": G, "FAIL": R, "SKIP": Y}.get(status, D)
    RESULTS.append((label, status, detail))
    print(f"  {label:<18}{col}{status:<6}{X}{D}{detail}{X}", flush=True)


def check_config():
    try:
        import config
    except ImportError:
        line("Config", "FAIL", "config.py nahi hai - 'First-time setup' chala")
        return None
    missing = [k for k in ("CLIENT_ID", "SECRET_KEY", "RESOLUTION", "BAR_MINUTES")
               if not getattr(config, k, None)]
    if missing:
        line("Config", "FAIL", "missing: " + ", ".join(missing))
    else:
        bm = int(getattr(config, "BAR_MINUTES", 375))
        line("Config", "OK", f"{'INTRADAY' if bm < 375 else 'SWING'} {bm}min · "
                             f"capital Rs {float(getattr(config,'CAPITAL',0)):,.0f} · "
                             f"{int(getattr(config,'LOTS_PER_TRADE',1) or 1)} lot")
    return config


def check_token():
    import os
    try:
        import config
        tf = getattr(config, "TOKEN_FILE", "access_token.txt")
    except Exception:
        tf = "access_token.txt"
    if not os.path.exists(tf):
        line("Token", "FAIL", "koi token nahi - '1 - START DAY' chala")
        return False
    age_h = (time.time() - os.path.getmtime(tf)) / 3600.0
    # A Fyers token is a day token. Age alone does not prove it works, so this only
    # reports age; the live calls below are what actually test it.
    line("Token", "OK", f"file {age_h:.1f} hrs purani")
    return True


def check_universe():
    try:
        import fno_universe as U
        names = U.fno_stocks()
        fallback = len({str(x).split(":")[-1].replace("-EQ", "") for x in names}) == \
            len(set(U.FALLBACK))
        line("Universe", "OK" if not fallback else "SKIP",
             f"{len(names)} F&O naam" + (" (built-in list - live fetch nahi hua)"
                                         if fallback else ""))
        return names
    except Exception as e:      # noqa
        line("Universe", "FAIL", str(e)[:60])
        return []


def check_candles():
    try:
        import rrg_engine as E
        pts, prices, bench = E.live_points(tail=3)
        bars = getattr(E, "LAST_BARS", {}) or {}
        n = len(bench or [])
        if n < 40:
            line("Spot candles", "FAIL", f"sirf {n} bars aaye - history kam hai")
            return None
        ohlcv = sum(1 for v in bars.values() if v)
        line("Spot candles", "OK", f"{n} bars · {len(prices)} naam · "
                                   f"{ohlcv} pe poore OHLCV")
        if not ohlcv:
            line("Features", "SKIP", "OHLCV nahi - VWAP/RVOL/levels test nahi ho sakte")
        return (pts, prices, bench, bars)
    except Exception as e:      # noqa
        line("Spot candles", "FAIL", str(e)[:60])
        return None


def check_expiry():
    try:
        import option_chain as OC
        import trade_card as TC
        label, days, _ = OC.pick_expiry(TC.min_days_for_thesis())
        if not label:
            line("Expiry", "FAIL", "chain se koi expiry nahi mili")
            return None
        stat = "OK" if days >= TC.min_days_for_thesis() else "FAIL"
        line("Expiry", stat, f"{label} · {days} din baaki "
                             f"(chahiye {TC.min_days_for_thesis()})")
        return label
    except Exception as e:      # noqa
        line("Expiry", "FAIL", str(e)[:60])
        return None


def check_chain(names):
    """The one check that has caught real money bugs: strikes, and the lot the chain
    itself reports. A lot that implies a contract value outside the SEBI band is wrong
    even when every other number looks fine."""
    try:
        import option_chain as OC
        sym = None
        for n in (names or []):
            sym = n if str(n).startswith("NSE:") else f"NSE:{n}-EQ"
            break
        if not sym:
            line("Option chain", "SKIP", "universe khaali - test nahi kar sakta")
            return
        ch = OC.tradeable_chain(sym)
        rows = (ch or {}).get("rows") or []
        lot = (ch or {}).get("lot")
        spot = (ch or {}).get("spot")
        if not rows:
            line("Option chain", "FAIL", f"{sym} pe koi strike nahi")
            return
        line("Option chain", "OK", f"{sym.split(':')[-1]} · {len(rows)} strikes")
        if not lot:
            line("Lot size", "FAIL", "chain ne lot nahi diya - qty 0 ka ticket banega")
        else:
            cv = (spot or 0) * lot
            ok = 3_00_000 <= cv <= 20_00_000        # SEBI band, with slack either side
            line("Lot size", "OK" if ok else "FAIL",
                 f"{lot} × {spot} = Rs {cv:,.0f} contract"
                 + ("" if ok else "  << F&O contracts ~Rs 5-10 lakh hote hain"))
    except Exception as e:      # noqa
        line("Option chain", "FAIL", str(e)[:60])


def check_regime(loaded):
    if not loaded:
        line("Regime", "SKIP", "candles nahi aaye")
        return
    try:
        import market_regime as MR
        _, prices, bench, _ = loaded
        import rrg_engine as E
        reg = MR.Regime(prices, bench, dates=getattr(E, "LAST_DATES", None)).at(len(bench))
        line("Regime", "OK", f"{reg['state']} ({reg['passed']}/{reg['of']} checks)")
    except Exception as e:      # noqa
        line("Regime", "FAIL", str(e)[:60])


def check_broker():
    try:
        import broker
        if broker.killed():
            line("Kill switch", "FAIL", "STOP_TRADING.txt maujood hai - sab band hai")
            return
        armed = broker.armed()
        line("Live orders", "OK", "ARMED - asli order jayenge" if armed
             else "disarmed - sirf paper")
    except Exception as e:      # noqa
        line("Live orders", "SKIP", str(e)[:60])


def check_telegram():
    try:
        import config
        tok = getattr(config, "TELEGRAM_TOKEN", "")
        chat = getattr(config, "TELEGRAM_CHAT", "")
    except Exception:
        tok = chat = ""
    if not tok or not chat:
        line("Telegram", "SKIP", "configured nahi - phone pe alert nahi aayega")
        return
    try:
        import alerts
        ok = alerts.send("T-Bone self-test: engine start ho raha hai.")
        line("Telegram", "OK" if ok else "FAIL",
             "message chala gaya" if ok else "bheja nahi ja saka")
    except Exception as e:      # noqa
        line("Telegram", "FAIL", str(e)[:60])


def main(argv):
    quiet = "--quiet" in argv
    if quiet:
        import io
        sys.stdout = io.StringIO()

    print(f"\n  {B}STARTUP SELF-TEST{X}   {D}har link alag se check ho raha hai{X}")
    print("  " + "=" * 66)
    check_config()
    tok = check_token()
    names = check_universe()
    loaded = check_candles() if tok else None
    if not tok:
        line("Spot candles", "SKIP", "token ke bina kuch fetch nahi hota")
        line("Expiry", "SKIP", "token nahi")
        line("Option chain", "SKIP", "token nahi")
    else:
        check_expiry()
        check_chain(names)
    check_regime(loaded)
    check_broker()
    check_telegram()
    print("  " + "=" * 66)

    fails = [r for r in RESULTS if r[1] == "FAIL"]
    skips = [r for r in RESULTS if r[1] == "SKIP"]
    if fails:
        print(f"  {R}SELF-TEST FAIL{X} - {len(fails)} cheez toot rahi hai: "
              f"{', '.join(r[0] for r in fails)}")
        print(f"  {D}Engine start mat kar jab tak ye theek na ho.{X}\n")
    else:
        print(f"  {G}SELF-TEST PASS{X}"
              + (f"  {Y}({len(skips)} cheez test hi nahi ho payi: "
                 f"{', '.join(r[0] for r in skips)}){X}" if skips else ""))
        print(f"  {D}Skip ka matlab 'pass' nahi hai - wo check hua hi nahi.{X}\n")

    if quiet:
        out = sys.stdout.getvalue()
        sys.stdout = sys.__stdout__
        if fails:
            print(out)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
