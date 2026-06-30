#!/usr/bin/env python3
"""Monthly budget sheet Jul-Dec 2026 with per-day expense limits. Printable A4 PDF."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
import os

NAVY=HexColor('#0d1b4c'); BLUE=HexColor('#1565c0'); TEAL=HexColor('#00897b')
GREEN=HexColor('#2e7d32'); RED=HexColor('#c62828'); ORANGE=HexColor('#e65100')
GOLD=HexColor('#b8860b'); GREY=HexColor('#6b7280'); WHITE=HexColor('#ffffff')
LRED=HexColor('#ffebee'); LGREEN=HexColor('#e8f5e9'); LORN=HexColor('#fff3e0')
LBLUE=HexColor('#e3f2fd'); CREAM=HexColor('#fff8e1'); DARK=HexColor('#1f2937')
LGREY=HexColor('#f4f7fb')

ss=getSampleStyleSheet()
def S(n,**k): return ParagraphStyle(n,parent=ss['Normal'],**k)
title=S('t',fontSize=21,textColor=NAVY,fontName='Helvetica-Bold',alignment=TA_CENTER,spaceAfter=1*mm)
sub=S('s',fontSize=11,textColor=BLUE,alignment=TA_CENTER,spaceAfter=3*mm)
h=S('h',fontSize=13,textColor=NAVY,fontName='Helvetica-Bold',spaceBefore=4*mm,spaceAfter=2*mm)
body=S('b',fontSize=9.5,textColor=DARK,leading=13)
cell=S('c',fontSize=9,textColor=DARK,leading=12)
cellb=S('cb',fontSize=9,textColor=NAVY,fontName='Helvetica-Bold',leading=12)
celld=S('cd',fontSize=8.5,textColor=GREEN,fontName='Helvetica-Bold',leading=11)
hdr=S('hd',fontSize=9,textColor=WHITE,fontName='Helvetica-Bold',alignment=TA_CENTER,leading=12)
note=S('n',fontSize=8,textColor=GREY,leading=11)

out='aios/ledger/monthly-budget-jul-dec-2026.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=14*mm,rightMargin=14*mm,topMargin=13*mm,bottomMargin=13*mm)
E=[]
def rs(x): return f"Rs {x:,.0f}"
DAYS=30

E.append(Paragraph("Monthly Budget — Jul to Dec 2026",title))
E.append(Paragraph("Net income Rs 3,20,000/month  •  50 / 30 / 20 plan  •  per-day limits in (brackets)",sub))
E.append(HRFlowable(width="100%",thickness=1.5,color=NAVY,spaceAfter=3*mm))

# 50/30/20 summary boxes
sumd=[[Paragraph("EMI — 50%",hdr),Paragraph("INVEST/LONG-TERM — 30%",hdr),Paragraph("DAILY EXPENSES — 20%",hdr)],
      [Paragraph("<b>Rs 1,60,000</b>",cellb),Paragraph("<b>Rs 96,000</b>",cellb),Paragraph("<b>Rs 64,000</b>",cellb)]]
st=Table(sumd,colWidths=[58*mm,64*mm,60*mm])
st.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),RED),('BACKGROUND',(1,0),(1,0),GREEN),('BACKGROUND',(2,0),(2,0),ORANGE),
    ('BACKGROUND',(0,1),(0,1),LRED),('BACKGROUND',(1,1),(1,1),LGREEN),('BACKGROUND',(2,1),(2,1),LORN),
    ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTSIZE',(0,1),(-1,1),13),
    ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('GRID',(0,0),(-1,-1),1,WHITE)]))
E.append(st)
E.append(Spacer(1,3*mm))

# DAILY EXPENSES card with per-day brackets
E.append(Paragraph("DAILY EXPENSES — Rs 64,000/month  (follow the per-day limit)",h))
daily=[
 ("Groceries (Zepto etc.)",15000,True),
 ("Miscellaneous / eating out",10000,True),
 ("Petrol / fuel",3000,True),
 ("Buffer / unplanned",3900,True),
 ("Maid (Akshata+Vidya)",15000,False),
 ("Society maintenance",12000,False),
 ("Light bill (Adani)",3500,False),
 ("Phone (Airtel)",1000,False),
 ("Car wash",600,False),
]
rows=[[Paragraph("Item",hdr),Paragraph("Per month",hdr),Paragraph("Per day allowed",hdr),Paragraph("Type",hdr)]]
disc=0
for name,amt,d in daily:
    perday=f"(Rs {amt/DAYS:,.0f}/day)" if d else "— (monthly)"
    if d: disc+=amt
    rows.append([Paragraph(name,cell),Paragraph(rs(amt),cell),
                 Paragraph(perday,celld if d else note),Paragraph("daily" if d else "fixed",note)])
rows.append([Paragraph("<b>TOTAL</b>",cellb),Paragraph("<b>Rs 64,000</b>",cellb),Paragraph("",cell),Paragraph("",cell)])
dt=Table(rows,colWidths=[70*mm,32*mm,48*mm,32*mm])
dsty=[('BACKGROUND',(0,0),(-1,0),ORANGE),('GRID',(0,0),(-1,-1),0.4,GREY),
   ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
   ('LEFTPADDING',(0,0),(-1,-1),5),('BACKGROUND',(0,len(rows)-1),(-1,len(rows)-1),CREAM)]
for i in range(1,len(rows)-1):
    dsty.append(('BACKGROUND',(0,i),(-1,i),LGREY if i%2 else WHITE))
dt.setStyle(TableStyle(dsty)); E.append(dt)
E.append(Spacer(1,2*mm))
E.append(Paragraph(f"<b>YOUR DAILY SPEND LIMIT = ~Rs {disc/DAYS:,.0f}/day</b>  "
   f"(groceries + eating out + fuel + buffer = Rs {disc:,.0f}/mo). "
   f"Maid, maintenance and bills are fixed monthly — not part of the daily limit.",
   S('lim',fontSize=10,textColor=ORANGE,fontName='Helvetica-Bold',leading=13)))

# INVEST/LONG-TERM card
E.append(Paragraph("INVEST / LONG-TERM — Rs 96,000/month",h))
lt=[("Sukanya Samriddhi (Reha)",12500,"savings"),
    ("Term / insurance (TATA)",8667,"policy"),
    ("Travel fund (Amsterdam/LTA)",16667,"commitment"),
    ("Reha school",16667,"child"),
    ("FREE to invest (fresh SIP)",41499,"wealth")]
lr=[[Paragraph("Item",hdr),Paragraph("Per month",hdr),Paragraph("Type",hdr)]]
for n,a,t in lt:
    bold = (n.startswith("FREE"))
    lr.append([Paragraph(("<b>"+n+"</b>") if bold else n,cellb if bold else cell),
               Paragraph(("<b>"+rs(a)+"</b>") if bold else rs(a),cellb if bold else cell),
               Paragraph(t,note)])
lr.append([Paragraph("<b>TOTAL</b>",cellb),Paragraph("<b>Rs 96,000</b>",cellb),Paragraph("",cell)])
ltb=Table(lr,colWidths=[92*mm,46*mm,44*mm])
lsty=[('BACKGROUND',(0,0),(-1,0),GREEN),('GRID',(0,0),(-1,-1),0.4,GREY),
   ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
   ('LEFTPADDING',(0,0),(-1,-1),5),('BACKGROUND',(0,len(lr)-1),(-1,len(lr)-1),CREAM),
   ('BACKGROUND',(0,5),(-1,5),LGREEN)]
ltb.setStyle(TableStyle(lsty)); E.append(ltb)

E.append(PageBreak())
# MONTHLY TRACKER Jul-Dec
E.append(Paragraph("Monthly Tracker — tick & fill as you go",title))
E.append(Paragraph("Same plan each month. Record what you actually spent on the daily bucket and whether you stayed under the limit.",sub))
E.append(HRFlowable(width="100%",thickness=1.2,color=NAVY,spaceAfter=3*mm))
months=["July","August","September","October","November","December"]
th=[Paragraph(x,hdr) for x in ["Month","EMI paid","Invested (96K)","Daily budget","Daily ACTUAL (fill)","Under limit?"]]
tr=[th]
for m in months:
    tr.append([Paragraph(m,cellb),Paragraph("Rs 1,60,000",cell),Paragraph("Rs 96,000",cell),
               Paragraph("Rs 64,000",cell),Paragraph("____________",cell),Paragraph("[  ] Y  [  ] N",cell)])
tt=Table(tr,colWidths=[24*mm,28*mm,30*mm,28*mm,38*mm,34*mm])
tsty=[('BACKGROUND',(0,0),(-1,0),NAVY),('GRID',(0,0),(-1,-1),0.5,GREY),
   ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
   ('LEFTPADDING',(0,0),(-1,-1),5)]
for i in range(1,len(tr)):
    tsty.append(('BACKGROUND',(0,i),(-1,i),LGREY if i%2 else WHITE))
tt.setStyle(TableStyle(tsty)); E.append(tt)
E.append(Spacer(1,4*mm))
E.append(Paragraph("THE RULES (keep it simple)",h))
for r in [
  "1.  Pay EMI Rs 1,60,000 FIRST every month.",
  f"2.  Stay under ~Rs {disc/DAYS:,.0f}/day on groceries + eating out + fuel. That is the whole game.",
  "3.  Auto-debit the SIP / SSY / policy so the 96K is saved before you can spend it.",
  "4.  Keep Rs 41,499/month flowing into investments — that is your wealth + your future buffer.",
  "5.  Any month you beat the daily limit, sweep the saving into the SIP.",
]:
    E.append(Paragraph(r,body)); E.append(Spacer(1,1*mm))
E.append(Spacer(1,3*mm))
E.append(Paragraph("Per-day = monthly amount / 30. Built from your 2026 expense sheet. EMI includes the Rs 20,000 extra prepayment.",note))

doc.build(E)
print("Saved:",out)
print(f"Daily discretionary limit: Rs {disc/DAYS:,.0f}/day (Rs {disc:,.0f}/mo)")
