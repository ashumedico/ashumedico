#!/usr/bin/env python3
"""DEBT FREEDOM MISSION — Colorful Goal-Setter PDF"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
from datetime import datetime

# ── CONFIG ──
L1_BAL = 1_48_00_000
L2_BAL = 21_60_000
L1_RATE = 0.071
L2_RATE = 0.0785
L1_BASE = 1_20_000
L2_BASE = 20_000
TOTAL = 1_60_000
FLEX = TOTAL - L1_BASE - L2_BASE
BONUS = 5_50_000
BONUS_MONTH = 3
START = datetime(2026, 7, 1)

# ── COLORS ──
NAVY = HexColor('#1a237e')
BLUE = HexColor('#1565c0')
LIGHT_BLUE = HexColor('#e3f2fd')
TEAL = HexColor('#00897b')
GREEN = HexColor('#2e7d32')
LIGHT_GREEN = HexColor('#e8f5e9')
BRIGHT_GREEN = HexColor('#43a047')
ORANGE = HexColor('#e65100')
AMBER = HexColor('#ff8f00')
RED = HexColor('#c62828')
LIGHT_RED = HexColor('#ffebee')
GOLD = HexColor('#f9a825')
LIGHT_GOLD = HexColor('#fff8e1')
PURPLE = HexColor('#6a1b9a')
LIGHT_PURPLE = HexColor('#f3e5f5')
GREY = HexColor('#9e9e9e')
LIGHT_GREY = HexColor('#fafafa')
WHITE = HexColor('#ffffff')
DARK = HexColor('#212121')
MINT = HexColor('#e0f2f1')

# ── HELPERS ──
def add_months(dt, n):
    m = dt.month - 1 + n
    y = dt.year + m // 12
    m = m % 12 + 1
    days = [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    d = min(dt.day, days[m - 1])
    return datetime(y, m, d)

def fmt_inr(x):
    if x >= 1_00_00_000:
        return f"{x / 1_00_00_000:.2f} Cr"
    if x >= 1_00_000:
        return f"{x / 1_00_000:.1f}L"
    if x >= 1000:
        return f"{x / 1000:.1f}K"
    return f"{x:.0f}"

def fmt_short(x):
    if x >= 1_00_00_000:
        return f"{x / 1_00_00_000:.2f}Cr"
    if x >= 1_00_000:
        return f"{x / 1_00_000:.1f}L"
    return f"{x / 1000:.0f}K"

# ── SIMULATE ──
def simulate(l1_extra, l2_extra, use_bonus=True, label=''):
    l1, l2 = float(L1_BAL), float(L2_BAL)
    records = []
    total_int = 0.0
    l2_dead = None

    for m in range(1, 500):
        dt = add_months(START, m - 1)
        l1_int = l1 * L1_RATE / 12
        l2_int = l2 * L2_RATE / 12

        bonus = BONUS if (use_bonus and dt.month == BONUS_MONTH and m > 1) else 0
        surplus = 0

        if l2 > 0:
            l2_pay = L2_BASE + l2_extra
            if bonus > 0:
                l2_pay += bonus
            if l2_pay > l2 + l2_int:
                surplus = l2_pay - (l2 + l2_int)
                l2_pay = l2 + l2_int
        else:
            l2_pay = 0.0
            if l2_dead is None:
                l2_dead = m - 1

        if l2 > 0:
            l1_pay = float(L1_BASE + l1_extra + surplus)
        else:
            l1_pay = float(TOTAL) + (bonus if bonus > 0 else 0)

        l1_pay = min(l1_pay, l1 + l1_int) if l1 > 0 else 0.0

        l1_prin = max(0, l1_pay - l1_int) if l1 > 0 else 0.0
        l2_prin = max(0, l2_pay - l2_int) if l2 > 0 else 0.0

        l1 = max(0, l1 - l1_prin)
        l2 = max(0, l2 - l2_prin)
        total_int += l1_int + l2_int
        daily_int = (l1 * L1_RATE + l2 * L2_RATE) / 365

        milestone = ''
        if l2 > 0 and l2 <= 0.01:
            milestone = 'L2 KILLED!'
        elif l2_dead == m - 1 and m > 1:
            milestone = 'SNOWBALL ON!'
        if l1 + l2 > 0:
            tb = l1 + l2
            prev_tb = records[-1]['total_bal'] if records else L1_BAL + L2_BAL
            if prev_tb >= 1_50_00_000 and tb < 1_50_00_000:
                milestone = '< 1.5 Cr!'
            elif prev_tb >= 1_25_00_000 and tb < 1_25_00_000:
                milestone = '< 1.25 Cr!'
            elif prev_tb >= 1_00_00_000 and tb < 1_00_00_000:
                milestone = 'UNDER 1 Cr!'
            elif prev_tb >= 75_00_000 and tb < 75_00_000:
                milestone = '< 75L!'
            elif prev_tb >= 50_00_000 and tb < 50_00_000:
                milestone = 'HALFWAY!'
            elif prev_tb >= 25_00_000 and tb < 25_00_000:
                milestone = '< 25L!'
            elif prev_tb >= 10_00_000 and tb < 10_00_000:
                milestone = 'SINGLE DIGITS!'

        if l1 <= 0.01 and l2 <= 0.01:
            milestone = 'DEBT FREE!'

        records.append({
            'month': m, 'date': dt,
            'l1_bal': l1, 'l2_bal': l2,
            'l1_pay': l1_pay, 'l2_pay': l2_pay,
            'l1_int': l1_int, 'l2_int': l2_int,
            'l1_prin': l1_prin, 'l2_prin': l2_prin,
            'total_bal': l1 + l2,
            'daily_int': daily_int,
            'cum_int': total_int,
            'bonus': bonus,
            'milestone': milestone,
        })

        if l1 <= 0.01 and l2 <= 0.01:
            break

    return {
        'label': label, 'records': records,
        'months': len(records), 'total_int': total_int,
        'l2_dead': l2_dead if l2_dead else len(records),
    }

# ── RUN STRATEGIES ──
bank = simulate(0, 0, False, "Bank's Plan")
current = simulate(10000, 10000, True, "Current Pattern")
current_nb = simulate(10000, 10000, False, "Current (No Bonus)")
snowball = simulate(0, FLEX, True, "SNOWBALL KILL")
snowball_nb = simulate(0, FLEX, False, "Snowball (No Bonus)")
best = snowball

print(f"Bank: {bank['months']} months, Interest: {fmt_inr(bank['total_int'])}")
print(f"Current: {current['months']} months, L2 dead: {current['l2_dead']}, Interest: {fmt_inr(current['total_int'])}")
print(f"Current NB: {current_nb['months']} months, Interest: {fmt_inr(current_nb['total_int'])}")
print(f"Snowball: {snowball['months']} months, L2 dead: {snowball['l2_dead']}, Interest: {fmt_inr(snowball['total_int'])}")
print(f"Snowball NB: {snowball_nb['months']} months, Interest: {fmt_inr(snowball_nb['total_int'])}")

# ── STYLES ──
def make_style(name, parent_name='Normal', **kw):
    from reportlab.lib.styles import getSampleStyleSheet
    base = getSampleStyleSheet()[parent_name]
    return ParagraphStyle(name, parent=base, **kw)

s_title = make_style('T', fontSize=30, textColor=NAVY, alignment=TA_CENTER,
                      fontName='Helvetica-Bold', spaceAfter=2*mm)
s_sub = make_style('Sub', fontSize=16, textColor=BLUE, alignment=TA_CENTER,
                    spaceAfter=3*mm)
s_body = make_style('B', fontSize=10, textColor=DARK, leading=14)
s_body_c = make_style('BC', fontSize=10, textColor=DARK, alignment=TA_CENTER, leading=14)
s_body_sm = make_style('BSm', fontSize=8, textColor=DARK, leading=10)
s_body_sm_c = make_style('BSmC', fontSize=8, textColor=DARK, alignment=TA_CENTER, leading=10)
s_heading = make_style('H', fontSize=14, textColor=NAVY, fontName='Helvetica-Bold',
                        spaceBefore=4*mm, spaceAfter=2*mm)
s_heading2 = make_style('H2', fontSize=12, textColor=TEAL, fontName='Helvetica-Bold',
                         spaceBefore=3*mm, spaceAfter=2*mm)
s_big_num = make_style('BN', fontSize=22, textColor=RED, fontName='Helvetica-Bold',
                        alignment=TA_CENTER)
s_big_green = make_style('BG', fontSize=22, textColor=GREEN, fontName='Helvetica-Bold',
                          alignment=TA_CENTER)
s_quote = make_style('Q', fontSize=10, textColor=PURPLE, fontName='Helvetica-Oblique',
                      alignment=TA_CENTER, spaceBefore=3*mm, spaceAfter=3*mm)
s_cell = make_style('Cell', fontSize=7, textColor=DARK, leading=9)
s_cell_c = make_style('CellC', fontSize=7, textColor=DARK, alignment=TA_CENTER, leading=9)
s_cell_r = make_style('CellR', fontSize=7, textColor=DARK, alignment=TA_RIGHT, leading=9)
s_cell_b = make_style('CellB', fontSize=7, textColor=DARK, fontName='Helvetica-Bold', leading=9)
s_cell_bc = make_style('CellBC', fontSize=7, textColor=DARK, fontName='Helvetica-Bold',
                        alignment=TA_CENTER, leading=9)
s_hdr = make_style('Hdr', fontSize=7, textColor=WHITE, fontName='Helvetica-Bold',
                    alignment=TA_CENTER, leading=9)
s_milestone_cell = make_style('MsC', fontSize=7, textColor=GREEN, fontName='Helvetica-Bold',
                               leading=9)

# ── BUILD PDF ──
output_path = 'aios/ledger/debt-freedom-mission.pdf'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
doc = SimpleDocTemplate(
    output_path, pagesize=A4,
    leftMargin=12*mm, rightMargin=12*mm,
    topMargin=12*mm, bottomMargin=12*mm,
)
elements = []

# ═══════════ PAGE 1: COVER ═══════════
elements.append(Spacer(1, 15*mm))
elements.append(Paragraph("DEBT FREEDOM", s_title))
elements.append(Spacer(1, 2*mm))
elements.append(Paragraph("MISSION", make_style('T2', fontSize=36, textColor=RED,
                           alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=3*mm)))
elements.append(Spacer(1, 2*mm))
elements.append(HRFlowable(width="80%", thickness=2, color=NAVY, spaceAfter=5*mm))
elements.append(Paragraph("Aashish & Kalyani Rajput", s_sub))
elements.append(Spacer(1, 5*mm))

# Cover stats
freedom_date = best['records'][-1]['date']
cover_data = [
    ['TOTAL DEBT TODAY', 'DAILY INTEREST', 'FREEDOM DATE'],
    [fmt_inr(L1_BAL + L2_BAL), f"{(L1_BAL*L1_RATE + L2_BAL*L2_RATE)/365:,.0f}/day",
     freedom_date.strftime('%B %Y')],
    ['MONTHLY BUDGET', 'STRATEGY', 'MONTHS TO GO'],
    [fmt_inr(TOTAL), 'SNOWBALL KILL', str(best['months'])],
]
cover_table = Table(cover_data, colWidths=[60*mm, 60*mm, 60*mm])
cover_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), NAVY),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('BACKGROUND', (0, 2), (-1, 2), TEAL),
    ('TEXTCOLOR', (0, 2), (-1, 2), WHITE),
    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('FONTSIZE', (0, 1), (-1, 1), 16),
    ('FONTSIZE', (0, 2), (-1, 2), 9),
    ('FONTSIZE', (0, 3), (-1, 3), 16),
    ('TEXTCOLOR', (0, 1), (0, 1), RED),
    ('TEXTCOLOR', (1, 1), (1, 1), ORANGE),
    ('TEXTCOLOR', (2, 1), (2, 1), GREEN),
    ('TEXTCOLOR', (0, 3), (0, 3), BLUE),
    ('TEXTCOLOR', (1, 3), (1, 3), PURPLE),
    ('TEXTCOLOR', (2, 3), (2, 3), BRIGHT_GREEN),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 4),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ('TOPPADDING', (0, 1), (-1, 1), 8),
    ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
    ('TOPPADDING', (0, 3), (-1, 3), 8),
    ('BOTTOMPADDING', (0, 3), (-1, 3), 8),
    ('BOX', (0, 0), (-1, -1), 1, NAVY),
    ('GRID', (0, 0), (-1, -1), 0.5, GREY),
]))
elements.append(cover_table)
elements.append(Spacer(1, 8*mm))

bank_int = bank['total_int']
best_int = best['total_int']
saved = bank_int - best_int
elements.append(Paragraph(f"Interest you'd pay the bank: {fmt_inr(bank_int)}", s_body_c))
elements.append(Paragraph(f"Interest with SNOWBALL KILL: {fmt_inr(best_int)}", s_body_c))
elements.append(Spacer(1, 5*mm))
elements.append(Paragraph(f"YOU SAVE: {fmt_inr(saved)}", s_big_green))
elements.append(Spacer(1, 3*mm))
elements.append(Paragraph(f"({bank['months'] - best['months']} months earlier than bank's plan)",
                           make_style('Sv', fontSize=11, textColor=TEAL, alignment=TA_CENTER)))
elements.append(Spacer(1, 8*mm))
elements.append(Paragraph('"Every rupee of extra payment today kills three rupees of future interest."',
                           s_quote))
elements.append(Spacer(1, 5*mm))
elements.append(Paragraph("HOW TO USE THIS TRACKER", s_heading2))
elements.append(Paragraph("1. Print this document and keep it visible", s_body))
elements.append(Paragraph("2. After each EMI payment, tick the checkbox for that month", s_body))
elements.append(Paragraph("3. Celebrate every milestone — you earned it!", s_body))
elements.append(Paragraph("4. If you get a bonus, note it in the margin — it accelerates everything", s_body))

elements.append(PageBreak())

# ═══════════ PAGE 2: STRATEGY ═══════════
elements.append(Paragraph("THE STRATEGY: SNOWBALL KILL", s_title))
elements.append(HRFlowable(width="80%", thickness=2, color=GREEN, spaceAfter=5*mm))

elements.append(Paragraph("WHY SNOWBALL WINS", s_heading))
elements.append(Paragraph(
    "Put ALL extra money into Loan 2 first. Kill it in ~33 months instead of letting it "
    "drag for 16 years. Once dead, your L1 payment jumps from 1.2L to 1.6L. "
    "At the same interest rate, total months are identical either way — but killing L2 first "
    "gives you the psychological win, frees up cash flow, and builds unstoppable momentum.", s_body))
elements.append(Spacer(1, 3*mm))

# Phase boxes
phase_data = [
    ['PHASE 1: KILL LOAN 2', 'PHASE 2: CRUSH LOAN 1'],
    [f'L1: {fmt_inr(L1_BASE)}/mo (base only)\nL2: {fmt_inr(L2_BASE + FLEX)}/mo (base + all extra)',
     f'L1: {fmt_inr(TOTAL)}/mo (FULL BUDGET!)\nL2: DEAD'],
    [f'Duration: ~{best["l2_dead"]} months', f'Duration: ~{best["months"] - best["l2_dead"]} months'],
]
phase_table = Table(phase_data, colWidths=[90*mm, 90*mm])
phase_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, 0), ORANGE),
    ('BACKGROUND', (1, 0), (1, 0), GREEN),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 11),
    ('FONTSIZE', (0, 1), (-1, 1), 9),
    ('FONTSIZE', (0, 2), (-1, 2), 9),
    ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
    ('TEXTCOLOR', (0, 2), (0, 2), ORANGE),
    ('TEXTCOLOR', (1, 2), (1, 2), GREEN),
    ('BACKGROUND', (0, 1), (0, 2), LIGHT_RED),
    ('BACKGROUND', (1, 1), (1, 2), LIGHT_GREEN),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('BOX', (0, 0), (-1, -1), 1.5, NAVY),
    ('LINEBEFORE', (1, 0), (1, -1), 1.5, NAVY),
]))
elements.append(phase_table)
elements.append(Spacer(1, 5*mm))

# Strategy comparison
elements.append(Paragraph("STRATEGY COMPARISON", s_heading))
comp_header = ['Strategy', 'L2 Dies', 'Total Months', 'Total Interest', 'You Save']
comp_rows = [comp_header]
for s in [bank, current, snowball]:
    sv = bank['total_int'] - s['total_int']
    comp_rows.append([
        s['label'],
        f"Month {s['l2_dead']}" if s['l2_dead'] < s['months'] else 'Last',
        str(s['months']),
        fmt_inr(s['total_int']),
        fmt_inr(sv) if sv > 0 else '—',
    ])

comp_table = Table(comp_rows, colWidths=[45*mm, 28*mm, 28*mm, 35*mm, 30*mm])
comp_styles = [
    ('BACKGROUND', (0, 0), (-1, 0), NAVY),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('BOX', (0, 0), (-1, -1), 1, NAVY),
    ('GRID', (0, 0), (-1, -1), 0.5, GREY),
    ('BACKGROUND', (0, 1), (-1, 1), LIGHT_RED),
    ('BACKGROUND', (0, 2), (-1, 2), LIGHT_BLUE),
    ('BACKGROUND', (0, 3), (-1, 3), LIGHT_GREEN),
    ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
    ('TEXTCOLOR', (0, 3), (0, 3), GREEN),
]
comp_table.setStyle(TableStyle(comp_styles))
elements.append(comp_table)
elements.append(Spacer(1, 5*mm))

# Bonus section
elements.append(Paragraph("BONUS ACCELERATOR", s_heading))
elements.append(Paragraph(
    f"If your variable component ({fmt_inr(BONUS)}/year) comes through, dump 100% into Loan 2. "
    f"Without bonus: Loan 2 dies in {snowball_nb['l2_dead']} months, total {snowball_nb['months']} months. "
    f"With bonus: Loan 2 dies in {snowball['l2_dead']} months, total {snowball['months']} months. "
    f"Bonus saves you {snowball_nb['months'] - snowball['months']} more months!", s_body))

elements.append(PageBreak())

# ═══════════ PAGE 3: MILESTONES ═══════════
elements.append(Paragraph("YOUR MILESTONE MAP", s_title))
elements.append(HRFlowable(width="80%", thickness=2, color=GOLD, spaceAfter=5*mm))

LEVELS = [
    ('LEVEL 1', 'DEBT WARRIOR', 'You started the mission', LIGHT_BLUE, BLUE),
    ('LEVEL 2', 'FIRST BLOOD', 'Loan 2 drops below 20L', LIGHT_BLUE, BLUE),
    ('LEVEL 3', 'HALF-KILL', 'Loan 2 drops below 10L', LIGHT_PURPLE, PURPLE),
    ('LEVEL 4', 'LOAN 2 DEAD', 'Snowball activated! Full power to L1', LIGHT_GOLD, ORANGE),
    ('LEVEL 5', 'UNDER 1.5 Cr', 'Total debt below 1.5 Crore', LIGHT_BLUE, TEAL),
    ('LEVEL 6', 'CRORE CRUSHER', 'Total debt below 1 Crore', LIGHT_GREEN, GREEN),
    ('LEVEL 7', 'HALFWAY HOME', 'Total debt below 75 Lakhs', LIGHT_GREEN, GREEN),
    ('LEVEL 8', 'FINAL STRETCH', 'Total debt below 50 Lakhs', LIGHT_GREEN, BRIGHT_GREEN),
    ('LEVEL 9', 'VICTORY LAP', 'Total debt below 25 Lakhs', LIGHT_GREEN, BRIGHT_GREEN),
    ('LEVEL MAX', 'DEBT FREE!', f'Freedom Day: {freedom_date.strftime("%B %Y")}', LIGHT_GREEN, GREEN),
]

# Find months for each milestone by scanning records for balance thresholds
def find_milestone(records, condition):
    for r in records:
        if condition(r):
            return r['month'], r['date']
    return None

recs_best = best['records']
level_data = {
    'DEBT WARRIOR': (1, START),
    'FIRST BLOOD': find_milestone(recs_best, lambda r: r['l2_bal'] < 20_00_000),
    'HALF-KILL': find_milestone(recs_best, lambda r: r['l2_bal'] < 10_00_000),
    'LOAN 2 DEAD': find_milestone(recs_best, lambda r: r['l2_bal'] <= 100),
    'UNDER 1.5 Cr': find_milestone(recs_best, lambda r: r['total_bal'] < 1_50_00_000),
    'CRORE CRUSHER': find_milestone(recs_best, lambda r: r['total_bal'] < 1_00_00_000),
    'HALFWAY HOME': find_milestone(recs_best, lambda r: r['total_bal'] < 75_00_000),
    'FINAL STRETCH': find_milestone(recs_best, lambda r: r['total_bal'] < 50_00_000),
    'VICTORY LAP': find_milestone(recs_best, lambda r: r['total_bal'] < 25_00_000),
    'DEBT FREE!': find_milestone(recs_best, lambda r: r['total_bal'] <= 100),
}

ms_header = ['Level', 'Title', 'When', 'Date', 'Done']
ms_rows = [ms_header]
for lvl, title, desc, bg, fg in LEVELS:
    data = level_data.get(title)
    if data:
        m, dt = data
        when = f"Month {m}"
        dt_str = dt.strftime('%b %Y') if isinstance(dt, datetime) else str(dt)
    else:
        when = '—'
        dt_str = '—'
    ms_rows.append([lvl, f"{title}\n{desc}", when, dt_str, ''])

ms_widths = [22*mm, 72*mm, 22*mm, 22*mm, 18*mm]
ms_table = Table(ms_rows, colWidths=ms_widths)
ms_styles = [
    ('BACKGROUND', (0, 0), (-1, 0), NAVY),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('BOX', (0, 0), (-1, -1), 1.5, NAVY),
    ('GRID', (0, 0), (-1, -1), 0.5, GREY),
]
for i, (lvl, title, desc, bg, fg) in enumerate(LEVELS):
    row = i + 1
    ms_styles.append(('BACKGROUND', (0, row), (-1, row), bg))
    ms_styles.append(('TEXTCOLOR', (0, row), (1, row), fg))
    ms_styles.append(('FONTNAME', (0, row), (0, row), 'Helvetica-Bold'))

ms_table.setStyle(TableStyle(ms_styles))
elements.append(ms_table)

elements.append(Spacer(1, 8*mm))
elements.append(Paragraph(
    '"The goal is not to be debt-free someday. The goal is to be debt-free '
    'by a specific date — and then beat it."', s_quote))

elements.append(PageBreak())

# ═══════════ PAGES 4+: MONTHLY TRACKER ═══════════
elements.append(Paragraph("MONTH-BY-MONTH BATTLE LOG", s_title))
elements.append(HRFlowable(width="80%", thickness=2, color=NAVY, spaceAfter=3*mm))
elements.append(Paragraph(
    "Tick each month after your EMI clears. Watch the daily interest fall. That's your money fighting back.",
    s_body_c))
elements.append(Spacer(1, 3*mm))

# Table headers
hdr = ['', '#', 'Month', 'L2 Pay', 'L2 Bal', 'L1 Pay', 'L1 Bal', 'Total', 'Daily Int', 'Milestone']
col_w = [7*mm, 8*mm, 16*mm, 16*mm, 18*mm, 16*mm, 20*mm, 20*mm, 16*mm, 25*mm]

current_year = None
rows_on_page = 0
MAX_ROWS = 28

recs = best['records']
daily_start = (L1_BAL * L1_RATE + L2_BAL * L2_RATE) / 365

for idx, r in enumerate(recs):
    yr = r['date'].year

    if yr != current_year:
        if current_year is not None:
            elements.append(Spacer(1, 2*mm))

        if rows_on_page > MAX_ROWS - 5:
            elements.append(PageBreak())
            rows_on_page = 0

        # Year banner
        yr_data = [
            [f"  {yr}", '', '', '', '', '', '', '', '', '']
        ]
        yr_table = Table(yr_data, colWidths=col_w)
        yr_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('SPAN', (0, 0), (-1, 0)),
            ('TOPPADDING', (0, 0), (-1, 0), 3),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
        ]))
        elements.append(yr_table)

        hdr_table = Table([hdr], colWidths=col_w)
        hdr_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 2),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ]))
        elements.append(hdr_table)
        current_year = yr
        rows_on_page += 2

    # Row data
    l2_bal_str = fmt_short(r['l2_bal']) if r['l2_bal'] > 100 else 'DEAD'
    l2_pay_str = fmt_short(r['l2_pay']) if r['l2_pay'] > 0 else '—'
    daily_str = f"{r['daily_int']:,.0f}"

    row = [
        '',
        str(r['month']),
        r['date'].strftime('%b'),
        l2_pay_str,
        l2_bal_str,
        fmt_short(r['l1_pay']),
        fmt_short(r['l1_bal']) if r['l1_bal'] > 100 else 'DONE',
        fmt_short(r['total_bal']) if r['total_bal'] > 100 else 'FREE!',
        daily_str,
        r['milestone'],
    ]

    row_table_data = [row]
    row_table = Table(row_table_data, colWidths=col_w)

    # Row styling
    row_styles = [
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 2),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('BOX', (0, 0), (0, 0), 0.5, GREY),
    ]

    if r['milestone']:
        if 'DEAD' in r['milestone'] or 'KILLED' in r['milestone']:
            row_styles.append(('BACKGROUND', (0, 0), (-1, 0), LIGHT_GOLD))
            row_styles.append(('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'))
            row_styles.append(('TEXTCOLOR', (9, 0), (9, 0), ORANGE))
        elif 'FREE' in r['milestone']:
            row_styles.append(('BACKGROUND', (0, 0), (-1, 0), LIGHT_GREEN))
            row_styles.append(('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'))
            row_styles.append(('TEXTCOLOR', (9, 0), (9, 0), GREEN))
        elif 'SNOWBALL' in r['milestone']:
            row_styles.append(('BACKGROUND', (0, 0), (-1, 0), LIGHT_GOLD))
            row_styles.append(('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'))
            row_styles.append(('TEXTCOLOR', (9, 0), (9, 0), ORANGE))
        else:
            row_styles.append(('BACKGROUND', (0, 0), (-1, 0), MINT))
            row_styles.append(('FONTNAME', (9, 0), (9, 0), 'Helvetica-Bold'))
            row_styles.append(('TEXTCOLOR', (9, 0), (9, 0), TEAL))
    elif r['bonus'] > 0:
        row_styles.append(('BACKGROUND', (0, 0), (-1, 0), LIGHT_PURPLE))
        row_styles.append(('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'))
    elif idx % 2 == 0:
        row_styles.append(('BACKGROUND', (0, 0), (-1, 0), WHITE))
    else:
        row_styles.append(('BACKGROUND', (0, 0), (-1, 0), LIGHT_GREY))

    if r['l2_bal'] <= 100 and r['l2_bal'] >= 0:
        row_styles.append(('TEXTCOLOR', (4, 0), (4, 0), RED))
        row_styles.append(('FONTNAME', (4, 0), (4, 0), 'Helvetica-Bold'))

    row_table.setStyle(TableStyle(row_styles))
    elements.append(row_table)
    rows_on_page += 1

    if rows_on_page >= MAX_ROWS:
        elements.append(PageBreak())
        # Re-add year and header
        yr_data2 = [[f"  {yr} (continued)", '', '', '', '', '', '', '', '', '']]
        yr_t2 = Table(yr_data2, colWidths=col_w)
        yr_t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('SPAN', (0, 0), (-1, 0)),
            ('TOPPADDING', (0, 0), (-1, 0), 3),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
        ]))
        elements.append(yr_t2)
        hdr_t2 = Table([hdr], colWidths=col_w)
        hdr_t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 2),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ]))
        elements.append(hdr_t2)
        rows_on_page = 2

elements.append(PageBreak())

# ═══════════ DAILY INTEREST DROP TABLE ═══════════
elements.append(Paragraph("DAILY INTEREST:", s_title))
elements.append(Paragraph("THE BLEED STOPS", make_style('BS', fontSize=24, textColor=RED,
                           alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=2*mm)))
elements.append(HRFlowable(width="80%", thickness=2, color=RED, spaceAfter=3*mm))
elements.append(Paragraph(
    f"Today you lose {daily_start:,.0f}/day to interest. Watch it fall to zero.",
    s_body_c))
elements.append(Spacer(1, 3*mm))

# Show every 6th month
di_header = ['Month', 'Date', 'L1 Daily', 'L2 Daily', 'Total Daily', 'vs Today']
di_rows = [di_header]
di_rows.append(['START', 'Jun 2026',
                f"{L1_BAL*L1_RATE/365:,.0f}",
                f"{L2_BAL*L2_RATE/365:,.0f}",
                f"{daily_start:,.0f}", '—'])

for r in recs:
    if r['month'] % 6 == 0 or r['milestone']:
        l1_daily = r['l1_bal'] * L1_RATE / 365
        l2_daily = r['l2_bal'] * L2_RATE / 365
        drop = daily_start - r['daily_int']
        pct = drop / daily_start * 100
        di_rows.append([
            str(r['month']),
            r['date'].strftime('%b %Y'),
            f"{l1_daily:,.0f}",
            f"{l2_daily:,.0f}" if l2_daily > 1 else '0',
            f"{r['daily_int']:,.0f}",
            f"-{pct:.0f}%",
        ])

# Add final row
last = recs[-1]
if last['month'] % 6 != 0:
    di_rows.append([
        str(last['month']),
        last['date'].strftime('%b %Y'),
        '0', '0', '0', '-100%',
    ])

di_table = Table(di_rows, colWidths=[18*mm, 24*mm, 24*mm, 22*mm, 26*mm, 18*mm])
di_styles = [
    ('BACKGROUND', (0, 0), (-1, 0), RED),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 8),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ('BOX', (0, 0), (-1, -1), 1, RED),
    ('GRID', (0, 0), (-1, -1), 0.5, GREY),
    ('BACKGROUND', (0, 1), (-1, 1), LIGHT_RED),
    ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
]
for i in range(2, len(di_rows)):
    if i == len(di_rows) - 1:
        di_styles.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GREEN))
        di_styles.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
        di_styles.append(('TEXTCOLOR', (0, i), (-1, i), GREEN))
    elif i % 2 == 0:
        di_styles.append(('BACKGROUND', (0, i), (-1, i), WHITE))
    else:
        di_styles.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GREY))

di_table.setStyle(TableStyle(di_styles))
elements.append(di_table)

elements.append(PageBreak())

# ═══════════ YEAR-WISE SUMMARY ═══════════
elements.append(Paragraph("YEAR-BY-YEAR PROGRESS", s_title))
elements.append(HRFlowable(width="80%", thickness=2, color=TEAL, spaceAfter=5*mm))

yrs_header = ['Year', 'L2 Bal', 'L1 Bal', 'Total Bal', 'Interest Paid', 'Principal Paid',
              'Daily Int']
yrs_rows = [yrs_header]

# Starting
yrs_rows.append(['START', fmt_short(L2_BAL), fmt_short(L1_BAL),
                  fmt_short(L1_BAL + L2_BAL), '—', '—',
                  f"{daily_start:,.0f}"])

prev_year = None
yr_int = 0
yr_prin = 0
for r in recs:
    yr = r['date'].year
    yr_int += r['l1_int'] + r['l2_int']
    yr_prin += r['l1_prin'] + r['l2_prin']

    is_dec = r['date'].month == 12
    is_last = r == recs[-1]

    if is_dec or is_last:
        yrs_rows.append([
            str(yr),
            fmt_short(r['l2_bal']) if r['l2_bal'] > 100 else 'DEAD',
            fmt_short(r['l1_bal']) if r['l1_bal'] > 100 else 'DONE',
            fmt_short(r['total_bal']) if r['total_bal'] > 100 else 'FREE!',
            fmt_short(yr_int),
            fmt_short(yr_prin),
            f"{r['daily_int']:,.0f}",
        ])
        yr_int = 0
        yr_prin = 0

yr_table = Table(yrs_rows, colWidths=[18*mm, 22*mm, 22*mm, 24*mm, 24*mm, 24*mm, 20*mm])
yr_styles = [
    ('BACKGROUND', (0, 0), (-1, 0), TEAL),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 8),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 4),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ('BOX', (0, 0), (-1, -1), 1, TEAL),
    ('GRID', (0, 0), (-1, -1), 0.5, GREY),
    ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
    ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
]
for i in range(2, len(yrs_rows)):
    if i == len(yrs_rows) - 1:
        yr_styles.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GREEN))
        yr_styles.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
    elif i % 2 == 0:
        yr_styles.append(('BACKGROUND', (0, i), (-1, i), WHITE))
    else:
        yr_styles.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GREY))

yr_table.setStyle(TableStyle(yr_styles))
elements.append(yr_table)

elements.append(PageBreak())

# ═══════════ FINAL PAGE: FREEDOM DAY ═══════════
elements.append(Spacer(1, 30*mm))
elements.append(Paragraph("FREEDOM DAY", make_style('FD', fontSize=40, textColor=GREEN,
                           alignment=TA_CENTER, fontName='Helvetica-Bold',
                           spaceAfter=8*mm)))
elements.append(Paragraph(freedom_date.strftime('%B %Y'),
                           make_style('FDd', fontSize=30, textColor=NAVY,
                                      alignment=TA_CENTER, fontName='Helvetica-Bold',
                                      spaceAfter=8*mm)))
elements.append(HRFlowable(width="60%", thickness=3, color=GREEN, spaceAfter=8*mm))

final_data = [
    ['TOTAL DEBT KILLED', 'INTEREST SAVED', 'MONTHS SAVED'],
    [fmt_inr(L1_BAL + L2_BAL), fmt_inr(saved), str(bank['months'] - best['months'])],
]
final_table = Table(final_data, colWidths=[55*mm, 55*mm, 55*mm])
final_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), GREEN),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('FONTSIZE', (0, 1), (-1, 1), 18),
    ('TEXTCOLOR', (0, 1), (0, 1), NAVY),
    ('TEXTCOLOR', (1, 1), (1, 1), GREEN),
    ('TEXTCOLOR', (2, 1), (2, 1), TEAL),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 1), (-1, 1), 10),
    ('BOTTOMPADDING', (0, 1), (-1, 1), 10),
    ('BOX', (0, 0), (-1, -1), 2, GREEN),
    ('GRID', (0, 0), (-1, -1), 1, GREEN),
]))
elements.append(final_table)

elements.append(Spacer(1, 10*mm))
elements.append(Paragraph(
    '"You didn\'t just pay off a loan. You bought back your freedom — '
    'month by month, rupee by rupee."', s_quote))

elements.append(Spacer(1, 15*mm))
elements.append(Paragraph("THE RULES", s_heading))
rules = [
    "1. Pay the Snowball EMI FIRST, before any other spending",
    "2. Every bonus, every windfall — 100% goes to the loan",
    "3. No new debt. Zero. Period.",
    "4. Track this sheet monthly. What gets measured gets killed.",
    "5. Celebrate every milestone. You earned it.",
]
for rule in rules:
    elements.append(Paragraph(rule, make_style('Rule', fontSize=10, textColor=NAVY,
                               fontName='Helvetica-Bold', leading=15)))

elements.append(Spacer(1, 10*mm))
elements.append(Paragraph("Game on.", make_style('GO', fontSize=20, textColor=RED,
                           alignment=TA_CENTER, fontName='Helvetica-Bold')))

# ── GENERATE ──
doc.build(elements)
print(f"\nPDF saved: {output_path}")
print(f"Pages: estimated {len(recs)//28 + 8}")
