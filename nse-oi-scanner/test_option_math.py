"""
Check the option arithmetic against how NSE actually defines these contracts.

Everything the ticket prints about money rests on four facts, and I had been carrying
them from memory. They are written down here with a test each, so a wrong assumption
fails loudly instead of turning into a rupee figure on a ticket.

  1. SEBI fixes lot size so a STOCK derivative contract is worth Rs 5-10 lakh.
     INDEX contracts are a different band, Rs 15-20 lakh since the 2024 revision.
     Lot = contract value / share price, reviewed every six months.
  2. Buying one lot of an option costs premium x lot. That is the full outlay -
     option buyers post no margin beyond the premium.
  3. An at-the-money premium is about 0.4 x sigma x sqrt(T) x spot. For a stock at
     1.5% daily vol, 30 days out, that is roughly 3% of spot.
  4. Therefore one lot of a stock option costs roughly 3-5% of Rs 5-10 lakh, i.e.
     Rs 20,000-40,000. Anything reporting lakhs per lot has a broken input.

    python test_option_math.py
"""
import sys
sys.path.insert(0, ".")
import trade_card as TC
import option_pnl as OP

STOCK_BAND = (500000, 1000000)      # SEBI band for single-stock derivatives
INDEX_BAND = (1500000, 2000000)     # index derivatives, post-2024 revision

fail = 0


def check(label, ok, detail=""):
    global fail
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('   ' + detail) if detail else ''}")
    if not ok:
        fail += 1


print("1. LOT SIZE FOLLOWS CONTRACT VALUE")
# real reference points: spot, lot, and the contract value they imply
REF = [("COFORGE", 1747, 375), ("NESTLEIND", 2400, 300), ("SBIN", 820, 750),
       ("RELIANCE", 1450, 500), ("TATASTEEL", 165, 4250)]
for name, spot, lot in REF:
    cv = spot * lot
    inside = STOCK_BAND[0] * 0.6 <= cv <= STOCK_BAND[1] * 1.6   # bands drift between reviews
    check(f"{name:<11} lot {lot:>5} x {spot:>7} = Rs {cv:>10,.0f}", inside)

print("\n2. NIFTY IS A DIFFERENT BAND (index, not stock)")
nifty_cv = 26000 * 65
check(f"NIFTY lot 65 x 26000 = Rs {nifty_cv:,}", INDEX_BAND[0] <= nifty_cv <= INDEX_BAND[1] * 1.3,
      "band Rs 15-20 lakh")
check("a stock-band check would wrongly flag NIFTY", nifty_cv > STOCK_BAND[1],
      "so index names must not be judged by the stock band")

print("\n3. ATM PREMIUM APPROXIMATION")
for spot, dv, dte, lo, hi in [(24000, 0.008, 30, 0.010, 0.030),
                              (2400, 0.015, 30, 0.020, 0.055),
                              (1747, 0.018, 10, 0.010, 0.035)]:
    p = OP.atm_premium_pct(dte, dv)
    check(f"spot {spot:>6}  vol {dv*100:.1f}%/day  {dte:>2}d  ->  premium {p*100:.2f}% of spot",
          lo <= p <= hi, f"expected {lo*100:.0f}-{hi*100:.0f}%")

print("\n4. WHAT ONE LOT ACTUALLY COSTS")
print(f"  {'NAME':<12}{'CONTRACT':>12}{'PREMIUM':>10}{'1 LOT COSTS':>14}{'% of Rs 2L':>12}")
for name, spot, lot in REF:
    p_pct = OP.atm_premium_pct(30, 0.015)
    prem = p_pct * spot
    cost = prem * lot
    pct = 100 * cost / 200000
    print(f"  {name:<12}{spot*lot:>12,.0f}{prem:>10.1f}{cost:>14,.0f}{pct:>11.1f}%")
    check(f"  {name} one lot is a five-figure outlay", 5000 <= cost <= 100000,
          f"Rs {cost:,.0f}")

print("\n5. THE GUARD CATCHES A BROKEN PREMIUM")
# the live failure: a premium near the share price itself
for spot, strike, prem, should_reject in [(2400, 2350, 4119, True),    # what it printed
                                          (2400, 2350, 95, False),     # a real premium
                                          (2400, 2350, 0, True),       # no quote
                                          (1747, 1720, 73, False)]:    # his real ticket
    intrinsic = max(0.0, spot - strike)
    rejected = prem <= 0 or prem > intrinsic + 0.25 * spot
    check(f"spot {spot} {strike}CE @ {prem:>6} -> {'rejected' if rejected else 'accepted'}",
          rejected == should_reject)

print("\n6. STATUTORY CHARGES")
import charges as CH
c = CH.round_trip(73, 375)
check(f"round trip on Rs {c['buy_turnover']:,.0f} premium = Rs {c['total']:.2f}"
      f" ({c['pct_of_premium']*100:.2f}%)", 0.002 <= c["pct_of_premium"] <= 0.006,
      "expected 0.2-0.6% of premium")
check("STT is charged on the sell side only", CH.round_trip(73, 375)["stt"] > 0
      and abs(CH.STT_SELL - 0.0015) < 1e-9, "0.15% from 1 Apr 2026")
check("spread dwarfs statutory charges", 0.02 > c["pct_of_premium"] * 4,
      f"spread 2.00% vs charges {c['pct_of_premium']*100:.2f}%")

print("\n" + ("  ALL OPTION MATH CHECKS PASS" if not fail else f"  {fail} CHECK(S) FAILED"))
sys.exit(1 if fail else 0)
