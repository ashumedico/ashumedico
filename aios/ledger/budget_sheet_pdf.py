#!/usr/bin/env python3
"""2026 Budget Plan on 50:30:20 (Rs 3.2L/mo), Excel-grid + per-day expense column. A4 landscape."""
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

NAVY=HexColor('#0d1b4c'); BLUE=HexColor('#1565c0'); RED=HexColor('#c62828')
GREEN=HexColor('#2e7d32'); ORANGE=HexColor('#e65100'); WHITE=HexColor('#ffffff')
GREY=HexColor('#6b7280'); LGREY=HexColor('#f4f7fb'); CREAM=HexColor('#fff8e1')
LRED=HexColor('#ffebee'); LGREEN=HexColor('#e8f5e9'); LORN=HexColor('#fff3e0')
LBLUE=HexColor('#e3f2fd'); DARK=HexColor('#1f2937')

MONTHS=['Jul','Aug','Sep','Oct','Nov','Dec']; N=len(MONTHS); DAYS=30
INCOME=3_20_000
EMI=[("Home Loan EMI (incl Rs 20k prepay)",1_60_000)]
INVEST=[("Sukanya Samriddhi (Reha)",12_500),("Term / insurance (TATA)",8_667),
        ("Travel fund (Amsterdam/LTA)",16_667),("Reha school",16_667),("FREE to invest (SIP)",41_499)]
# Grocery 25k; buffer removed (->grocery), eating out 10k-6.1k = 3.9k
EXP=[("Groceries",25_000),("Maid",15_000),("Society maintenance",12_000),("Misc / eating out",3_900),
     ("Light bill",3_500),("Petrol / fuel",3_000),("Phone",1_000),("Car wash",600)]

ss=getSampleStyleSheet()
def S(n,**k): return ParagraphStyle(n,parent=ss['Normal'],**k)
title=S('t',fontSize=19,textColor=NAVY,fontName='Helvetica-Bold',alignment=TA_CENTER,spaceAfter=1*mm)
sub=S('s',fontSize=11,textColor=BLUE,alignment=TA_CENTER,spaceAfter=3*mm)
cl=S('c',fontSize=8.5,textColor=DARK,leading=10)
clr=S('cr',fontSize=8.5,textColor=DARK,leading=10,alignment=2)
clb=S('cb',fontSize=8.5,textColor=NAVY,fontName='Helvetica-Bold',leading=10)
clbr=S('cbr',fontSize=8.5,textColor=NAVY,fontName='Helvetica-Bold',leading=10,alignment=2)
pday=S('pd',fontSize=8,textColor=GREEN,fontName='Helvetica-Bold',leading=10,alignment=TA_CENTER)
hd=S('hd',fontSize=8.5,textColor=WHITE,fontName='Helvetica-Bold',alignment=TA_CENTER,leading=10)
sec=S('se',fontSize=9,textColor=WHITE,fontName='Helvetica-Bold',leading=11)
note=S('n',fontSize=8,textColor=GREY,leading=11)

out='aios/ledger/2026-budget-plan-50-30-20.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=11*mm,bottomMargin=11*mm)
E=[]
E.append(Paragraph("2026 Budget Plan — 50 : 30 : 20",title))
E.append(Paragraph("Net income Rs 3,20,000 / month  •  EMI 50% · Invest 30% · Expenses 20%  •  Jul–Dec  •  per-day on expenses",sub))
E.append(HRFlowable(width="100%",thickness=1.4,color=NAVY,spaceAfter=3*mm))

def rs(x): return f"{x:,.0f}"
def row(label,amt,sl,sr,perday=None):
    pd = Paragraph(f"{amt/DAYS:,.0f}/day",pday) if perday else Paragraph("",cl)
    return [Paragraph(label,sl),pd]+[Paragraph(rs(amt),sr)]*N+[Paragraph(rs(amt*N),sr)]
def sec_row(text): return [Paragraph(text,sec)]+['']*(N+2)

header=[Paragraph('Category',hd),Paragraph('Per day',hd)]+[Paragraph(m,hd) for m in MONTHS]+[Paragraph('6-mo TOTAL',hd)]
data=[header]
data.append(row("NET INCOME",INCOME,clb,clbr))
data.append(sec_row("EMI — 50%  (Rs 1,60,000/mo)"))
for l,a in EMI: data.append(row(l,a,cl,clr))
data.append(sec_row("INVEST / LONG-TERM — 30%  (Rs 96,000/mo)"))
for l,a in INVEST: data.append(row(l,a,cl,clr))
data.append(row("  subtotal invest",sum(a for _,a in INVEST),clb,clbr))
data.append(sec_row("DAILY EXPENSES — 20%  (Rs 64,000/mo)"))
for l,a in EXP: data.append(row(l,a,cl,clr,perday=True))
data.append(row("  subtotal expenses",sum(a for _,a in EXP),clb,clbr,perday=True))
data.append(row("TOTAL ALLOCATED",INCOME,clb,clbr))

cw=[52*mm,20*mm]+[24*mm]*N+[27*mm]
t=Table(data,colWidths=cw,repeatRows=1)
sty=[('GRID',(0,0),(-1,-1),0.3,GREY),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
     ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
     ('LEFTPADDING',(0,0),(-1,-1),4),('BACKGROUND',(0,0),(-1,0),NAVY),
     ('BACKGROUND',(0,1),(-1,1),LBLUE)]
def idx_of(text):
    for i,rw in enumerate(data):
        if isinstance(rw[0],Paragraph) and text in rw[0].text: return i
    return None
for txt,colr in [("EMI — 50%",RED),("INVEST / LONG-TERM — 30%",GREEN),("DAILY EXPENSES — 20%",ORANGE)]:
    i=idx_of(txt); sty.append(('SPAN',(0,i),(-1,i))); sty.append(('BACKGROUND',(0,i),(-1,i),colr))
for txt,bg in [("subtotal invest",LGREEN),("subtotal expenses",LORN),("TOTAL ALLOCATED",CREAM)]:
    i=idx_of(txt)
    if i: sty.append(('BACKGROUND',(0,i),(-1,i),bg)); sty.append(('LINEABOVE',(0,i),(-1,i),0.8,NAVY))
t.setStyle(TableStyle(sty))
E.append(t)
E.append(Spacer(1,3*mm))
disc=25_000+3_900+3_000
E.append(Paragraph(f"<b>Daily discretionary limit ~Rs {disc/DAYS:,.0f}/day</b> (groceries + eating out + fuel = Rs {disc:,.0f}/mo). "
  f"Grocery raised to Rs 25,000 (from buffer Rs 3,900 + eating-out Rs 6,100). Maid, maintenance & bills are fixed monthly. "
  f"EMI includes the Rs 20,000 extra prepayment; Rs 41,499/mo flows into fresh investments.",
  S('lim',fontSize=8.5,textColor=ORANGE,fontName='Helvetica-Bold',leading=11)))

doc.build(E)
print("Saved:",out)
print("Expenses total:",sum(a for _,a in EXP),"| daily discretionary:",disc,"=",disc/DAYS,"/day")
