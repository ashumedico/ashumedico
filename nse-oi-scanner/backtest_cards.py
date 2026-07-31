"""
backtest_cards.py  —  what the SUGGESTIONS would have done, not what the rotation did.

Everything measured so far scored a stock-level rotation: equal weight, hold, rebalance.
That is not what this system tells him to do. It prints a card - one ATM option, one lot,
a stop, T1, T2, a trail and a timeout - and the account pays premium, spread, STT and
brokerage. Those are different programs, and only one of them is the product.

So this replays history bar by bar and, at each step, builds the SAME card the check-in
would have printed, opens it, and hands it to `paper.step()` - the identical exit function
the live loop calls. Not a copy of the rules: the function itself. The one time this
system had two implementations of one rule, the backtest ranked candidates differently
from the live selector and it traded a strategy nobody had tested for weeks.

WHAT IS REAL HERE AND WHAT IS MODELLED  (read this before believing a number)

  REAL      the stock path, bar by bar, from the same history the signals use
  REAL      the entry rule, the gates, the stop / T1 / T2 / trail / timeout logic
  REAL      charges - STT, exchange, SEBI, stamp, GST, brokerage - via charges.py
  MODELLED  the option premium. There is no historical option chain anywhere in this
            system, so entry premium is estimated from realised vol and the exit premium
            moves with delta. That ignores gamma, theta and any change in implied vol.
  MODELLED  the spread, as a flat OPTION_SPREAD_PCT of premium on both legs.

Theta is the one that matters most and it is NOT here: a real intraday option bleeds time
value all day, and this does not charge for that. So treat the result as an UPPER BOUND on
what the same rules would have paid in cash. If it does not clear the bar here, it will not
clear it live.

    python backtest_cards.py --demo            # synthetic - mechanics only
    python backtest_cards.py --days 900        # live history (needs a Fyers token)
    python backtest_cards.py --days 900 --side both

NOT financial advice.
"""
import argparse
import sys

G, R, Y, B, D, X = ("\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[90m", "\033[0m")


def _fake_broker():
    """No orders from a backtest, ever - and no silent exceptions either."""
    import types
    m = types.ModuleType("broker")
    m.buy = lambda *a, **k: (False, "backtest")
    m.sell = lambda *a, **k: (False, "backtest")
    m.armed = lambda: False
    m.killed = lambda: True
    sys.modules["broker"] = m


def _cfg():
    """config.py is git-ignored, so it is absent on any machine that has not been set up.
    A backtest that cannot run without credentials is a backtest nobody runs."""
    try:
        import config
        return config
    except ImportError:
        class _C:
            CAPITAL = 200000
            LOTS_PER_TRADE = 1
            MAX_POSITIONS = 1
            DEFAULT_LOT = 50
            LOT_SIZES = {}
        return _C()


def run(prices, bench, dates, bars_by_symbol, rule, params, side="long",
        max_pos=1, warmup=60, verbose=False):
    config = _cfg()
    import features as F
    import paper as P
    import rrg_strategy as S
    import trade_card as TC

    _fake_broker()
    n = len(bench or [])
    by_sym = {s: c for s, c in prices.items()}
    capital = float(getattr(config, "CAPITAL", 200000))
    lot_cfg = getattr(config, "LOT_SIZES", {}) or {}
    default_lot = int(getattr(config, "DEFAULT_LOT", 50) or 50)

    book = {"open": [], "closed": []}
    opened_at = {}                    # name -> bar index it was opened on
    equity, peak, maxdd = capital, capital, 0.0
    curve = []

    for t in range(warmup, n):
        # ---- mark what is open, using the live exit function ----
        for tr in list(book["open"]):
            closes = by_sym.get(tr["symbol"])
            if not closes or t >= len(closes):
                continue
            px = closes[t]
            bars = t - opened_at.get(tr["name"], t)
            reason, _ = P.step(tr, px, bars)
            if reason:
                P.close(book, tr, px, reason)
                equity += book["closed"][-1].get("pnl", 0)
                peak = max(peak, equity)
                maxdd = max(maxdd, (peak - equity) / peak if peak else 0)
        curve.append(equity)

        if len(book["open"]) >= max_pos:
            continue

        # ---- build the points AS OF t, with no bar at or after t visible ----
        # build_points is the function the live path uses. Recomputing abs_trend here in
        # a shorter, "obviously equivalent" form is exactly how the ranking drifted last
        # time: two definitions of one number, and the tested strategy stops being the
        # traded one. So the real function is called on truncated history.
        import rrg_engine as E
        hist = {s: c[:t] for s, c in by_sym.items() if len(c) >= t and len(c[:t]) >= 40}
        if len(hist) < 5:
            continue
        pts = E.build_points(hist, bench[:t], {}, tail=3,
                             dates=(dates[:t] if dates else None))
        # features from the same truncated bars - F.at() already refuses to look at or
        # past the decision bar
        for p in pts:
            b = (bars_by_symbol or {}).get(p.get("symbol"))
            if b and len(b) >= t:
                f = F.at(b[:t], dates, t=None)
                if f:
                    p["feat"] = f
        if not pts:
            continue

        sel = S.select(pts, rule, params, max_pos=max_pos, prices=None)
        picks = []
        if side in ("long", "both"):
            picks += [(p, "LONG") for p in sel.get("longs") or []]
        if side in ("short", "both"):
            picks += [(p, "SHORT") for p in sel.get("shorts") or []]
        if not picks:
            continue

        p, sd = picks[0]
        if any(o["name"] == p["name"] for o in book["open"]):
            continue
        closes = by_sym[p["symbol"]][:t]
        card = TC.build_card(p, closes, expiry_label="bt",
                             days_to_expiry=TC.min_days_for_thesis(),
                             capital=capital, side=sd)
        if card.get("action") == "SKIP":
            continue
        o = card.get("option") or {}
        if not o.get("premium"):
            continue
        # A lot the backtest guessed would make every rupee figure meaningless, so it uses
        # the pinned lot when there is one and a stated default otherwise - and the report
        # says how many trades used which.
        lot = int(lot_cfg.get(p["name"]) or default_lot)
        card["size"] = {"qty": lot * int(getattr(config, "LOTS_PER_TRADE", 1) or 1),
                        "lot": lot,
                        "lots": int(getattr(config, "LOTS_PER_TRADE", 1) or 1),
                        "cost_per_lot": o["premium"] * lot}
        card["symbol"] = p["symbol"]
        tr, why = P.take(book, card, p)
        if tr is None:
            continue
        tr["lot_source"] = "pinned" if p["name"] in lot_cfg else "default"
        opened_at[p["name"]] = t
        if verbose:
            print(f"   {t:>4}  OPEN  {sd:<5} {p['name']:<12} "
                  f"{o['type']} {o['strike']} @ {o['premium']}")

    # square off whatever is still open at the last bar, so nothing is scored as if it
    # were still running forever
    for tr in list(book["open"]):
        closes = by_sym.get(tr["symbol"]) or []
        if closes:
            P.close(book, tr, closes[min(n, len(closes)) - 1], "END")
            equity += book["closed"][-1].get("pnl", 0)

    closed = book["closed"]
    wins = [c for c in closed if c.get("pnl", 0) > 0]
    losses = [c for c in closed if c.get("pnl", 0) <= 0]
    pnl = sum(c.get("pnl", 0) for c in closed)
    costs = sum(c.get("total_cost", 0) for c in closed)
    reasons = {}
    for c in closed:
        reasons[c.get("reason", "?")] = reasons.get(c.get("reason", "?"), 0) + 1
    return {
        "trades": len(closed), "wins": len(wins), "losses": len(losses),
        "win_rate": round(100 * len(wins) / len(closed), 1) if closed else 0.0,
        "pnl": round(pnl), "costs": round(costs),
        "avg_win": round(sum(c["pnl"] for c in wins) / len(wins)) if wins else 0,
        "avg_loss": round(sum(c["pnl"] for c in losses) / len(losses)) if losses else 0,
        "best": round(max((c["pnl"] for c in closed), default=0)),
        "worst": round(min((c["pnl"] for c in closed), default=0)),
        "pct_of_capital": round(100 * pnl / capital, 1) if capital else 0.0,
        "max_dd_pct": round(100 * maxdd, 1),
        "reasons": reasons, "curve": curve,
        "pinned_lots": sum(1 for c in closed if c.get("lot_source") == "pinned"),
    }


def report(res, title, note=""):
    if not res or not res["trades"]:
        print(f"\n  {Y}{title}: ek bhi trade nahi bana.{X}")
        print(f"  {D}Gates itne tight hain ki kuch pass hi nahi hua - ye bhi ek natija "
              f"hai, aur ise 'kaam karta hai' nahi padha jaata.{X}")
        return
    col = G if res["pnl"] > 0 else R
    print(f"\n  {B}{title}{X}  {D}{note}{X}")
    print("  " + "-" * 66)
    print(f"  Trades        {res['trades']:>8}      jeete {res['wins']} / haare {res['losses']}"
          f"   ({res['win_rate']}%)")
    print(f"  Net P&L       {col}Rs {res['pnl']:>+9,}{X}   = {res['pct_of_capital']:+.1f}% capital")
    print(f"  Charges       {D}Rs {res['costs']:>9,}{X}   {D}(spread + STT + exchange + GST){X}")
    print(f"  Avg jeet      Rs {res['avg_win']:>+9,}      Avg haar  Rs {res['avg_loss']:+,}")
    print(f"  Best / Worst  Rs {res['best']:>+9,}      Rs {res['worst']:+,}")
    print(f"  Max drawdown  {res['max_dd_pct']:>8.1f}%")
    if res["reasons"]:
        bits = "  ".join(f"{k} {v}" for k, v in
                         sorted(res["reasons"].items(), key=lambda x: -x[1]))
        print(f"  Kaise nikle   {D}{bits}{X}")
    if res["trades"] and res["pinned_lots"] < res["trades"]:
        print(f"  {Y}Note{X}          {res['trades'] - res['pinned_lots']} trades ka lot "
              f"DEFAULT_LOT se liya gaya - rupee figures utne hi sahi hain jitna wo lot.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--side", default="long", choices=["long", "short", "both"])
    ap.add_argument("--max-pos", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    config = _cfg()
    import rrg_engine as E
    import rrg_strategy as S

    if a.demo:
        print(f"\n  {Y}[DEMO] synthetic universe - mechanics proof, NOT an edge.{X}")
        pts, prices, bench = E.demo_points()
    else:
        try:
            pts, prices, bench = E.live_points(tail=3, days=a.days)
        except Exception as e:      # noqa
            print(f"\n  {R}Live history nahi aayi: {e}{X}")
            print(f"  {D}Token chahiye. '1 - START DAY' chala, phir dobara.{X}\n")
            return 2
    dates = getattr(E, "LAST_DATES", None) or []
    bars = getattr(E, "LAST_BARS", {}) or {}
    rule, params, _ = S.load_best()
    max_pos = a.max_pos or int(getattr(config, "MAX_POSITIONS", 1) or 1)

    print(f"\n  {B}SUGGESTIONS KA BACKTEST{X}")
    print(f"  {D}rule={rule} · {len(prices)} naam · {len(bench)} bars · "
          f"{max_pos} position at a time · 1 lot{X}")
    print(f"  {D}OHLCV bars: {sum(1 for v in bars.values() if v)}/{len(prices)} naam "
          f"(feature gates sirf inhi pe lagte hain){X}")

    res = run(prices, bench, dates, bars, rule, params, side=a.side,
              max_pos=max_pos, verbose=a.verbose)
    report(res, f"{a.side.upper()} — jo cards chhape hote, unka hisaab")

    print("\n  " + "=" * 66)
    print(f"  {Y}Premium MODEL hai, itihaas nahi.{X} Is system mein purani option chain "
          f"hai hi nahi,")
    print(f"  isliye entry premium vol se estimate hota hai aur exit delta se chalta hai.")
    print(f"  {R}Theta is mein nahi hai{X} - asli option din bhar time value khota hai.")
    print(f"  Matlab ye number ek {B}UPPER BOUND{X} hai. Yahan pass nahi hua toh live "
          f"kabhi nahi hoga.")
    print(f"  {D}Ek backtest hypothesis hai, waada nahi.{X}")
    print("  " + "=" * 66 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
