"""
test_book_trust.py  —  can a book still print a win rate it has not earned?

Written from a live screen that read 7 closed, 86% won, +84.1% of capital. Six of the
seven rows were the same name at the same entry premium. At most two distinct trades were
in there, so the win rate was one trade counted six times and the return was its P&L
multiplied by six. Nothing on the page said so.

    python test_book_trust.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FAILED = []


def check(name, cond, detail=""):
    d = " ".join(str(detail).split())[:130]
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + d if d else ''}")
    if not cond:
        FAILED.append(name)


def trade(name, prem=100.0, day="2026-08-03", qty=50, pnl=1000, src="live chain"):
    return {"name": name, "premium_in": prem, "opened": f"{day}T09:20:00+05:30",
            "qty": qty, "pnl": pnl, "premium_source": src}


def main():
    import book_trust as BT
    import paper as PB
    print("\n  BOOK TRUST")
    print("  " + "-" * 62)

    # ---- the exact shape that reached the screen --------------------------
    real = {"open": [], "closed": [trade("ICICIPRULI", 8.4, pnl=-21422, qty=22315)]
            + [trade("PERSISTENT", 136.7, pnl=35831) for _ in range(6)]}
    a = BT.audit(real, capital=200000)
    check("seven rows of two trades is refused", not a["trustworthy"], a["rows"])
    check("and it counts the distinct trades, not the rows",
          a["rows"] == 7 and a["distinct"] == 2, f"{a['rows']} rows, {a['distinct']} distinct")
    check("the duplicate reason names the fix",
          any("--reset" in r for r in a["reasons"]),
          next((r for r in a["reasons"] if "--reset" in r), ""))
    # 22,315 x Rs 8.4 = Rs 187,446 of premium on a Rs 2 lakh account. A wrong lot scales
    # every rupee figure while leaving every percentage looking reasonable.
    check("and the impossible position size is caught from the row's OWN numbers",
          any("Lot Audit" in r for r in a["reasons"]),
          next((r for r in a["reasons"] if "Lot Audit" in r), ""))

    # ---- a clean book is not refused for the sake of it --------------------
    clean = {"open": [], "closed": [trade(f"N{i}", 100.0, day=f"2026-07-{i+1:02d}")
                                    for i in range(25)]}
    c = BT.audit(clean, capital=200000)
    check("a clean book of 25 distinct trades IS scored", c["trustworthy"], c["reasons"])

    # Same name on different days is two trades, not a duplicate. Getting this backwards
    # would refuse every book that ever traded a name twice.
    twice = {"open": [], "closed": [trade(f"N{i}", 100.0, day=f"2026-07-{i+1:02d}")
                                    for i in range(24)]
             + [trade("N0", 100.0, day="2026-07-30")]}
    t2 = BT.audit(twice, capital=200000)
    check("the same name on a different day is a second trade, not a duplicate",
          t2["trustworthy"], t2["reasons"])

    # ---- too few is its own refusal ---------------------------------------
    small = {"open": [], "closed": [trade(f"N{i}", 100.0, day=f"2026-07-{i+1:02d}")
                                    for i in range(5)]}
    s = BT.audit(small, capital=200000)
    check("five trades cannot carry a win rate, and it says so",
          not s["trustworthy"] and any("too few" in r for r in s["reasons"]),
          s["reasons"])

    est = {"open": [], "closed": [trade(f"N{i}", 100.0, day=f"2026-07-{i+1:02d}",
                                        src="estimated") for i in range(25)]}
    e = BT.audit(est, capital=200000)
    check("a book of modelled premiums measures the model, and says so",
          not e["trustworthy"] and any("ESTIMATED" in r for r in e["reasons"]),
          e["reasons"])

    check("an empty book is not accused of anything",
          BT.audit({"open": [], "closed": []})["rows"] == 0)

    # ---- the desk must ACT on the audit -------------------------------------
    src = open(os.path.join(HERE, "desk.py"), encoding="utf-8").read()
    check("the score tab withholds the win rate on an untrusted book",
          'audit["trustworthy"]' in src and "import book_trust" in src)
    check("and the backtest comparison does not run on one either",
          'if exp and closed and audit["trustworthy"]:' in src)

    # ---- and the duplicate can no longer be created --------------------------
    # The audit reports the damage; this is the door it came through. take() only ever
    # refused a name that was still OPEN, so a closed trade freed it for the same day.
    bk = {"open": [], "closed": [dict(trade("X"), opened=PB.now().isoformat())]}
    card = {"name": "X", "spot": 100, "option": {"strike": 100, "type": "CE",
            "premium": 10, "premium_source": "live chain", "stop": 5},
            "size": {"qty": 50, "lot": 50, "lots": 1}, "stock": {"stop": 95}}
    t, why = PB.take(bk, card, {})
    check("a name closed earlier today cannot be taken again",
          t is None and "ek din mein ek baar" in (why or ""), why)

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the summary is earned, not printed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
