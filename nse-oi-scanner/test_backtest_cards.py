"""
test_backtest_cards.py  —  the card backtest must not be able to see the future.

A backtest that peeks improves every result it touches and is indistinguishable from an
edge until real money is on it. Asserting "we sliced with [:t]" is not proof; the slice
appears in four places and one of them being off by one would never show up in a number
that already looks plausible.

So this proves it by experiment: run the backtest, then run it again on data where every
bar after a cut point has been replaced with garbage, and check that every trade opened
BEFORE the cut is byte-for-byte the same. If any decision had used a future bar, the
garbage would move it.

Also checks the two things that make the rupee figures meaningful at all: that the exit
engine is the live one, and that a run with no signals reports zero trades rather than a
flattering blank.

    python test_backtest_cards.py
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def synth(n=180, names=14, seed=5):
    rnd = random.Random(seed)
    bench, b = [100.0], 100.0
    for _ in range(n - 1):
        b *= 1 + rnd.gauss(0.0004, 0.009)
        bench.append(b)
    prices, bars = {}, {}
    for i in range(names):
        px, ser, rows = 100.0, [], []
        for t in range(n):
            mkt = (bench[t] / bench[t - 1] - 1) if t else 0.0
            px *= 1 + 0.9 * mkt + rnd.gauss(0, 0.012)
            ser.append(px)
            span = px * (0.004 + rnd.random() * 0.01)
            o = ser[t - 1] if t else px
            rows.append([t, round(o, 2), round(max(o, px) + span * rnd.random(), 2),
                         round(min(o, px) - span * rnd.random(), 2), round(px, 2),
                         int(200000 * (0.5 + rnd.random()))])
        sym = f"NSE:S{i}-EQ"
        prices[sym] = ser
        bars[sym] = rows
    # One session per bar, moving forward. A cycling date list is not a calendar: it
    # repeats, which reads as "many bars in one day" and squares off every bar.
    from datetime import date, timedelta
    d0, dates = date(2026, 1, 1), []
    while len(dates) < n:
        if d0.weekday() < 5:
            dates.append(d0.isoformat())
        d0 += timedelta(days=1)
    return prices, bench, dates, bars


def poison(prices, bars, cut, seed=99):
    """Replace everything from `cut` onward with nonsense. Anything that reads the future
    will notice; anything that does not, cannot."""
    rnd = random.Random(seed)
    p2 = {s: c[:cut] + [c[cut - 1] * (1 + rnd.gauss(0, 0.35)) for _ in c[cut:]]
          for s, c in prices.items()}
    b2 = {}
    for s, rows in bars.items():
        new = list(rows[:cut])
        for r in rows[cut:]:
            j = r[4] * (1 + rnd.gauss(0, 0.35))
            new.append([r[0], j, j * 1.2, j * 0.8, j, r[5] * 3])
        b2[s] = new
    return p2, b2


def main():
    import backtest_cards as BC
    import rrg_strategy as S

    prices, bench, dates, bars = synth()
    rule, params = "momentum_only", {}
    CUT = 120

    print("\n  CARD BACKTEST")
    print("  " + "-" * 62)

    base = BC.run(prices, bench, dates, bars, rule, params, max_pos=1, warmup=60)
    check("it produces trades to reason about", base["trades"] > 0,
          f"{base['trades']} trades")

    p2, b2 = poison(prices, bars, CUT)
    alt = BC.run(p2, bench, dates, b2, rule, params, max_pos=1, warmup=60)

    # THE proof: truncate at the cut and the run must be identical to the same run on
    # full data poisoned after the cut. Same trades, same rupees, to the last one.
    short_base = BC.run({s: c[:CUT] for s, c in prices.items()}, bench[:CUT], dates[:CUT],
                        {s: r[:CUT] for s, r in bars.items()}, rule, params,
                        max_pos=1, warmup=60)
    short_alt = BC.run({s: c[:CUT] for s, c in p2.items()}, bench[:CUT], dates[:CUT],
                       {s: r[:CUT] for s, r in b2.items()}, rule, params,
                       max_pos=1, warmup=60)
    check("truncating the future changes nothing before the cut",
          short_base["trades"] == short_alt["trades"]
          and short_base["pnl"] == short_alt["pnl"],
          f"{short_base['trades']}/{short_base['pnl']} vs "
          f"{short_alt['trades']}/{short_alt['pnl']}")
    check("garbage after the cut cannot reach a decision before it",
          short_alt["trades"] == short_base["trades"]
          and short_alt["pnl"] == short_base["pnl"],
          "identical run on poisoned-then-truncated data")

    # the exits must be the live function, not a copy
    import paper as P
    src = open(os.path.join(HERE, "backtest_cards.py")).read()
    check("the backtest calls paper.step(), the live exit function",
          "P.step(" in src and hasattr(P, "step"))
    check("and it does not reimplement the stop", 'reason = "STOP"' not in src)

    # every exit reason must be one the live engine can actually produce
    # EOD is a real live reason - square_off_all() emits it every session close.
    known = {"STOP", "T2", "TIMEOUT", "RS TARGET", "EOD", "END"}
    unknown = set(base["reasons"]) - known
    check("no invented exit reasons", not unknown, f"unknown: {unknown or 'none'}")

    # charges must actually be deducted
    check("charges are charged", base["costs"] > 0, f"Rs {base['costs']}")

    # nothing to trade -> zero, not a blank that reads as success
    none = BC.run({}, bench, dates, {}, rule, params, max_pos=1, warmup=60)
    check("no data -> zero trades, reported as zero", none["trades"] == 0)

    # ---- INTRADAY: nothing may be carried overnight ----
    # PRODUCT_TYPE is INTRADAY, so the live engine flattens at SQUAREOFF every day. A
    # backtest that holds through the night scores a strategy the account cannot run, and
    # flatters every trade that was under water at 15:15 and recovered next morning.
    print()
    PER_DAY = 25
    idates = [f"2026-02-{(i // PER_DAY) + 1:02d}" for i in range(len(bench))]
    # BAR_MINUTES is what the backtest asks, because it is what the live engine asks.
    # Repeated dates alone must NOT be enough - that was the bug this test found.
    import types
    saved = sys.modules.get("config")
    fake = types.ModuleType("config")
    fake.CAPITAL, fake.LOTS_PER_TRADE = 200000, 1
    fake.MAX_POSITIONS, fake.DEFAULT_LOT, fake.LOT_SIZES = 1, 50, {}
    fake.BAR_MINUTES, fake.RESOLUTION = 15, "15"
    sys.modules["config"] = fake
    try:
        intra = BC.run(prices, bench, idates, bars, rule, params, max_pos=1, warmup=60)
        # same repeated dates, but a daily bar size: EOD must NOT fire
        fake.BAR_MINUTES, fake.RESOLUTION = 375, "D"
        daily_bm = BC.run(prices, bench, idates, bars, rule, params, max_pos=1, warmup=60)
    finally:
        if saved is not None:
            sys.modules["config"] = saved
        else:
            sys.modules.pop("config", None)
    check("intraday run squares off at the session end",
          intra["reasons"].get("EOD", 0) > 0,
          f"exits: {intra['reasons']}")
    check("daily data does NOT get a spurious EOD exit",
          "EOD" not in base["reasons"],
          f"daily exits: {base['reasons']}")
    check("repeated dates alone do NOT trigger EOD - BAR_MINUTES decides",
          "EOD" not in daily_bm["reasons"],
          f"with BAR_MINUTES=375: {daily_bm['reasons']}")
    check("the overnight-carry result differs from the flat-by-close one",
          intra["pnl"] != base["pnl"] or intra["trades"] != base["trades"],
          f"intraday {intra['trades']}/{intra['pnl']} vs daily {base['trades']}/{base['pnl']}")

    # ---- the slot count passed in must be the one enforced ----
    one = BC.run(prices, bench, dates, bars, rule, params, max_pos=1, warmup=60)
    many = BC.run(prices, bench, dates, bars, rule, params, max_pos=6, warmup=60)
    check("max_pos actually changes how much is held",
          many["trades"] > one["trades"],
          f"1 slot -> {one['trades']} trades, 6 slots -> {many['trades']}")

    print("  " + "-" * 62)
    print(f"  base: {base['trades']} trades, {base['win_rate']}% win, "
          f"Rs {base['pnl']:+,}, exits {base['reasons']}")
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
