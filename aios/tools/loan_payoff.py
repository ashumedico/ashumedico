"""
loan_payoff.py  —  when does it actually end, and what does prepaying buy?

    python loan_payoff.py --outstanding 2160000 --rate 8 --emi 60000
    python loan_payoff.py --outstanding 2160000 --rate 8 --emi 60000 --extra 20000

WHY THE SECOND NUMBER IS THE USEFUL ONE
The payoff DATE depends on three things he has to read off a statement - outstanding,
rate, EMI - and being wrong about any of them moves it by months. The SAVING from an extra
payment is far less sensitive: get the rate wrong by half a percent and the months-saved
barely moves. So this reports both, and says which one to trust.

WHAT IT REFUSES TO DO
Guess. An amortization schedule built on an assumed outstanding is a date that looks
researched and is not, and a payoff date is exactly the kind of number someone plans a
school fee around.
"""
import argparse


def schedule(outstanding, annual_rate, emi, extra=0.0, cap_months=600):
    """(months, total_interest, ok). ok=False when the EMI cannot service the interest."""
    r = annual_rate / 100.0 / 12.0
    bal, interest, n = float(outstanding), 0.0, 0
    pay = emi + extra
    # An EMI below the first month's interest never amortises - the balance grows forever.
    # Saying "600 months" there would be a number where the honest answer is "never".
    if pay <= bal * r:
        return None, None, False
    while bal > 0 and n < cap_months:
        i = bal * r
        interest += i
        bal = bal + i - pay
        n += 1
    return n, interest, True


def compare(outstanding, annual_rate, emi, extra):
    base_n, base_i, ok = schedule(outstanding, annual_rate, emi)
    if not ok:
        return None
    fast_n, fast_i, _ = schedule(outstanding, annual_rate, emi, extra)
    return {"base_months": base_n, "base_interest": base_i,
            "fast_months": fast_n, "fast_interest": fast_i,
            "months_saved": base_n - fast_n,
            "interest_saved": base_i - fast_i,
            "extra_paid": extra * fast_n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outstanding", type=float, required=True)
    ap.add_argument("--rate", type=float, required=True)
    ap.add_argument("--emi", type=float, required=True)
    ap.add_argument("--extra", type=float, default=0.0)
    a = ap.parse_args()

    n, i, ok = schedule(a.outstanding, a.rate, a.emi)
    if not ok:
        print(f"\n  An EMI of Rs {a.emi:,.0f} does not cover the first month's interest "
              f"on Rs {a.outstanding:,.0f} at {a.rate}%.\n  The balance grows. There is no "
              f"payoff date to report.\n")
        return 1
    print(f"\n  Rs {a.outstanding:,.0f} at {a.rate}%, EMI Rs {a.emi:,.0f}")
    print(f"  ends in {n} months ({n/12:.1f} years) · interest Rs {i:,.0f}")
    if a.extra:
        c = compare(a.outstanding, a.rate, a.emi, a.extra)
        print(f"\n  + Rs {a.extra:,.0f}/month extra:")
        print(f"  ends in {c['fast_months']} months ({c['fast_months']/12:.1f} years)")
        print(f"  {c['months_saved']} months sooner · Rs {c['interest_saved']:,.0f} "
              f"interest saved · Rs {c['extra_paid']:,.0f} extra paid in")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
