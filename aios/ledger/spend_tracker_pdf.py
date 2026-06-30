#!/usr/bin/env python3
"""2026 Daily Spend Tracker — one tick box per day, all 12 months. A4 landscape."""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
import calendar, os

NAVY=HexColor('#0d1b4c'); BLUE=HexColor('#1565c0'); ORANGE=HexColor('#e65100')
GREEN=HexColor('#2e7d32'); GOLD=HexColor('#ffc107'); WHITE=HexColor('#ffffff')
GREY=HexColor('#90a4ae'); BLACKOUT=HexColor('#cfd8dc'); LGREY=HexColor('#f4f7fb')
CREAM=HexColor('#fff8e1'); DARK=HexColor('#263238')

LIMIT = 1063
DAYS_GOAL = 25
YEAR = 2026
out='aios/ledger/2026-daily-spend-tracker.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
W,H = landscape(A4)
c=canvas.Canvas(out,pagesize=landscape(A4))

def txt(x,y,s,sz,col,font='Helvetica-Bold',center=False):
    c.setFillColor(col); c.setFont(font,sz)
    (c.drawCentredString if center else c.drawString)(x,y,s)

# background
c.setFillColor(HexColor('#fefcf3')); c.rect(0,0,W,H,fill=1,stroke=0)

# title band
c.setFillColor(NAVY); c.roundRect(8*mm,H-26*mm,W-16*mm,19*mm,3*mm,fill=1,stroke=0)
txt(W/2,H-15*mm,"2026 DAILY SPEND TRACKER",20,GOLD,center=True)
txt(W/2,H-22*mm,f"Tick every day you stay under Rs {LIMIT:,}/day (groceries + eating out + fuel).  "
                f"Goal: {DAYS_GOAL}+ ticks each month.",10.5,WHITE,center=True)

# grid geometry
left=8*mm; right=W-8*mm
lbl=24*mm; goal=20*mm
day_x0=left+lbl
day_area=(right-goal)-day_x0
dw=day_area/31.0
top=H-30*mm; bot=10*mm; hh=7*mm
rh=(top-hh-bot)/12.0

months=[(calendar.month_name[m], calendar.monthrange(YEAR,m)[1]) for m in range(1,13)]

# header
hy=top-hh
c.setFillColor(NAVY); c.rect(left,hy,right-left,hh,fill=1,stroke=0)
txt(left+lbl/2,hy+2.4*mm,"MONTH",8,WHITE,center=True)
for d in range(1,32):
    txt(day_x0+(d-0.5)*dw,hy+2.4*mm,str(d),6,WHITE,center=True)
txt((right-goal)+goal/2,hy+2.4*mm,"v / 31",7.5,GOLD,center=True)

# rows
for i,(name,ndays) in enumerate(months):
    ry=hy-(i+1)*rh
    c.setFillColor(LGREY if i%2 else WHITE); c.rect(left,ry,right-left,rh,fill=1,stroke=0)
    # month label
    c.setFillColor(BLUE); c.rect(left,ry,lbl,rh,fill=1,stroke=0)
    txt(left+2*mm,ry+rh*0.34,name[:3].upper(),9,WHITE)
    # day cells
    for d in range(1,32):
        cx=day_x0+(d-1)*dw
        if d>ndays:
            c.setFillColor(BLACKOUT); c.rect(cx,ry,dw,rh,fill=1,stroke=0)
        else:
            c.setStrokeColor(GREY); c.setLineWidth(0.3); c.rect(cx,ry,dw,rh,fill=0,stroke=1)
    # goal cell
    c.setFillColor(CREAM); c.rect(right-goal,ry,goal,rh,fill=1,stroke=0)
    c.setStrokeColor(GREY); c.setLineWidth(0.3); c.rect(right-goal,ry,goal,rh,fill=0,stroke=1)
    txt((right-goal)+goal/2,ry+rh*0.34,f"___/{ndays}",8,DARK,center=True)

# outer border + separators
c.setStrokeColor(NAVY); c.setLineWidth(1.2); c.rect(left,bot,right-left,top-bot,fill=0,stroke=1)
c.line(day_x0,bot,day_x0,top); c.line(right-goal,bot,right-goal,top)

# footer
txt(left,bot-5*mm,"Tick = under daily limit. Cross = over. Fill the right column at month-end. "
    "Beat the goal -> sweep the saving into your SIP.",7.5,GREY,font='Helvetica')

c.showPage(); c.save()
print("Saved:",out)
