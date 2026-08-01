"""
risk_limits.py  —  the drawdown halt, which until now did not exist.

`config.py` has carried these three settings since the beginning:

    DAY_DD   = 0.02     # daily drawdown auto-halt (flatten + stand down)
    WEEK_DD  = 0.06
    MAX_LOSS = 5000     # hard worst-case rupee cap per trade

Every one of them read like protection. Not one of them was enforced anywhere in the
codebase - a grep for them found the comments in config.example.py and nothing else. A
setting that looks like a safety net and does nothing is worse than no setting, because
it gets trusted: the day the account is down 4% is exactly the day nobody re-reads the
config to check whether the halt is real.

This makes them real, at the one place every live order has to pass through.

WHAT COUNTS AS TODAY'S LOSS
Realised P&L from the paper book's closed trades - which is where every exit is booked,
after spread and statutory charges, because a halt computed on gross would trigger late.
Open positions are NOT marked in: a position that is down at 11am and green at 2pm is not
a loss yet, and halting on unrealised marks would stand him down on noise.

FAILURE MODES, DECIDED DELIBERATELY
  - No book file at all      -> zero trades today. A fresh day genuinely has none. ALLOW.
  - Book present, unreadable -> BLOCK. "I do not know today's loss" is not "today's loss
                                is acceptable", and unknown is never a yes.
  - Limit missing from config-> not enforced, and `state()` says so out loud rather than
                                inventing a default. A limit he never set is not a limit
                                he agreed to.

    python risk_limits.py            # where the account stands right now
"""
import json
import os
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
BOOK = "paper_trades.json"

try:
    import config
except ImportError:                     # noqa
    class _C:
        CAPITAL = 200000
    config = _C()


def now():
    return datetime.now(IST)


def _closed_at(t):
    """The IST date a trade was booked on, or None if the record cannot say."""
    s = t.get("closed")
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=IST)
    return d.astimezone(IST).date()


def load_book(path=None):
    """(book, error). A missing file is not an error - it is an empty day.

    The default is resolved at CALL time, not bound at definition. `path=BOOK` in the
    signature freezes whatever BOOK was when the module was imported, which makes the
    ledger location impossible to redirect - including by the test that proves an
    unreadable ledger blocks trading. A safety check that cannot be tested is a safety
    check nobody has verified."""
    path = path or BOOK
    if not os.path.exists(path):
        return {"open": [], "closed": []}, None
    try:
        with open(path) as f:
            b = json.load(f)
        if not isinstance(b, dict):
            return None, f"{path} is not an object"
        return b, None
    except Exception as e:      # noqa
        return None, f"{path} could not be read: {str(e)[:120]}"


def realised(book, since_date):
    """Rupees booked on or after a date. Costs are already inside each trade's pnl."""
    total = 0.0
    for t in (book.get("closed") or []):
        d = _closed_at(t)
        if d and d >= since_date and t.get("pnl") is not None:
            total += float(t["pnl"])
    return round(total, 2)


def week_start(d=None):
    """Monday of the current IST week."""
    d = d or now().date()
    return d - timedelta(days=d.weekday())


def state(book=None, capital=None, cfg=None):
    """Where the account stands against its own limits.

    Returns a dict a screen can render and a gate can act on. `enforced` lists which
    limits are actually live, so a missing setting is visible instead of assumed.
    """
    cfg = cfg or config
    capital = float(capital if capital is not None else
                    getattr(cfg, "CAPITAL", 200000) or 200000)
    err = None
    if book is None:
        book, err = load_book()
    if book is None:
        return {"error": err, "halted": True,
                "reason": f"{err}. Refusing to trade against a ledger I cannot read — "
                          f"not knowing today's loss is not the same as it being small."}

    today, wk = now().date(), week_start()
    day_pnl, week_pnl = realised(book, today), realised(book, wk)

    day_dd = getattr(cfg, "DAY_DD", None)
    week_dd = getattr(cfg, "WEEK_DD", None)
    day_cap = -abs(float(day_dd)) * capital if day_dd else None
    week_cap = -abs(float(week_dd)) * capital if week_dd else None

    enforced = [n for n, v in (("DAY_DD", day_dd), ("WEEK_DD", week_dd),
                               ("MAX_LOSS", getattr(cfg, "MAX_LOSS", None))) if v]
    missing = [n for n in ("DAY_DD", "WEEK_DD", "MAX_LOSS") if n not in enforced]

    halted, reason = False, None
    if day_cap is not None and day_pnl <= day_cap:
        halted = True
        reason = (f"Day limit hit: booked Rs {day_pnl:,.0f} against a DAY_DD floor of "
                  f"Rs {day_cap:,.0f} ({float(day_dd)*100:.1f}% of Rs {capital:,.0f}). "
                  f"Stand down for the session.")
    elif week_cap is not None and week_pnl <= week_cap:
        halted = True
        reason = (f"Week limit hit: booked Rs {week_pnl:,.0f} since Monday against a "
                  f"WEEK_DD floor of Rs {week_cap:,.0f} "
                  f"({float(week_dd)*100:.1f}% of Rs {capital:,.0f}).")

    return {
        "capital": capital,
        "day_pnl": day_pnl, "week_pnl": week_pnl,
        "day_cap": day_cap, "week_cap": week_cap,
        # how much more can be lost before each limit bites
        "day_room": round(day_pnl - day_cap, 2) if day_cap is not None else None,
        "week_room": round(week_pnl - week_cap, 2) if week_cap is not None else None,
        "trades_today": sum(1 for t in (book.get("closed") or [])
                            if _closed_at(t) == today),
        "open_positions": len(book.get("open") or []),
        "enforced": enforced, "not_enforced": missing,
        "halted": halted, "reason": reason, "error": None,
    }


def per_trade_ok(worst_case_rupees, cfg=None):
    """(ok, reason) for MAX_LOSS — the hard rupee cap on one trade's worst case.

    Worst case is what the ticket itself says it can lose: (premium − stop) × qty. Not a
    percentage of anything, because the point of this limit is to be absolute.
    """
    cfg = cfg or config
    cap = getattr(cfg, "MAX_LOSS", None)
    if not cap or worst_case_rupees is None:
        return True, None
    if float(worst_case_rupees) > float(cap):
        return False, (f"worst case on this ticket is Rs {float(worst_case_rupees):,.0f}, "
                       f"over the MAX_LOSS cap of Rs {float(cap):,.0f}")
    return True, None


def gate(cfg=None):
    """(allowed, reason) — the check every live ENTRY passes through.

    Exits are never gated. A halt must never trap him inside a position: the whole point
    of standing down is to be flat, and a rule that blocks the sell is not a risk limit,
    it is a trap.
    """
    s = state(cfg=cfg)
    if s.get("halted"):
        return False, s.get("reason")
    return True, None


def main():
    s = state()
    print("\n  RISK LIMITS")
    print("  " + "-" * 62)
    if s.get("error"):
        print(f"  BLOCKED — {s['reason']}\n")
        return 1
    print(f"  capital            Rs {s['capital']:,.0f}")
    print(f"  booked today       Rs {s['day_pnl']:+,.0f}"
          + (f"   floor Rs {s['day_cap']:,.0f}   room Rs {s['day_room']:,.0f}"
             if s['day_cap'] is not None else "   (DAY_DD not set)"))
    print(f"  booked this week   Rs {s['week_pnl']:+,.0f}"
          + (f"   floor Rs {s['week_cap']:,.0f}   room Rs {s['week_room']:,.0f}"
             if s['week_cap'] is not None else "   (WEEK_DD not set)"))
    print(f"  trades today       {s['trades_today']}   open {s['open_positions']}")
    print(f"  enforced           {', '.join(s['enforced']) or 'NOTHING'}")
    if s["not_enforced"]:
        print(f"  NOT enforced       {', '.join(s['not_enforced'])} — not set in config.py, "
              f"so it is not a limit")
    print("  " + "-" * 62)
    print(f"  {'HALTED — ' + s['reason'] if s['halted'] else 'clear to trade'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
