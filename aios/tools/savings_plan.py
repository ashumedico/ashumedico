"""
savings_plan.py  —  give it goals, it tells you what to put aside each month.

    python savings_plan.py 2027-04-30=130000 2026-12-01=200000
    python savings_plan.py 2027-04-30=130000 --have 25000 --rate 6.5

WHAT IT REFUSES TO SMOOTH OVER
A single "you need Rs X a month" is the wrong answer whenever goals overlap, and goals
almost always overlap. Two targets four months apart are not two separate plans - for the
months they share, the money comes out of the SAME salary, and the number that decides
whether the plan is possible is the total in the heaviest month, not the average.

So the headline is the month-by-month schedule. The per-goal figures are shown too, but
they are inputs to that, not the answer.

TWO READINGS OF THE SAME GOALS, both shown, because they differ by a lot:
  SEPARATE   each goal is spent when it arrives (a purchase, a fee, a trip). Saving for
             the later goal has to run alongside, not after.
  ONE POT    the money keeps accumulating and the later target includes the earlier one.
             Cheaper, and only true if the first goal is not actually spent.

Nothing is annualised, nothing is rounded up into comfort. Rs 0 assumed in hand and 0%
return unless told otherwise, because assuming either would quietly reduce the monthly
figure he acts on.
"""
import argparse
import sys
from datetime import date

C = {"h": "\033[96m", "g": "\033[92m", "y": "\033[93m", "r": "\033[91m",
     "d": "\033[90m", "b": "\033[1m", "x": "\033[0m"}


def months_between(a, b):
    """Whole monthly deposits from a (inclusive) up to and including b.

    Counted as deposits, not as elapsed time. A goal on 1 Dec with today 5 Sep gets three
    deposits (5 Sep, 5 Oct, 5 Nov) - the 5 Dec one lands after the money is needed, and
    counting it would understate every monthly figure by a third.
    """
    n = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        n -= 1
    return max(n + 1, 1)


def monthly_for(target, n, have=0.0, annual_rate=0.0):
    """What to set aside each month to reach `target` in `n` deposits."""
    r = float(annual_rate) / 100.0 / 12.0
    if r <= 0:
        return max(0.0, (target - have) / n)
    grown = have * (1 + r) ** n
    return max(0.0, (target - grown) * r / ((1 + r) ** n - 1))


def parse_goal(s):
    d, _, amt = s.partition("=")
    y, m, day = (int(x) for x in d.split("-"))
    return date(y, m, day), float(amt)


def plan(goals, today=None, have=0.0, rate=0.0, mode="separate"):
    """[{goal, amount, deposits, monthly}] plus the month-by-month load."""
    today = today or date.today()
    goals = sorted(goals)
    rows, running = [], 0.0
    for when, amt in goals:
        n = months_between(today, when)
        # ONE POT: the later target already contains the earlier one, so only the gap is
        # newly funded. SEPARATE: the earlier goal is spent, so the later one is funded in
        # full, alongside.
        need = amt - running if mode == "pot" else amt
        start_have = have if not rows else 0.0
        rows.append({"date": when, "amount": amt, "funding": max(need, 0.0),
                     "deposits": n,
                     "monthly": monthly_for(max(need, 0.0), n, start_have, rate)})
        if mode == "pot":
            running = amt
    return rows


def load_by_month(rows, today=None):
    """{month -> total} — what leaves the account each month with all goals running."""
    today = today or date.today()
    last = max(r["date"] for r in rows)
    out, y, m = [], today.year, today.month
    while (y, m) <= (last.year, last.month):
        tot = 0.0
        for r in rows:
            # a goal draws money in every month from now until the month before it lands
            if (y, m) < (r["date"].year, r["date"].month) or \
               ((y, m) == (r["date"].year, r["date"].month) and r["date"].day > today.day):
                if (y, m) >= (today.year, today.month):
                    tot += r["monthly"]
        out.append((date(y, m, 1), tot))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def render(rows, load, today, rate, mode):
    tag = "SEPARATE (each goal is spent)" if mode == "separate" else "ONE POT (accumulating)"
    print(f"\n  {C['b']}SAVINGS PLAN{C['x']}  {C['d']}from {today}  ·  {tag}"
          f"  ·  {rate}% return assumed{C['x']}")
    print("  " + "-" * 68)
    print(f"  {'GOAL DATE':<13}{'TARGET':>12}{'DEPOSITS':>10}{'PER MONTH':>14}")
    print("  " + "-" * 68)
    for r in rows:
        col = C["g"] if r["monthly"] < 20000 else C["y"] if r["monthly"] < 50000 else C["r"]
        print(f"  {str(r['date']):<13}{'Rs ' + format(r['amount'], ',.0f'):>12}"
              f"{r['deposits']:>10}{col}{'Rs ' + format(r['monthly'], ',.0f'):>14}{C['x']}")
    print("  " + "-" * 68)
    peak = max(t for _, t in load) if load else 0
    print(f"\n  {C['b']}WHAT ACTUALLY LEAVES THE ACCOUNT{C['x']}  "
          f"{C['d']}(overlapping goals add up){C['x']}")
    for when, tot in load:
        col = C["g"] if tot < 20000 else C["y"] if tot < 50000 else C["r"]
        bar = "#" * int(28 * tot / peak) if peak else ""
        print(f"  {when:%b %Y}  {col}Rs {tot:>9,.0f}{C['x']}  {C['d']}{bar}{C['x']}")
    print(f"\n  {C['b']}Heaviest month: Rs {peak:,.0f}{C['x']} — this is the number that "
          f"decides\n  whether the plan is possible, not the average.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("goals", nargs="+", help="YYYY-MM-DD=AMOUNT")
    ap.add_argument("--have", type=float, default=0.0, help="already saved")
    ap.add_argument("--rate", type=float, default=0.0, help="annual %% return")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for what-ifs")
    ap.add_argument("--mode", choices=["separate", "pot", "both"], default="both")
    a = ap.parse_args()

    today = date(*(int(x) for x in a.today.split("-"))) if a.today else date.today()
    try:
        goals = [parse_goal(g) for g in a.goals]
    except ValueError as e:
        # A date that does not exist is a typo worth naming, not a crash to decode.
        print(f"\n  {C['r']}Bad goal: {e}{C['x']}")
        print(f"  {C['d']}Use YYYY-MM-DD=AMOUNT. Check the day exists — April has 30.{C['x']}\n")
        return 2
    past = [d for d, _ in goals if d <= today]
    if past:
        print(f"\n  {C['r']}Goal date {past[0]} is not in the future.{C['x']}\n")
        return 2

    for mode in (["separate", "pot"] if a.mode == "both" else [a.mode]):
        rows = plan(goals, today, a.have, a.rate, mode)
        render(rows, load_by_month(rows, today), today, a.rate, mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
