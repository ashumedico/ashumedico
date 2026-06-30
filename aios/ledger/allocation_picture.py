#!/usr/bin/env python3
"""50/30/20 picture: EMI vs Invest vs Expenses — wealth-vs-debt crossover."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np, calendar
from datetime import datetime

# ── CONFIG ──
NET_M   = 3_20_000
EMI_M   = 1_60_000          # 50%  (L1 1.2L + L2 0.2L base + 0.2L extra prepay)
INVEST_M= 96_000            # 30%
EXP_M   = 64_000            # 20%
STEPUP  = 0.05              # SIP grows 5%/yr (tracks income)
R_MAIN, R_LO, R_HI = 0.12, 0.10, 0.14   # equity SIP return assumptions
# loan
L1_BAL, L2_BAL = 1_48_00_000, 21_60_000
L1_RATE, L2_RATE = 0.071, 0.0785
L1_EMI, L2_BASE, EXTRA = 1_20_000, 20_000, 20_000
START = datetime(2026, 7, 1)

def add_m(dt, n):
    m=dt.month-1+n; y=dt.year+m//12; m=m%12+1
    return datetime(y, m, min(dt.day, calendar.monthrange(y,m)[1]))

# loan monthly balance (prepay, no bonus)
def loan_curve():
    l1,l2=float(L1_BAL),float(L2_BAL); pts={}
    for k in range(1,700):
        dt=add_m(START,k-1)
        i1,i2=l1*L1_RATE/12, l2*L2_RATE/12; sp=0
        if l2>0:
            p2=L2_BASE+EXTRA
            if p2>l2+i2: sp=p2-(l2+i2); p2=l2+i2
            l2=max(0,l2-(p2-i2))
        if l1>0:
            p1=(L1_EMI+L2_BASE+EXTRA) if l2<=0 else (L1_EMI+sp)
            p1=min(p1,l1+i1); l1=max(0,l1-(p1-i1))
        pts[dt]=l1+l2
        if l1<=1 and l2<=1: break
    return pts

# SIP corpus monthly at rate r, step-up yearly
def sip_curve(r, horizon_months):
    bal=0.0; sip=INVEST_M; pts={}
    for k in range(1,horizon_months+1):
        dt=add_m(START,k-1)
        if k>1 and dt.month==START.month: sip*=(1+STEPUP)   # annual step-up
        bal=bal*(1+r/12)+sip
        pts[dt]=bal
    return pts

loan=loan_curve()
H=len(loan)+12
sip_main=sip_curve(R_MAIN,H); sip_lo=sip_curve(R_LO,H); sip_hi=sip_curve(R_HI,H)

# yearly sampling (Dec each year + final)
def yearly(pts):
    out={}
    for dt,v in pts.items():
        if dt.month==12 or dt==list(pts)[-1]: out[dt.year]=v
    return out
loanY=yearly(loan); mainY=yearly(sip_main); loY=yearly(sip_lo); hiY=yearly(sip_hi)
yrs=sorted(set(loanY)|set(mainY))

# crossover: corpus(main) >= loan balance
cross=None
for dt in sorted(sip_main):
    lb=loan.get(dt, 0 if dt>max(loan) else None)
    if lb is None: continue
    if sip_main[dt]>=lb and lb>0:
        cross=dt; break

# ── FIGURE ──
plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans'})
fig=plt.figure(figsize=(13,11))
gs=fig.add_gridspec(2,2,height_ratios=[1,1.15],hspace=0.32,wspace=0.25)
fig.suptitle("The 50 / 30 / 20 Picture — Rs 3,20,000 a month", fontsize=19, fontweight='bold', color='#0d1b4c', y=0.98)
def lakh(x,_): return f"{x/1e5:.0f}L" if x<1e7 else f"{x/1e7:.2f}Cr"

# Panel A: donut split
axA=fig.add_subplot(gs[0,0])
vals=[EMI_M,INVEST_M,EXP_M]; labs=[f"EMI 50%\nRs 1,60,000",f"Invest 30%\nRs 96,000",f"Expenses 20%\nRs 64,000"]
cols=['#c62828','#2e7d32','#f57c00']
w,_=axA.pie(vals,labels=labs,colors=cols,startangle=90,counterclock=False,
            wedgeprops=dict(width=0.42,edgecolor='white',linewidth=2),
            textprops=dict(fontsize=9.5,fontweight='bold'))
axA.text(0,0,"Rs 3.2L\n/month",ha='center',va='center',fontsize=12,fontweight='bold',color='#0d1b4c')
axA.set_title("Where each month goes",fontsize=11,color='#0d1b4c')

# Panel B: monthly flows as bars (annual figures)
axB=fig.add_subplot(gs[0,1])
ann=[EMI_M*12,INVEST_M*12,EXP_M*12]
b=axB.bar(['EMI','Invest','Expenses'],ann,color=cols,alpha=0.9,width=0.6)
axB.bar_label(b,labels=[f"{v/1e5:.2f}L/yr" for v in ann],fontsize=9,fontweight='bold',padding=3)
axB.yaxis.set_major_formatter(FuncFormatter(lakh)); axB.set_ylabel("Rs per year")
axB.set_title("Per year",fontsize=11,color='#0d1b4c'); axB.grid(axis='y',alpha=0.25)
axB.set_ylim(0,max(ann)*1.18)

# Panel C: wealth vs debt
axC=fig.add_subplot(gs[1,:])
axC.plot(yrs,[loanY.get(y,0) for y in yrs],color='#c62828',lw=2.8,marker='o',ms=4,label='Loan balance (falling)')
axC.plot(yrs,[mainY.get(y,0) for y in yrs],color='#2e7d32',lw=2.8,marker='o',ms=4,label='Investment corpus @12% (rising)')
axC.fill_between(yrs,[loY.get(y,0) for y in yrs],[hiY.get(y,0) for y in yrs],color='#2e7d32',alpha=0.12,label='corpus range (10–14%)')
axC.yaxis.set_major_formatter(FuncFormatter(lakh)); axC.set_xlabel("Year"); axC.set_ylabel("Rs")
axC.set_title("Wealth vs Debt — investing 30% builds a corpus while the loan dies",fontsize=12,color='#0d1b4c',pad=8)
axC.legend(loc='upper left',fontsize=9,framealpha=0.95); axC.grid(alpha=0.25); axC.set_ylim(bottom=0)
if cross:
    cy=cross.year+ (cross.month-1)/12
    axC.axvline(cy,color='#6a1b9a',ls=':',lw=2)
    axC.annotate(f"CROSSOVER {cross.strftime('%b %Y')}\ninvestments > debt",
                 xy=(cy,mainY.get(cross.year,sip_main[cross])),xytext=(cy-3.5,max(hiY.values())*0.55),
                 fontsize=9.5,color='#6a1b9a',fontweight='bold',arrowprops=dict(arrowstyle='->',color='#6a1b9a'))

# corpus milestones text
def corpus_at(yr): return mainY.get(yr,0)
m5=add_m(START,60).year; m10=add_m(START,120).year; m15=add_m(START,180).year
fig.text(0.5,0.015,
   f"Assumptions: Rs 96,000/mo SIP, +5%/yr step-up, ~12% equity return (range 10–14% shaded; returns NOT guaranteed, markets carry risk). "
   f"Loan: prepay, no bonus, ends Jun 2040.  Corpus ~{corpus_at(m5)/1e5:.0f}L by {m5} · ~{corpus_at(m10)/1e7:.1f}Cr by {m10} · ~{corpus_at(m15)/1e7:.1f}Cr by {m15}.",
   ha='center',fontsize=8,color='#6b7280',style='italic')

plt.savefig('aios/ledger/allocation-50-30-20.png',dpi=150,bbox_inches='tight')
print("Saved")
print(f"Crossover: {cross.strftime('%b %Y') if cross else 'n/a'}")
print(f"Corpus @12%: {m5}->{corpus_at(m5)/1e5:.0f}L | {m10}->{corpus_at(m10)/1e7:.2f}Cr | {m15}->{corpus_at(m15)/1e7:.2f}Cr")
