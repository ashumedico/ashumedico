#!/usr/bin/env python3
"""Render 2026 expense Excel into a matching PDF (monthly grid + summaries). A3 landscape."""
import openpyxl, os
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

NAVY=HexColor('#0d1b4c'); BLUE=HexColor('#1565c0'); RED=HexColor('#c62828')
GREEN=HexColor('#2e7d32'); ORANGE=HexColor('#e65100'); WHITE=HexColor('#ffffff')
GREY=HexColor('#6b7280'); LGREY=HexColor('#f4f7fb'); CREAM=HexColor('#fff8e1')
LBLUE=HexColor('#e3f2fd'); DARK=HexColor('#1f2937'); LGREEN=HexColor('#e8f5e9')

wb=openpyxl.load_workbook('aios/ledger/2026_MAIN_EXPENSES_SHEET.xlsx',data_only=True)
ws=wb.worksheets[0]
rows=list(ws.iter_rows(values_only=True))

def num(v):
    if isinstance(v,(int,float)): return f"{v:,.0f}"
    if v is None: return ""
    return str(v)

# locate the expense category header row
hdr_i=None
for i,r in enumerate(rows):
    if r and r[1]=='Category' and r[2]=='Type':
        hdr_i=i; break
# expense data rows until 'TOTAL MONTHLY EXPENSES'
exp=[]
for r in rows[hdr_i+1:]:
    label=r[1]
    if label=='TOTAL MONTHLY EXPENSES': break
    if r[0] is None and label is None: continue
    vendor=r[0] or ''
    cat=label or ''
    name=(f"{cat}" if cat else str(vendor))
    months=[num(r[c]) for c in range(3,15)]
    total=num(r[15]) if len(r)>15 else ''
    exp.append([name]+months+[total])
# total row
totrow=None
for r in rows:
    if r and r[1]=='TOTAL MONTHLY EXPENSES':
        totrow=['TOTAL EXPENSES']+[num(r[c]) for c in range(3,15)]+[num(r[15])]; break

ss=getSampleStyleSheet()
def S(n,**k): return ParagraphStyle(n,parent=ss['Normal'],**k)
title=S('t',fontSize=20,textColor=NAVY,fontName='Helvetica-Bold',alignment=TA_CENTER,spaceAfter=1*mm)
sub=S('s',fontSize=10.5,textColor=BLUE,alignment=TA_CENTER,spaceAfter=3*mm)
h=S('h',fontSize=13,textColor=NAVY,fontName='Helvetica-Bold',spaceBefore=4*mm,spaceAfter=2*mm)
cl=S('c',fontSize=7,textColor=DARK,leading=8.5)
clr=S('cr',fontSize=7,textColor=DARK,leading=8.5,alignment=2)
hd=S('hd',fontSize=7,textColor=WHITE,fontName='Helvetica-Bold',alignment=TA_CENTER,leading=8.5)
body=S('b',fontSize=9.5,textColor=DARK,leading=13)

out='aios/ledger/2026-expense-sheet.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
doc=SimpleDocTemplate(out,pagesize=landscape(A3),leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm)
E=[]
E.append(Paragraph("2026 Annual Expense Tracking Sheet",title))
E.append(Paragraph("Aashish & Kalyani  •  monthly breakdown  •  (rebuilt from your Excel)",sub))
E.append(HRFlowable(width="100%",thickness=1.4,color=NAVY,spaceAfter=3*mm))

mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
header=[Paragraph('Category',hd)]+[Paragraph(m,hd) for m in mn]+[Paragraph('TOTAL',hd)]
data=[header]
for r in exp:
    data.append([Paragraph(r[0],cl)]+[Paragraph(v,clr) for v in r[1:]])
if totrow:
    data.append([Paragraph('<b>'+totrow[0]+'</b>',cl)]+[Paragraph('<b>'+v+'</b>',clr) for v in totrow[1:]])

cw=[34*mm]+[20*mm]*12+[24*mm]
t=Table(data,colWidths=cw,repeatRows=1)
tsty=[('BACKGROUND',(0,0),(-1,0),NAVY),('GRID',(0,0),(-1,-1),0.3,GREY),
      ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),2.5),('BOTTOMPADDING',(0,0),(-1,-1),2.5),
      ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]
for i in range(1,len(data)-1):
    tsty.append(('BACKGROUND',(0,i),(-1,i),LGREY if i%2 else WHITE))
tsty.append(('BACKGROUND',(0,len(data)-1),(-1,len(data)-1),CREAM))
tsty.append(('LINEABOVE',(0,len(data)-1),(-1,len(data)-1),1,NAVY))
t.setStyle(TableStyle(tsty))
E.append(t)
E.append(Spacer(1,4*mm))

# Annual summary + category summary side by side
def find(label):
    for r in rows:
        if r and r[1]==label: return r
    return None
inc=find('Total Annual Income'); ex=find('Total Annual Expenses'); sur=find('Annual Surplus'); sr=find('Savings Rate %')
sumtbl=[[Paragraph('ANNUAL SUMMARY',hd),Paragraph('',hd)],
        [Paragraph('Total Annual Income',cl),Paragraph(num(inc[2]) if inc else '',clr)],
        [Paragraph('Total Annual Expenses',cl),Paragraph(num(ex[2]) if ex else '',clr)],
        [Paragraph('Annual Surplus',cl),Paragraph(num(sur[2]) if sur else '',clr)],
        [Paragraph('Savings Rate',cl),Paragraph(str(sr[2]) if sr else '',clr)]]
stt=Table(sumtbl,colWidths=[55*mm,35*mm])
stt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('SPAN',(0,0),(1,0)),('GRID',(0,0),(-1,-1),0.3,GREY),
   ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),('LEFTPADDING',(0,0),(-1,-1),4),
   ('BACKGROUND',(0,3),(-1,3),LGREEN)]))

# category summary block
cat_i=None
for i,r in enumerate(rows):
    if r and r[1]=='Category' and r[2]=='Annual Amount': cat_i=i; break
catrows=[[Paragraph('CATEGORY',hd),Paragraph('Annual',hd),Paragraph('%',hd),Paragraph('Monthly',hd)]]
if cat_i:
    for r in rows[cat_i+1:]:
        if not r or r[1] is None: break
        catrows.append([Paragraph(str(r[1]),cl),Paragraph(num(r[2]),clr),Paragraph(str(r[3]),clr),Paragraph(num(r[4]),clr)])
ctt=Table(catrows,colWidths=[40*mm,28*mm,20*mm,26*mm])
csty=[('BACKGROUND',(0,0),(-1,0),GREEN),('GRID',(0,0),(-1,-1),0.3,GREY),
   ('TOPPADDING',(0,0),(-1,-1),2.5),('BOTTOMPADDING',(0,0),(-1,-1),2.5),('LEFTPADDING',(0,0),(-1,-1),4)]
for i in range(1,len(catrows)):
    csty.append(('BACKGROUND',(0,i),(-1,i),LGREY if i%2 else WHITE))
ctt.setStyle(TableStyle(csty))

side=Table([[stt,ctt]],colWidths=[95*mm,118*mm])
side.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(0,0),12)]))
E.append(side)
E.append(Spacer(1,3*mm))
E.append(Paragraph("Note: values exactly as in your Excel (some cells were planned vs actual / formula blanks). "
   "Annual surplus Rs 42,804 = 1.46% savings rate — the thin liquid cash that caused the mid-month crunch.",
   S('n',fontSize=8,textColor=GREY,leading=11)))

doc.build(E)
print("Saved:",out,"| expense rows:",len(exp))
