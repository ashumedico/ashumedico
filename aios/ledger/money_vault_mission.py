#!/usr/bin/env python3
"""MONEY VAULT MISSION — Single A3 playful goal-setter poster with cartoon mascot."""

from reportlab.lib.pagesizes import A3
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas
from datetime import datetime
import math, os

# ── CONFIG ──
L1_BAL, L2_BAL = 1_48_00_000, 21_60_000
L1_RATE = 0.071
L2_RATE = 0.0785
L1_BASE, L2_BASE = 1_20_000, 20_000
FLEX = 20_000              # extra into L2
BONUS = 5_50_000
BONUS_MONTH = 3
START = datetime(2026, 7, 1)

# ── COLORS ──
NAVY   = HexColor('#0d1b4c')
BLUE   = HexColor('#1565c0')
SKY    = HexColor('#4fc3f7')
LSKY   = HexColor('#b3e5fc')
TEAL   = HexColor('#00897b')
GREEN  = HexColor('#2e7d32')
LGREEN = HexColor('#a5d6a7')
LIME   = HexColor('#7cb342')
RED    = HexColor('#d32f2f')
CRIMSON= HexColor('#b71c1c')
ORANGE = HexColor('#f57c00')
GOLD   = HexColor('#ffc107')
GOLD2  = HexColor('#ffa000')
YELLOW = HexColor('#fff176')
CREAM  = HexColor('#fff8e1')
PURPLE = HexColor('#7b1fa2')
LPURP  = HexColor('#ce93d8')
PINK   = HexColor('#ec407a')
WHITE  = HexColor('#ffffff')
BLACK  = HexColor('#1a1a1a')
BEAK   = HexColor('#ff9800')
PAPER  = HexColor('#fefcf3')
GREY   = HexColor('#9e9e9e')

# ── SIMULATE ──
def add_months(dt, n):
    m = dt.month - 1 + n
    y = dt.year + m // 12
    m = m % 12 + 1
    days = [31, 29 if y%4==0 and (y%100!=0 or y%400==0) else 28,31,30,31,30,31,31,30,31,30,31]
    return datetime(y, m, min(dt.day, days[m-1]))

def simulate():
    l1, l2 = float(L1_BAL), float(L2_BAL)
    recs = []
    for m in range(1, 400):
        dt = add_months(START, m-1)
        l1_int, l2_int = l1*L1_RATE/12, l2*L2_RATE/12
        bonus = BONUS if (dt.month == BONUS_MONTH and m > 1) else 0
        surplus = 0
        if l2 > 0:
            l2_pay = L2_BASE + FLEX + (bonus if bonus else 0)
            if l2_pay > l2 + l2_int:
                surplus = l2_pay - (l2 + l2_int); l2_pay = l2 + l2_int
        else:
            l2_pay = 0
        if l2 > 0:
            l1_pay = L1_BASE + surplus
        else:
            l1_pay = (L1_BASE + L2_BASE + FLEX) + (bonus if bonus else 0)
        l1_pay = min(l1_pay, l1 + l1_int) if l1 > 0 else 0
        l1_prin = max(0, l1_pay - l1_int) if l1 > 0 else 0
        l2_prin = max(0, l2_pay - l2_int) if l2 > 0 else 0
        l1 = max(0, l1 - l1_prin); l2 = max(0, l2 - l2_prin)
        recs.append({'m': m, 'dt': dt, 'l1': l1, 'l2': l2, 'tot': l1+l2,
                     'daily': (l1*L1_RATE + l2*L2_RATE)/365})
        if l1 <= 0.01 and l2 <= 0.01:
            break
    return recs

recs = simulate()
def first(cond):
    for r in recs:
        if cond(r): return r
    return recs[-1]

freedom = recs[-1]['dt']
months = len(recs)
daily0 = (L1_BAL*L1_RATE + L2_BAL*L2_RATE)/365

# ── MILESTONES (checkpoints) ──
CP = [
    ("START!",  START,                              "Rs 1.70 Cr",  "Adventure\nbegins", SKY),
    ("Lvl 2",   first(lambda r: r['l2'] < 20_00_000)['dt'], "L2 < 20L", "First\nBlood!", BLUE),
    ("Lvl 3",   first(lambda r: r['l2'] < 10_00_000)['dt'], "Under 1.5Cr", "Half-kill\nLoan 2", PURPLE),
    ("BOOM!",   first(lambda r: r['l2'] <= 100)['dt'],      "LOAN 2 DEAD", "Snowball\nUNLEASHED", GOLD2),
    ("Lvl 5",   first(lambda r: r['tot'] < 1_25_00_000)['dt'], "Under 1.25Cr", "Picking up\nspeed", TEAL),
    ("Lvl 6",   first(lambda r: r['tot'] < 1_00_00_000)['dt'], "UNDER 1 CRORE", "Crore\nCrusher!", GREEN),
    ("Lvl 7",   first(lambda r: r['tot'] < 75_00_000)['dt'],  "Under 75L", "Three\nquarters", LIME),
    ("Lvl 8",   first(lambda r: r['tot'] < 50_00_000)['dt'],  "HALFWAY HOME", "Downhill\nfrom here", ORANGE),
    ("Lvl 9",   first(lambda r: r['tot'] < 25_00_000)['dt'],  "Under 25L", "Victory\nlap", PINK),
    ("Lvl 10",  first(lambda r: r['tot'] < 10_00_000)['dt'],  "Single digits", "Almost\nthere!", RED),
    ("FREEDOM", freedom,                            "Rs 0 — FREE!", "VAULT\nUNLOCKED", GREEN),
]

# ══════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ══════════════════════════════════════════════════════════
W, H = A3  # portrait points
c = None

def text(x, y, s, size, col, font='Helvetica-Bold', center=False, right=False, angle=0):
    c.saveState()
    c.translate(x, y)
    if angle: c.rotate(angle)
    c.setFillColor(col)
    c.setFont(font, size)
    if center: c.drawCentredString(0, 0, s)
    elif right: c.drawRightString(0, 0, s)
    else: c.drawString(0, 0, s)
    c.restoreState()

def coin(x, y, r, label=None):
    c.setFillColor(GOLD2); c.circle(x, y, r, fill=1, stroke=0)
    c.setFillColor(GOLD);  c.circle(x, y, r*0.82, fill=1, stroke=0)
    c.setStrokeColor(GOLD2); c.setLineWidth(0.8); c.circle(x, y, r*0.82, fill=0, stroke=1)
    if label:
        c.setFillColor(GOLD2); c.setFont('Helvetica-Bold', r*0.9)
        c.drawCentredString(x, y - r*0.32, label)
    # shine
    c.setFillColor(WHITE); c.circle(x - r*0.3, y + r*0.3, r*0.16, fill=1, stroke=0)

def coin_pile(cx, cy, w):
    """Mound of gold coins."""
    import random
    rnd = [(0.0,0.0),( -0.35,0.05),(0.35,0.04),(-0.18,0.22),(0.18,0.20),(0.0,0.38),
           (-0.5,0.0),(0.5,0.0),(-0.28,-0.02),(0.28,-0.02),(0.0,0.12),(-0.42,0.18),(0.42,0.16)]
    for i,(dx,dy) in enumerate(rnd):
        coin(cx + dx*w, cy + dy*w*0.6, w*0.12)

def sparkle(x, y, r, col=YELLOW):
    c.setFillColor(col)
    p = c.beginPath()
    for i in range(8):
        ang = math.radians(i*45)
        rr = r if i%2==0 else r*0.4
        px, py = x + rr*math.cos(ang), y + rr*math.sin(ang)
        if i==0: p.moveTo(px,py)
        else: p.lineTo(px,py)
    p.close(); c.drawPath(p, fill=1, stroke=0)

def star(x, y, r, col=GOLD):
    c.setFillColor(col)
    p = c.beginPath()
    for i in range(10):
        ang = math.radians(-90 + i*36)
        rr = r if i%2==0 else r*0.42
        px, py = x + rr*math.cos(ang), y + rr*math.sin(ang)
        if i==0: p.moveTo(px,py)
        else: p.lineTo(px,py)
    p.close(); c.drawPath(p, fill=1, stroke=0)

def rrect(x, y, w, h, r, fill, stroke=None, sw=1):
    c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1 if stroke else 0)

def duck(cx, cy, s):
    """Cartoon rich-uncle duck, top hat + monocle + cane, tossing coins."""
    # --- tail coat (red) behind body ---
    c.setFillColor(CRIMSON)
    c.setStrokeColor(BLACK); c.setLineWidth(1.5)
    # body coat
    p = c.beginPath()
    p.moveTo(cx-22*s, cy-8*s)
    p.curveTo(cx-30*s, cy-40*s, cx-14*s, cy-52*s, cx, cy-52*s)
    p.curveTo(cx+14*s, cy-52*s, cx+30*s, cy-40*s, cx+22*s, cy-8*s)
    p.curveTo(cx+12*s, cy+2*s, cx-12*s, cy+2*s, cx-22*s, cy-8*s)
    p.close(); c.drawPath(p, fill=1, stroke=1)
    # coat tails
    c.setFillColor(CRIMSON)
    for sgn in (-1, 1):
        p = c.beginPath()
        p.moveTo(cx+sgn*8*s, cy-48*s)
        p.lineTo(cx+sgn*22*s, cy-66*s)
        p.lineTo(cx+sgn*2*s, cy-52*s)
        p.close(); c.drawPath(p, fill=1, stroke=1)
    # belly (gold waistcoat)
    c.setFillColor(GOLD)
    p = c.beginPath()
    p.moveTo(cx-12*s, cy-12*s)
    p.curveTo(cx-16*s, cy-40*s, cx+16*s, cy-40*s, cx+12*s, cy-12*s)
    p.close(); c.drawPath(p, fill=1, stroke=1)
    # buttons
    c.setFillColor(BLACK)
    for i in range(3):
        c.circle(cx, cy-18*s - i*8*s, 1.3*s, fill=1, stroke=0)

    # --- legs + spats ---
    c.setStrokeColor(BEAK); c.setLineWidth(3*s)
    c.line(cx-8*s, cy-50*s, cx-8*s, cy-60*s)
    c.line(cx+8*s, cy-50*s, cx+8*s, cy-60*s)
    c.setFillColor(WHITE); c.setStrokeColor(BLACK); c.setLineWidth(1.2)
    c.roundRect(cx-13*s, cy-66*s, 11*s, 8*s, 2*s, fill=1, stroke=1)  # spat
    c.roundRect(cx+2*s,  cy-66*s, 11*s, 8*s, 2*s, fill=1, stroke=1)
    c.setFillColor(BEAK)
    c.ellipse(cx-15*s, cy-69*s, cx-1*s, cy-63*s, fill=1, stroke=1)   # feet
    c.ellipse(cx+1*s,  cy-69*s, cx+15*s, cy-63*s, fill=1, stroke=1)

    # --- arms ---
    c.setFillColor(CRIMSON); c.setStrokeColor(BLACK); c.setLineWidth(1.5)
    # left arm up (tossing)
    c.saveState(); c.translate(cx-20*s, cy-18*s); c.rotate(35)
    c.roundRect(0, 0, 22*s, 9*s, 4*s, fill=1, stroke=1); c.restoreState()
    # right arm holding cane
    c.saveState(); c.translate(cx+20*s, cy-20*s); c.rotate(-25)
    c.roundRect(-2*s, 0, 20*s, 9*s, 4*s, fill=1, stroke=1); c.restoreState()
    # hands (white gloves)
    c.setFillColor(WHITE)
    c.circle(cx-36*s, cy+6*s, 4.5*s, fill=1, stroke=1)
    c.circle(cx+36*s, cy-30*s, 4.5*s, fill=1, stroke=1)

    # --- cane ---
    c.setStrokeColor(HexColor('#5d4037')); c.setLineWidth(2.5*s)
    c.line(cx+36*s, cy-30*s, cx+44*s, cy-66*s)
    c.setStrokeColor(GOLD2); c.setLineWidth(3*s)
    c.saveState(); c.translate(cx+36*s, cy-30*s)
    c.arc(-3*s, -3*s, 7*s, 9*s, 0, 200); c.restoreState()

    # --- head ---
    c.setFillColor(WHITE); c.setStrokeColor(BLACK); c.setLineWidth(1.5)
    c.circle(cx, cy+16*s, 18*s, fill=1, stroke=1)
    # side whiskers (sideburns)
    c.setFillColor(WHITE)
    for sgn in (-1,1):
        p = c.beginPath()
        p.moveTo(cx+sgn*15*s, cy+22*s)
        p.curveTo(cx+sgn*26*s, cy+18*s, cx+sgn*24*s, cy+4*s, cx+sgn*16*s, cy+6*s)
        p.close(); c.drawPath(p, fill=1, stroke=1)
    # beak
    c.setFillColor(BEAK)
    p = c.beginPath()
    p.moveTo(cx-6*s, cy+14*s)
    p.curveTo(cx-16*s, cy+12*s, cx-16*s, cy+6*s, cx-5*s, cy+7*s)
    p.curveTo(cx-2*s, cy+5*s, cx-2*s, cy+15*s, cx-6*s, cy+14*s)
    p.close(); c.drawPath(p, fill=1, stroke=1)
    # eyes
    c.setFillColor(WHITE); c.setStrokeColor(BLACK); c.setLineWidth(1)
    c.circle(cx+2*s, cy+22*s, 5*s, fill=1, stroke=1)
    c.circle(cx+11*s, cy+22*s, 5*s, fill=1, stroke=1)
    c.setFillColor(BLACK)
    c.circle(cx+3*s, cy+22*s, 1.8*s, fill=1, stroke=0)
    c.circle(cx+12*s, cy+22*s, 1.8*s, fill=1, stroke=0)
    # monocle on right eye
    c.setStrokeColor(GOLD2); c.setLineWidth(1.5*s)
    c.circle(cx+11*s, cy+22*s, 6.5*s, fill=0, stroke=1)
    c.setStrokeColor(GOLD2); c.setLineWidth(0.8*s)
    c.line(cx+15*s, cy+17*s, cx+18*s, cy+8*s)
    # eyebrows (rich & smug)
    c.setStrokeColor(WHITE); c.setLineWidth(3*s)
    c.line(cx-2*s, cy+29*s, cx+6*s, cy+30*s)
    c.line(cx+8*s, cy+30*s, cx+15*s, cy+29*s)

    # --- top hat (blue) ---
    c.setFillColor(NAVY); c.setStrokeColor(BLACK); c.setLineWidth(1.5)
    c.ellipse(cx-20*s, cy+30*s, cx+18*s, cy+36*s, fill=1, stroke=1)   # brim
    c.roundRect(cx-13*s, cy+34*s, 26*s, 20*s, 2*s, fill=1, stroke=1)  # crown
    c.setFillColor(RED)
    c.rect(cx-13*s, cy+34*s, 26*s, 4*s, fill=1, stroke=0)             # band

    # --- tossed coins + sparkles ---
    coin(cx-44*s, cy+22*s, 5*s); coin(cx-50*s, cy+8*s, 4*s)
    coin(cx-40*s, cy+36*s, 4*s)
    sparkle(cx-46*s, cy+34*s, 4*s); sparkle(cx+30*s, cy+40*s, 3.5*s)
    star(cx+44*s, cy+20*s, 4*s, YELLOW)

# ══════════════════════════════════════════════════════════
#  BUILD PAGE
# ══════════════════════════════════════════════════════════
out = 'aios/ledger/money-vault-mission-A3.pdf'
os.makedirs(os.path.dirname(out), exist_ok=True)
c = canvas.Canvas(out, pagesize=A3)

# background
c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
# playful border
c.setStrokeColor(NAVY); c.setLineWidth(6); c.setDash(1)
c.roundRect(10*mm, 10*mm, W-20*mm, H-20*mm, 8*mm, fill=0, stroke=1)
c.setStrokeColor(GOLD2); c.setLineWidth(2)
c.roundRect(13*mm, 13*mm, W-26*mm, H-26*mm, 7*mm, fill=0, stroke=1)
c.setDash()

# scattered background coins (faint)
for (cx,cy) in [(30,395),(270,400),(25,40),(275,35),(150,30),(290,200),(20,210)]:
    coin(cx*mm, cy*mm, 4*mm)

# ── TITLE BANNER ──
rrect(20*mm, 340*mm, W-40*mm, 60*mm, 6*mm, NAVY, GOLD2, 3)
text(W/2, 385*mm, "OPERATION:", 30, GOLD, center=True)
text(W/2, 366*mm, "MONEY VAULT", 46, WHITE, center=True)
text(W/2, 349*mm, "Aashish & Kalyani's Great Debt Escape", 16, LSKY, font='Helvetica-BoldOblique', center=True)
# mascot on banner
duck(58*mm, 367*mm, 0.78)
coin_pile(54*mm, 345*mm, 44*mm)

# ── STATS STRIP ──
stat_y = 312*mm
sw = (W-40*mm)/4
stats = [("THE BEAST", "Rs 1.70 Cr", "total debt", RED),
         ("THE LEAK", f"Rs {daily0:,.0f}/day", "interest bleed", ORANGE),
         ("WAR CHEST", "Rs 1.6L/mo", "L1 1.2L + L2 40k", BLUE),
         ("FREEDOM", freedom.strftime('%b %Y'), f"{months} months", GREEN)]
for i,(t,big,sub,col) in enumerate(stats):
    x = 20*mm + i*sw
    rrect(x+2*mm, stat_y, sw-4*mm, 22*mm, 4*mm, WHITE, col, 2)
    text(x+sw/2, stat_y+16*mm, t, 11, col, center=True)
    text(x+sw/2, stat_y+8.5*mm, big, 16, NAVY, center=True)
    text(x+sw/2, stat_y+3*mm, sub, 8, GREY, font='Helvetica', center=True)

# ── BOARD GAME PATH ──
cols = [62, 148.5, 235]
rows = [290, 228, 166, 104]
# snake order positions for 11 checkpoints + treasure
slots = [
    (cols[0],rows[0]),(cols[1],rows[0]),(cols[2],rows[0]),
    (cols[2],rows[1]),(cols[1],rows[1]),(cols[0],rows[1]),
    (cols[0],rows[2]),(cols[1],rows[2]),(cols[2],rows[2]),
    (cols[2],rows[3]),(cols[1],rows[3]),
]
treasure_slot = (cols[0], rows[3])

# draw connecting dotted path (snake)
path_pts = [(x*mm, y*mm) for (x,y) in slots] + [(treasure_slot[0]*mm, treasure_slot[1]*mm)]
c.setStrokeColor(GOLD2); c.setLineWidth(5); c.setDash(2, 6); c.setLineCap(1)
c.setStrokeColor(HexColor('#ffcc66'))
for i in range(len(path_pts)-1):
    x0,y0 = path_pts[i]; x1,y1 = path_pts[i+1]
    c.line(x0, y0, x1, y1)
c.setDash()

# footprint coins along path
for i in range(len(path_pts)-1):
    x0,y0 = path_pts[i]; x1,y1 = path_pts[i+1]
    for t in (0.33, 0.66):
        coin(x0+(x1-x0)*t, y0+(y1-y0)*t, 2.6*mm)

# draw checkpoints
R = 21*mm
for i,(name, dt, big, sub, col) in enumerate(CP):
    x, y = slots[i][0]*mm, slots[i][1]*mm
    boom = name in ("BOOM!", "START!")
    # token shadow
    c.setFillColor(HexColor('#00000022')); c.circle(x+1.5*mm, y-1.5*mm, R, fill=1, stroke=0)
    # token
    c.setFillColor(col); c.setStrokeColor(WHITE); c.setLineWidth(3)
    c.circle(x, y, R, fill=1, stroke=1)
    c.setStrokeColor(NAVY); c.setLineWidth(1.5); c.circle(x, y, R, fill=0, stroke=1)
    if name == "BOOM!":
        sparkle(x-R, y+R*0.6, 6*mm); sparkle(x+R, y+R*0.7, 5*mm)
    # number badge
    c.setFillColor(WHITE); c.circle(x-R+5*mm, y+R-5*mm, 6*mm, fill=1, stroke=0)
    c.setStrokeColor(col); c.setLineWidth(1.5); c.circle(x-R+5*mm, y+R-5*mm, 6*mm, fill=0, stroke=1)
    text(x-R+5*mm, y+R-7*mm, str(i+1), 13, col, center=True)
    # content
    tc = WHITE if col in (NAVY,BLUE,PURPLE,GREEN,RED,TEAL,CRIMSON,ORANGE,PINK,GOLD2) else NAVY
    text(x, y+9*mm, name, 13, tc, center=True)
    text(x, y+1.5*mm, big, 11, tc, center=True)
    for j,ln in enumerate(sub.split('\n')):
        text(x, y-5*mm - j*4.2*mm, ln, 8.5, tc, font='Helvetica-Bold', center=True)
    # date ribbon under token
    rrect(x-16*mm, y-R-9*mm, 32*mm, 7*mm, 2*mm, NAVY, None)
    text(x, y-R-6.8*mm, dt.strftime('%b %Y'), 9.5, GOLD, center=True)
    # tick box
    c.setFillColor(WHITE); c.setStrokeColor(NAVY); c.setLineWidth(2)
    c.roundRect(x+R-7*mm, y-R+1*mm, 8*mm, 8*mm, 1.5*mm, fill=1, stroke=1)
    text(x+R-5.5*mm, y-R+8.5*mm, "done", 5.5, GREY, font='Helvetica', center=False)

# ── TREASURE CHEST FINALE ──
tx, ty = treasure_slot[0]*mm, treasure_slot[1]*mm
# burst
for k in range(12):
    ang = math.radians(k*30)
    c.setStrokeColor(GOLD); c.setLineWidth(2.5)
    c.line(tx, ty, tx + (R+8*mm)*math.cos(ang), ty + (R+8*mm)*math.sin(ang))
sparkle(tx-R, ty+R, 6*mm); sparkle(tx+R, ty+R, 6*mm); star(tx, ty+R+9*mm, 6*mm)
# chest base
c.setFillColor(HexColor('#6d4c41')); c.setStrokeColor(BLACK); c.setLineWidth(2)
c.roundRect(tx-19*mm, ty-13*mm, 38*mm, 20*mm, 2*mm, fill=1, stroke=1)
# lid
c.setFillColor(HexColor('#5d4037'))
p = c.beginPath()
p.moveTo(tx-19*mm, ty+7*mm); p.lineTo(tx-19*mm, ty+12*mm)
p.curveTo(tx-10*mm, ty+22*mm, tx+10*mm, ty+22*mm, tx+19*mm, ty+12*mm)
p.lineTo(tx+19*mm, ty+7*mm); p.close(); c.drawPath(p, fill=1, stroke=1)
# gold bands
c.setFillColor(GOLD2)
c.rect(tx-19*mm, ty-13*mm, 38*mm, 2.5*mm, fill=1, stroke=0)
c.rect(tx-3*mm, ty-13*mm, 6*mm, 20*mm, fill=1, stroke=0)
# lock
c.setFillColor(GOLD); c.circle(tx, ty+1*mm, 4*mm, fill=1, stroke=1)
c.setFillColor(BLACK); c.circle(tx, ty+1*mm, 1.3*mm, fill=1, stroke=0)
# overflowing coins
for (dx,dy) in [(-13,9),(-6,13),(2,14),(10,12),(15,9),(-2,11),(7,13)]:
    coin(tx+dx*mm, ty+dy*mm, 3*mm)
# label
rrect(tx-21*mm, ty-R-9*mm, 42*mm, 7*mm, 2*mm, GREEN, None)
text(tx, ty-R-6.8*mm, "FREEDOM DAY!", 10, WHITE, center=True)
text(tx, ty-13*mm-6*mm, freedom.strftime('%B %Y'), 12, GREEN, center=True)

# ── FOOTER: GOLDEN RULES + PAYOFF ──
fy = 22*mm
rrect(20*mm, fy, W-40*mm, 50*mm, 5*mm, CREAM, GOLD2, 2.5)
text(36*mm, fy+40*mm, "THE 5 GOLDEN RULES", 17, CRIMSON)
rules = [
    "1.  Pay the Rs 1.6L EMI FIRST — before anything else hits the account.",
    "2.  Every bonus & windfall = 100% into the loan. No exceptions.",
    "3.  Loan 2 dies first (month 33). Then ALL Rs 1.6L smashes Loan 1.",
    "4.  Zero new debt. Not a single rupee.",
    "5.  Tick a box every month. Colour the coin. Celebrate every Level!",
]
for i,r in enumerate(rules):
    text(36*mm, fy+33*mm - i*6*mm, r, 11.5, NAVY, font='Helvetica')
# payoff badge
bank_int = None
# quick bank interest vs ours
def total_interest(extra_l1, extra_l2, bonus_on):
    l1,l2 = float(L1_BAL), float(L2_BAL); ti=0
    for m in range(1,600):
        dt=add_months(START,m-1)
        i1,i2=l1*L1_RATE/12,l2*L2_RATE/12; ti+=i1+i2
        bonus=BONUS if (bonus_on and dt.month==BONUS_MONTH and m>1) else 0
        sp=0
        if l2>0:
            pay=L2_BASE+extra_l2+(bonus if bonus else 0)
            if pay>l2+i2: sp=pay-(l2+i2); pay=l2+i2
        else: pay=0
        p1=L1_BASE+extra_l1+sp if l2>0 else (L1_BASE+L2_BASE+extra_l2)+(bonus if bonus else 0)
        p1=min(p1,l1+i1) if l1>0 else 0
        l1=max(0,l1-(max(0,p1-i1) if l1>0 else 0)); l2=max(0,l2-(max(0,pay-i2) if l2>0 else 0))
        if l1<=0.01 and l2<=0.01: return ti, m
    return ti, m
bank_i, bank_m = total_interest(0,0,False)
our_i, our_m = total_interest(0,FLEX,True)
saved = bank_i - our_i
rrect(W-95*mm, fy+5*mm, 75*mm, 40*mm, 4*mm, GREEN, None)
text(W-57.5*mm, fy+37*mm, "YOUR REWARD", 12, YELLOW, center=True)
text(W-57.5*mm, fy+27*mm, f"Rs {saved/1e5:.0f}L SAVED", 21, WHITE, center=True)
text(W-57.5*mm, fy+18*mm, f"{bank_m - our_m} months earlier", 12, LGREEN, center=True)
text(W-57.5*mm, fy+9*mm, "vs the bank's slow plan", 9.5, CREAM, font='Helvetica-Oblique', center=True)

c.showPage(); c.save()
print(f"Saved: {out}")
print(f"Freedom: {freedom.strftime('%B %Y')} ({months} months)")
print(f"Bank interest: {bank_i/1e5:.1f}L over {bank_m} mo | Ours: {our_i/1e5:.1f}L over {our_m} mo | Saved: {saved/1e5:.1f}L")
print(f"L2 dies: month {first(lambda r: r['l2']<=100)['m']}")
