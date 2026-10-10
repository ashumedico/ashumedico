"""
book_trust.py  —  is this paper book worth computing a win rate from?

A scorecard is the one screen built to be believed. It takes a list of rows and returns a
percentage, and the percentage carries no memory of where the rows came from. That is
fine when the rows are trades. It is dangerous when they are not, because nothing about
the output changes.

WHAT THIS WAS WRITTEN FROM
A live book showed 7 closed trades, 86% won, +84.1% of capital. Six of the seven rows were
the same name at the same entry premium, closed for the same reason - one signal recorded
six times, because `take()` only ever refused a duplicate that was still OPEN. At most two
distinct trades were in there. The win rate was one trade counted six times, and the
capital return was the same trade's P&L multiplied by six.

A duplicated row does not overstate a result slightly. It multiplies whichever way that
trade happened to go, so a book like this is equally capable of reporting a catastrophe
that never happened.

Beside it sat the second problem, visible in the arithmetic: a row losing Rs 0.96 per unit
booked Rs 21,422 of loss, which is a quantity of about 22,300 on an account of Rs 2 lakh.
A wrong lot does not announce itself either - it scales every rupee figure in the table
while leaving every percentage looking reasonable.

THE RULE
Refuse the summary, not the data. The rows stay visible, because he needs to see what is
in there. What is withheld is the win rate and the capital return - the two numbers that
read as a verdict. A screen that shows the rows and says "this cannot be scored yet, here
is why" is more useful than one that prints 86%.
"""


def _distinct(trades):
    """A trade's identity: same name, same entry premium, same day is one trade."""
    seen = set()
    for t in trades or []:
        seen.add((t.get("name"),
                  round(float(t.get("premium_in") or 0), 2),
                  str(t.get("opened") or "")[:10]))
    return seen


def audit(book, capital=None):
    """{'trustworthy': bool, 'reasons': [...], 'rows', 'distinct'} for a paper book.

    Every reason names the thing to fix, because "this book is unreliable" without the
    cause is a dead end - and the causes here are each one command away from fixed.
    """
    closed = list((book or {}).get("closed") or [])
    rows = len(closed)
    distinct = len(_distinct(closed))
    reasons = []

    if rows and distinct < rows:
        reasons.append(
            f"{rows} rows but only {distinct} distinct trades — the same signal is "
            f"recorded more than once. A win rate over duplicated rows multiplies one "
            f"outcome. Fix: `python paper.py --reset` after the lot is right.")

    # A position that swallowed the account. Derived from the row's OWN numbers rather
    # than from config, so it still fires when config is the thing that is wrong.
    #
    # The threshold is half the account, and it was set from a real row rather than a
    # feeling: 22,315 units at Rs 8.4 is Rs 187,446 of premium on Rs 2 lakh - 94% of
    # everything in one option. An earlier version tested against 1.5x capital, which is
    # arithmetically impossible to reach and therefore never fired. A guard whose
    # threshold cannot be crossed is not a loose guard, it is decoration.
    #
    # It says CHECK the lot rather than "the lot is wrong": on an expensive name a single
    # legitimate lot can approach half a small account, and this is the summary being
    # withheld, not the trade being refused.
    if capital:
        for t in closed:
            qty = float(t.get("qty") or 0)
            prem = float(t.get("premium_in") or 0)
            if qty and prem and (qty * prem) > 0.5 * float(capital):
                reasons.append(
                    f"{t.get('name')}: {int(qty)} x Rs {prem} = Rs {qty*prem:,.0f} of "
                    f"premium — {100*qty*prem/float(capital):.0f}% of the account in one "
                    f"position. If the lot is wrong it scales every rupee figure here "
                    f"while leaving the percentages looking reasonable. "
                    f"Check: Tools → Lot Audit.")
                break

    # A book measuring the model rather than the market.
    est = sum(1 for t in closed if (t.get("premium_source") or "") == "estimated")
    if est:
        reasons.append(f"{est} row(s) entered at an ESTIMATED premium, not a quoted one — "
                       f"those measure the pricing model, not the market.")

    if rows and rows < 20:
        reasons.append(f"only {distinct} distinct trades — too few to read a win rate "
                       f"from at all. Twenty is the point where the number starts "
                       f"meaning something.")

    return {"trustworthy": not reasons, "reasons": reasons,
            "rows": rows, "distinct": distinct}


def verdict_line(a):
    """One line for the top of the scorecard."""
    if a["trustworthy"]:
        return f"{a['distinct']} distinct trades — scored."
    return (f"NOT SCORED — {a['rows']} rows, {a['distinct']} distinct. "
            f"{len(a['reasons'])} reason(s) below.")
