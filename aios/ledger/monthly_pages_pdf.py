#!/usr/bin/env python3
"""Household budget — one styled page per month, Jul 2026 -> Dec 2027 (18 pages). A4 portrait."""
import os, calendar
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, PageBreak, Image)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

NAVY=HexColor('#0d1b4c'); BLUE=HexColor('#1565c0'); RED=HexColor('#c62828')
GREEN=HexColor('#2e7d32'); ORANGE=HexColor('#e65100'); WHITE=HexColor('#ffffff')
GREY=HexColor('#6b7280'); CREAM=HexColor('#fff8e1'); DARK=HexColor('#1f2937')
LRED=HexColor('#ffebee'); LGREEN=HexColor('#e8f5e9'); LORN=HexColor('#fff3e0'); LBLUE=HexColor('#eef3fb')

DAYS=30; INCOME=3_20_000
EMI=[("Home Loan (incl Rs 20k extra prepay)",1_60_000,None)]
INVEST=[("Sukanya Samriddhi (Reha)",12_500,None),("Term / insurance (TATA)",8_667,None),
        ("Travel fund (Amsterdam/LTA)",16_667,None),("Reha School",16_667,None),("FREE to invest (SIP)",41_499,None)]
EXP=[("Groceries",25_000,True),("Maid",15_000,True),("Society Maintenance",12_000,True),
     ("Misc / Eating Out",3_900,True),("Light Bill",3_500,True),("Petrol / Fuel",3_000,True),
     ("Phone",1_000,True),("Car Wash",600,True)]

ss=getSampleStyleSheet()
def S(n,**k): return ParagraphStyle(n,parent=ss['Normal'],**k)
hbig=S('hb',fontSize=26,textColor=NAVY,fontName='Helvetica-Bold',alignment=TA_RIGHT,leading=26)
hsub=S('hs',fontSize=11,textColor=GREY,alignment=TA_RIGHT)
fam=S('fm',fontSize=10,textColor=GREEN,fontName='Helvetica-Bold')
cl=S('c',fontSize=9.5,textColor=DARK,leading=12)
clr=S('cr',fontSize=9.5,textColor=DARK,leading=12,alignment=TA_RIGHT)
clc=S('cc',fontSize=9,textColor=GREEN,fontName='Helvetica-Bold',leading=12,alignment=TA_CENTER)
clb=S('cb',fontSize=9.5,textColor=NAVY,fontName='Helvetica-Bold',leading=12)
clbr=S('cbr',fontSize=9.5,textColor=NAVY,fontName='Helvetica-Bold',leading=12,alignment=TA_RIGHT)
hd=S('hd',fontSize=9,textColor=WHITE,fontName='Helvetica-Bold',alignment=TA_CENTER,leading=11)
sec=S('se',fontSize=10,textColor=WHITE,fontName='Helvetica-Bold',leading=12)

out='aios/ledger/monthly-household-budget-2026-2027.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=14*mm,rightMargin=14*mm,topMargin=12*mm,bottomMargin=12*mm)
def rs(x): return f"{x:,.0f}"

months=[(m,2026) for m in range(7,13)]+[(m,2027) for m in range(1,13)]
E=[]
for pi,(mo,yr) in enumerate(months):
    mname=calendar.month_name[mo].upper()
    # header
    htbl=Table([[Paragraph("THE HAPPY & HEALTHY<br/>FAMILY BUDGET",fam),
                 Paragraph(f"{mname} {yr}<br/>HOUSEHOLD EXPENSES",hbig)],
                ['',Paragraph(f"Net Monthly Income: Rs {INCOME:,}",hsub)]],
               colWidths=[60*mm,122*mm])
    htbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('SPAN',(0,0),(0,1))]))
    E.append(htbl)
    E.append(HRFlowable(width="100%",thickness=1.5,color=NAVY,spaceBefore=2*mm,spaceAfter=3*mm))

    data=[[Paragraph('CATEGORY',hd),Paragraph('Daily rate',hd),Paragraph('Monthly',hd),Paragraph('Actual (fill)',hd)]]
    def secrow(t): return [Paragraph(t,sec),'','','']
    def itemrow(l,a,daily):
        dr=Paragraph(f"{a/DAYS:,.0f}/day",clc) if daily else Paragraph("-",clc)
        return [Paragraph(l,cl),dr,Paragraph(rs(a),clr),Paragraph("________",cl)]
    data.append(secrow("MORTGAGE / EMI - 50%  (Rs 1,60,000)"))
    for l,a,d in EMI: data.append(itemrow(l,a,d))
    data.append(secrow("INVESTMENT & LONG-TERM - 30%  (Rs 96,000)"))
    for l,a,d in INVEST: data.append(itemrow(l,a,d))
    data.append([Paragraph("Subtotal Investment",clb),Paragraph("-",clc),Paragraph("96,000",clbr),Paragraph("",cl)])
    data.append(secrow("DAILY LIVING EXPENSES - 20%  (Rs 64,000)"))
    for l,a,d in EXP: data.append(itemrow(l,a,d))
    data.append([Paragraph("Subtotal Daily Expenses",clb),Paragraph("2,133/day",clc),Paragraph("64,000",clbr),Paragraph("",cl)])
    data.append([Paragraph("TOTAL ALLOCATED",clb),Paragraph("-",clc),Paragraph("3,20,000",clbr),Paragraph("",cl)])

    t=Table(data,colWidths=[80*mm,28*mm,34*mm,40*mm],repeatRows=1)
    sty=[('GRID',(0,0),(-1,-1),0.3,GREY),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
         ('TOPPADDING',(0,0),(-1,-1),3.5),('BOTTOMPADDING',(0,0),(-1,-1),3.5),('LEFTPADDING',(0,0),(-1,-1),5),
         ('BACKGROUND',(0,0),(-1,0),NAVY)]
    def idx(text):
        for i,r in enumerate(data):
            if isinstance(r[0],Paragraph) and text in r[0].text: return i
        return None
    for txt,c in [("MORTGAGE / EMI",RED),("INVESTMENT & LONG-TERM",GREEN),("DAILY LIVING",ORANGE)]:
        i=idx(txt); sty.append(('SPAN',(0,i),(-1,i))); sty.append(('BACKGROUND',(0,i),(-1,i),c))
    for txt,bg in [("Subtotal Investment",LGREEN),("Subtotal Daily",LORN),("TOTAL ALLOCATED",CREAM)]:
        i=idx(txt); sty.append(('BACKGROUND',(0,i),(-1,i),bg)); sty.append(('LINEABOVE',(0,i),(-1,i),0.8,NAVY))
    t.setStyle(TableStyle(sty))
    E.append(t)
    E.append(Spacer(1,4*mm))

    # donut + discretionary box
    img=Image('aios/ledger/_donut.png',width=42*mm,height=42*mm)
    disc=Paragraph("<b>Discretionary Limit</b><br/>(Groceries + Eating Out + Fuel)<br/>"
                   "<font color='#e65100' size=14><b>Rs 1,063/day</b></font><br/>(~Rs 31,900/mo)",
                   S('d',fontSize=10,textColor=DARK,alignment=TA_CENTER,leading=15))
    foot=Table([[img,disc]],colWidths=[60*mm,122*mm])
    foot.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(0,0),'CENTER'),
        ('BOX',(1,0),(1,0),1,GREY),('BACKGROUND',(1,0),(1,0),LBLUE),
        ('TOPPADDING',(1,0),(1,0),6),('BOTTOMPADDING',(1,0),(1,0),6)]))
    E.append(foot)
    if pi<len(months)-1: E.append(PageBreak())

doc.build(E)
print("Saved:",out,"| pages:",len(months))
