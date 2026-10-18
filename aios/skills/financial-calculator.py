#!/usr/bin/env python3
"""
T-Bone Financial Calculator — Standalone
Run: python3 financial-calculator.py
Update the CONFIG section below with current numbers, then run.
No AI needed — pure math.
"""
import math
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIG — UPDATE THESE NUMBERS WHENEVER YOU RE-RUN
# ═══════════════════════════════════════════════════════════════

CONFIG = {
    # --- PEOPLE ---
    "person_1": {
        "name": "Aashish",
        "age": 37,
        "ctc": 4000000,          # Annual CTC
        "variable": 550000,       # Variable component (uncertain)
        "basic_pct": 0.40,        # Basic as % of CTC
        "retirement_age": 60,
    },
    "person_2": {
        "name": "Kalyani",
        "age": 35,
        "ctc": 2100000,
        "variable": 0,
        "basic_pct": 0.40,
        "retirement_age": 60,
    },

    # --- LOANS (update outstanding from YONO) ---
    "loan_1": {
        "name": "Loan 1 (****4054)",
        "outstanding": 14799767,  # UPDATE from YONO
        "annual_rate": 8.0,
        "current_emi": 160000,
        "required_emi": 140000,   # Bank's minimum
        "original_tenure_years": 30,
    },
    "loan_2": {
        "name": "Loan 2 (****3321)",
        "outstanding": 2163142,   # UPDATE from YONO
        "annual_rate": 8.0,
        "current_emi": 15872,
        "original_tenure_years": 30,
    },
    "loan_split": 0.50,  # 50:50 joint

    # --- KILL STRATEGY ---
    "kill_strategy": {
        "loan2_monthly_attack": 25000,
        "annual_bonus_total": 160000,   # Kalyani 1L + Aashish 60K
        "bonus_month": 3,               # Month of year for bonus dump (1-12)
        "variable_dump_month": 9,       # When variable arrives
        "variable_hit_rate": 0.50,      # % of years variable actually comes
    },

    # --- POST-DEBT INVESTING ---
    "sip_annual_return": 0.12,   # Equity MF long-term
    "epf_annual_return": 0.0825, # EPF interest rate
    "inflation_rate": 0.06,
    "safe_withdrawal_rate": 0.04,

    # --- EXPENSES (monthly) ---
    "monthly_expenses": {
        "household": 50000,
        "credit_cards": 40000,
        "child": 15000,
        "transport": 10000,
        "insurance": 5000,
        "misc": 15000,
    }
}

# ═══════════════════════════════════════════════════════════════
# TAX ENGINE — India FY 2025-26
# ═══════════════════════════════════════════════════════════════

def ctc_to_gross(ctc, basic_pct, variable=0):
    basic = ctc * basic_pct
    epf_employer = basic * 0.12
    gratuity = basic * 0.0481
    gross = ctc - epf_employer - gratuity
    gross_no_var = gross - variable
    epf_employee = epf_employer  # employee matches employer
    return {
        "gross_with_var": gross,
        "gross_no_var": gross_no_var,
        "basic": basic,
        "epf_employer": epf_employer,
        "epf_employee": epf_employee,
        "gratuity": gratuity,
    }

def new_regime_tax(gross):
    std = 75000
    taxable = max(0, gross - std)
    slabs = [(400000,0),(800000,0.05),(1200000,0.10),(1600000,0.15),
             (2000000,0.20),(2400000,0.25),(float('inf'),0.30)]
    tax = 0
    prev = 0
    for limit, rate in slabs:
        if taxable <= prev: break
        tax += (min(taxable, limit) - prev) * rate
        prev = limit
    if taxable <= 1200000:
        tax = max(0, tax - 60000)
    cess = tax * 0.04
    return {"taxable": taxable, "tax": tax + cess, "rebate_87a": taxable <= 1200000}

def old_regime_tax(gross, sec24b=0, sec80c_extra=0, epf=0):
    std = 50000
    total_80c = min(epf + sec80c_extra, 150000)
    s24b = min(sec24b, 200000)
    taxable = max(0, gross - std - total_80c - s24b)
    tax = 0
    if taxable > 1000000:
        tax += (taxable - 1000000) * 0.30
        rem = 1000000
    else:
        rem = taxable
    if rem > 500000:
        tax += (rem - 500000) * 0.20
        rem = 500000
    if rem > 250000:
        tax += (rem - 250000) * 0.05
    if taxable <= 500000:
        tax = max(0, tax - 12500)
    cess = tax * 0.04
    return {"taxable": taxable, "tax": tax + cess, "sec80c": total_80c, "sec24b": s24b}

# ═══════════════════════════════════════════════════════════════
# LOAN ENGINE
# ═══════════════════════════════════════════════════════════════

def calc_emi(principal, annual_rate, tenure_months):
    r = annual_rate / 12 / 100
    if r == 0:
        return principal / tenure_months
    return principal * r * (1+r)**tenure_months / ((1+r)**tenure_months - 1)

def months_to_clear(principal, annual_rate, emi):
    r = annual_rate / 12 / 100
    if emi <= principal * r:
        return 9999
    return math.ceil(math.log(emi / (emi - principal * r)) / math.log(1 + r))

def simulate_loan(principal, annual_rate, monthly_payment,
                   annual_lump=0, lump_month=3,
                   variable=0, var_month=9, var_hit_rate=1.0,
                   max_months=600):
    r = annual_rate / 12 / 100
    bal = principal
    total_paid = 0
    total_int = 0
    months = 0
    yearly = []

    while bal > 0 and months < max_months:
        months += 1
        interest = bal * r
        if monthly_payment >= bal + interest:
            total_paid += bal + interest
            total_int += interest
            bal = 0
        else:
            p = monthly_payment - interest
            if p <= 0:
                return None
            bal -= p
            total_paid += monthly_payment
            total_int += interest

        if annual_lump > 0 and months % 12 == lump_month % 12 and bal > 0:
            dump = min(annual_lump, bal)
            bal -= dump
            total_paid += dump

        if variable > 0 and months % 12 == var_month % 12 and bal > 0:
            effective_var = variable * var_hit_rate
            dump = min(effective_var, bal)
            bal -= dump
            total_paid += dump

        if months % 12 == 0 or bal <= 0:
            yearly.append({
                "year": math.ceil(months/12),
                "month": months,
                "balance": max(0, bal),
                "total_paid": total_paid,
                "total_interest": total_int,
            })

    baseline_emi = calc_emi(principal, annual_rate, 360)
    baseline_interest = baseline_emi * 360 - principal

    return {
        "months": months,
        "years": months / 12,
        "total_paid": total_paid,
        "total_interest": total_int,
        "interest_saved": baseline_interest - total_int,
        "yearly": yearly,
    }

def fmt(amount):
    if abs(amount) >= 10000000:
        return f"₹{amount/10000000:.2f} Cr"
    elif abs(amount) >= 100000:
        return f"₹{amount/100000:.1f}L"
    else:
        return f"₹{amount:,.0f}"

# ═══════════════════════════════════════════════════════════════
# MAIN REPORT
# ═══════════════════════════════════════════════════════════════

def run():
    c = CONFIG
    p1 = c["person_1"]
    p2 = c["person_2"]
    l1 = c["loan_1"]
    l2 = c["loan_2"]
    ks = c["kill_strategy"]

    print("=" * 70)
    print(f"  T-BONE FINANCIAL REPORT — {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 70)

    # ── CTC BREAKDOWN ──
    g1 = ctc_to_gross(p1["ctc"], p1["basic_pct"], p1["variable"])
    g2 = ctc_to_gross(p2["ctc"], p2["basic_pct"], p2["variable"])

    print(f"\n  CTC BREAKDOWN")
    print(f"  {'─' * 60}")
    print(f"  {'':25} {p1['name']:>14} {p2['name']:>14}")
    print(f"  {'CTC':<25} {fmt(p1['ctc']):>14} {fmt(p2['ctc']):>14}")
    print(f"  {'Variable':<25} {fmt(p1['variable']):>14} {fmt(p2['variable']):>14}")
    print(f"  {'Gross (no var)':<25} {fmt(g1['gross_no_var']):>14} {fmt(g2['gross_no_var']):>14}")
    print(f"  {'EPF employee':<25} {fmt(g1['epf_employee']):>14} {fmt(g2['epf_employee']):>14}")

    # ── TAX COMPARISON ──
    total_interest = (l1["outstanding"] + l2["outstanding"]) * l1["annual_rate"] / 100
    each_interest = total_interest * c["loan_split"]
    total_emi_annual = (l1["current_emi"] + l2["current_emi"]) * 12
    each_principal = (total_emi_annual - total_interest) * c["loan_split"]

    print(f"\n\n{'█' * 70}")
    print(f"  TAX REGIME COMPARISON — NEW vs OLD")
    print(f"{'█' * 70}")

    for person, g in [(p1, g1), (p2, g2)]:
        gross = g["gross_no_var"]
        n = new_regime_tax(gross)
        o_with = old_regime_tax(gross, sec24b=each_interest,
                                sec80c_extra=each_principal, epf=g["epf_employee"])
        o_without = old_regime_tax(gross, epf=g["epf_employee"])
        hl_benefit = o_without["tax"] - o_with["tax"]

        print(f"\n  {person['name']} — Gross {fmt(gross)}")
        print(f"  {'─' * 55}")
        print(f"  {'Regime':<35} {'Tax':>12} {'Verdict':>14}")
        print(f"  {'NEW REGIME':<35} {fmt(n['tax']):>12}", end="")
        print(f" {'★ WINNER' if n['tax'] <= o_with['tax'] else '':>14}")
        print(f"  {'OLD + home loan':<35} {fmt(o_with['tax']):>12}", end="")
        print(f" {'★ WINNER' if o_with['tax'] < n['tax'] else '':>14}")
        print(f"  {'Home loan benefit in old':<35} {fmt(hl_benefit):>12}")

        diff = o_with["tax"] - n["tax"]
        if diff > 0:
            print(f"  → New regime saves {fmt(diff)}/year. Home loan benefit IRRELEVANT.")
        else:
            print(f"  → Old regime saves {fmt(-diff)}/year WITH home loan.")
            print(f"    But you pay {fmt(each_interest)} interest to save {fmt(hl_benefit)} tax.")
            if each_interest > hl_benefit:
                print(f"    NET LOSS: {fmt(each_interest - hl_benefit)}. Still not worth keeping loan.")

        if n.get("rebate_87a"):
            print(f"  ⚡ 87A rebate applies — effectively ZERO tax in new regime!")

    # ── MONTHLY CASH FLOW ──
    n1 = new_regime_tax(g1["gross_no_var"])
    n2 = new_regime_tax(g2["gross_no_var"])
    m1_net = (g1["gross_no_var"] - g1["epf_employee"] - n1["tax"]) / 12
    m2_net = (g2["gross_no_var"] - g2["epf_employee"] - n2["tax"]) / 12
    household_net = m1_net + m2_net
    total_emi = l1["current_emi"] + l2["current_emi"]
    emi_ratio = total_emi / household_net * 100

    print(f"\n\n{'█' * 70}")
    print(f"  MONTHLY CASH FLOW (new regime, no variable)")
    print(f"{'█' * 70}")
    print(f"\n  {p1['name']} in-hand: {fmt(m1_net)}/month")
    print(f"  {p2['name']} in-hand: {fmt(m2_net)}/month")
    print(f"  Household:      {fmt(household_net)}/month")
    print(f"  Total EMI:      {fmt(total_emi)}/month")
    print(f"  EMI ratio:      {emi_ratio:.0f}%", end="")
    if emi_ratio > 50: print(" ← DANGER")
    elif emi_ratio > 40: print(" ← STRESSED")
    else: print(" ← OK")
    print(f"  After EMI:      {fmt(household_net - total_emi)}/month")

    total_expenses = sum(c["monthly_expenses"].values())
    after_everything = household_net - total_emi - total_expenses
    print(f"  Expenses:       {fmt(total_expenses)}/month")
    print(f"  Savings:        {fmt(after_everything)}/month ({after_everything/household_net*100:.0f}%)")

    # ── LOAN KILL STRATEGIES ──
    mr1 = l1["annual_rate"] / 12 / 100
    mr2 = l2["annual_rate"] / 12 / 100

    print(f"\n\n{'█' * 70}")
    print(f"  LOAN 2 KILL STRATEGIES — {l2['name']}")
    print(f"  Outstanding: {fmt(l2['outstanding'])} @ {l2['annual_rate']}%")
    print(f"{'█' * 70}")

    baseline_emi = calc_emi(l2["outstanding"], l2["annual_rate"],
                            l2["original_tenure_years"] * 12)
    baseline_interest = baseline_emi * l2["original_tenure_years"] * 12 - l2["outstanding"]

    print(f"\n  Bank's plan: {fmt(baseline_emi)}/mo × {l2['original_tenure_years']}yr = {fmt(baseline_interest)} interest")

    scenarios = [
        ("Bank minimum only", baseline_emi, 0, 0, 1.0),
        ("₹20K/month", 20000, 0, 0, 1.0),
        ("₹25K/month", 25000, 0, 0, 1.0),
        ("₹35K/month", 35000, 0, 0, 1.0),
        ("₹50K/month (blitz)", 50000, 0, 0, 1.0),
        ("Hybrid (no variable)", ks["loan2_monthly_attack"],
         ks["annual_bonus_total"], 0, 1.0),
        ("Hybrid + variable 50%", ks["loan2_monthly_attack"],
         ks["annual_bonus_total"], p1["variable"], 0.5),
        ("Hybrid + variable 100%", ks["loan2_monthly_attack"],
         ks["annual_bonus_total"], p1["variable"], 1.0),
    ]

    print(f"\n  {'Strategy':<30} {'Months':>8} {'Interest':>12} {'Saved':>12}")
    print(f"  {'─'*30} {'─'*8} {'─'*12} {'─'*12}")

    hybrid_result = None
    for name, monthly, bonus, var, var_rate in scenarios:
        r = simulate_loan(l2["outstanding"], l2["annual_rate"], monthly,
                         annual_lump=bonus, lump_month=ks["bonus_month"],
                         variable=var, var_month=ks["variable_dump_month"],
                         var_hit_rate=var_rate)
        if r:
            saved_str = fmt(r["interest_saved"]) if r["interest_saved"] > 0 else "—"
            print(f"  {name:<30} {r['months']:>8} {fmt(r['total_interest']):>12} {saved_str:>12}")
            if "Hybrid (no var" in name:
                hybrid_result = r

    # ── YEAR-BY-YEAR (recommended strategy) ──
    if hybrid_result:
        print(f"\n  HYBRID KILL — YEAR BY YEAR:")
        print(f"  {'Year':<6} {'Balance':>14} {'Paid':>14} {'Interest':>12}")
        print(f"  {'─'*6} {'─'*14} {'─'*14} {'─'*12}")
        for y in hybrid_result["yearly"]:
            if y["balance"] > 0:
                print(f"  {y['year']:<6} {fmt(y['balance']):>14} {fmt(y['total_paid']):>14} {fmt(y['total_interest']):>12}")
            else:
                done_str = "DONE ✓"
                print(f"  {y['year']:<6} {done_str:>14} {fmt(y['total_paid']):>14} {fmt(y['total_interest']):>12}")

    # ── FULL TIMELINE TO DEBT-FREE ──
    print(f"\n\n{'█' * 70}")
    print(f"  DEBT-FREE TIMELINE")
    print(f"{'█' * 70}")

    # Phase 1: Kill Loan 2
    l2_months = hybrid_result["months"] if hybrid_result else 70

    # Loan 1 balance after Phase 1 (at required EMI)
    bal_l1 = l1["outstanding"]
    for m in range(l2_months):
        interest = bal_l1 * mr1
        bal_l1 -= (l1["required_emi"] - interest)

    # Phase 2: Snowball into Loan 1
    phase2_emi = l1["required_emi"] + ks["loan2_monthly_attack"] + int(baseline_emi)
    bal = bal_l1
    phase2_months = 0
    for m in range(600):
        interest = bal * mr1
        bal -= (phase2_emi - interest)
        if (m + 1) % 12 == ks["bonus_month"] and bal > 0:
            bal -= min(ks["annual_bonus_total"], bal)
        phase2_months += 1
        if bal <= 0:
            break

    total_months = l2_months + phase2_months
    debt_free_age = p1["age"] + total_months / 12
    invest_years = p1["retirement_age"] - debt_free_age

    print(f"\n  Phase 1 — Kill Loan 2:")
    print(f"    Attack: {fmt(ks['loan2_monthly_attack'])}/mo + {fmt(ks['annual_bonus_total'])}/yr bonus")
    print(f"    Duration: {l2_months} months ({l2_months/12:.1f} years)")
    print(f"    {p1['name']} age at completion: ~{p1['age'] + l2_months/12:.0f}")

    print(f"\n  Phase 2 — Kill Loan 1 (snowball):")
    print(f"    Loan 1 balance at start: {fmt(bal_l1)}")
    print(f"    Attack: {fmt(phase2_emi)}/mo + {fmt(ks['annual_bonus_total'])}/yr bonus")
    print(f"    Duration: {phase2_months} months ({phase2_months/12:.1f} years)")

    print(f"\n  TOTAL: Debt-free in {total_months} months ({total_months/12:.1f} years)")
    print(f"  Debt-free age: ~{debt_free_age:.0f}")

    # ── RETIREMENT PROJECTION ──
    print(f"\n\n{'█' * 70}")
    print(f"  RETIREMENT PROJECTION")
    print(f"{'█' * 70}")

    # EPF corpus
    a_epf_annual = g1["epf_employee"] * 2
    k_epf_annual = g2["epf_employee"] * 2
    years_retire = p1["retirement_age"] - p1["age"]

    a_epf = 0
    k_epf = 0
    for y in range(years_retire):
        a_epf = (a_epf + a_epf_annual) * (1 + c["epf_annual_return"])
        k_epf = (k_epf + k_epf_annual) * (1 + c["epf_annual_return"])

    print(f"\n  EPF at {p1['retirement_age']}:")
    print(f"    {p1['name']}: {fmt(a_epf)} ({fmt(a_epf_annual)}/yr × {years_retire}yr @{c['epf_annual_return']*100}%)")
    print(f"    {p2['name']}: {fmt(k_epf)} ({fmt(k_epf_annual)}/yr × {years_retire+2}yr @{c['epf_annual_return']*100}%)")
    epf_total = a_epf + k_epf
    print(f"    Combined: {fmt(epf_total)}")

    # Post-debt SIP
    invest_months = max(0, int(invest_years * 12))
    sip_monthly = phase2_emi
    mr_sip = c["sip_annual_return"] / 12
    if invest_months > 0 and mr_sip > 0:
        sip_corpus = sip_monthly * (((1+mr_sip)**invest_months - 1) / mr_sip) * (1+mr_sip)
    else:
        sip_corpus = 0

    print(f"\n  Post-debt SIP:")
    print(f"    Monthly: {fmt(sip_monthly)} (freed EMI)")
    print(f"    Return: {c['sip_annual_return']*100}% p.a.")
    print(f"    Duration: {invest_years:.0f} years")
    print(f"    Corpus: {fmt(sip_corpus)}")

    total_corpus = epf_total + sip_corpus
    monthly_retire = total_corpus * c["safe_withdrawal_rate"] / 12
    total_years_ahead = years_retire
    real_value = monthly_retire / (1 + c["inflation_rate"]) ** total_years_ahead

    print(f"\n  ┌─────────────────────────────────────────────┐")
    print(f"  │  TOTAL CORPUS AT {p1['retirement_age']}:  {fmt(total_corpus):>20}  │")
    print(f"  │  EPF:             {fmt(epf_total):>20}  │")
    print(f"  │  SIP:             {fmt(sip_corpus):>20}  │")
    print(f"  │                                             │")
    print(f"  │  Monthly income ({c['safe_withdrawal_rate']*100:.0f}% SWR): {fmt(monthly_retire):>13}  │")
    print(f"  │  In today's money:        {fmt(real_value):>13}  │")
    print(f"  └─────────────────────────────────────────────┘")

    # ── CURRENT vs RECOMMENDED ──
    print(f"\n\n{'═' * 70}")
    print(f"  CURRENT PATTERN vs RECOMMENDED")
    print(f"{'═' * 70}")

    # Current: L2 at bank minimum
    m_l2_current = months_to_clear(l2["outstanding"], l2["annual_rate"], baseline_emi)
    current_debt_free_age = p1["age"] + max(
        months_to_clear(l1["outstanding"], l1["annual_rate"], l1["current_emi"]),
        m_l2_current
    ) / 12

    print(f"\n  {'Metric':<30} {'CURRENT':>16} {'RECOMMENDED':>16}")
    print(f"  {'─'*30} {'─'*16} {'─'*16}")
    print(f"  {'Loan 1 EMI':<30} {fmt(l1['current_emi']):>16} {fmt(l1['required_emi']):>16}")
    print(f"  {'Loan 2 EMI':<30} {fmt(int(baseline_emi)):>16} {fmt(ks['loan2_monthly_attack']):>16}")
    print(f"  {'Total monthly':<30} {fmt(l1['current_emi']+int(baseline_emi)):>16} {fmt(l1['required_emi']+ks['loan2_monthly_attack']):>16}")
    print(f"  {'Loan 2 cleared (age)':<30} {'~' + str(int(p1['age'] + m_l2_current/12)):>16} {'~' + str(int(p1['age'] + l2_months/12)):>16}")
    print(f"  {'Debt-free age':<30} {'~' + str(int(current_debt_free_age)):>16} {'~' + str(int(debt_free_age)):>16}")
    invest_current = max(0, p1["retirement_age"] - current_debt_free_age)
    print(f"  {'Years to invest':<30} {str(int(invest_current)):>16} {str(int(invest_years)):>16}")
    print(f"  {'Retirement corpus':<30} {'?':>16} {fmt(total_corpus):>16}")

    # ── ACTION ITEMS ──
    print(f"\n\n{'█' * 70}")
    print(f"  ACTION ITEMS — THIS WEEK")
    print(f"{'█' * 70}")
    print(f"""
  1. CONFIRM TAX REGIME: Both → New Regime (saves {fmt(247915)}/year combined)
  2. DROP Loan 1 EMI: {fmt(l1['current_emi'])} → {fmt(l1['required_emi'])} (call SBI/YONO)
  3. SET UP Loan 2 attack: {fmt(ks['loan2_monthly_attack'])}/month auto-debit
  4. CALENDAR bonus dumps: Feb (Kalyani) + Apr (Aashish) → Loan 2
  5. VARIABLE RULE: If ₹{p1['variable']/100000:.1f}L comes → 100% to Loan 2. Never budget it.
  6. RE-RUN this script every 6 months with updated YONO balances.
""")
    print("=" * 70)


if __name__ == "__main__":
    run()
