"""
test_capital_view.py  —  does the money panel keep the three "capitals" apart?

The failure here is not a crash. It is a panel that adds the broker's balance to a paper
simulation, or reports "free" as a confident number when nobody asked the account, or
prints a percentage of a denominator it does not have. Each one reads as a fact.

    python test_capital_view.py
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


class Cfg:
    CAPITAL = 200000


class Broker:
    def __init__(self, rows=None, err=None, boom=False):
        self._rows, self._err, self._boom = rows, err, boom

    def funds(self):
        if self._boom:
            raise RuntimeError("network gone")
        return self._rows, self._err


def book(open_=(), closed=()):
    return {"open": list(open_), "closed": list(closed)}


def main():
    import capital_view as CV
    print("\n  CAPITAL VIEW")
    print("  " + "-" * 62)

    live = Broker(rows=[("Total Balance", 250000.0), ("Available Balance", 180000.0)])
    b = book(open_=[{"name": "X", "qty": 50, "premium_in": 120.0, "live_qty": 50}],
             closed=[{"total_cost": 53.0}, {"total_cost": 118.0}])

    v = CV.view(book=b, cfg=Cfg, broker=live)
    # "Available", not "Total". Total includes money that cannot be deployed, and sizing
    # against it buys with capital that is not there.
    check("the balance read is the AVAILABLE line, not the total",
          v["broker_balance"] == 180000.0, v["broker_balance"])
    check("committed is premium x confirmed quantity", v["committed"] == 6000, v["committed"])
    check("free is the account minus what is committed", v["free"] == 174000, v["free"])
    # Charges do not come back; committed premium does, changed. Adding them would report
    # a lakh spent on a day one option was bought and Rs 171 was paid to do it.
    check("charges are counted separately and are not added to committed",
          v["charges_paid"] == 171 and v["committed"] == 6000,
          f"{v['charges_paid']} / {v['committed']}")

    # ---- unknown is unknown ------------------------------------------------
    for label, brk in (("no broker at all", None),
                       ("the funds call fails", Broker(boom=True)),
                       ("funds returns an error", Broker(rows=None, err="token expired"))):
        u = CV.view(book=b, cfg=Cfg, broker=brk)
        check(f"with {label}, the balance is UNKNOWN, not config.CAPITAL",
              u["broker_balance"] is None, u["broker_balance"])
        check(f"...and 'free' is not invented from it", u["free"] is None, u["free"])
    u = CV.view(book=b, cfg=Cfg, broker=None)
    check("and the panel says the figures are not from the account",
          any("not from the account" in w for w in u["warnings"]), u["warnings"])

    # A funds reply with no available line is not a zero balance.
    odd = CV.view(book=b, cfg=Cfg, broker=Broker(rows=[("Some Other Limit", 5.0)]))
    check("an unrecognised funds reply is unknown, not zero",
          odd["broker_balance"] is None and "no 'available'" in (odd["broker_error"] or ""),
          odd["broker_error"])

    # ---- THE DRIFT CHECK ---------------------------------------------------
    # Sizing computes from config and cannot see the account; the broker sees the account
    # and cannot see config. Nothing but this compares them.
    poor = CV.view(book=book(), cfg=Cfg, broker=Broker(rows=[("Available Balance", 50000.0)]))
    check("config far above the real balance is flagged, with the command to fix it",
          any("configure.py --capital 50000" in w for w in poor["warnings"]),
          poor["warnings"])
    close = CV.view(book=book(), cfg=Cfg,
                    broker=Broker(rows=[("Available Balance", 195000.0)]))
    check("and a small, ordinary difference is not nagged about",
          not close["warnings"], close["warnings"])

    # ---- percentages need a denominator ------------------------------------
    class NoCap:
        pass
    n = CV.view(book=b, cfg=NoCap, broker=None)
    check("with no balance and no configured capital, there is no percentage",
          n["deployed_pct"] is None, n["deployed_pct"])
    check("and the panel names which denominator it used when there is one",
          v["deployed_of"] == "account", v["deployed_of"])

    # ---- an unfilled entry is not money out --------------------------------
    unfilled = book(open_=[{"name": "X", "qty": 50, "premium_in": 120.0, "live_qty": 0}])
    z = CV.view(book=unfilled, cfg=Cfg, broker=live)
    check("an entry that never filled is not counted as committed",
          z["committed"] == 0, z["committed"])
    # But a record written before live_qty existed has no confirmation either way, and
    # reading that absence as zero would understate what is deployed.
    old = book(open_=[{"name": "X", "qty": 50, "premium_in": 120.0}])
    o = CV.view(book=old, cfg=Cfg, broker=live)
    check("while a pre-upgrade record falls back to its recorded quantity",
          o["committed"] == 6000, o["committed"])

    src = open(os.path.join(HERE, "desk.py"), encoding="utf-8").read()
    check("the deck renders the panel", "import capital_view" in src
          and 'mc[0].metric("In the account"' in src)

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - three capitals, kept apart\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
