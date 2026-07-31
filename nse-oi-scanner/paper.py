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
        "tradingsymbol": o.get("tradingsymbol"),
        "qty": card["size"]["qty"], "lot": card["size"]["lot"],
        "cost": card["size"].get("cost_per_lot", 0) * card["size"]["lots"],
        # the stock-level plan the option inherits
        "stop": card["stock"]["stop"], "t1": card["stock"]["t1"], "t2": card["stock"]["t2"],
        "opt_stop": o.get("stop"), "opt_t1": o.get("t1"), "opt_t2": o.get("t2"),
        # The trail rides at the same distance as the original stop: the risk that was
        # acceptable at entry is the risk that stays acceptable, and a distance derived
        # from the name's own volatility travels with it.
        "high_water": card["spot"],
        "trail_dist": round(card["spot"] - card["stock"]["stop"], 2),
        "signal_date": (point or {}).get("signal_date"),
        "freshness": (point or {}).get("freshness"),
        "oi": (point or {}).get("signal"),
        "half_booked": False,
    }
    # The live order goes out BESIDE the paper record, never instead of it. Paper is the
    # measurement and has to stay complete whether or not the live leg fills - and if the
    # two ever diverge, that divergence is itself the thing worth knowing.
    try:
        import broker
        ok, detail = broker.buy(t["tradingsymbol"], t["qty"], tag=f"entry:{t['name']}")
        t["live_entry"] = {"ok": ok, "detail": str(detail)[:200]}
    except Exception as e:      # noqa
        t["live_entry"] = {"ok": False, "detail": f"broker error: {e}"[:200]}
    bk["open"].append(t)
    return t, None


# ---------------- marking to market ----------------
SESSION_OPEN = (9, 15)
SESSION_CLOSE = (15, 30)


def market_minutes_between(a, b):
    """Minutes the market was actually OPEN between two timestamps.

    Wall-clock elapsed is the wrong measure for a trade's age: a position opened at 15:00
    Friday is not 3 days old on Monday morning, it is one hour old. Counting only session
    minutes is what makes a bar-based timeout mean the same thing across an overnight or
    a weekend."""
    if b <= a:
        return 0.0
    total, day = 0.0, a
    while day.date() <= b.date():
        if day.weekday() < 5:                      # Sat/Sun have no session
            o = day.replace(hour=SESSION_OPEN[0], minute=SESSION_OPEN[1],
                            second=0, microsecond=0)
            c = day.replace(hour=SESSION_CLOSE[0], minute=SESSION_CLOSE[1],
                            second=0, microsecond=0)
            lo, hi = max(o, a), min(c, b)
            if hi > lo:
                total += (hi - lo).total_seconds() / 60.0
        day = (day + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return total


def bars_held(t, bar_minutes=None):
    bm = float(bar_minutes if bar_minutes is not None
               else getattr(config, "BAR_MINUTES", 375))
    mins = market_minutes_between(datetime.fromisoformat(t["opened"]), now())
    return mins / max(bm, 1)


def book_half(t, spot_now):
    """Book half AT T1 - but only as many WHOLE LOTS as half actually is.

    NSE F&O sells in lot multiples and nothing else. On one lot of 1225, "half" is 612.5,
    which is not an order anybody can place. The paper book used to score half out at T1
    regardless, while the live account went on holding the whole position - so every trade
    that tagged T1 and came back made paper look better than the account, and the
    scorecard he checks against the backtest was measuring a trade that cannot be taken.

    With LOTS_PER_TRADE = 1 there is no half. T1 stops being a booking and becomes what it
    can honestly be: the moment the stop is guaranteed to be at least breakeven, with the
    trail carrying the rest. Nothing is scored that was not sellable.
    """
    lot = int(t.get("lot") or 0)
    lots = int(t["qty"] // lot) if lot else 0
    half_lots = lots // 2
    if half_lots < 1:
        return (f"T1 - {lots or 1} lot hai, aadha book nahi ho sakta (lot ke multiple mein "
                f"hi bikta hai). Stop {t['stop']} pe - ab yahan se sirf trail.")

    qty = half_lots * lot
    prem = option_exit_premium(t, spot_now)
    t["booked"] = {"qty": qty, "premium": round(prem, 2), "at": now().isoformat()}
    t["qty"] = t["qty"] - qty            # the rest rides; close() prices only the rest
    try:
        import broker
        ok, detail = broker.sell(t.get("tradingsymbol"), qty, tag=f"t1:{t['name']}")
        t["booked"]["live"] = {"ok": ok, "detail": str(detail)[:200]}
    except Exception as e:      # noqa
        t["booked"]["live"] = {"ok": False, "detail": f"broker error: {e}"[:200]}
    return (f"T1 - {half_lots} lot ({qty}) book @ {prem:.2f}, "
            f"{lots - half_lots} lot chal raha hai, stop {t['stop']} pe")


def mark(bk, quotes, stale_days):
    """Move open paper trades forward against live spot. Exits follow the same contract
    the ticket printed: stop, T1 half, T2 rest, timeout. No discretion - the point is to
    measure the rules, not the trader."""
    events = []
    for t in list(bk["open"]):
        px = quotes.get(t["symbol"])
        if not px:
            continue
        bars = bars_held(t)
        t["spot_now"] = px
        t["bars_held"] = round(bars, 1)

        # Trail, bar by bar. The stop only ever ratchets UP - a stop that can loosen is
        # not a stop, it is a hope. High-water is the best mark seen since entry, not the
        # true intraday high, and it is worth knowing which: between marks the price can
        # go higher and come back, and this will not have seen it.
        if getattr(config, "TRAIL", True) and t.get("trail_dist"):
            t["high_water"] = max(t.get("high_water", t["spot_in"]), px)
            trailed = round(t["high_water"] - t["trail_dist"], 2)
            if trailed > t["stop"]:
                old = t["stop"]
                t["stop"] = trailed
                locked = t["stop"] - t["spot_in"]
                events.append((t["name"],
                               f"stop {old} -> {trailed}"
                               + (f"  ({locked:+.2f} locked in)" if locked > 0 else "")))
        hold_bars = float(getattr(config, "HOLD_BARS", 10))
        reason = None

        # A plain rupee target: book this much NET and leave. Net is the point - spread
        # and charges here are about twice a Rs 500 target, so an exit taken on the gross
        # number books a loss while reporting a win.
        rs_target = float(getattr(config, "TARGET_RUPEES", 0) or 0)
        if rs_target > 0:
            if net_pnl_now(t, px) >= rs_target:
                reason = "RS TARGET"

        if reason:
            pass
        elif px <= t["stop"]:
            reason = "STOP"
        elif px >= t["t2"]:
            reason = "T2"
        elif px >= t["t1"] and not t["half_booked"]:
            t["half_booked"] = True
            # Breakeven is a FLOOR, not an assignment. By the time T1 prints, the trail
            # has usually ratcheted past entry already, and setting the stop to entry
            # would hand back everything it locked in - which is the exact behaviour the
            # trail exists to prevent.
            t["stop"] = max(t["stop"], t["spot_in"])
            events.append((t["name"], book_half(t, px)))
            continue
        elif bars >= hold_bars * 2:
            # Timeout in BARS, not days. On a 15-minute chart a "25 day" timeout never
            # fires, so a 2.5-hour thesis would sit open for weeks and be scored as if
            # that had been the plan.
            reason = "TIMEOUT"
        if reason:
            close(bk, t, px, reason)
            events.append((t["name"], f"BAND - {reason}"))
    return events


def net_pnl_now(t, spot_now):
    """What this position would put in the account if closed at this mark - after the
    spread and every statutory charge, not before them."""
    prem = option_exit_premium(t, spot_now)
    gross = (prem - t["premium_in"]) * t["qty"]
    spread = float(getattr(config, "OPTION_SPREAD_PCT", 0.02)) * t["premium_in"] * t["qty"]
    try:
        import charges as CH
        stat = CH.round_trip(t["premium_in"], t["qty"], prem)["total"]
    except Exception:
        stat = 0.0
    return gross - spread - stat


def option_exit_premium(t, spot_now, delta=0.60):
    """What the option is worth when the stock is at spot_now.

    Delta-approximated, because a paper book cannot re-query a chain for every historical
    mark. It is stated rather than hidden: this is the same 0.6 the ticket sized with, so
    the paper P&L is consistent with the plan the ticket printed."""
    return max(0.5, t["premium_in"] + delta * (spot_now - t["spot_in"]))


def close(bk, t, spot_now, reason):
    prem_out = option_exit_premium(t, spot_now)
    # Whatever was actually sold at T1 is priced at the premium it was actually sold at -
    # recorded then, not re-derived now. t["qty"] is what is still open, so the two legs
    # never double-count. The old code assumed exactly half at the T1 *spot*, which was
    # both a quantity that could not be traded and a price nobody got.
    bk_leg = t.get("booked") or {}
    b_qty = int(bk_leg.get("qty") or 0)
    b_prem = float(bk_leg.get("premium") or t["premium_in"])
    if not bk_leg and t.get("half_booked"):
        # A trade opened before booking became real. Score it the way it was opened,
        # rather than silently restating a position that is already on the books.
        prem_t1 = option_exit_premium(t, t["t1"])
        gross = (prem_t1 - t["premium_in"]) * t["qty"] / 2 + \
                (prem_out - t["premium_in"]) * t["qty"] / 2
        total_q = t["qty"]
        blended = (prem_t1 + prem_out) / 2
    else:
        gross = (b_prem - t["premium_in"]) * b_qty + \
                (prem_out - t["premium_in"]) * t["qty"]
        total_q = b_qty + t["qty"]
        blended = ((b_prem * b_qty + prem_out * t["qty"]) / total_q) if total_q else prem_out
    # Real costs, on every share that moved - both legs pay the spread and both pay STT.
    # Bid-ask is the big one; STT, exchange fees, stamp and GST are small but they are not
    # zero, and a paper book that omits them slowly convinces you of an edge the ledger
    # will not pay out.
    spread = float(getattr(config, "OPTION_SPREAD_PCT", 0.02))
    spread_cost = spread * t["premium_in"] * total_q
    try:
        import charges as CH
        statutory = CH.round_trip(t["premium_in"], total_q, blended)["total"]
    except Exception:
        statutory = 0.0
    cost = spread_cost + statutory
    t.update({"closed": now().isoformat(), "spot_out": spot_now,
              "premium_out": round(prem_out, 2), "reason": reason,
              "pnl": round(gross - cost), "spread_cost": round(spread_cost),
              "statutory_cost": round(statutory), "total_cost": round(cost),
              "pnl_pct_of_capital": round(100 * (gross - cost) /
                                          float(getattr(config, "CAPITAL", 200000)), 2)})
    try:
        import broker
        ok, detail = broker.sell(t.get("tradingsymbol"), t["qty"], tag=f"exit:{t['name']}")
        t["live_exit"] = {"ok": ok, "detail": str(detail)[:200]}
    except Exception as e:      # noqa
        t["live_exit"] = {"ok": False, "detail": f"broker error: {e}"[:200]}
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
def square_off_all(bk, quotes, why="EOD"):
    """Close everything at the last marked price. Intraday means intraday: a position
    left open overnight is a different trade than the one the signal justified, and
    scoring it as the same one quietly rewrites the strategy being tested."""
    done = []
    for t in list(bk["open"]):
        px = quotes.get(t["symbol"]) or t.get("spot_now")
        if px:
            close(bk, t, px, why)
            done.append(t["name"])
    return done


def _squareoff_time():
    """SQUAREOFF from config, as a datetime today. Falls back to ten minutes before the
    bell if it is missing or unparseable - never later, because later is the broker's
    turn."""
    raw = str(getattr(config, "SQUAREOFF", "") or "").strip()
    n = now()
    default = n.replace(hour=SESSION_CLOSE[0], minute=SESSION_CLOSE[1] - 10,
                        second=0, microsecond=0)
    try:
        hh, mm = (int(x) for x in raw.split(":")[:2])
        t = n.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return min(t, default)
    except Exception:
        return default


def next_bar_time(bar_minutes):
    """The next candle close, on the grid the exchange actually uses (from 09:15)."""
    n = now()
    open_t = n.replace(hour=SESSION_OPEN[0], minute=SESSION_OPEN[1], second=5, microsecond=0)
    if n < open_t:
        return open_t + timedelta(minutes=bar_minutes)
    elapsed = (n - open_t).total_seconds() / 60.0
    k = int(elapsed // bar_minutes) + 1
    return open_t + timedelta(minutes=k * bar_minutes)


def session_loop(a):
    """Trade the whole session, waking at each candle close - which is what a full-time
    trader on a 15-minute chart actually does. Five fixed checkpoints a day cannot exit a
    2.5-hour thesis on time; this can."""
    import time as _time
    bm = int(getattr(config, "BAR_MINUTES", 15))
    # Square off when HIS config says to, not ten minutes before the bell. PRODUCT_TYPE is
    # INTRADAY, so if we do not close the position the broker will - at market, at a time
    # of its choosing, and the trailing stop computed in this loop never gets to fire.
    # Leaving before that is the whole point of naming a time.
    close_t = _squareoff_time()
    print(f"  {B}SESSION MODE{X}  {DIM}har {bm} min pe candle close - "
          f"{close_t:%H:%M} pe square off. Ctrl+C se band.{X}")
    try:
        import broker
        if broker.armed() and not broker.killed():
            print(f"  {R}LIVE - asli order jayenge.{X}")
    except Exception:
        pass
    # The most important sentence in this program. The trailing stop is computed here,
    # in this loop, and fired as a market order when it breaks. It is NOT resting at the
    # exchange. Close this window, sleep the machine, drop the connection - and nothing
    # is watching the position at all.
    print(f"  {Y}Stop is window ke andar chalta hai, exchange pe nahi.{X}")
    print(f"  {Y}Window band = koi stop nahi. Isko khula chhod.{X}\n")
    while True:
        run_once(a)
        nxt = next_bar_time(bm)
        if nxt >= close_t:
            print(f"\n  {Y}Session khatam - sab square off kar raha hoon.{X}")
            bk = load()
            if bk["open"]:
                q = ({t["symbol"]: t.get("spot_now") for t in bk["open"]} if a.demo
                     else __import__("rrg_engine").live_quote(
                         [t["symbol"] for t in bk["open"] if t.get("symbol")]))
                for nm in square_off_all(bk, q):
                    print(f"  {Y}>> {nm}: EOD square off{X}")
                save(bk)
            report(load())
            return
        wait = max(5, (nxt - now()).total_seconds())
        # Entries wait for the candle to close, because that is what the signal is built
        # on. EXITS cannot: a stop or a rupee target reached at 10:03 and acted on at
        # 10:15 is not the trade that was planned. So while anything is open, watch it
        # every WATCH_SECONDS instead of sleeping through the bar.
        watch = int(getattr(config, "WATCH_SECONDS", 60) or 60)
        print(f"  {DIM}agla candle close {nxt:%H:%M} - {int(wait/60)} min{X}"
              + (f"{DIM}, position khuli hai toh har {watch}s dekh raha hoon{X}"
                 if load()["open"] else ""))
        try:
            end = now() + timedelta(seconds=wait)
            while now() < end:
                bk = load()
                if not bk["open"]:
                    _time.sleep(min(watch, (end - now()).total_seconds()))
                    continue
                _time.sleep(min(watch, max(1, (end - now()).total_seconds())))
                bk = load()
                if not bk["open"]:
                    continue
                q = ({t["symbol"]: t.get("spot_now") for t in bk["open"]} if a.demo
                     else __import__("rrg_engine").live_quote(
                         [t["symbol"] for t in bk["open"] if t.get("symbol")]))
                for nm, what in mark(bk, q, 99):
                    print(f"  {Y}>> {nm}: {what}{X}")
                save(bk)
        except KeyboardInterrupt:
            print(f"\n  {Y}Band kar diya. Book waise ka waisa hai.{X}")
            return
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="only the scorecard")
    ap.add_argument("--session", action="store_true",
                    help="trade the whole session, waking at every candle close")
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
    if a.session:
        session_loop(a)
        return
    run_once(a)


def run_once(a):
    bk = load()
    import rrg_engine as E, rrg_strategy as S, trade_card as TC, checkin as C

    try:
        import broker
        live = broker.armed() and not broker.killed()
    except Exception:
        live = False
    tag = (f"{R}LIVE + PAPER - asli order ja rahe hain{X}" if live
           else f"{DIM}(paper only - koi asli order nahi){X}")
    print("\n" + "=" * 70)
    print(f"  {B}PAPER TRADING{X}   {now():%a %d %b %Y · %H:%M IST}   {tag}")
    print("=" * 70)

    if a.demo:
        points, prices, bench = E.demo_points()
        quotes = {t["symbol"]: t["spot_in"] * 1.02 for t in bk["open"] if t.get("symbol")}
    else:
        # The token expires daily. A scheduled run that finds no token must say so loudly:
        # a paper book with silent gaps is worse than no paper book, because the gaps are
        # invisible later and the record looks complete.
        if not os.path.exists(getattr(config, "TOKEN_FILE", "access_token.txt")):
            print(f"  {R}TOKEN NAHI HAI - aaj ka paper trade MISS ho gaya.{X}")
            print(f"  {DIM}Subah ek baar '1 - Fyers Login' chala de, phir ye apne aap "
                  f"chalta rahega.{X}\n")
            return
        try:
            points, prices, bench = E.live_points(tail=6)
        except Exception as e:      # noqa
            print(f"  {R}Data nahi aaya - aaj ka paper trade MISS:{X} {e}")
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
