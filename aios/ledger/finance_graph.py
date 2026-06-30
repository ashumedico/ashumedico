#!/usr/bin/env python3
"""Year-wise finance graph: salary vs expenses vs loan (prepay vs no-prepay)."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import calendar
from datetime import datetime

# ── CONFIG (real numbers) ──
L1_BAL, L2_BAL = 1_48_00_000, 21_60_000
L1_RATE, L2_RATE = 0.071, 0.0785
L1_EMI, L2_BASE = 1_20_000, 20_000
EXTRA = 20_000              # extra/month into L2 (prepay scenario)
BONUS, BONUS_M = 5_50_000, 3
START = datetime(2026, 7, 1)
NET_SALARY_YR = 45_00_000   # household net take-home (assumption, new regime, incl variable)
EXPENSES_YR   = 12_00_000   # <= Rs 1L/month (user input, upper bound)

def add_m(dt, n):
    m = dt.month-1+n; y = dt.year+m//12; m = m%12+1
    return datetime(y, m, min(dt.day, calendar.monthrange(y, m)[1]))

def simulate(prepay):
    l1, l2 = float(L1_BAL), float(L2_BAL)
    out = {}          # year -> loan outflow
    bal = {}          # year -> year-end total balance
    for k in range(1, 600):
        dt = add_m(START, k-1); yr = dt.year
        i1, i2 = l1*L1_RATE/12, l2*L2_RATE/12
        bonus = BONUS if (prepay and dt.month==BONUS_M and k>1) else 0
        pay = 0; sp = 0
        if l2 > 0:
            p2 = L2_BASE + (EXTRA if prepay else 0) + bonus
            if p2 > l2+i2: sp = p2-(l2+i2); p2 = l2+i2
            l2 = max(0, l2-(p2-i2)); pay += p2
        if l1 > 0:
            p1 = L1_EMI + (sp if prepay else 0)
            if l2<=0 and prepay: p1 = (L1_EMI+L2_BASE+EXTRA) + (bonus if l2<=0 else 0)
            p1 = min(p1, l1+i1)
            l1 = max(0, l1-(p1-i1)); pay += p1
        out[yr] = out.get(yr, 0) + pay
        bal[yr] = l1+l2
        if l1<=1 and l2<=1: break
    return out, bal

out_pre, bal_pre = simulate(True)
out_no,  bal_no  = simulate(False)
end_pre = max(bal_pre); end_no = max(bal_no)

# ── FIGURE ──
plt.rcParams.update({'font.size':10, 'font.family':'DejaVu Sans'})
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 11), height_ratios=[1.05,1])
fig.suptitle("Aashish & Kalyani — Year-wise Money Map", fontsize=19, fontweight='bold', color='#0d1b4c', y=0.985)
fig.text(0.5, 0.945, "Salary vs Expenses vs Loan outflow  •  Prepayment vs No-prepayment  •  rates L1 7.1% / L2 7.85%",
         ha='center', fontsize=10.5, color='#1565c0')

def lakh(x, _): return f"{x/1e5:.0f}L" if x<1e7 else f"{x/1e7:.2f}Cr"

# Panel 1: year-wise grouped bars 2026-2038
yrs = list(range(2026, 2039))
import numpy as np
x = np.arange(len(yrs)); w = 0.38
emi_pre = [out_pre.get(y,0) for y in yrs]
emi_no  = [out_no.get(y,0) for y in yrs]
ax1.bar(x-w/2, emi_no,  w, label='Loan outflow — NO prepayment', color='#c62828', alpha=0.9)
ax1.bar(x+w/2, emi_pre, w, label='Loan outflow — WITH prepayment', color='#2e7d32', alpha=0.9)
ax1.axhline(NET_SALARY_YR, color='#1565c0', lw=2.2, ls='-', label='Net salary (take-home) ~45L/yr')
ax1.axhline(EXPENSES_YR, color='#f57c00', lw=2.2, ls='--', label='Living expenses <=12L/yr')
ax1.fill_between([-0.5, len(yrs)-0.5], EXPENSES_YR, NET_SALARY_YR, color='#1565c0', alpha=0.05)
ax1.set_xticks(x); ax1.set_xticklabels(yrs)
ax1.set_xlim(-0.6, len(yrs)-0.4)
ax1.yaxis.set_major_formatter(FuncFormatter(lakh))
ax1.set_ylabel("Rs per year")
ax1.set_title("Annual cash flow — the gap between the salary line and the bars is your yearly surplus",
              fontsize=11, color='#0d1b4c', pad=8)
ax1.legend(loc='upper right', fontsize=8.5, framealpha=0.95, ncol=1)
ax1.grid(axis='y', alpha=0.25)
# annotate prepay loan ends
ax1.annotate("Loan GONE\n(Feb 2036)", xy=(yrs.index(2036)+w/2, out_pre.get(2036,0)),
             xytext=(yrs.index(2036)-1.4, NET_SALARY_YR*0.62), fontsize=8.5, color='#2e7d32', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#2e7d32'))
ax1.annotate("After payoff: ~33L/yr\nbecomes free surplus", xy=(yrs.index(2037)+0.4, 1_00_000),
             xytext=(yrs.index(2036)+0.7, NET_SALARY_YR*0.30), fontsize=8.5, color='#2e7d32', fontweight='bold')

# Panel 2: loan balance lines full horizon
def series(bal):
    ys = sorted(bal); return ys, [bal[y] for y in ys]
yp, vp = series(bal_pre); yn, vn = series(bal_no)
ax2.plot(yn, vn, color='#c62828', lw=2.6, marker='o', ms=3, label=f'NO prepayment — ends ~{yn[-1]}')
ax2.plot(yp, vp, color='#2e7d32', lw=2.6, marker='o', ms=3, label=f'WITH prepayment — ends Feb 2036')
ax2.fill_between(yp, vp, color='#2e7d32', alpha=0.07)
ax2.yaxis.set_major_formatter(FuncFormatter(lakh))
ax2.set_ylabel("Outstanding loan balance")
ax2.set_xlabel("Year")
ax2.set_title("Loan balance over time — prepayment kills it ~8 years sooner (2036 vs 2044)", fontsize=11, color='#0d1b4c', pad=8)
ax2.legend(loc='upper right', fontsize=9, framealpha=0.95)
ax2.grid(alpha=0.25)
ax2.set_ylim(bottom=0)

fig.text(0.5, 0.012,
   "Assumptions: net household take-home ~Rs 45L/yr (new regime, incl. variable); living expenses at the <=Rs 1L/month cap. "
   "Floating rates. Surplus (~26-30L/yr) shows the Rs 50K crunch is a LIQUIDITY/timing gap, not an income gap.",
   ha='center', fontsize=8, color='#6b7280', style='italic')

plt.tight_layout(rect=[0, 0.025, 1, 0.94])
plt.savefig('aios/ledger/finance-year-wise-graph.png', dpi=150, bbox_inches='tight')
print("Saved PNG")
print(f"No-prepay ends ~{yn[-1]} | Prepay ends {yp[-1]} (Feb 2036)")
print(f"Annual surplus (with prepay, during loan): ~{(NET_SALARY_YR-EXPENSES_YR-out_pre.get(2027,0))/1e5:.1f}L")
print(f"Annual surplus after payoff: ~{(NET_SALARY_YR-EXPENSES_YR)/1e5:.1f}L")
