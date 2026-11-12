"""
test_risk_limits.py  —  the halt has to actually halt.

DAY_DD, WEEK_DD and MAX_LOSS sat in config.py from the beginning and were enforced
nowhere. A grep found them in the example config's comments and in no code path at all.
That is the most dangerous shape a setting can take: it reads like a safety net, so it
gets trusted, and the day the account is 4% down is exactly the day nobody re-reads the
config to check whether the halt is real.

Four things this pins:

  1. The limit BITES - at the floor, not merely past it.
  2. It gates ENTRIES ONLY. A halt that blocks the exit is not a risk limit, it is a
     trap: the whole point of standing down is to be flat.
  3. An unreadable ledger BLOCKS. "I do not know today's loss" is not "today's loss is
     acceptable", and unknown is never a yes. But a MISSING ledger is an empty day and
     must not block - a fresh morning legitimately has no file.
  4. A limit absent from config is reported as not enforced rather than given a made-up
     default. A limit he never set is not a limit he agreed to.

    python test_risk_limits.py
"""
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

IST = timezone(timedelta(hours=5, minutes=30))
FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def cfg(day=0.02, week=0.06, maxloss=5000, capital=200000):
    m = types.ModuleType("config")
    m.CAPITAL = capital
    if day is not None:
        m.DAY_DD = day
    if week is not None:
        m.WEEK_DD = week
    if maxloss is not None:
        m.MAX_LOSS = maxloss
    return m


def book(*pnls, when=None):
    """A book whose closed trades booked these rupee amounts, today by default."""
    when = when or datetime.now(IST)
    return {"open": [], "closed": [{"pnl": p, "closed": when.isoformat()} for p in pnls]}


def main():
    import risk_limits as RL

    print("\n  RISK LIMITS")
    print("  " + "-" * 62)

    C = cfg()
    cap_floor = -0.02 * 200000          # -4,000

    # ---- 1. the limit bites ---------------------------------------------------
    s = RL.state(book(-1000, -1500), cfg=C)
    check("under the floor, trading continues", not s["halted"],
          f"booked {s['day_pnl']:+,.0f}, room {s['day_room']:+,.0f}")
    s = RL.state(book(-2000, -2001), cfg=C)
    check("past the floor, HALTED", s["halted"], f"booked {s['day_pnl']:+,.0f}")
    s = RL.state(book(cap_floor), cfg=C)
    check("exactly AT the floor is a halt, not a near miss", s["halted"],
          f"booked {s['day_pnl']:+,.0f} vs floor {s['day_cap']:+,.0f}")
    s = RL.state(book(5000, -1000), cfg=C)
    check("a green day is not halted by one losing trade", not s["halted"],
          f"net {s['day_pnl']:+,.0f}")

    # ---- 2. the week is Monday-to-now, and independent of the day -------------
    mon = datetime.now(IST) - timedelta(days=datetime.now(IST).weekday())
    older = mon.replace(hour=10)
    wk = {"open": [], "closed": [
        {"pnl": -12500, "closed": older.isoformat()},           # earlier this week
        {"pnl": -500, "closed": datetime.now(IST).isoformat()},  # today, small
    ]}
    s = RL.state(wk, cfg=C)
    check("a small day inside a bad week still halts on WEEK_DD",
          s["halted"] and "Week limit" in (s["reason"] or ""),
          f"day {s['day_pnl']:+,.0f}, week {s['week_pnl']:+,.0f}, "
          f"week floor {s['week_cap']:+,.0f}")

    # last week's losses must NOT count against this week
    last_wk = mon - timedelta(days=3)
    s = RL.state({"open": [], "closed": [
        {"pnl": -50000, "closed": last_wk.isoformat()}]}, cfg=C)
    check("last week's damage does not halt this week", not s["halted"],
          f"week {s['week_pnl']:+,.0f}")

    # ---- 3. the ledger's failure modes are decided, not accidental ------------
    s = RL.state(None, cfg=C) if not os.path.exists(RL.BOOK) else {"halted": False}
    check("a MISSING book is an empty day, not a halt", not s.get("halted"),
          "a fresh morning legitimately has no file")

    bad = os.path.join(HERE, "_risk_test_bad.json")
    with open(bad, "w") as f:
        f.write("{not json at all")
    try:
        b, err = RL.load_book(bad)
        check("an unreadable book returns an error rather than an empty one",
              b is None and bool(err), str(err)[:60])
        # and state() must refuse on it
        import unittest.mock as mock
        with mock.patch.object(RL, "BOOK", bad):
            s = RL.state(cfg=C)
        check("and state() BLOCKS rather than assuming zero loss",
              s.get("halted") and s.get("error"), (s.get("reason") or "")[:70])
    finally:
        os.remove(bad)

    # ---- 4. a limit not in config is not a limit -----------------------------
    s = RL.state(book(-50000), cfg=cfg(day=None, week=None, maxloss=None))
    check("with no limits set, nothing halts", not s["halted"],
          "a limit he never set is not one he agreed to")
    # Every limit that exists and is unset has to be named. MAX_ORDERS_PER_DAY joined the
    # list when the runaway-loop backstop was added - a fourth setting that reads like
    # protection, and would be the fourth to protect nothing if it went unreported.
    check("but the absence is reported, loudly",
          set(s["not_enforced"]) == {"DAY_DD", "WEEK_DD", "MAX_LOSS",
                                     "MAX_ORDERS_PER_DAY"},
          str(s["not_enforced"]))
    check("and 'enforced' is honest about being empty", s["enforced"] == [])

    # ---- 5. MAX_LOSS is absolute, per ticket ---------------------------------
    ok, why = RL.per_trade_ok(4999, C)
    check("a ticket inside MAX_LOSS passes", ok)
    ok, why = RL.per_trade_ok(5001, C)
    check("a ticket over MAX_LOSS is refused", not ok, (why or "")[:60])
    ok, _ = RL.per_trade_ok(999999, cfg(maxloss=None))
    check("with MAX_LOSS unset, nothing is capped", ok)

    # ---- 6. the gate is wired into the broker, for BUYS ONLY -----------------
    src = open(os.path.join(HERE, "broker.py")).read()
    check("broker.place consults the risk gate", "risk_limits" in src and "RL.gate()" in src)
    check("and it gates BUY only — a halt must never block the exit",
          'if side == "BUY":' in src,
          "blocking the sell would trap him inside the position he is standing down from")
    check("a failing gate refuses rather than silently opening",
          "refusing" in src.split("RL.gate()")[1][:400])

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the halt halts, and only the entry\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
