"""
charges.py  —  what the exchange and the government take, on every option trade.

Until now the cost model had one line in it: a 2% bid-ask spread. Statutory charges were
simply absent, which means every paper result and every break-even number was flattering
by whatever they come to. They are small next to the spread, but they are not zero, and a
cost you have not written down is a cost you will discover from your ledger.

VERIFIED RATES (checked 31 Jul 2026 - re-check after any Budget, they move):

  STT              0.15% of premium on the SELL side only.
                   Raised from 0.125% in Budget 2026, effective 1 April 2026.
                   Buying costs no STT. Letting an ITM option get EXERCISED costs
                   0.125% of INTRINSIC value, which is why you square off instead.
  Exchange txn     Rs 35.03 per lakh of premium turnover = 0.03503%, both sides. (NSE
                   equity options, rate effective Oct 2024.)
  SEBI turnover    0.0001% both sides.
  Stamp duty       0.003% on the BUY side only.
  GST              18% on brokerage + exchange txn + SEBI fees. NOT on STT.
  Brokerage        Rs 20 per order flat at most discount brokers; Fyers charges the
                   lower of Rs 20 or 0.03% of turnover.

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
STT_EXERCISE    = 0.00125     # 0.125% of INTRINSIC if exercised at expiry
EXCH_TXN        = 0.0003503   # Rs 35.03 per lakh of premium, both sides
SEBI_FEES       = 0.000001    # 0.0001%, both sides
STAMP_BUY       = 0.00003     # 0.003%, buy side only
GST             = 0.18        # on brokerage + exchange + SEBI
BROKERAGE_FLAT  = 20.0        # per order
BROKERAGE_PCT   = 0.0003      # or 0.03% of turnover, whichever is lower


def brokerage(turnover):
    flat = float(getattr(config, "BROKERAGE_FLAT", BROKERAGE_FLAT))
    pct = float(getattr(config, "BROKERAGE_PCT", BROKERAGE_PCT))
    return min(flat, pct * turnover)


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
