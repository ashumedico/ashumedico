"""
checkin.py  —  the ONE command. Run it whenever you sit down, then leave.

Aashish's actual workflow: show up, look at the terminal, buy, take profit, leave, come
back days later. No dashboard, no scrolling, no hunting. So this answers only the three
questions that matter, in order, and then gets out of the way:

    1. WHAT DO I DO WITH WHAT I ALREADY HOLD?   book / hold / get out
    2. IS THERE A NEW TRADE TODAY?              the exact ticket, or nothing
    3. ANYTHING ELSE?                           usually no - go home

State lives in positions.json, so leaving and returning a week later still works: the
next check-in remembers what you bought and grades it against live prices.

    python checkin.py                 # the check-in
    python checkin.py --buy           # record that you took today's suggested trade
    python checkin.py --sold HAVELLS  # record that you exited (asks for the price)
    python checkin.py --demo          # try it with synthetic data

NOT financial advice. Signals are inputs; the trade is yours.
"""
import os, json, argparse
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
BOOK = "positions.json"

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 500000; RISK_PCT = 0.005
    config = _C()

G, R, Y, B, DIM, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[90m", "\033[0m"


def _supports_colour():
    return os.environ.get("TERM") or os.name != "nt" or os.environ.get("WT_SESSION")


if not _supports_colour():
    G = R = Y = B = DIM = X = ""





def now():
    return datetime.now(IST)


def _cache_ready():
    """Is today's universe already on disk? Decides whether to warn about a slow pull."""
    import glob
    day = datetime.now(IST).strftime("%Y%m%d")
    return bool(glob.glob(os.path.join("cache", f"hist2_D_*_{day}.json")))


def _progress(i, n):
    bar = "#" * int(24 * i / n)
    print(f"  {DIM}[{bar:<24}] {i}/{n}{X}", end="\r", flush=True)


# ---------------- position book ----------------
def load():
    if os.path.exists(BOOK):
        try:
            with open(BOOK) as f:
                return json.load(f)
        except Exception:
            pass
    return {"open": [], "closed": []}


def save(bk):
    with open(BOOK, "w") as f:
        json.dump(bk, f, indent=2)


def _pct(a, b):
    return (a / b - 1) * 100 if b else 0.0


# ---------------- the three questions ----------------
def review_open(bk, quotes):
    """Question 1: what to do with what he already holds."""
    if not bk["open"]:
        print(f"  {DIM}Koi position nahi hai. Saaf slate.{X}\n")
        return []
    print(f"  {B}TERE PAAS ABHI ({len(bk['open'])}){X}")
    print("  " + "-" * 66)
    actions = []
    for p in bk["open"]:
        ltp = quotes.get(p["symbol"])
        held_days = (now() - datetime.fromisoformat(p["bought_on"])).days
        line = f"  {p['name']}"
        if p.get("option"):
            line += f" {p['option']['strike']:g}{p['option']['type']}"
        line += f"   liya {p['bought_on'][:10]} @ {p['entry']}"
        print(line)

        if ltp is None:
            print(f"    {DIM}live price nahi mila (market band?) - agli baar dekh{X}\n")
            continue

        chg = _pct(ltp, p["entry"])
        col = G if chg >= 0 else R
        print(f"    ab {ltp:,.2f}   {col}{chg:+.1f}%{X}   ({held_days} din)")

        # the decision, in plain words
        if p.get("t2") and ltp >= p["t2"]:
            verdict, why = f"{G}>> POORA BOOK KAR{X}", f"T2 {p['t2']} touch ho gaya - target complete"
            actions.append(("SELL ALL", p, ltp))
        elif p.get("t1") and ltp >= p["t1"] and not p.get("half_booked"):
            verdict, why = f"{G}>> AADHA BOOK KAR{X}", (f"T1 {p['t1']} hit - aadha nikaal, "
                                                        f"baaki ka stop breakeven ({p['entry']}) pe la")
            actions.append(("SELL HALF", p, ltp))
        elif p.get("stop") and ltp <= p["stop"]:
            verdict, why = f"{R}>> NIKAL JA{X}", f"stop {p['stop']} toot gaya - thesis galat, average mat kar"
            actions.append(("SELL ALL", p, ltp))
        elif held_days >= 25:
            verdict, why = f"{Y}>> BAND KAR{X}", f"{held_days} din ho gaye, kuch nahi hua - dead money"
            actions.append(("SELL ALL", p, ltp))
        else:
            nxt = p.get("t1") if not p.get("half_booked") else p.get("t2")
            verdict = f"  {DIM}HOLD{X}"
            why = f"stop {p.get('stop')} | agla target {nxt}"
        print(f"    {verdict}   {DIM}{why}{X}\n")
    return actions


def show_new(card, chk, point):
    """Question 2: is there a new trade, and can he act on it right now."""
    print(f"  {B}AAJ KA NAYA TRADE{X}")
    print("  " + "-" * 66)
    if not card:
        print(f"  {DIM}Aaj kuch nahi. Koi naam setup pass nahi kar raha.{X}")
        print(f"  {DIM}Na lena bhi ek position hai - ghar ja.{X}\n")
        return
    o = card.get("option") or {}
    state = chk.get("state") if chk else None

    if state == "ENTER NOW":
        head = f"{G}>> ABHI LE LE{X}"
    elif state == "WAIT":
        head = f"{Y}>> ABHI NAHI - limit lagao{X}"
    elif state in ("SKIP", "MISSED"):
        head = f"{R}>> CHHOD DE{X}"
    else:
        head = f"{B}>> {card['action']}{X}"

    print(f"  {head}   {card['name']}")
    if o:
        print(f"    KHAREED : {card['name']} {o['strike']:g} {o['type']} ({o['expiry']})"
              f"   premium ~{o['premium']}  {DIM}[{o['premium_source']}]{X}")
    print(f"    QTY     : {card['size']['qty']}  "
          f"({card['size']['lots']} lot x {card['size']['lot']})")
    print(f"    LIMIT   : {card['stock']['entry']}")
    print(f"    STOP    : {R}{card['stock']['stop']}{X}"
          + (f"   (premium {o['stop']})" if o else ""))
    print(f"    T1      : {G}{card['stock']['t1']}{X}  aadha book"
          + (f"   (premium {o['t1']})" if o else ""))
    print(f"    T2      : {G}{card['stock']['t2']}{X}  baaki book"
          + (f"   (premium {o['t2']})" if o else ""))
    fresh = point.get("freshness") if point else None
    if fresh:
        print(f"    SIGNAL  : {fresh} - {point.get('signal_date')} "
              f"({point.get('age_bars')} session purana)")
    if chk:
        print(f"    {DIM}{chk['line']}{X}")
    print(f"\n    {DIM}Le liya? phir chala:  python checkin.py --buy{X}\n")


# ---------------- record actions ----------------
def record_buy(card, point):
    bk = load()
    if any(p["name"] == card["name"] for p in bk["open"]):
        print(f"  {Y}{card['name']} pehle se book mein hai.{X}")
        return
    o = card.get("option") or {}
    bk["open"].append({
        "name": card["name"], "symbol": card.get("symbol"),
        "bought_on": now().isoformat(), "entry": card["stock"]["entry"],
        "stop": card["stock"]["stop"], "t1": card["stock"]["t1"], "t2": card["stock"]["t2"],
        "qty": card["size"]["qty"], "half_booked": False,
        "option": ({"strike": o["strike"], "type": o["type"], "premium": o["premium"]}
                   if o else None),
        "signal_date": (point or {}).get("signal_date"),
    })
    save(bk)
    print(f"  {G}[OK]{X} {card['name']} book mein daal diya. "
          f"Agli baar check-in pe iska status dikhega.")


def record_sell(name, price=None, half=False):
    bk = load()
    hit = next((p for p in bk["open"] if p["name"].upper() == name.upper()), None)
    if not hit:
        print(f"  {R}{name} book mein nahi mila.{X}")
        return
    if price is None:
        try:
            price = float(input(f"  Kis price pe nikla {hit['name']}? "))
        except Exception:
            print(f"  {R}Price chahiye. Phir se chala.{X}")
            return
    if half and not hit.get("half_booked"):
        hit["half_booked"] = True
        hit["stop"] = hit["entry"]           # rest rides at breakeven
        save(bk)
        print(f"  {G}[OK]{X} aadha book. Baaki ka stop breakeven ({hit['entry']}) pe aa gaya.")
        return
    pnl_pct = _pct(price, hit["entry"])
    hit.update({"exit": price, "exit_on": now().isoformat(), "pnl_pct": round(pnl_pct, 2)})
    bk["open"] = [p for p in bk["open"] if p is not hit]
    bk["closed"].append(hit)
    save(bk)
    col = G if pnl_pct >= 0 else R
    print(f"  {G}[OK]{X} {hit['name']} band. {col}{pnl_pct:+.1f}%{X}")


def scorecard(bk):
    """Question 3: how have the closed ones actually gone?"""
    done = bk.get("closed", [])
    if not done:
        return
    wins = [p for p in done if (p.get("pnl_pct") or 0) > 0]
    avg = sum(p.get("pnl_pct") or 0 for p in done) / len(done)
    col = G if avg >= 0 else R
    print(f"  {DIM}Ab tak: {len(done)} trades, {len(wins)} jeete "
          f"({len(wins)/len(done)*100:.0f}%), average {col}{avg:+.1f}%{DIM} per trade{X}\n")


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buy", action="store_true", help="record today's suggested trade as taken")
    ap.add_argument("--sold", metavar="NAME", help="record an exit")
    ap.add_argument("--half", action="store_true", help="with --sold: booked half only")
    ap.add_argument("--price", type=float, help="exit price for --sold")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.sold:
        record_sell(a.sold, a.price, a.half)
        return

    import rrg_engine as E, rrg_strategy as S, trade_card as TC

    print("\n" + "=" * 70)
    print(f"  {B}WAPAS AA GAYA, AASHISH{X}        {now():%a %d %b %Y · %H:%M IST}")
    print("=" * 70 + "\n")

    bk = load()

    # --- Q1 FIRST: his own positions only need a couple of quotes, so this is instant.
    # The universe pull below can take minutes on a cold cache; making him stare at a
    # blank screen before seeing his own book is the wrong order. ---
    quotes = {}
    if bk["open"]:
        if a.demo:
            quotes = {p["symbol"]: p["entry"] * 1.06 for p in bk["open"] if p.get("symbol")}
        else:
            quotes = E.live_quote([p["symbol"] for p in bk["open"] if p.get("symbol")])
    review_open(bk, quotes)

    # --- data for today's idea ---
    if a.demo:
        points, prices, bench = E.demo_points()
    else:
        cold = not _cache_ready()
        if cold:
            print(f"  {DIM}Pehli baar aaj: 204 stocks ki history laa raha hoon "
                  f"(2-5 min, sirf ek baar). Aage se instant.{X}")
        try:
            points, prices, bench = E.live_points(
                tail=6, progress=(_progress if cold else None))
        except Exception as e:      # noqa
            print(f"  {R}Data nahi aaya:{X} {e}")
            print(f"  {DIM}Token expire ho gaya? chala:  python fyers_auth.py{X}\n")
            return
        if cold:
            print(" " * 60, end="\r")

    # --- Q2: today's trade ---
    rule, params, _best = S.load_best()
    sel = S.select(points, rule, params, max_pos=4)
    held = {p["name"] for p in bk["open"]}
    fresh = [p for p in sel["longs"] if p["name"] not in held]

    card = chk = point = None
    if fresh:
        point = fresh[0]
        closes = prices.get(point["symbol"]) or [point["close"]]
        chain = None
        if not a.demo:
            try:
                import option_chain as oc
                chain, _ = oc.fetch_live(point["symbol"])
            except Exception:
                chain = None
        card = TC.build_card(point, closes, chain=chain,
                             expiry_label=getattr(config, "FUT_EXPIRY", "current"))
        ltp = (E.live_quote([point["symbol"]]).get(point["symbol"])
               if not a.demo else point["close"])
        chk = E.entry_check(card, ltp)

    if a.buy:
        if card:
            record_buy(card, point)
        else:
            print(f"  {Y}Aaj koi trade suggest nahi hua - kuch record nahi kiya.{X}")
        return

    show_new(card, chk, point)
    scorecard(bk)

    print("=" * 70)
    print(f"  {DIM}Bas itna hi. Not financial advice - decision tera.{X}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
