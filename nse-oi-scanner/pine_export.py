"""
pine_export.py  —  put TODAY'S names into the chart, instead of names someone picked once.

The screener shipped with twenty symbols chosen by hand. That is the wrong twenty: the
system scans the whole F&O list and surfaces a different handful every session, and a chart
showing a fixed list is showing yesterday's opinion no matter how good the gates are.

This takes the names the scan actually surfaced and writes them out three ways:

    tradingview/AashishScreener_live.pine   the screener with today's symbols filled in
    tradingview/watchlist.txt               a TradingView watchlist file to import
    stdout                                  the plain list, to copy

WHAT THIS IS AND IS NOT
It is a SNAPSHOT. The moment it is written it starts going stale, so the file carries the
timestamp it was made and the count it was made from. Re-run it to refresh. A chart quietly
showing a three-day-old list is worse than a chart showing twenty names you know are
arbitrary, because the first one looks current.

    python pine_export.py                 # top names that pass, both books
    python pine_export.py --top 20        # how many slots to fill (max 20)
    python pine_export.py --side long     # long book only
    python pine_export.py --all           # every scanned name, not just the passing ones

NOT financial advice.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
HERE = os.path.dirname(os.path.abspath(__file__))
TV = os.path.join(HERE, "tradingview")
TEMPLATE = os.path.join(TV, "AashishScreener.pine")
OUT_PINE = os.path.join(TV, "AashishScreener_live.pine")
OUT_LIST = os.path.join(TV, "watchlist.txt")
MAX_SLOTS = 20              # the template has 20; TradingView caps request.* at 40

G, R, Y, B, D, X = ("\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[90m", "\033[0m")


def tv_symbol(sym):
    """NSE:RELIANCE-EQ -> NSE:RELIANCE. TradingView does not use the -EQ suffix, and a
    symbol it cannot resolve makes request.security throw rather than skip."""
    s = str(sym or "")
    name = s.split(":")[-1].replace("-EQ", "")
    return f"NSE:{name}" if name else ""


def collect(side="both", top=MAX_SLOTS, everything=False):
    import rrg_engine as E
    import rrg_strategy as S

    # This function writes a TRADINGVIEW WATCHLIST - a file he opens and trades from. It
    # used to fall back to synthetic names when the token was missing, printing one yellow
    # line and then producing a watchlist indistinguishable from a real one. A warning on
    # a terminal that has already scrolled is not a safety mechanism; the artifact outlives
    # it. No token, no watchlist.
    import real_only as RO
    demo = not os.path.exists("access_token.txt")
    if demo and not RO.allowed():
        raise RO.Synthetic(
            f"no token, so these would be invented names in a watchlist you trade "
            f"from. Nothing written. {RO.FIX}")
    if demo:
        print(f"  {Y}[SYNTHETIC] test process - these names are not a scan.{X}")
        pts, prices, bench = E.demo_points()
    else:
        pts, prices, bench = E.live_points(tail=6)

    rule, params, _ = S.load_best()
    sel = S.select(pts, rule, params, max_pos=top, prices=prices)
    picks = []
    if everything:
        picks = [(p, "scan") for p in pts]
    else:
        if side in ("long", "both"):
            picks += [(p, "LONG") for p in sel.get("longs") or []]
        if side in ("short", "both"):
            picks += [(p, "SHORT") for p in sel.get("shorts") or []]

    seen, out = set(), []
    for p, sd in picks:
        t = tv_symbol(p.get("symbol"))
        if not t or t in seen:
            continue
        seen.add(t)
        out.append({"tv": t, "name": p.get("name"), "side": sd,
                    "close": p.get("close"), "pct": p.get("abs_pct")})
        if len(out) >= top:
            break
    return out, len(pts), demo


def write_pine(rows, demo):
    if not os.path.exists(TEMPLATE):
        return None, f"{os.path.basename(TEMPLATE)} nahi mila"
    src = open(TEMPLATE, encoding="utf-8").read()
    stamp = f"{datetime.now(IST):%d %b %Y %H:%M IST}"

    # Replace only the default inside each input.symbol("...", "N", ...). Everything else
    # in the file - gates, table, comments - is left byte for byte alone, so the exported
    # copy cannot drift from the template it came from.
    import re
    for i in range(1, MAX_SLOTS + 1):
        want = rows[i - 1]["tv"] if i <= len(rows) else ""
        src = re.sub(rf'(input\.symbol\(")[^"]*("\s*,\s*"{i}")',
                     lambda m: m.group(1) + want + m.group(2), src, count=1)

    filled = min(len(rows), MAX_SLOTS)
    header = (
        "// -----------------------------------------------------------------------------\n"
        f"//  GENERATED {stamp} by pine_export.py — {filled} name(s) from the live scan.\n"
        "//  This is a SNAPSHOT. It started going stale the moment it was written; re-run\n"
        "//  `python pine_export.py` (Tools -> Chart list) to refresh. A chart quietly\n"
        "//  showing a three-day-old list is worse than one you know is arbitrary,\n"
        "//  because the stale one looks current.\n"
        + ("//  *** DEMO DATA - no token was present. These are not real signals. ***\n"
           if demo else "")
        + "// -----------------------------------------------------------------------------\n")
    src = src.replace('indicator("Aashish Screener (F&O)", overlay = true)',
                      header + 'indicator("Aashish Screener LIVE", overlay = true)')
    os.makedirs(TV, exist_ok=True)
    open(OUT_PINE, "w", encoding="utf-8").write(src)
    return OUT_PINE, None


def write_list(rows, demo):
    stamp = f"{datetime.now(IST):%Y-%m-%d %H:%M IST}"
    lines = [f"###AASHISH {stamp}" + (" (DEMO)" if demo else "")]
    lines += [r["tv"] for r in rows]
    os.makedirs(TV, exist_ok=True)
    open(OUT_LIST, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return OUT_LIST


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=MAX_SLOTS)
    ap.add_argument("--side", default="both", choices=["long", "short", "both"])
    ap.add_argument("--all", action="store_true",
                    help="every scanned name, not just the ones that passed")
    a = ap.parse_args()
    top = max(1, min(a.top, MAX_SLOTS))

    os.chdir(HERE)
    try:
        rows, universe, demo = collect(a.side, top, a.all)
    except Exception as e:      # noqa
        print(f"\n  {R}Scan nahi chala: {e}{X}")
        print(f"  {D}Token chahiye - '1 - START DAY' chala, phir dobara.{X}\n")
        return 2

    print(f"\n  {B}CHART LIST{X}  {D}{universe} naam scan hue · "
          f"{'sab' if a.all else a.side} · top {top}{X}")
    print("  " + "=" * 58)
    if not rows:
        print(f"  {Y}Aaj koi naam pass nahi kar raha.{X}")
        print(f"  {D}Khaali list bhi ek jawab hai. Purani list chart pe chhod dena{X}")
        print(f"  {D}usse bura hai - wo aaj ka lagta hai.{X}")
        print(f"  {D}Sab naam chahiye toh:  python pine_export.py --all{X}\n")
        return 0

    for i, r in enumerate(rows, 1):
        side = (f"{G}LONG {X}" if r["side"] == "LONG"
                else f"{R}SHORT{X}" if r["side"] == "SHORT" else f"{D}scan {X}")
        print(f"  {i:>2}. {side} {r['tv']:<20}"
              f"{(r['close'] or 0):>10.2f}  {(r['pct'] or 0):+6.2f}%")
    print("  " + "=" * 58)

    pine, err = write_pine(rows, demo)
    if err:
        print(f"  {R}Pine nahi bana: {err}{X}")
    else:
        print(f"  Pine   -> {pine}")
    print(f"  List   -> {write_list(rows, demo)}")
    print(f"\n  {D}TradingView mein:{X}")
    print(f"  {D}  Pine    - AashishScreener_live.pine ka content copy -> Pine Editor "
          f"-> Add to chart{X}")
    print(f"  {D}  Charts  - watchlist.txt ko Watchlist -> Import karo, phir naamo pe "
          f"click karte ja{X}")
    print(f"\n  {Y}Ye SNAPSHOT hai.{X} {D}Naya scan chahiye toh dobara chala.{X}")
    print(f"  {D}Not financial advice.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
