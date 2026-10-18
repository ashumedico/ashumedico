"""
test_events.py  —  an empty calendar must never read as "safe".

Implied vol rises into a results date because the market knows a jump is coming. A buyer
who enters then pays for that jump in the premium; the result prints, uncertainty
resolves, and IV collapses. The stock can move exactly as predicted and the option still
loses. It is the most reliable way to be right about a company and wrong about the trade.

The bug this file exists to prevent is not the blackout logic. It is the SHAPE of the
answer. A boolean `is_blackout()` collapses two completely different situations:

    "no event near this name"        -> safe to buy
    "no calendar has ever been loaded" -> nothing was checked

Both come back False, and False reads as a green tick — on a ticket that might be one day
from results. So the answer has THREE states, and the third one is the whole point.

    python test_events.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

IST = timezone(timedelta(hours=5, minutes=30))
FAILED = []
TMP = "_events_test.json"


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def day(n):
    return (datetime.now(IST) + timedelta(days=n)).strftime("%Y-%m-%d")


def main():
    import events as EV

    print("\n  EVENT BLACKOUT")
    print("  " + "-" * 62)
    if os.path.exists(TMP):
        os.remove(TMP)

    try:
        # ---- 1. the three states ------------------------------------------
        st, note = EV.blackout("RELIANCE", path=TMP)
        check("with NO calendar the answer is 'unchecked', not 'clear'",
              st == "unchecked", f"{st} — {note[:50]}")
        check("and it says event risk is not being checked",
              "NOT being checked" in note)

        EV.add("RELIANCE", day(1), "results", path=TMP)
        st, note = EV.blackout("RELIANCE", path=TMP)
        check("one day BEFORE results is a blackout", st == "blackout", note[:60])
        check("and the note explains the IV side of it",
              "carrying the jump" in note)

        EV.add("TCS", day(20), "results", path=TMP)
        st, note = EV.blackout("TCS", path=TMP)
        check("twenty days away is clear", st == "clear", note[:50])

        st, _ = EV.blackout("SOMENAMENOTONIT", path=TMP)
        check("a name with no event, on a POPULATED calendar, is clear", st == "clear",
              "this is the only situation where 'clear' is an honest answer")

        # ---- 2. both sides of the event -----------------------------------
        EV.add("INFY", day(-1), "results", path=TMP)
        st, note = EV.blackout("INFY", path=TMP)
        check("the day AFTER results is still a blackout", st == "blackout", note[:60])
        check("and it names the crush, not the jump", "collapsed" in note)

        EV.add("WIPRO", day(-5), "results", path=TMP)
        st, _ = EV.blackout("WIPRO", path=TMP)
        check("five days after, the crush is done and it is clear again", st == "clear")

        # ---- 3. the window is configurable, and respected ------------------
        EV.add("HDFCBANK", day(4), "results", path=TMP)
        st, _ = EV.blackout("HDFCBANK", path=TMP)
        check("four days out is clear on the default 2-day window", st == "clear")
        st, _ = EV.blackout("HDFCBANK", before=7, path=TMP)
        check("...and a blackout on a 7-day window", st == "blackout",
              "the window is a decision, not a constant")

        # ---- 4. symbol shapes ---------------------------------------------
        st, _ = EV.blackout("NSE:RELIANCE-EQ", path=TMP)
        check("a Fyers symbol resolves to the same name", st == "blackout",
              "NSE:RELIANCE-EQ and RELIANCE are one company")

        ok, msg = EV.add("X", "not-a-date", path=TMP)
        check("a bad date is refused rather than stored", not ok, msg)

        # ---- 5. an unreadable store is 'unchecked', never 'clear' ----------
        bad = "_events_bad.json"
        with open(bad, "w") as f:
            f.write("{ not json")
        try:
            st, note = EV.blackout("RELIANCE", path=bad)
            check("a corrupt calendar is 'unchecked', not 'clear'", st == "unchecked",
                  note[:60])
        finally:
            os.remove(bad)

        # ---- 6. the ticket refuses on a blackout ---------------------------
        import types, random
        m = types.ModuleType("config")
        for k, v in dict(CAPITAL=200000, RISK_PCT=0.005, LOTS_PER_TRADE=1,
                         BAR_MINUTES=375, RESOLUTION="D", HOLD_BARS=10,
                         MIN_EXPIRY_DAYS=15, DEFAULT_LOT=50, LOT_SIZES={},
                         MAX_POSITIONS=1, OPTION_SPREAD_PCT=0.02).items():
            setattr(m, k, v)
        sys.modules["config"] = m
        for mod in ("trade_card", "events"):
            sys.modules.pop(mod, None)
        import trade_card as TC
        import events as EV2
        # point the card's calendar at the test store
        EV2.STORE = TMP

        rnd = random.Random(3)
        closes = [1000.0]
        for _ in range(60):
            closes.append(closes[-1] * (1 + rnd.gauss(0.0005, 0.012)))
        p = {"name": "RELIANCE", "symbol": "NSE:RELIANCE-EQ", "close": closes[-1],
             "abs_trend": 1.0, "abs_pct": 3.0}
        c = TC.build_card(p, closes, days_to_expiry=25, capital=200000, lot=50)
        check("a ticket on a results blackout carries a refusal",
              any("blackout" in x for x in c["option"]["quality_fails"]),
              str(c["option"]["quality_fails"])[:70])
        check("and it does so with NO chain — the calendar gate is about the date",
              c["option"].get("quality") is None,
              "a name on results is a bad buy at any premium")

        p2 = dict(p, name="TCS", symbol="NSE:TCS-EQ")
        c2 = TC.build_card(p2, closes, days_to_expiry=25, capital=200000, lot=50)
        check("a clear name is not refused", c2["option"]["quality_fails"] == [],
              str(c2["option"]["quality_fails"])[:60])
    finally:
        if os.path.exists(TMP):
            os.remove(TMP)

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - an empty calendar cannot clear a name\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
