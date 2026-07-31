"""
paper.py  —  paper trading, run daily, judged against what the backtest promised.

Paper results on their own are close to useless for weeks: twenty trades tell you almost
nothing, and a good run feels like proof while a bad one feels like failure. What makes
them worth keeping is the comparison. The backtest made a specific claim - this win rate,
this average trade. Paper trading is the experiment that claim has to survive. So every
report here puts the two side by side and says whether live is inside the range the
backtest would produce by chance.

It also trades the OPTION, not the stock. A paper book that records "the stock went up
0.8%" would flatter every result, because the account pays premium, spread and decay.

    python paper.py            # take today's signal, mark open trades, show the book
    python paper.py --report   # just the scorecard
    python paper.py --reset    # start the book over (asks first)

Nothing here places a real order. It writes to paper_trades.json only.

NOT financial advice.
"""
import os, json, math, argparse
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
BOOK = "paper_trades.json"

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 200000; RISK_PCT = 0.05; MAX_POSITIONS = 1
    config = _C()

G, R, Y, B, DIM, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[90m", "\033[0m"
if os.name == "nt" and not (os.environ.get("WT_SESSION") or os.environ.get("TERM")):
    G = R = Y = B = DIM = X = ""


def now():
    return datetime.now(IST)


def load():
    if os.path.exists(BOOK):
        try:
            with open(BOOK) as f:
                return json.load(f)
        except Exception:
            pass
    return {"open": [], "closed": [], "started": now().isoformat()}


def save(bk):
    with open(BOOK, "w") as f:
        json.dump(bk, f, indent=2)


# ---------------- taking a trade ----------------
def take(bk, card, point):
    """Record the ticket exactly as the check-in printed it - same size, same stop, same
    targets. A paper book that improves on the ticket is measuring a different strategy."""
    cap = int(getattr(config, "MAX_POSITIONS", 1) or 1)
    if len(bk["open"]) >= cap:
        return None, f"{len(bk['open'])}/{cap} slot bhare hain"
    if any(p["name"] == card["name"] for p in bk["open"]):
        return None, f"{card['name']} pehle se book mein hai"
    o = card.get("option") or {}
    if not o:
        return None, "option leg nahi bana"
    t = {
        "name": card["name"], "symbol": card.get("symbol"),
        "opened": now().isoformat(),
        "spot_in": card["spot"],
        "strike": o["strike"], "type": o["type"], "expiry": o.get("expiry"),
        "premium_in": o["premium"], "premium_source": o.get("premium_source"),
        "qty": card["size"]["qty"], "lot": card["size"]["lot"],
        "cost": card["size"].get("cost_per_lot", 0) * card["size"]["lots"],
        # the stock-level plan the option inherits
        "stop": card["stock"]["stop"], "t1": card["stock"]["t1"], "t2": card["stock"]["t2"],
        "opt_stop": o.get("stop"), "opt_t1": o.get("t1"), "opt_t2": o.get("t2"),
        "signal_date": (point or {}).get("signal_date"),
        "freshness": (point or {}).get("freshness"),
        "oi": (point or {}).get("signal"),
        "half_booked": False,
    }
    bk["open"].append(t)
    return t, None


# ---------------- marking to market ----------------
def mark(bk, quotes, stale_days):
    """Move open paper trades forward against live spot. Exits follow the same contract
    the ticket printed: stop, T1 half, T2 rest, timeout. No discretion - the point is to
    measure the rules, not the trader."""
    events = []
    for t in list(bk["open"]):
        px = quotes.get(t["symbol"])
        if not px:
            continue
        held = (now() - datetime.fromisoformat(t["opened"])).days
        t["spot_now"] = px
        reason = None
        if px <= t["stop"]:
            reason = "STOP"
        elif px >= t["t2"]:
            reason = "T2"
        elif px >= t["t1"] and not t["half_booked"]:
            t["half_booked"] = True
            t["stop"] = t["spot_in"]                      # rest rides at breakeven
            events.append((t["name"], "T1 - aadha book, stop breakeven pe"))
            continue
        elif held >= stale_days:
            reason = "TIMEOUT"
        if reason:
            close(bk, t, px, reason)
            events.append((t["name"], f"BAND - {reason}"))
    return events


def option_exit_premium(t, spot_now, delta=0.60):
    """What the option is worth when the stock is at spot_now.

    Delta-approximated, because a paper book cannot re-query a chain for every historical
    mark. It is stated rather than hidden: this is the same 0.6 the ticket sized with, so
    the paper P&L is consistent with the plan the ticket printed."""
    return max(0.5, t["premium_in"] + delta * (spot_now - t["spot_in"]))


def close(bk, t, spot_now, reason):
    prem_out = option_exit_premium(t, spot_now)
    # half booked at T1 means half the quantity left at the T1 premium
    if t.get("half_booked"):
        prem_t1 = option_exit_premium(t, t["t1"])
        gross = (prem_t1 - t["premium_in"]) * t["qty"] / 2 + \
                (prem_out - t["premium_in"]) * t["qty"] / 2
    else:
        gross = (prem_out - t["premium_in"]) * t["qty"]
    # Real costs, both halves. Bid-ask is the big one; STT, exchange fees, stamp and GST
    # are small but they are not zero, and a paper book that omits them slowly convinces
    # you of an edge the ledger will not pay out.
    spread = float(getattr(config, "OPTION_SPREAD_PCT", 0.02))
    spread_cost = spread * t["premium_in"] * t["qty"]
    try:
        import charges as CH
        statutory = CH.round_trip(t["premium_in"], t["qty"], prem_out)["total"]
    except Exception:
        statutory = 0.0
    cost = spread_cost + statutory
    t.update({"closed": now().isoformat(), "spot_out": spot_now,
              "premium_out": round(prem_out, 2), "reason": reason,
              "pnl": round(gross - cost), "spread_cost": round(spread_cost),
              "statutory_cost": round(statutory), "total_cost": round(cost),
              "pnl_pct_of_capital": round(100 * (gross - cost) /
                                          float(getattr(config, "CAPITAL", 200000)), 2)})
    bk["open"] = [p for p in bk["open"] if p is not t]
    bk["closed"].append(t)


# ---------------- the scorecard, against the backtest ----------------
def expectation():
    """What the validated setup claimed. Read from disk if a sweep has been saved."""
    for f in ("rrg_best_setup.json",):
        if os.path.exists(f):
            try:
                with open(f) as fh:
                    d = json.load(fh)
                r = d.get("result") or d
                if r.get("win_rate"):
                    return {"win_rate": r.get("win_rate"), "trades": r.get("trades"),
                            "source": f, "label": d.get("label") or d.get("rule")}
            except Exception:
                pass
    return None


def binomial_band(n, p):
    """Range of win counts a fair run of the backtest's win rate would produce ~95% of
    the time. Live results inside this band are not evidence of anything yet - which is
    the single most useful thing a small paper sample can tell you."""
    if not n:
        return None
    mean = n * p
    sd = math.sqrt(max(n * p * (1 - p), 1e-9))
    return max(0, mean - 2 * sd), min(n, mean + 2 * sd)


def report(bk):
    closed, open_ = bk.get("closed", []), bk.get("open", [])
    print(f"\n  {B}PAPER BOOK{X}   {DIM}shuru {bk.get('started','?')[:10]}{X}")
    print("  " + "=" * 68)
    if open_:
        print(f"  {B}KHULE ({len(open_)}){X}")
        for t in open_:
            live = t.get("spot_now")
            mv = (f"{(option_exit_premium(t, live) / t['premium_in'] - 1) * 100:+.0f}%"
                  if live else "?")
            print(f"    {t['name']:<12} {t['strike']:g}{t['type']} @ {t['premium_in']}"
                  f"   ab {mv}   {DIM}stop {t['stop']} | t1 {t['t1']}{X}")
        print()
    if not closed:
        print(f"  {DIM}Abhi tak koi trade band nahi hua. Roz chalata reh.{X}")
        print("  " + "=" * 68 + "\n")
        return
    wins = [t for t in closed if t["pnl"] > 0]
    pnl = sum(t["pnl"] for t in closed)
    cap = float(getattr(config, "CAPITAL", 200000))
    print(f"  {'NAAM':<12}{'IN':>9}{'OUT':>9}{'KYUN':>10}{'P&L':>12}")
    for t in closed[-12:]:
        col = G if t["pnl"] > 0 else R
        print(f"    {t['name']:<10}{t['premium_in']:>9.1f}{t['premium_out']:>9.1f}"
              f"{t['reason']:>10}{col}{t['pnl']:>+12,}{X}")
    print("  " + "-" * 68)
    wr = 100.0 * len(wins) / len(closed)
    col = G if pnl >= 0 else R
    print(f"  {len(closed)} trades   {len(wins)} jeete ({wr:.0f}%)   "
          f"kul {col}Rs {pnl:+,}{X} ({pnl/cap*100:+.1f}% capital)")

    exp = expectation()
    if exp and exp.get("win_rate"):
        band = binomial_band(len(closed), exp["win_rate"] / 100.0)
        lo, hi = band
        inside = lo <= len(wins) <= hi
        print("  " + "-" * 68)
        print(f"  {DIM}Backtest ne {exp['win_rate']}% win rate ka daava kiya tha"
              f" ({exp.get('label') or 'saved setup'}){X}")
        print(f"  {DIM}{len(closed)} trades pe wo {lo:.0f}-{hi:.0f} jeet deta"
              f" - tere paas {len(wins)} hain{X}")
        if inside:
            print(f"  {Y}Abhi tak sab normal range mein hai - na proof, na problem."
                  f" Chalate reh.{X}")
        elif len(wins) < lo:
            print(f"  {R}Backtest se neeche hai. Ek baar aur {max(10, len(closed))} "
                  f"trades dekh, phir setup pe shak karna banta hai.{X}")
        else:
            print(f"  {G}Backtest se upar - achha, par itne kam trades pe luck bhi "
                  f"aisa hi dikhta hai.{X}")
    else:
        print(f"  {DIM}Backtest ka result save nahi hai, toh comparison nahi ho sakta."
              f"\n  Icon '6 - Find Best Setup' chala ke rrg_best_setup.json banao.{X}")
    print("  " + "=" * 68 + "\n")


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="only the scorecard")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    bk = load()
    if a.reset:
        if input("  Poora paper book mita doon? (haan/nahi): ").strip().lower() in ("haan", "y", "yes"):
            save({"open": [], "closed": [], "started": now().isoformat()})
            print("  Book saaf. Aaj se naya.")
        return
    if a.report:
        report(bk)
        return

    import rrg_engine as E, rrg_strategy as S, trade_card as TC, checkin as C

    print("\n" + "=" * 70)
    print(f"  {B}PAPER TRADING{X}   {now():%a %d %b %Y · %H:%M IST}"
          f"   {DIM}(koi asli order nahi){X}")
    print("=" * 70)

    if a.demo:
        points, prices, bench = E.demo_points()
        quotes = {t["symbol"]: t["spot_in"] * 1.02 for t in bk["open"] if t.get("symbol")}
    else:
        try:
            points, prices, bench = E.live_points(tail=6)
        except Exception as e:      # noqa
            print(f"  {R}Data nahi aaya:{X} {e}")
            print(f"  {DIM}Token expire? icon '1 - Fyers Login' chala.{X}\n")
            return
        quotes = E.live_quote([t["symbol"] for t in bk["open"] if t.get("symbol")])

    # 1. move what is already open
    for name, what in mark(bk, quotes, C._stale_after()):
        print(f"  {Y}>> {name}: {what}{X}")

    # 2. take today's signal, if there is room
    rule, params, _ = S.load_best()
    sel = S.select(points, rule, params, max_pos=4)
    held = {t["name"] for t in bk["open"]}
    for cand in sel["longs"]:
        if cand["name"] in held:
            continue
        closes = prices.get(cand["symbol"]) or [cand["close"]]
        card = TC.build_card(cand, closes, expiry_label="paper",
                             days_to_expiry=TC.min_days_for_thesis())
        cost = card["size"].get("cost_per_lot", 0) * card["size"]["lots"]
        if cost > float(getattr(config, "CAPITAL", 200000)):
            continue
        t, why = take(bk, card, cand)
        if t:
            print(f"  {G}>> LIYA (paper): {t['name']} {t['strike']:g}{t['type']} "
                  f"@ {t['premium_in']}   qty {t['qty']}   Rs {t['cost']:,}{X}")
        else:
            print(f"  {DIM}naya nahi liya - {why}{X}")
        break
    else:
        print(f"  {DIM}Aaj koi setup pass nahi hua.{X}")

    save(bk)
    report(bk)


if __name__ == "__main__":
    main()
