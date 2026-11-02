"""
test_agentic.py  —  the three things that only break when nobody is watching.

A human at the desk is a reconciliation layer nobody wrote down. He sees the positions
tab, he notices the order that did not fill, he gets bored of pressing the button. Take
him out of the loop and each of those becomes a defect:

  1. ACCEPTED IS NOT FILLED.  broker.place() returns ok when Fyers takes the order and
     gives it an id. The book recorded that as a position. If it never traded, the exit
     that followed SOLD AN OPTION THAT WAS NEVER BOUGHT - which is writing it, a margin
     position with open-ended risk, the one shape of loss this system refuses by design.

  2. THE STOP DIED WITH THE PROCESS.  The session loop computed its trailing stop in
     Python and fired a market order when it broke. Close the window and nothing watched
     the position at all. Bounded - he only buys - but a planned 45% stop silently became
     a 100% loss of premium.

  3. NOBODY GETS TIRED OF PRESSING THE BUTTON.  No cap on orders per day. A retry that
     never gives up, or a signal that re-fires every tick, is a failure mode a human does
     not have and an unattended process has by default.

Every check here drives the real functions against a fake broker, because the failure is
in the handoff between our code and theirs, and a test that mocks our own logic would
prove nothing about it.

    python test_agentic.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
IST = timezone(timedelta(hours=5, minutes=30))
FAILED = []


def check(name, cond, detail=""):
    d = " ".join(str(detail).split())[:130]
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + d if d else ''}")
    if not cond:
        FAILED.append(name)


class FakeFyers:
    """Stands in for the Fyers SDK. Records what it was asked to do."""

    def __init__(self, orders=None, positions=None, fail=None):
        self._orders = orders if orders is not None else []
        self._positions = positions
        self._fail = fail or set()
        self.sent = []
        self.cancelled = []

    def _boom(self, what):
        if what in self._fail:
            raise RuntimeError(f"{what} exploded")

    def place_order(self, req):
        self._boom("place")
        self.sent.append(dict(req))
        return {"s": "ok", "id": "ORD1"}

    def orderbook(self, data=None):
        self._boom("orderbook")
        return {"s": "ok", "orderBook": self._orders}

    def positions(self):
        self._boom("positions")
        if self._positions is None:
            return {"s": "error", "message": "nope"}
        return {"s": "ok", "netPositions": self._positions}

    def cancel_order(self, data=None):
        self._boom("cancel")
        self.cancelled.append((data or {}).get("id"))
        return {"s": "ok", "id": (data or {}).get("id")}


def broker_with(fake, armed=True):
    """broker.py wired to a fake exchange, with the live gates open so we reach the new
    ones. real_only stays untouched - it is tested where it belongs."""
    import broker as B
    B._client = lambda: fake
    B.armed = lambda: armed
    B.killed = lambda: False
    import risk_limits as RL
    RL.gate = lambda cfg=None: (True, None)
    return B


def main():
    print("\n  AGENTIC  (what breaks when nobody is watching)")
    print("  " + "-" * 62)
    os.environ.pop("DESK_SYNTHETIC", None)
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)

    import broker as B

    # ---- reading the broker's own records --------------------------------
    # The container key has been renamed between API versions. A KeyError on it would
    # read as "no position", which is the exact wrong direction to fail in.
    check("the orderbook is found whatever its wrapper is called",
          B._rows({"s": "ok", "somethingElse": [{"id": "1", "filledQty": 5}]},
                  ("id", "filledQty")) == [{"id": "1", "filledQty": 5}])
    check("and an error reply is not mistaken for an empty one",
          B._rows({"s": "error"}, ("id",)) is None)

    # ---- 1. accepted is not filled ---------------------------------------
    fake = FakeFyers(orders=[{"id": "ORD1", "filledQty": 50, "status": 2}])
    B = broker_with(fake)
    filled, row, err = B.fill_of("ORD1")
    check("a filled order reports its quantity", filled == 50 and err is None,
          f"{filled} {err}")

    fake = FakeFyers(orders=[], fail={"orderbook"})
    B = broker_with(fake)
    filled, _, err = B.fill_of("ORD1")
    # THE DISTINCTION THE WHOLE LAYER RESTS ON. Zero would become "sell nothing" - safe
    # by luck. But the same value elsewhere means "position is flat", and a transport
    # error must never be able to say that.
    check("but an unreachable broker reports UNKNOWN, not zero",
          filled is None and err, f"{filled} {err}")

    fake = FakeFyers(orders=[{"id": "OTHER", "filledQty": 50}])
    B = broker_with(fake)
    filled, _, err = B.fill_of("ORD1")
    check("and an order that is not in the book is unknown too",
          filled is None and "not found" in (err or ""), err)

    # ---- the sell gate ----------------------------------------------------
    fake = FakeFyers(positions=[{"symbol": "NSE:X", "netQty": 0}])
    B = broker_with(fake)
    ok, why = B.place("NSE:X", 50, "SELL")
    check("selling what the broker says you do not hold is REFUSED",
          not ok and "WRITE" in why and not fake.sent, why)

    fake = FakeFyers(positions=[{"symbol": "NSE:X", "netQty": 25}])
    B = broker_with(fake)
    ok, why = B.place("NSE:X", 50, "SELL")
    check("holding less than asked clamps to what is held, it does not refuse",
          ok and fake.sent and fake.sent[-1]["qty"] == 25,
          fake.sent[-1] if fake.sent else why)

    # A broker API blip must never lock him inside a live position. This file already
    # carries that lesson from the drawdown halt: a rule that blocks the exit is a trap.
    fake = FakeFyers(positions=None)
    B = broker_with(fake)
    ok, why = B.place("NSE:X", 50, "SELL")
    check("but an unknown holding still lets him OUT - no trap",
          ok and fake.sent and fake.sent[-1]["qty"] == 50, why)

    fake = FakeFyers(positions=[{"symbol": "NSE:X", "netQty": 0}])
    B = broker_with(fake)
    ok, why = B.place("NSE:X", 50, "BUY")
    check("and the gate is on SELL only - a buy is untouched", ok, why)

    # ---- 2. the resting stop ---------------------------------------------
    fake = FakeFyers(positions=[{"symbol": "NSE:X", "netQty": 50}])
    B = broker_with(fake)
    ok, _ = B.stop_loss("NSE:X", 50, 12.5, tag="t")
    sl = fake.sent[-1] if fake.sent else {}
    check("a resting stop goes to the exchange as SL-M with its trigger",
          ok and sl.get("type") == 3 and sl.get("stopPrice") == 12.5, sl)

    ok, _ = B.cancel("ORD1")
    check("and it can be cancelled", ok and fake.cancelled == ["ORD1"], fake.cancelled)

    # ---- the book sizes off the CONFIRMED quantity ------------------------
    import paper as P
    t = {"name": "X", "tradingsymbol": "NSE:X", "qty": 50, "live_qty": 0,
         "stop_order": {"id": "SL1"}, "spot_in": 100, "premium_in": 10,
         "strike": 100, "type": "CE", "dir": 1, "opened": datetime.now(IST).isoformat(),
         "lot": 50, "cost": 0, "half_booked": False, "stop": 95, "t1": 110, "t2": 120}
    bk = {"open": [t], "closed": []}
    fake = FakeFyers(positions=[{"symbol": "NSE:X", "netQty": 50}])
    broker_with(fake)
    P.close(bk, t, 105, "TEST")
    check("an unconfirmed entry sends NO exit order",
          not [s for s in fake.sent if s["side"] == -1],
          [s for s in fake.sent if s["side"] == -1])
    check("and the resting stop is cancelled anyway - an orphan SL-M is a naked short",
          fake.cancelled == ["SL1"], fake.cancelled)

    # THE MIGRATION CASE, and the one this suite originally got wrong. A position opened
    # BEFORE live_qty existed carries no confirmation either way. Reading that absence as
    # zero would strip the exit off every position already open in his book on the day he
    # upgrades - a position the system cannot close, which is the trap every other rule
    # here is written to avoid. Absent falls back to the recorded quantity and lets the
    # broker's own holding check decide.
    old = dict(t, live_qty=None, qty=50, stop_order=None)
    old.pop("live_qty")
    bk = {"open": [old], "closed": []}
    fake = FakeFyers(positions=[{"symbol": "NSE:X", "netQty": 50}])
    broker_with(fake)
    P.close(bk, old, 105, "TEST")
    sold = [s for s in fake.sent if s["side"] == -1]
    check("a position opened before this change can still be exited",
          len(sold) == 1 and sold[0]["qty"] == 50, sold)

    # ---- 3. the order cap -------------------------------------------------
    import risk_limits as RL
    log = os.path.join(tmp, "orders.jsonl")
    today = datetime.now(IST)
    with open(log, "w") as f:
        for i in range(3):
            f.write(json.dumps({"event": "sending", "at": today.isoformat()}) + "\n")
        f.write(json.dumps({"event": "reply", "at": today.isoformat()}) + "\n")
        f.write(json.dumps({"event": "sending",
                            "at": (today - timedelta(days=1)).isoformat()}) + "\n")
        f.write("{torn line\n")
    n, err = RL.orders_today(log, today.date())
    check("orders sent today are counted from the audit log, not the book",
          n == 3 and err is None, f"{n} {err}")
    check("yesterday's orders and a torn line do not confuse the count", n == 3, n)

    class Cfg:
        CAPITAL = 200000
        MAX_ORDERS_PER_DAY = 3

    RL.ORDER_LOG = log
    s = RL.state(book={"open": [], "closed": []}, cfg=Cfg)
    check("the cap halts once it is reached",
          s["halted"] and "Order cap" in (s.get("reason") or ""), s.get("reason"))

    # A MISSING log and an UNREADABLE one are different facts. A fresh day genuinely has
    # no file, and halting on that would stand him down every morning - so missing counts
    # as zero, exactly as the book does. Unreadable is an absence of knowledge and must
    # halt. Tested with a directory in the file's place, which makes open() raise a real
    # OSError rather than simulating one.
    missing = os.path.join(tmp, "not-created-yet.jsonl")
    n_missing, e_missing = RL.orders_today(missing, today.date())
    check("a log that does not exist yet is zero - a fresh day has none",
          n_missing == 0 and e_missing is None, f"{n_missing} {e_missing}")

    unreadable = os.path.join(tmp, "unreadable.jsonl")
    os.mkdir(unreadable)
    n_bad, e_bad = RL.orders_today(unreadable, today.date())
    check("but an unreadable log is UNKNOWN, not zero",
          n_bad is None and e_bad, f"{n_bad} {e_bad}")

    RL.ORDER_LOG = unreadable
    s2 = RL.state(book={"open": [], "closed": []}, cfg=Cfg)
    check("and unknown halts, because it is never a yes",
          s2["halted"] and "Cannot count" in (s2.get("reason") or ""),
          s2.get("reason"))

    class NoCap:
        CAPITAL = 200000

    RL.ORDER_LOG = log
    s3 = RL.state(book={"open": [], "closed": []}, cfg=NoCap)
    check("and a cap he never set says so instead of inventing one",
          "MAX_ORDERS_PER_DAY" in s3["not_enforced"], s3["not_enforced"])

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the loop can run with nobody watching it\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
