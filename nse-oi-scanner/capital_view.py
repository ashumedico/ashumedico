"""
capital_view.py  —  how much is mine, how much is committed, how much is left.

THREE DIFFERENT NUMBERS CALL THEMSELVES "MY CAPITAL", and the whole point of this module
is to keep them apart. Every one of them is legitimate; putting any two in the same box is
how a position gets sized against money that is not there.

  BROKER BALANCE   what the account actually holds, read from Fyers. The only one that is
                   money. Unknown without a token, and unknown is reported as unknown.
  CONFIGURED       config.CAPITAL - what he TOLD the system he has. Every position size is
                   computed from this one, which is why it being stale is expensive rather
                   than untidy: sizing against Rs 2,00,000 when the account holds Rs 50,000
                   does not fail, it just quietly buys three times too much.
  PAPER P&L        a simulation. Not money, and never added to either of the above.

THE CHECK THAT MATTERS
When the broker balance is readable and disagrees with the configured capital, say so
loudly. Nothing else in this system can notice that drift: the sizing code trusts config,
the broker trusts the account, and neither is in a position to compare them. This is.

WHAT "SPENT" MEANS HERE
Two different things, kept separate for the same reason:
  COMMITTED   premium currently sitting in open positions - it comes back, changed
  COST        brokerage, STT, exchange, GST, spread - it does not come back at all
A dashboard that adds them together tells you that you spent a lakh on a day you bought
one option and paid Rs 53 to do it.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def committed(book):
    """(rupees, positions) sitting in open positions right now.

    Sized on the CONFIRMED live quantity where one exists. A trade whose entry was
    acknowledged and never filled is not money out of the account, and counting it would
    understate what is actually free - see paper._live_qty for the same distinction.
    """
    total, n = 0.0, 0
    for t in (book or {}).get("open") or []:
        qty = t.get("live_qty")
        qty = _num(t.get("qty")) if qty is None else _num(qty)
        prem = _num(t.get("premium_in"))
        if qty and prem:
            total += qty * prem
            n += 1
    return round(total), n


def charges_paid(book):
    """Rupees that will not come back: brokerage, STT, exchange, GST, spread.

    Read from what each closed trade RECORDED at the time, not recomputed from today's
    rates. The rates move - STT went from 0.10% to 0.15% in April - and recomputing would
    quietly restate the cost of every trade taken before the change.
    """
    total = 0.0
    for t in (book or {}).get("closed") or []:
        c = _num(t.get("total_cost"))
        if c:
            total += c
    return round(total)


def view(book=None, cfg=None, broker=None):
    """Everything the money panel needs, with each number's source attached.

    `broker` is passed in rather than imported so this stays testable without a token and
    so a caller that has no broker gets an honest 'unknown' instead of an exception.
    """
    cfg_cap = _num(getattr(cfg, "CAPITAL", None)) if cfg else None

    real, real_err = None, "not checked"
    if broker is not None:
        try:
            rows, err = broker.funds()
            real_err = err
            if rows:
                # The broker returns several limits. The one that answers "what can I
                # deploy" is the available/withdrawable figure; anything else is a
                # different question wearing the word 'balance'.
                for title, val in rows:
                    if "available" in str(title).lower() or "withdraw" in str(title).lower():
                        real, real_err = _num(val), None
                        break
                if real is None:
                    real_err = ("funds came back but no 'available' line in it - "
                                f"got {[t for t, _ in rows]}")
        except Exception as e:      # noqa
            real, real_err = None, f"funds call failed: {str(e)[:120]}"

    used, n_open = committed(book)
    cost = charges_paid(book)

    warnings = []
    # THE DRIFT CHECK. Sizing runs off the configured number and cannot see the account;
    # the account cannot see the config. Nothing but this compares them.
    if real is not None and cfg_cap:
        gap = abs(real - cfg_cap) / cfg_cap
        if gap > 0.20:
            warnings.append(
                f"config says Rs {cfg_cap:,.0f} but the account holds Rs {real:,.0f} "
                f"({gap*100:.0f}% apart) — every position size is computed from the "
                f"config number. Fix: python configure.py --capital {int(real)}")
    if real is None:
        warnings.append(f"broker balance unknown ({real_err}) — the figures below are "
                        f"from the paper book and your config, not from the account.")

    free = None if real is None else round(real - used)
    return {
        "broker_balance": real, "broker_error": real_err,
        "configured": cfg_cap,
        "committed": used, "open_positions": n_open,
        "charges_paid": cost,
        "free": free,
        # Deployed as a share of whichever number we are entitled to use. None when the
        # denominator is unknown - a percentage of an unknown is not a percentage.
        "deployed_pct": (round(100 * used / real, 1) if real else
                         round(100 * used / cfg_cap, 1) if cfg_cap else None),
        "deployed_of": ("account" if real else "config" if cfg_cap else None),
        "warnings": warnings,
    }
