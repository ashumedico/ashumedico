#!/usr/bin/env python3
"""Loan 1 & 2 payoff graph, and 20-year investment projection."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np, calendar
from datetime import datetime

# ── loans ──
L1_BAL,L2_BAL=1_48_00_000,21_60_000
L1_RATE,L2_RATE=0.071,0.0785
L1_EMI,L2_BASE,EXTRA=1_20_000,20_000,20_000
START=datetime(2026,7,1)
def add_m(dt,n):
    m=dt.month-1+n; y=dt.year+m//12; m=m%12+1
    return datetime(y,m,min(dt.day,calendar.monthrange(y,m)[1]))
def lakh(x,_): return f"{x/1e5:.0f}L" if x<1e7 else f"{x/1e7:.2f}Cr"

l1,l2=float(L1_BAL),float(L2_BAL); dts=[]; b1=[]; b2=[]; l1_end=l2_end=None
for k in range(1,700):
    dt=add_m(START,k-1); i1,i2=l1*L1_RATE/12,l2*L2_RATE/12; sp=0
    if l2>0:
        p2=L2_BASE+EXTRA
        if p2>l2+i2: sp=p2-(l2+i2); p2=l2+i2
        l2=max(0,l2-(p2-i2))
        if l2<=1 and l2_end is None: l2_end=dt
    if l1>0:
        p1=(L1_EMI+L2_BASE+EXTRA) if l2<=0 else (L1_EMI+sp)
        p1=min(p1,l1+i1); l1=max(0,l1-(p1-i1))
        if l1<=1 and l1_end is None: l1_end=dt
    dts.append(dt); b1.append(l1); b2.append(l2)
    if l1<=1 and l2<=1: break
xs=[d.year+(d.month-1)/12 for d in dts]

fig,ax=plt.subplots(figsize=(12,6))
ax.plot(xs,b2,color='#e65100',lw=2.8,label=f'Loan 2 (Rs 21.6L @7.85%) - dies {l2_end.strftime("%b %Y")}')
ax.plot(xs,b1,color='#c62828',lw=2.8,label=f'Loan 1 (Rs 1.48Cr @7.1%) - dies {l1_end.strftime("%b %Y")}')
ax.fill_between(xs,b1,color='#c62828',alpha=0.06); ax.fill_between(xs,b2,color='#e65100',alpha=0.10)
ax.axhline(0,color='#2e7d32',lw=1)
for end,col,nm in [(l2_end,'#e65100','L2 ZERO'),(l1_end,'#c62828','L1 ZERO - DEBT FREE')]:
    ex=end.year+(end.month-1)/12
    ax.axvline(ex,color=col,ls=':',lw=1.6)
    ax.annotate(f"{nm}\n{end.strftime('%b %Y')}",xy=(ex,0),xytext=(ex-2.2,L1_BAL*0.30),
                fontsize=9,color=col,fontweight='bold',arrowprops=dict(arrowstyle='->',color=col))
ax.annotate("Loan 2 dies -> its Rs 40k\nrolls into Loan 1 (snowball)",xy=(l2_end.year+0.3,b1[dts.index(l2_end)]),
            xytext=(l2_end.year+1,L1_BAL*0.78),fontsize=8.5,color='#6a1b9a',
            arrowprops=dict(arrowstyle='->',color='#6a1b9a'))
ax.yaxis.set_major_formatter(FuncFormatter(lakh)); ax.set_ylim(bottom=0)
ax.set_xlabel("Year"); ax.set_ylabel("Outstanding balance")
ax.set_title("Loan 1 & Loan 2 — balance till zero (EMI Rs 1.6L, rates 7.1%/7.85%)",fontsize=13,color='#0d1b4c',fontweight='bold')
ax.legend(loc='upper right',fontsize=9.5); ax.grid(alpha=0.25)
fig.text(0.5,0.005,"Plan: L1 Rs 1.2L + L2 Rs 0.4L (incl Rs 20k extra). When L2 clears, full Rs 1.6L hits L1. Bonus not counted.",
         ha='center',fontsize=8,color='#6b7280',style='italic')
plt.tight_layout(rect=[0,0.02,1,1])
plt.savefig('aios/ledger/loan-1-2-payoff.png',dpi=150,bbox_inches='tight')
print(f"Loans: L2 {l2_end.strftime('%b %Y')} | L1 {l1_end.strftime('%b %Y')}")

# ── investments 20 yr ──
YEARS=20; MO=YEARS*12
SIP0=41_499; SIP_R=0.12; STEP=0.05
SSY=12_500; SSY_R=0.08; SSY_MONTHS=15*12   # 15-yr deposit period
sip=0.0; ssy=0.0; sipc=[]; ssyc=[]; sip_m=SIP0
yrs=[]
for k in range(1,MO+1):
    if k>1 and (k-1)%12==0: sip_m*=(1+STEP)
    sip=sip*(1+SIP_R/12)+sip_m
    ssy=ssy*(1+SSY_R/12)+(SSY if k<=SSY_MONTHS else 0)
    if k%12==0:
        yrs.append(2026+k//12); sipc.append(sip); ssyc.append(ssy)
tot=[a+b for a,b in zip(sipc,ssyc)]

fig2,ax2=plt.subplots(figsize=(12,6))
ax2.stackplot(yrs,ssyc,sipc,colors=['#1565c0','#2e7d32'],alpha=0.85,
              labels=['Sukanya Samriddhi @8% (Rs 12.5k/mo, 15 yrs)','Equity SIP @12% (Rs 41.5k/mo, +5%/yr step-up)'])
ax2.plot(yrs,tot,color='#0d1b4c',lw=2.5,marker='o',ms=4)
for i,y in enumerate(yrs):
    if y in (2031,2036,2041,2046):
        ax2.annotate(f"Rs {tot[i]/1e7:.1f}Cr",xy=(y,tot[i]),xytext=(y-0.5,tot[i]+max(tot)*0.05),
                     fontsize=9,fontweight='bold',color='#0d1b4c')
ax2.yaxis.set_major_formatter(FuncFormatter(lakh)); ax2.set_ylim(bottom=0)
ax2.set_xlabel("Year"); ax2.set_ylabel("Total money in hand (corpus)")
ax2.set_title(f"Investments — 20-year picture  |  Total ~Rs {tot[-1]/1e7:.1f}Cr by {yrs[-1]}",
              fontsize=13,color='#0d1b4c',fontweight='bold')
ax2.legend(loc='upper left',fontsize=9.5); ax2.grid(alpha=0.25)
fig2.text(0.5,0.005,"Corpus-builders only (SIP + SSY). Term insurance, travel & school are protection/expense, not corpus. "
          "PF & NPS NOT yet included - to be added. Returns assumed, not guaranteed.",
          ha='center',fontsize=8,color='#6b7280',style='italic')
plt.tight_layout(rect=[0,0.02,1,1])
plt.savefig('aios/ledger/investment-20yr.png',dpi=150,bbox_inches='tight')
print(f"Corpus: 10yr ~{tot[4]/1e7:.2f}Cr | 15yr ~{tot[9]/1e7:.2f}Cr | 20yr ~{tot[-1]/1e7:.2f}Cr")
