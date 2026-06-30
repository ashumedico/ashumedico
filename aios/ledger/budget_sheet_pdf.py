#!/usr/bin/env python3
"""2026 Budget Plan on 50:30:20 (Rs 3.2L/mo) in Excel-grid format. Jul-Dec. A4 landscape."""
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
LRED=HexColor('#ffebee'); LGREEN=HexColor('#e8f5e9'); LORN=HexColor('#fff3e0'); DARK=HexColor('#1f2937')

MONTHS=['Jul','Aug','Sep','Oct','Nov','Dec']; N=len(MONTHS)
INCOME=3_20_000

# (label, monthly, bucket)  bucket: head color
EMI=[("Home Loan EMI (incl Rs 20k prepay)",1_60_000)]
INVEST=[("Sukanya Samriddhi (Reha)",12_500),("Term / insurance (TATA)",8_667),
        ("Travel fund (Amsterdam/LTA)",16_667),("Reha school",16_667),("FREE to invest (SIP)",41_499)]
EXP=[("Groceries",15_000),("Maid",15_000),("Society maintenance",12_000),("Misc / eating out",10_000),
     ("Light bill",3_500),("Petrol / fuel",3_000),("Phone",1_000),("Car wash",600),("Buffer / unplanned",3_900)]

ss=getSampleStyleSheet()
def S(n,**k): return ParagraphStyle(n,parent=ss['Normal'],**k)
title=S('t',fontSize=19,textColor=NAVY,fontName='Helvetica-Bold',alignment=TA_CENTER,spaceAfter=1*mm)
sub=S('s',fontSize=11,textColor=BLUE,alignment=TA_CENTER,spaceAfter=3*mm)
cl=S('c',fontSize=8.5,textColor=DARK,leading=10)
clr=S('cr',fontSize=8.5,textColor=DARK,leading=10,alignment=2)
clb=S('cb',fontSize=8.5,textColor=NAVY,fontName='Helvetica-Bold',leading=10)
clbr=S('cbr',fontSize=8.5,textColor=NAVY,fontName='Helvetica-Bold',leading=10,alignment=2)
hd=S('hd',fontSize=8.5,textColor=WHITE,fontName='Helvetica-Bold',alignment=TA_CENTER,leading=10)
sec=S('se',fontSize=9,textColor=WHITE,fontName='Helvetica-Bold',leading=11)
note=S('n',fontSize=8,textColor=GREY,leading=11)

out='aios/ledger/2026-budget-plan-50-30-20.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=12*mm,rightMargin=12*mm,topMargin=11*mm,bottomMargin=11*mm)
E=[]
E.append(Paragraph("2026 Budget Plan — 50 : 30 : 20",title))
E.append(Paragraph("Net income Rs 3,20,000 / month  •  EMI 50% · Invest 30% · Expenses 20%  •  Jul–Dec",sub))
E.append(HRFlowable(width="100%",thickness=1.4,color=NAVY,spaceAfter=3*mm))

def rs(x): return f"{x:,.0f}"
def mrow(label,amt,style_l,style_r): return [Paragraph(label,style_l)]+[Paragraph(rs(amt),style_r)]*N+[Paragraph(rs(amt*N),style_r)]
def sec_row(text): return [Paragraph(text,sec)]+['']*(N+1)

header=[Paragraph('Category',hd)]+[Paragraph(m,hd) for m in MONTHS]+[Paragraph('6-mo TOTAL',hd)]
data=[header]
# income
data.append(mrow("NET INCOME",INCOME,clb,clbr))
# EMI
data.append(sec_row("EMI — 50%  (Rs 1,60,000/mo)"))
for l,a in EMI: data.append(mrow(l,a,cl,clr))
# INVEST
data.append(sec_row("INVEST / LONG-TERM — 30%  (Rs 96,000/mo)"))
for l,a in INVEST: data.append(mrow(l,a,cl,clr))
data.append(mrow("  subtotal invest",sum(a for _,a in INVEST),clb,clbr))
# EXPENSES
data.append(sec_row("DAILY EXPENSES — 20%  (Rs 64,000/mo)"))
for l,a in EXP: data.append(mrow(l,a,cl,clr))
data.append(mrow("  subtotal expenses",sum(a for _,a in EXP),clb,clbr))
# allocated total
data.append(mrow("TOTAL ALLOCATED",INCOME,clb,clbr))

cw=[62*mm]+[26*mm]*N+[30*mm]
t=Table(data,colWidths=cw,repeatRows=1)
sty=[('GRID',(0,0),(-1,-1),0.3,GREY),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
     ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
     ('LEFTPADDING',(0,0),(-1,-1),4),('BACKGROUND',(0,0),(-1,0),NAVY)]
# locate special rows
inc_i=1
sty.append(('BACKGROUND',(0,inc_i),(-1,inc_i),LBLUE if (LBLUE:=HexColor('#e3f2fd')) else WHITE))
# section header backgrounds + spans
section_rows={}
r=2
def idx_of(text):
    for i,row in enumerate(data):
        if isinstance(row[0],Paragraph) and text in row[0].text: return i
    return None
for txt,colr in [("EMI — 50%",RED),("INVEST / LONG-TERM — 30%",GREEN),("DAILY EXPENSES — 20%",ORANGE)]:
    i=idx_of(txt)
    sty.append(('SPAN',(0,i),(-1,i)))
    sty.append(('BACKGROUND',(0,i),(-1,i),colr))
# subtotal / total shading
for txt,bg in [("subtotal invest",LGREEN),("subtotal expenses",LORN),("TOTAL ALLOCATED",CREAM)]:
    i=idx_of(txt)
    if i: sty.append(('BACKGROUND',(0,i),(-1,i),bg)); sty.append(('LINEABOVE',(0,i),(-1,i),0.8,NAVY))
sty.append(('BACKGROUND',(0,inc_i),(-1,inc_i),HexColor('#e3f2fd')))
t.setStyle(TableStyle(sty))
E.append(t)
E.append(Spacer(1,3*mm))
E.append(Paragraph("This replaces the old Excel actuals (which ran at 1.46% savings). New rule: expenses are CAPPED at Rs 64,000/mo "
   "(~Rs 1,063/day discretionary), and Rs 41,499/mo flows into fresh investments. EMI includes the Rs 20,000 extra prepayment.",note))

doc.build(E)
print("Saved:",out)
print("Check: EMI 160000 + invest", sum(a for _,a in INVEST), "+ exp", sum(a for _,a in EXP), "=", 160000+sum(a for _,a in INVEST)+sum(a for _,a in EXP))
