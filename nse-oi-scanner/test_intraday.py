"""
Prove the intraday switch did not quietly break the things that reason in calendar time.

Three failures are possible the moment the signal moves from daily bars to 15-minute
bars, and none of them announce themselves - the numbers stay plausible, just wrong:

  1. option premium priced off 15-minute volatility (a month of time from five hours)
  2. the market regime measured in 15-minute bars (a "50-period trend" = two days)
  3. timeout and dead-money rules still counting sessions

    python test_intraday.py
"""
import sys
sys.path.insert(0, ".")
import types

# a config that says: 15-minute bars, 10-bar hold
cfg = sys.modules.get("config") or types.ModuleType("config")
cfg.CAPITAL = 200000; cfg.RISK_PCT = 0.05; cfg.HOLD_BARS = 10
cfg.BAR_MINUTES = 15; cfg.RESOLUTION = "15"; cfg.DEFAULT_LOT = 1
cfg.TOKEN_FILE = "access_token.txt"; cfg.CLIENT_ID = ""
sys.modules["config"] = cfg

import trade_card as TC
import market_regime as MR
import rrg_engine as E

fail = 0

# ---------- 1. volatility scaling ----------
print("1. VOLATILITY SCALING")
daily_sd, spot = 0.018, 1000.0                     # 1.8% a day
bar_sd = daily_sd / (25 ** 0.5)                    # same stock seen on 15-min bars
closes_d = [spot * (1 + daily_sd) ** 0 for _ in range(60)]
vol_bar = spot * bar_sd
recovered = TC.bar_to_daily_vol(vol_bar, 15)
print(f"   15-min vol Rs {vol_bar:.2f}  ->  daily Rs {recovered:.2f}"
      f"   (true daily Rs {spot*daily_sd:.2f})")
if abs(recovered - spot * daily_sd) > 0.01:
    print("   *** scaling wrong ***"); fail += 1
else:
    print("   ok - sqrt(25) recovers the daily figure")

prem_bar = TC.premium_estimate(spot, 980, "BULLISH", vol_bar, 30)
prem_day = TC.premium_estimate(spot, 980, "BULLISH", recovered, 30)
print(f"   30-day premium off 15-min vol: Rs {prem_bar:.1f}   "
      f"off daily vol: Rs {prem_day:.1f}   ({prem_day/prem_bar:.1f}x)")
if prem_day <= prem_bar * 1.5:
    print("   *** the bug this guards against is not being exercised ***"); fail += 1
else:
    print("   ok - unscaled vol would have understated the premium materially")

# ---------- 2. regime folds intraday bars into sessions ----------
print("\n2. REGIME ON INTRADAY BARS")
_p, prices, bench = E.demo_points()
dates = []
for i in range(len(bench)):                        # 25 bars per session
    dates.append(f"2026-01-{(i // 25) % 28 + 1:02d}")
daily = MR.to_daily(bench, dates)
print(f"   {len(bench)} intraday bars  ->  {len(daily)} sessions")
reg_intra = MR.Regime(prices, bench, dates=dates)
reg_naive = MR.Regime(prices, bench)               # what it did before: bars as sessions
a = reg_intra.at(len(bench))
b = reg_naive.at(len(bench))
print(f"   folded  : {a['state']:<9} ({a['passed']}/{a['of']})")
print(f"   unfolded: {b['state']:<9} ({b['passed']}/{b['of']})   <- measured on 15-min bars")
if reg_intra.map is None:
    print("   *** folding did not happen ***"); fail += 1
else:
    print(f"   ok - folded to sessions; bar {len(bench)} answers from session "
          f"{reg_intra._t(len(bench))} of {len(daily)}")
    if reg_intra._t(len(bench)) >= len(daily):
        print("   *** uses a session that has not closed ***"); fail += 1
    else:
        print("   ok - answers from the last CLOSED session, not today's partial bar")

# ---------- 3. time rules speak the right unit ----------
print("\n3. TIME RULES")
print(f"   hold          : {TC.hold_days()*375/60:.1f} hrs")
print(f"   expiry needs  : {TC.min_days_for_thesis()} days")
print(f"   timeout rule  : {TC._timeout_rule()}")
import checkin
print(f"   dead money at : {checkin._stale_after()} days held")
if "sessions" in TC._timeout_rule():
    print("   *** timeout still speaking in sessions ***"); fail += 1
else:
    print("   ok - timeout stated in bars and hours")

# ---------- 4. T1 cannot book a quantity that is not sellable ----------
print("\n4. T1 PARTIAL BOOK  (NSE sells in lot multiples, nothing else)")
import paper as P

sold = []


class _FakeBroker:
    """Records what would have gone to the exchange, and places nothing."""
    @staticmethod
    def sell(sym, qty, tag=""):
        sold.append(qty)
        return True, "ok"

    @staticmethod
    def buy(sym, qty, tag=""):
        return True, "ok"


sys.modules["broker"] = _FakeBroker

LOT = 1225
base = dict(name="X", symbol="NSE:X-EQ", tradingsymbol="X25AUG750CE", lot=LOT,
            spot_in=100.0, premium_in=10.0, strike=100, type="CE",
            stop=95.0, t1=110.0, t2=120.0, high_water=100.0, trail_dist=5.0,
            half_booked=False, opened="2026-07-31T09:30:00")

# one lot: half of 1225 is 612.5, which is not an order. Nothing may be sold.
one = dict(base, qty=LOT)
msg = P.book_half(one, 110.0)
print(f"   1 lot  -> {msg[:72]}")
if sold or one.get("booked") or one["qty"] != LOT:
    print("   *** booked a fraction of a lot ***"); fail += 1
else:
    print("   ok - nothing sold, position intact, trail carries it")

# three lots: half is one whole lot, and it must actually reach the broker
sold.clear()
three = dict(base, qty=LOT * 3)
msg = P.book_half(three, 110.0)
print(f"   3 lots -> {msg[:72]}")
if sold != [LOT] or three["qty"] != LOT * 2:
    print(f"   *** sold {sold}, left {three['qty']} - expected [{LOT}] and {LOT*2} ***")
    fail += 1
else:
    print("   ok - 1 lot sold live, 2 lots still open")

# and the P&L must price the two legs separately, not assume 'half at the T1 spot'
bk = {"open": [three], "closed": []}
P.close(bk, three, 118.0, "T2")
t = bk["closed"][0]
b = t["booked"]
if t.get("pnl") is None or b["qty"] != LOT:
    print("   *** booked leg not priced separately ***"); fail += 1
else:
    print(f"   ok - booked {b['qty']} @ {b['premium']} + rest @ {t['premium_out']}, "
          f"net Rs {t['pnl']:+,}")

# ---------- 5. momentum radar only answers what the bars can answer ----------
print("\n5. MOMENTUM RADAR  (day-high / day-low turns need intraday bars)")
import sectors as SEC


def _bars(seq):
    """seq of (o,h,l,c) -> the [epoch,o,h,l,c,v] rows the rest of the system uses."""
    return [[i, o, h, l, c, 1000] for i, (o, h, l, c) in enumerate(seq)]


TODAY, YEST = "2026-07-31", "2026-07-30"

# rose to 110, then came off to 106 - a day-high reversal
rev = _bars([(100, 101, 99, 100), (100, 104, 100, 103), (103, 110, 102, 109),
             (109, 110, 106, 106), (106, 107, 105, 106)])
d_rev = [YEST] + [TODAY] * 4
got = SEC.classify(rev, d_rev, {"trend_struct": "HH-HL"})
print(f"   high 110 -> 106      : {got}")
if got != "DAY-HIGH REVERSAL":
    print("   *** turn off the day high not detected ***"); fail += 1
else:
    print("   ok - reversal seen, and it outranks the plain uptrend read")

# fell to 90, then bounced to 95
bnc = _bars([(100, 101, 99, 100), (100, 100, 95, 96), (96, 96, 90, 91),
             (91, 95, 90, 95), (95, 96, 94, 95)])
got = SEC.classify(bnc, d_rev, {"trend_struct": "LH-LL"})
print(f"   low 90 -> 95         : {got}")
if got != "BOUNCING OFF LOW":
    print("   *** bounce off the day low not detected ***"); fail += 1
else:
    print("   ok - bounce seen")

# no dates: the session cannot be located, so neither turn can be claimed
got = SEC.classify(rev, [], {"trend_struct": "HH-HL"})
print(f"   bina dates           : {got}")
if got != "UPTREND":
    print("   *** claimed a turn it could not measure ***"); fail += 1
else:
    print("   ok - falls back to the trend read, does not invent a turn")

# nothing at all to judge on
got = SEC.classify([], [], {})
if got is not None:
    print(f"   *** judged an empty name as {got} ***"); fail += 1
else:
    print("   ok - no bars, no verdict (None, not FLAT)")

# and the radar must COUNT what it could not judge, never hide it
pts = [{"name": "A", "symbol": "NSE:A-EQ", "abs_pct": 2.0,
        "feat": {"trend_struct": "HH-HL"}},
       {"name": "B", "symbol": "NSE:B-EQ", "abs_pct": -1.0, "feat": {}}]
r = SEC.radar(pts, {"NSE:A-EQ": rev}, d_rev)
print(f"   radar                : judged={r['judged']} unjudged={r['unjudged']} "
      f"{r['counts']}")
if r["unjudged"] != 1 or r["judged"] != 1:
    print("   *** unjudged names not reported ***"); fail += 1
else:
    print("   ok - the name with no bars is counted as unjudged, not as calm")

print("\n" + ("  ALL INTRADAY CHECKS PASS" if not fail else f"  {fail} CHECK(S) FAILED"))
sys.exit(1 if fail else 0)
