"""
charges.py  —  what the exchange and the government take, on every option trade.

Until now the cost model had one line in it: a 2% bid-ask spread. Statutory charges were
simply absent, which means every paper result and every break-even number was flattering
by whatever they come to. They are small next to the spread, but they are not zero, and a
cost you have not written down is a cost you will discover from your ledger.

VERIFIED RATES (checked 31 Jul 2026 - re-check after any Budget, they move):

  STT              0.15% of premium on the SELL side only.
                   Raised from 0.10% in Budget 2026, effective 1 April 2026.
                   Buying costs no STT. Letting an ITM option get EXERCISED costs
                   0.15% too (raised from 0.125% in the same Budget) - but of INTRINSIC
                   VALUE, not of premium, and intrinsic on a deep-ITM option dwarfs the
                   premium. The rates converged; the bases did not. Square off.
  Exchange txn     Rs 35.03 per lakh of premium turnover = 0.03503%, both sides. (NSE
                   equity options, rate effective Oct 2024.)
  SEBI turnover    0.0001% both sides.
  Stamp duty       0.003% on the BUY side only.
  GST              18% on brokerage + exchange txn + SEBI fees. NOT on STT.
  Brokerage        Fyers OPTIONS: flat Rs 20 per executed order. No percentage
                   alternative - the "lower of Rs 20 or 0.03%" rule is the FUTURES and
                   intraday-equity one, and applying it here understated brokerage 26x on
                   a one-lot trade. Rs 15 on the Rs 4,990/yr Prime plan (set
                   FYERS_PRIME = True in config).

The single most useful number this produces is the round-trip cost as a percentage of the
premium paid, because that is what the trade has to clear before it earns anything.

    python charges.py --premium 73 --qty 375
    python charges.py --premium 73 --qty 375 --exit 85

NOT financial advice.
"""
import argparse

try:
    import config
except ImportError:
    class _C:
        pass
    config = _C()

# All rates as fractions of turnover unless noted.
STT_SELL        = 0.0015      # 0.15% of premium, sell side only (from 1 Apr 2026)
STT_EXERCISE    = 0.0015      # 0.15% of INTRINSIC if exercised (raised 1 Apr 2026)
EXCH_TXN        = 0.0003503   # Rs 35.03 per lakh of premium, both sides
SEBI_FEES       = 0.000001    # 0.0001%, both sides
STAMP_BUY       = 0.00003     # 0.003%, buy side only
GST             = 0.18        # on brokerage + exchange + SEBI
BROKERAGE_FLAT  = 20.0        # per executed order - Fyers standard
BROKERAGE_PRIME = 15.0        # per executed order on the Rs 4,990/yr Prime plan


def brokerage(turnover):
    """Fyers brokerage on ONE option order. Flat, and turnover does not enter it.

    THIS USED TO BE min(Rs 20, 0.03% of turnover), and that is the futures and
    intraday-equity rule, not the options one. Fyers charges options at a flat Rs 20 per
    executed order with no percentage alternative - so on a small position the old formula
    picked the percentage and reported a fraction of the real cost.

    The error scaled the wrong way. On a one-lot trade with Rs 2,500 of premium turnover
    it modelled 0.03% = Rs 0.75 a side against a true Rs 20 - understating brokerage 26x,
    and understating the round trip by about Rs 39 on a Rs 2,500 position. That is ~1.5%
    of the position, silently removed from the hurdle every trade had to clear. It mattered
    least for the large positions nobody here trades and most for the small ones that are
    the entire use case.
    """
    if getattr(config, "FYERS_PRIME", False):
        return float(getattr(config, "BROKERAGE_FLAT", BROKERAGE_PRIME))
    return float(getattr(config, "BROKERAGE_FLAT", BROKERAGE_FLAT))


def round_trip(premium_in, qty, premium_out=None):
    """Every statutory charge on one complete option trade, itemised.

    premium_out defaults to premium_in, which is the right assumption when you want the
    cost of trading rather than the cost of a particular outcome.
    """
    premium_out = premium_in if premium_out is None else premium_out
    buy_turnover = premium_in * qty
    sell_turnover = premium_out * qty

    brok = brokerage(buy_turnover) + brokerage(sell_turnover)
    stt = STT_SELL * sell_turnover                      # sell side only
    exch = EXCH_TXN * (buy_turnover + sell_turnover)
    sebi = SEBI_FEES * (buy_turnover + sell_turnover)
    stamp = STAMP_BUY * buy_turnover
    gst = GST * (brok + exch + sebi)

    total = brok + stt + exch + sebi + stamp + gst
    return {
        "brokerage": brok, "stt": stt, "exchange": exch, "sebi": sebi,
        "stamp": stamp, "gst": gst, "total": total,
        "pct_of_premium": (total / buy_turnover) if buy_turnover else 0.0,
        "buy_turnover": buy_turnover, "sell_turnover": sell_turnover,
    }


def cost_pct(premium_in, qty, premium_out=None):
    """Round-trip statutory cost as a fraction of the premium paid."""
    return round_trip(premium_in, qty, premium_out)["pct_of_premium"]


def total_drag_pct(premium_in, qty, spread_pct=None, premium_out=None):
    """Statutory charges PLUS bid-ask, as a fraction of premium. This is the real number
    a trade has to clear - quoting either half alone understates it."""
    sp = float(spread_pct if spread_pct is not None
               else getattr(config, "OPTION_SPREAD_PCT", 0.02))
    return cost_pct(premium_in, qty, premium_out) + sp


def render(premium_in, qty, premium_out=None):
    c = round_trip(premium_in, qty, premium_out)
    out = premium_out if premium_out is not None else premium_in
    print(f"\n  CHARGES  ·  buy {qty} @ {premium_in}  ->  sell @ {out}")
    print("  " + "-" * 56)
    print(f"  premium paid            Rs {c['buy_turnover']:>12,.0f}")
    print("  " + "-" * 56)
    for k, label in (("brokerage", "brokerage (both sides)"),
                     ("stt", "STT 0.15% (sell side)"),
                     ("exchange", "exchange txn 0.035%"),
                     ("stamp", "stamp duty (buy side)"),
                     ("sebi", "SEBI fees"),
                     ("gst", "GST 18%")):
        print(f"  {label:<24}Rs {c[k]:>12,.2f}")
    print("  " + "-" * 56)
    print(f"  {'TOTAL':<24}Rs {c['total']:>12,.2f}"
          f"   = {c['pct_of_premium']*100:.2f}% of premium")
    sp = float(getattr(config, "OPTION_SPREAD_PCT", 0.02))
    print(f"  {'+ bid-ask spread':<24}Rs {sp*c['buy_turnover']:>12,.2f}"
          f"   = {sp*100:.2f}%")
    tot = c["pct_of_premium"] + sp
    print(f"  {'REAL DRAG':<24}Rs {tot*c['buy_turnover']:>12,.2f}"
          f"   = {tot*100:.2f}% of premium")
    print("  " + "-" * 56)
    print(f"  The premium must rise {tot*100:.2f}% before this trade earns a rupee.")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--premium", type=float, required=True)
    ap.add_argument("--qty", type=int, required=True)
    ap.add_argument("--exit", type=float, default=None, dest="exit_premium")
    a = ap.parse_args()
    render(a.premium, a.qty, a.exit_premium)


if __name__ == "__main__":
    main()
