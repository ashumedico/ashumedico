#!/usr/bin/env python3
"""DAILY FREEDOM TRACKER — A3 checklist table. ONE BOX = ONE DAY.
Rows = months, Columns = days 1..31. Daily interest calculated per month."""

from reportlab.lib.pagesizes import A3
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from datetime import datetime
import calendar, os

# ── CONFIG ──
L1_BAL, L2_BAL = 1_48_00_000, 21_60_000
L1_RATE = 0.071
L2_RATE = 0.0785
L1_BASE, L2_BASE = 1_20_000, 20_000
FLEX = 20_000
BONUS = 5_50_000
BONUS_MONTH = 3
START = datetime(2026, 7, 1)

# ── COLORS ──
NAVY  = HexColor('#0d1b4c')
BLUE  = HexColor('#1565c0')
LBLUE = HexColor('#e3f2fd')
SKY   = HexColor('#bbdefb')
TEAL  = HexColor('#00897b')
GREEN = HexColor('#2e7d32')
LGREEN= HexColor('#c8e6c9')
RED   = HexColor('#d32f2f')
LRED  = HexColor('#ffcdd2')
ORANGE= HexColor('#f57c00')
LORNG = HexColor('#ffe0b2')
GOLD  = HexColor('#ffc107')
LGOLD = HexColor('#fff3c4')
PURPLE= HexColor('#7b1fa2')
LPURP = HexColor('#e1bee7')
WHITE = HexColor('#ffffff')
PAPER = HexColor('#fefcf3')
GREY  = HexColor('#9e9e9e')
DARK  = HexColor('#37474f')
BLACKOUT = HexColor('#cfd8dc')
ROWA  = HexColor('#ffffff')
ROWB  = HexColor('#f4f7fb')

# ── SIM ──
def add_months(dt, n):
    m = dt.month - 1 + n
    y = dt.year + m // 12
    m = m % 12 + 1
    d = calendar.monthrange(y, m)[1]
    return datetime(y, m, min(dt.day, d))

def fmt(x):
    if x <= 0: return "0"
    if x >= 1_00_00_000: return f"{x/1_00_00_000:.2f}Cr"
    if x >= 1_00_000: return f"{x/1_00_000:.1f}L"
    return f"{x/1000:.0f}K"

rows = []   # one per month
l1, l2 = float(L1_BAL), float(L2_BAL)
l2_dead_m = None
for m in range(1, 400):
    dt = add_months(START, m-1)
    bal_start = l1 + l2
    daily = (l1*L1_RATE + l2*L2_RATE) / 365   # blended daily interest this month
    i1, i2 = l1*L1_RATE/12, l2*L2_RATE/12
    bonus = BONUS if (dt.month == BONUS_MONTH and m > 1) else 0
    sp = 0
    if l2 > 0:
        pay = L2_BASE + FLEX + (bonus if bonus else 0)
        if pay > l2 + i2: sp = pay - (l2 + i2); pay = l2 + i2
    else:
        pay = 0
        if l2_dead_m is None: l2_dead_m = m
    p1 = (L1_BASE + sp) if l2 > 0 else ((L1_BASE+L2_BASE+FLEX)+(bonus if bonus else 0))
    p1 = min(p1, l1 + i1) if l1 > 0 else 0
    l1 = max(0, l1 - (max(0, p1-i1) if l1 > 0 else 0))
    l2 = max(0, l2 - (max(0, pay-i2) if l2 > 0 else 0))
    rows.append({'m': m, 'dt': dt, 'days': calendar.monthrange(dt.year, dt.month)[1],
                 'daily': daily, 'end': l1+l2, 'l2': l2})
    if l1 <= 0.01 and l2 <= 0.01:
        break

n_months = len(rows)
total_days = sum(r['days'] for r in rows)
freedom = rows[-1]['dt']

# milestones: month -> (short tag, fill, textcol)
ms = {}
def mark(cond, tag, fill, tc):
    for r in rows:
        if cond(r):
            ms[r['m']] = (tag, fill, tc); return
ms[1] = ("START", SKY, NAVY)
mark(lambda r: r['l2'] < 20_00_000, "L2<20L", LBLUE, BLUE)
mark(lambda r: r['l2'] < 10_00_000, "L2<10L", LPURP, PURPLE)
if l2_dead_m: ms[l2_dead_m] = ("L2 DEAD!", GOLD, NAVY)
mark(lambda r: r['end'] < 1_00_00_000, "<1Cr", LGREEN, GREEN)
mark(lambda r: r['end'] < 50_00_000, "HALF", LORNG, ORANGE)
mark(lambda r: r['end'] < 25_00_000, "<25L", LRED, RED)
ms[n_months] = ("FREE!", GREEN, WHITE)

# ══════════════════════════════════════════
out = 'aios/ledger/daily-freedom-tracker-A3.pdf'
os.makedirs(os.path.dirname(out), exist_ok=True)
W, H = A3
c = canvas.Canvas(out, pagesize=A3)

def txt(x, y, s, sz, col, font='Helvetica', center=False, right=False):
    c.setFillColor(col); c.setFont(font, sz)
    if center: c.drawCentredString(x, y, s)
    elif right: c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)

# background
c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)

# ── TITLE ──
c.setFillColor(NAVY); c.roundRect(8*mm, H-30*mm, W-16*mm, 22*mm, 4*mm, fill=1, stroke=0)
txt(W/2, H-19*mm, "DAILY FREEDOM TRACKER", 24, GOLD, 'Helvetica-Bold', center=True)
txt(W/2, H-26.5*mm, f"ONE BOX = ONE DAY   |   {total_days:,} days to freedom   |   "
                    f"tick a box every single day & watch the daily bleed shrink",
    11, WHITE, 'Helvetica-Bold', center=True)

# ── TABLE GEOMETRY ──
left = 8*mm
lbl_m, lbl_d, lbl_b = 20*mm, 17*mm, 17*mm      # month / daily-int / balance label cols
day_x0 = left + lbl_m + lbl_d + lbl_b
day_area = (W - 8*mm) - day_x0
dw = day_area / 31.0                           # day column width
top = H - 34*mm
header_h = 7*mm
bot = 9*mm
rh = (top - header_h - bot) / n_months         # row height

# ── HEADER ROW ──
hy = top - header_h
c.setFillColor(NAVY); c.rect(left, hy, (W-8*mm)-left, header_h, fill=1, stroke=0)
txt(left + lbl_m/2, hy + 2.3*mm, "MONTH", 6.5, WHITE, 'Helvetica-Bold', center=True)
txt(left + lbl_m + lbl_d/2, hy + 2.3*mm, "Rs/DAY", 6.5, GOLD, 'Helvetica-Bold', center=True)
txt(left + lbl_m + lbl_d + lbl_b/2, hy + 2.3*mm, "BALANCE", 6.5, WHITE, 'Helvetica-Bold', center=True)
for d in range(1, 32):
    cx = day_x0 + (d-0.5)*dw
    txt(cx, hy + 2.3*mm, str(d), 5, WHITE, 'Helvetica-Bold', center=True)

# ── DATA ROWS ──
c.setLineWidth(0.25)
prev_year = None
for idx, r in enumerate(rows):
    ry = hy - (idx+1)*rh
    milestone = ms.get(r['m'])
    # row background (alternating + milestone tint on label area)
    base = ROWB if idx % 2 else ROWA
    c.setFillColor(base); c.rect(left, ry, (W-8*mm)-left, rh, fill=1, stroke=0)

    # label cells fill (milestone color)
    if milestone:
        tag, fill, tc = milestone
        c.setFillColor(fill)
        c.rect(left, ry, lbl_m+lbl_d+lbl_b, rh, fill=1, stroke=0)
    else:
        tc = DARK

    # month label (+ milestone tag)
    mlabel = r['dt'].strftime("%b %y")
    txt(left + 1.2*mm, ry + rh*0.30, mlabel, 6, tc, 'Helvetica-Bold')
    if milestone:
        txt(left + lbl_m - 0.8*mm, ry + rh*0.30, milestone[0], 5.2, milestone[2],
            'Helvetica-Bold', right=True)
    # daily interest
    txt(left + lbl_m + lbl_d - 1*mm, ry + rh*0.30, f"{r['daily']:,.0f}", 6,
        (tc if milestone else RED), 'Helvetica-Bold', right=True)
    # balance
    txt(left + lbl_m + lbl_d + lbl_b - 1*mm, ry + rh*0.30, fmt(r['end']), 6,
        tc, 'Helvetica-Bold', right=True)

    # day cells
    for d in range(1, 32):
        cx = day_x0 + (d-1)*dw
        if d > r['days']:
            c.setFillColor(BLACKOUT); c.rect(cx, ry, dw, rh, fill=1, stroke=0)
        else:
            c.setStrokeColor(HexColor('#b0bec5')); c.setLineWidth(0.25)
            c.rect(cx, ry, dw, rh, fill=0, stroke=1)

    # year separator (thick line + tab) when year changes
    if r['dt'].year != prev_year:
        c.setStrokeColor(NAVY); c.setLineWidth(1.2)
        c.line(left, ry + rh, W-8*mm, ry + rh)
        prev_year = r['dt'].year

# outer table border
c.setStrokeColor(NAVY); c.setLineWidth(1.5)
c.rect(left, bot, (W-8*mm)-left, top - bot, fill=0, stroke=1)
# vertical separators for label columns
c.setLineWidth(1)
for vx in (left+lbl_m, left+lbl_m+lbl_d, day_x0):
    c.line(vx, bot, vx, top)

# ── FOOTER LEGEND ──
ly = bot - 0*mm
c.setFillColor(NAVY); c.setFont('Helvetica-Bold', 7)
# (legend kept minimal; title carries the instructions)

c.showPage(); c.save()
print(f"Saved: {out}")
print(f"Months: {n_months} | Total day-boxes: {total_days:,} | Freedom: {freedom.strftime('%B %Y')}")
print(f"Row height: {rh/mm:.2f}mm | Day box: {dw/mm:.2f}w x {rh/mm:.2f}h mm | L2 dead month {l2_dead_m}")
