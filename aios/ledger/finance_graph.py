#!/usr/bin/env python3
"""Year-wise finance graph: salary vs expenses vs loan (prepay vs no-prepay).
Income +5%/yr, expenses +6% inflation. Bonus ignored (variable)."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import calendar
from datetime import datetime

# ── CONFIG (real numbers) ──
L1_BAL, L2_BAL = 1_48_00_000, 21_60_000
L1_RATE, L2_RATE = 0.071, 0.0785
L1_EMI, L2_BASE = 1_20_000, 20_000
EXTRA = 20_000              # extra/month into L2 (prepay scenario)
BONUS = 0                  # bonus IGNORED — variable/subjective
BONUS_M = 3
START = datetime(2026, 7, 1)
NET_SALARY_YR = 36_00_000  # household net take-home, year 1 (after tax, EXCLUDING bonus)
EXPENSES_YR   = 12_00_000  # <= Rs 1L/month (user input, upper bound), year 1
INCOME_GROWTH = 0.05       # +5% / year average
INFLATION     = 0.06       # expenses grow with ~6% inflation

def add_m(dt, n):
    m = dt.month-1+n; y = dt.year+m//12; m = m%12+1
    return datetime(y, m, min(dt.day, calendar.monthrange(y, m)[1]))

def simulate(prepay):
    l1, l2 = float(L1_BAL), float(L2_BAL)
    out, bal = {}, {}
    end_dt = None
    for k in range(1, 700):
        dt = add_m(START, k-1); yr = dt.year
        i1, i2 = l1*L1_RATE/12, l2*L2_RATE/12
        bonus = BONUS if (prepay and dt.month==BONUS_M and k>1) else 0
        pay = 0; sp = 0
        if l2 > 0:
            p2 = L2_BASE + (EXTRA if prepay else 0) + bonus
            if p2 > l2+i2: sp = p2-(l2+i2); p2 = l2+i2
            l2 = max(0, l2-(p2-i2)); pay += p2
        if l1 > 0:
            if l2<=0 and prepay:
                p1 = (L1_EMI+L2_BASE+EXTRA)
            else:
                p1 = L1_EMI + (sp if prepay else 0)
            p1 = min(p1, l1+i1)
            l1 = max(0, l1-(p1-i1)); pay += p1
        out[yr] = out.get(yr, 0) + pay
        bal[yr] = l1+l2
        if l1<=1 and l2<=1:
            end_dt = dt; break
    return out, bal, end_dt

out_pre, bal_pre, end_pre = simulate(True)
out_no,  bal_no,  end_no  = simulate(False)
pre_lbl = end_pre.strftime('%b %Y'); no_lbl = end_no.strftime('%b %Y')
pre_y, no_y = end_pre.year, end_no.year

# ── FIGURE ──
plt.rcParams.update({'font.size':10, 'font.family':'DejaVu Sans'})
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 11), height_ratios=[1.05,1])
fig.suptitle("Aashish & Kalyani — Year-wise Money Map", fontsize=19, fontweight='bold', color='#0d1b4c', y=0.985)
fig.text(0.5, 0.945, "Net salary Rs 36L (ex-bonus) +5%/yr  •  expenses +6% inflation  •  Prepay vs No-prepay  •  rates 7.1%/7.85%",
         ha='center', fontsize=10.5, color='#1565c0')

def lakh(x, _): return f"{x/1e5:.0f}L" if x<1e7 else f"{x/1e7:.2f}Cr"

# Panel 1: year-wise grouped bars + growing salary & expense lines
yrs = list(range(2026, pre_y+2))
x = np.arange(len(yrs)); w = 0.38
def frac(y): return 0.5 if y == 2026 else 1.0
sal = [NET_SALARY_YR*(1+INCOME_GROWTH)**(y-2026)*frac(y) for y in yrs]
exp = [EXPENSES_YR*(1+INFLATION)**(y-2026)*frac(y) for y in yrs]
emi_pre = [out_pre.get(y,0) for y in yrs]
emi_no  = [out_no.get(y,0) for y in yrs]
ymax = max(sal)*1.10
ax1.bar(x-w/2, emi_no,  w, label='Loan outflow — NO prepayment', color='#c62828', alpha=0.9)
ax1.bar(x+w/2, emi_pre, w, label='Loan outflow — WITH prepayment', color='#2e7d32', alpha=0.9)
ax1.fill_between(x, exp, sal, color='#1565c0', alpha=0.06)
ax1.plot(x, sal, color='#1565c0', lw=2.6, marker='o', ms=4, label='Net salary (+5%/yr, ex-bonus)')
ax1.plot(x, exp, color='#f57c00', lw=2.4, ls='--', marker='s', ms=3.5, label='Living expenses (+6% inflation)')
ax1.set_xticks(x); ax1.set_xticklabels(yrs, rotation=45 if len(yrs)>13 else 0)
ax1.set_xlim(-0.6, len(yrs)-0.4); ax1.set_ylim(0, ymax)
ax1.yaxis.set_major_formatter(FuncFormatter(lakh))
ax1.set_ylabel("Rs per year")
ax1.set_title("Annual cash flow — salary rises 5%/yr, expenses 6%; the blue-shaded gap is your surplus",
              fontsize=11, color='#0d1b4c', pad=8)
ax1.legend(loc='upper left', fontsize=8.5, framealpha=0.95, ncol=2)
ax1.grid(axis='y', alpha=0.25)
# annotate prepay loan ends
if pre_y in yrs:
    ax1.annotate(f"Loan GONE\n({pre_lbl})", xy=(yrs.index(pre_y)+w/2, out_pre.get(pre_y,0)),
                 xytext=(yrs.index(pre_y)-1.8, ymax*0.30), fontsize=8.5, color='#2e7d32', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='#2e7d32'))
i27 = yrs.index(2027)
s27 = sal[i27]-exp[i27]-emi_pre[i27]
ax1.annotate(f"surplus ~{s27/1e5:.0f}L", xy=(i27, (sal[i27]+emi_pre[i27])/2),
             fontsize=8, color='#1565c0', ha='center')
last = len(yrs)-1
s_last = sal[last]-exp[last]
ax1.annotate(f"after payoff:\nsurplus ~{s_last/1e5:.0f}L/yr", xy=(last, exp[last]),
             xytext=(last-1.6, ymax*0.60), fontsize=8.5, color='#2e7d32', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#2e7d32'))

# Panel 2: loan balance lines full horizon
def series(bal):
    ys = sorted(bal); return ys, [bal[y] for y in ys]
yp, vp = series(bal_pre); yn, vn = series(bal_no)
ax2.plot(yn, vn, color='#c62828', lw=2.6, marker='o', ms=3, label=f'NO prepayment — ends ~{no_y}')
ax2.plot(yp, vp, color='#2e7d32', lw=2.6, marker='o', ms=3, label=f'WITH prepayment — ends {pre_lbl}')
ax2.fill_between(yp, vp, color='#2e7d32', alpha=0.07)
ax2.yaxis.set_major_formatter(FuncFormatter(lakh))
ax2.set_ylabel("Outstanding loan balance"); ax2.set_xlabel("Year")
ax2.set_title(f"Loan balance over time — prepayment kills it ~{no_y-pre_y} years sooner ({pre_y} vs {no_y})",
              fontsize=11, color='#0d1b4c', pad=8)
ax2.legend(loc='upper right', fontsize=9, framealpha=0.95)
ax2.grid(alpha=0.25); ax2.set_ylim(bottom=0)

fig.text(0.5, 0.012,
   "Assumptions: net take-home Rs 36L/yr year 1 (after tax, BONUS EXCLUDED as variable), +5%/yr; expenses Rs 12L/yr (<=1L/mo), +6%; "
   "fixed EMIs, floating rates 7.1%/7.85%; 2026 is a half year. Surplus widens yearly -> the Rs 50K crunch is liquidity, not income.",
   ha='center', fontsize=8, color='#6b7280', style='italic')

plt.tight_layout(rect=[0, 0.025, 1, 0.94])
plt.savefig('aios/ledger/finance-year-wise-graph.png', dpi=150, bbox_inches='tight')
print("Saved PNG")
print(f"No-prepay ends {no_lbl} | Prepay ends {pre_lbl}")
print(f"Yr-1 surplus (prepay): ~{(sal[yrs.index(2027)]-exp[yrs.index(2027)]-out_pre.get(2027,0))/1e5:.1f}L")
print(f"After-payoff surplus (final yr shown): ~{(sal[-1]-exp[-1])/1e5:.0f}L")
