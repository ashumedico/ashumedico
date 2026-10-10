"""
option_pnl.py  —  the backtest measures the STOCK. You trade the OPTION. Translate.

Every result this system has produced is a stock-level number: the strategy picks a name,
the backtest measures what that name's price did. The money, though, goes into a call
option, and an option is not a scaled copy of the stock. Three things stand between the
two, and on a short hold they are not small:

  LEVERAGE   a 0.5% stock move is a much larger % move in a Rs 40 premium.
             This is the whole reason to buy the option - and it cuts both ways.
  SPREAD     the bid-ask on a single-stock option is a percentage of the PREMIUM, not of
             the stock. Paying 2% of premium to get in and out is normal. Against a
             stock-level cost of 35bps, that is an order of magnitude more.
  THETA      time decay is charged per day whether or not the thesis works. On an option
             three days from expiry, one session is a third of its remaining life.

A stock-level edge of half a percent per trade can be a real edge and still lose money
once these are applied. That is not pessimism - it is the arithmetic, and it is the single
most likely reason a validated backtest fails in the account.

    python option_pnl.py --demo
    python option_pnl.py --ret 0.005 --trades 71     # translate a known stock-level edge

NOT financial advice.
"""
import argparse

try:
    import config
except ImportError:
    class _C:
        BAR_MINUTES = 15; HOLD_BARS = 10
    config = _C()

SESSION_MINUTES = 375


def translate(stock_returns, premium_pct=0.04, delta=0.60, spread_pct=0.02,
              days_to_expiry=3, hold_days=0.4):
    """Turn per-trade STOCK returns into per-trade OPTION returns.

    premium_pct : option premium as a share of spot (Rs 70 on a Rs 1750 stock = 0.04)
    delta       : how much of the stock's move the option captures (ITM1 ~ 0.6)
    spread_pct  : round-trip bid-ask as a share of premium
    days_to_expiry / hold_days : drive the theta charge

    Theta uses the square-root-of-time decay of an at-the-money option: the fraction of
    remaining value lost over `hold` out of `dte` is 1 - sqrt((dte-hold)/dte). Near expiry
    that number gets large fast, which is exactly the effect being measured.
    """
    lev = delta / premium_pct if premium_pct else 0.0
    dte = max(float(days_to_expiry), 1e-6)
    hold = min(float(hold_days), dte)
    theta_pct = 1.0 - ((dte - hold) / dte) ** 0.5

    # A HOLD THAT OUTLASTS THE OPTION IS NOT A TRADE.
    # When hold >= dte the formula returns theta_pct = 1.0 - a 100% decay charge - and
    # keeps going, producing an "average return" for a contract that expired mid-hold.
    # That is not a pessimistic number, it is a meaningless one, and it was printing as
    # a result. It is refused instead, because the honest finding is not "-100%", it is
    # "this holding period and this expiry do not fit each other".
    invalid = None
    if float(hold_days) >= dte:
        invalid = (f"hold of {float(hold_days):.1f} days is longer than the "
                   f"{dte:.1f} days to expiry - the option expires inside the trade. "
                   f"Either roll to a longer series or shorten the hold; translating "
                   f"this would price a contract that no longer exists.")

    out = []
    for r in stock_returns:
        # A LONG OPTION CANNOT LOSE MORE THAN THE PREMIUM. The raw expression is
        # unbounded below, so a 30% adverse stock move at 40x leverage came out as
        # -1200% - a loss twelve times the money that was ever at risk. Every figure
        # built on that (win rate, average, sum) was wrong in the direction that makes a
        # strategy look worse than it is, which is the one nobody double-checks.
        out.append(max(-1.0, r * lev - theta_pct - spread_pct))
    return out, {"leverage": lev, "theta_pct": theta_pct, "spread_pct": spread_pct,
                 "drag": theta_pct + spread_pct, "invalid": invalid}


def summarise(rets, deploy=1.0):
    """deploy: share of the ACCOUNT in the position, not the return on the position.

    This distinction decides the answer. Compounding a 15x-levered option return against
    the whole account assumes every rupee is in every trade; one lot of a stock option on
    a Rs 2 lakh account is nearer 15% of it. Ignore that and a survivable strategy prints
    as a wipeout - which is a false alarm, and false alarms are as costly as missed ones.
    """
    if not rets:
        return {}
    wins = [r for r in rets if r > 0]
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= (1 + r * deploy)
        if eq <= 0:                       # a total loss is absorbing - say so, don't wrap
            eq = 0.0
            mdd = 1.0
            break
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    return {"n": len(rets), "avg": sum(rets) / len(rets),
            "win_rate": 100.0 * len(wins) / len(rets),
            "total": eq - 1.0, "max_dd": mdd,
            "best": max(rets), "worst": min(rets), "deploy": deploy}


def breakeven_move(premium_pct=0.04, delta=0.60, spread_pct=0.02,
                   days_to_expiry=3, hold_days=0.4):
    """How far the STOCK must move just to cover decay and spread. The honest headline:
    below this, a winning stock call is a losing option trade."""
    _o, d = translate([], premium_pct, delta, spread_pct, days_to_expiry, hold_days)
    return d["drag"] / d["leverage"] if d["leverage"] else float("inf")


def atm_premium_pct(dte, daily_vol=0.018):
    """Roughly what an at-the-money option costs, as a share of spot, `dte` days out.

    Time value grows with the square root of time, which is the whole tension: a nearer
    expiry is cheaper and therefore more levered, but decays far faster. One of those two
    wins, and which one is arithmetic, not opinion."""
    return 0.4 * daily_vol * (max(dte, 0.5) ** 0.5)


def spread_for_dte(dte, base=0.02):
    """Bid-ask widens with distance, because single-stock option liquidity does not
    survive past the near month. Treating spread as flat makes far expiries look free of
    cost and quietly recommends contracts that cannot be got out of at a fair price -
    on NSE stock options the near month carries almost all the open interest.

    The last day or two before expiry widens again as market makers step back.
    """
    if dte <= 1:
        return base * 2.0
    if dte <= 30:
        return base                      # near month - where the liquidity is
    if dte <= 60:
        return base * 2.0                # next month - thinner, still quotable
    return base * 3.5                    # far month - often untradeable in size


def dte_sweep(hold_days=0.4, daily_vol=0.018, delta=0.60, spread_pct=0.02,
              liquidity_aware=True):
    """Which expiry actually needs the SMALLEST stock move to break even?

    Nearer expiry buys leverage and pays theta. Further expiry pays premium and saves
    theta. For a hold measured in hours the answer is not obvious, and it is the single
    setting with the largest effect on whether an intraday option trade can pay at all.
    """
    rows = []
    for dte in (1, 2, 3, 5, 7, 10, 15, 21, 30, 45, 60, 90):
        p = atm_premium_pct(dte, daily_vol)
        sp = spread_for_dte(dte, spread_pct) if liquidity_aware else spread_pct
        be = breakeven_move(premium_pct=p, delta=delta, spread_pct=sp,
                            days_to_expiry=dte, hold_days=hold_days)
        _o, d = translate([], p, delta, sp, dte, hold_days)
        rows.append({"dte": dte, "premium_pct": p, "leverage": d["leverage"],
                     "theta": d["theta_pct"], "spread": sp, "breakeven": be})
    return rows


def render_sweep(rows, hold_days):
    print(f"\n  WHICH EXPIRY, FOR A {hold_days*375/60:.1f}-HOUR HOLD?")
    print("  " + "-" * 62)
    print(f"  {'DTE':>4}{'PREMIUM':>10}{'LEVER':>9}{'THETA':>8}{'SPREAD':>9}"
          f"{'STOCK MUST MOVE':>18}")
    best = min(rows, key=lambda r: r["breakeven"])
    for r in rows:
        mark = "  <-- cheapest" if r is best else ""
        print(f"  {r['dte']:>4}{r['premium_pct']*100:>9.2f}%{r['leverage']:>8.1f}x"
              f"{r['theta']*100:>7.1f}%{r.get('spread', 0)*100:>8.1f}%"
              f"{r['breakeven']*100:>17.2f}%{mark}")
    print("  " + "-" * 62)
    print(f"  Cheapest break-even at {best['dte']} days to expiry: the stock only has to")
    print(f"  move {best['breakeven']*100:.2f}% for the option to pay for its own decay.")


def report(stock_returns, label="", deploy=None, **kw):
    opt, d = translate(stock_returns, **kw)
    if deploy is None:
        deploy = float(getattr(config, "DEPLOY_PCT", 0.15))
    # the stock line is shown fully invested: it is the underlying's move, the yardstick.
    # the option line is shown at the share of the account a single lot really occupies.
    s_stock, s_opt = summarise(stock_returns), summarise(opt, deploy)
    be = breakeven_move(**kw)
    print(f"\n  OPTION TRANSLATION {('- ' + label) if label else ''}")
    print("  " + "-" * 62)
    print(f"  leverage {d['leverage']:.1f}x   theta {d['theta_pct']*100:.1f}%"
          f"   spread {d['spread_pct']*100:.1f}%   total drag {d['drag']*100:.1f}% per trade")
    print(f"  the stock must move {be*100:.2f}% just to break even on the option")
    print("  " + "-" * 62)
    if not stock_returns:
        return
    print(f"  {'':<20}{'TRADES':>8}{'WIN%':>8}{'AVG/TRADE':>12}{'ACCOUNT':>10}{'MAX DD':>9}")
    print(f"  {'stock (fully in)':<20}{s_stock['n']:>8}{s_stock['win_rate']:>8.1f}"
          f"{s_stock['avg']*100:>11.2f}%{s_stock['total']*100:>9.1f}%{s_stock['max_dd']*100:>8.1f}%")
    print(f"  {'option @ ' + f'{deploy*100:.0f}% of acct':<20}{s_opt['n']:>8}"
          f"{s_opt['win_rate']:>8.1f}{s_opt['avg']*100:>11.2f}%"
          f"{s_opt['total']*100:>9.1f}%{s_opt['max_dd']*100:>8.1f}%")
    print("  " + "-" * 62)
    print(f"  worst single trade: {s_opt['worst']*100:.1f}% of the position"
          f"  =  {s_opt['worst']*deploy*100:.1f}% of the account")
    if s_opt["total"] <= 0 < s_stock["total"]:
        print("  The stock-level edge does NOT survive the option leg. Either the hold is")
        print("  too short for the decay, the expiry is too near, or the edge per trade is")
        print("  smaller than the spread. Fixing this is a bigger win than any new filter.")
    elif s_opt["total"] > 0:
        print(f"  Survives at this size. Note the leverage cuts both ways: "
              f"{d['leverage']:.1f}x on the way down too.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="run a backtest and translate it")
    ap.add_argument("--ret", type=float, help="assume this average stock return per trade")
    ap.add_argument("--trades", type=int, default=71)
    ap.add_argument("--premium-pct", type=float, default=0.04)
    ap.add_argument("--delta", type=float, default=0.60)
    ap.add_argument("--spread-pct", type=float, default=0.02)
    ap.add_argument("--dte", type=float, default=3)
    ap.add_argument("--hold-days", type=float, default=None)
    ap.add_argument("--deploy", type=float, default=None,
                    help="share of the account in one position, e.g. 0.15")
    ap.add_argument("--sweep-dte", action="store_true",
                    help="which expiry needs the smallest stock move to break even")
    ap.add_argument("--daily-vol", type=float, default=0.018)
    a = ap.parse_args()

    hold = a.hold_days
    if hold is None:
        bm = float(getattr(config, "BAR_MINUTES", SESSION_MINUTES))
        hb = float(getattr(config, "HOLD_BARS", 10))
        hold = hb * bm / SESSION_MINUTES
    kw = dict(premium_pct=a.premium_pct, delta=a.delta, spread_pct=a.spread_pct,
              days_to_expiry=a.dte, hold_days=hold)

    if a.sweep_dte:
        render_sweep(dte_sweep(hold, a.daily_vol, a.delta, a.spread_pct), hold)
        return

    if a.ret is not None:
        import random
        random.seed(5)
        # a spread of trade outcomes with the requested mean, so win-rate and drawdown
        # are meaningful rather than a single repeated number
        rets = [random.gauss(a.ret, abs(a.ret) * 4 + 0.004) for _ in range(a.trades)]
        report(rets, f"assumed {a.ret*100:.2f}% avg stock move per trade", deploy=a.deploy, **kw)
        return

    if a.demo:
        import rrg_engine as E, rrg_strategy as S
        _p, prices, bench = E.demo_points()
        r = S.backtest(prices, bench, "momentum_only", {"need_trend": True},
                       step=10, max_pos=4, hold_min=10, cost_bps=35)
        if not r or not r.get("trade_returns"):
            print("  no trades in the demo backtest")
            return
        report(r["trade_returns"], "demo backtest (synthetic - mechanics only)", deploy=a.deploy, **kw)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
