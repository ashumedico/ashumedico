#!/usr/bin/env python3
"""2026 Finance Audit (Jan-Jun) — complete Excel workbook."""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os

SRC='aios/ledger/2026_MAIN_EXPENSES_SHEET.xlsx'
OUT='aios/ledger/2026-finance-audit-jan-jun.xlsx'

NAVY='0d1b4c'; RED='c62828'; GREEN='2e7d32'; ORANGE='e65100'; GOLD='b8860b'
WHITE='FFFFFF'; LGREY='f4f7fb'; CREAM='fff8e1'; LRED='ffebee'; LGREEN='e8f5e9'
thin=Side(style='thin',color='b0bec5')
border=Border(left=thin,right=thin,top=thin,bottom=thin)
def fill(c): return PatternFill('solid',fgColor=c)
def hdr(cell): cell.font=Font(bold=True,color=WHITE,size=10); cell.fill=fill(NAVY); cell.alignment=Alignment(horizontal='center',vertical='center'); cell.border=border
def bold(cell,color=NAVY): cell.font=Font(bold=True,color=color); cell.border=border
def norm(cell): cell.font=Font(color='1f2937'); cell.border=border

# ── read source Jan-Jun ──
src=openpyxl.load_workbook(SRC,data_only=True); ws=src.worksheets[0]
rows=list(ws.iter_rows(values_only=True))
hi=None
for i,r in enumerate(rows):
    if r and r[1]=='Category' and r[2]=='Type': hi=i; break
cats=[]
for r in rows[hi+1:]:
    if r and r[1]=='TOTAL MONTHLY EXPENSES': break
    if r and (r[0] or r[1]):
        name=r[1] or r[0]
        janjun=[r[c] if isinstance(r[c],(int,float)) else 0 for c in range(3,9)]  # Jan-Jun
        if any(janjun): cats.append((str(name),janjun))
totrow=None
for r in rows:
    if r and r[1]=='TOTAL MONTHLY EXPENSES':
        totrow=[r[c] if isinstance(r[c],(int,float)) else 0 for c in range(3,9)]; break

wb=openpyxl.Workbook()

# ═══ SHEET 1: Jan-Jun actuals ═══
s1=wb.active; s1.title='Jan-Jun Actuals'
s1['A1']='2026 EXPENSE ACTUALS — Jan to Jun'; s1['A1'].font=Font(bold=True,size=14,color=NAVY)
months=['Jan','Feb','Mar','Apr','May','Jun']
head=['Category']+months+['H1 Total']
for j,h in enumerate(head,1): hdr(s1.cell(row=3,column=j,value=h))
r=4
for name,vals in cats:
    s1.cell(row=r,column=1,value=name); norm(s1.cell(row=r,column=1))
    for j,v in enumerate(vals,2):
        c=s1.cell(row=r,column=j,value=v); norm(c); c.number_format='#,##0'
    tc=s1.cell(row=r,column=8,value=sum(vals)); bold(tc); tc.number_format='#,##0'
    if r%2==0:
        for j in range(1,9): s1.cell(row=r,column=j).fill=fill(LGREY)
    r+=1
# totals
s1.cell(row=r,column=1,value='TOTAL EXPENSES'); bold(s1.cell(row=r,column=1),RED)
if totrow:
    for j,v in enumerate(totrow,2):
        c=s1.cell(row=r,column=j,value=v); bold(c,RED); c.number_format='#,##0'; c.fill=fill(CREAM)
    tc=s1.cell(row=r,column=8,value=sum(totrow)); bold(tc,RED); tc.number_format='#,##0'; tc.fill=fill(CREAM)
s1.column_dimensions['A'].width=26
for col in 'BCDEFGH': s1.column_dimensions[col].width=12

# ═══ SHEET 2: Subscriptions Audit ═══
s2=wb.create_sheet('Subscriptions Audit')
s2['A1']='SUBSCRIPTIONS & RECURRING — found in Gmail'; s2['A1'].font=Font(bold=True,size=14,color=NAVY)
subhead=['Service','Monthly (Rs)','Annual (Rs)','Status','Verdict']
for j,h in enumerate(subhead,1): hdr(s2.cell(row=3,column=j,value=h))
subs=[
 ('Claude Pro (via Apple)',1999,23988,'ACTIVE','KEEP but bill DIRECT (Apple adds ~Rs 300/mo markup)'),
 ('Netflix',649,7788,'ACTIVE (billing failed 4x)','REVIEW — downgrade or cut if unused'),
 ('Google One storage',130,1560,'About to force upgrade (93% full)','CLEAN UP inbox first — avoid paying'),
 ('PlayStation Plus',749,8988,'CANCELLED','DONE — already killed (good)'),
]
r=4
for name,mo,yr,status,verdict in subs:
    s2.cell(row=r,column=1,value=name); norm(s2.cell(row=r,column=1))
    c=s2.cell(row=r,column=2,value=mo); norm(c); c.number_format='#,##0'
    c=s2.cell(row=r,column=3,value=yr); norm(c); c.number_format='#,##0'
    s2.cell(row=r,column=4,value=status); norm(s2.cell(row=r,column=4))
    s2.cell(row=r,column=5,value=verdict); norm(s2.cell(row=r,column=5))
    tint = LGREEN if 'CANCELLED' in status else (LRED if 'REVIEW' in verdict or 'CLEAN' in verdict else LGREY)
    for j in range(1,6): s2.cell(row=r,column=j).fill=fill(tint)
    r+=1
s2.cell(row=r,column=1,value='TOTAL SUBSCRIPTIONS'); bold(s2.cell(row=r,column=1))
c=s2.cell(row=r,column=2,value=sum(x[1] for x in subs)); bold(c); c.number_format='#,##0'; c.fill=fill(CREAM)
c=s2.cell(row=r,column=3,value=sum(x[2] for x in subs)); bold(c); c.number_format='#,##0'; c.fill=fill(CREAM)
r+=2
s2.cell(row=r,column=1,value='CREDIT CARD SPENDS (YES Bank, to investigate)').font=Font(bold=True,color=ORANGE)
r+=1
for d,amt in [('01 Jun',12600),('08 Jun',29533),('15 Jun',6500)]:
    s2.cell(row=r,column=1,value=f'YES Bank CC spend — {d}')
    c=s2.cell(row=r,column=2,value=amt); c.number_format='#,##0'
    s2.cell(row=r,column=5,value='What was this? (the 15 Jun 6500 is the one you asked about)')
    r+=1
s2.column_dimensions['A'].width=30; s2.column_dimensions['B'].width=14; s2.column_dimensions['C'].width=14
s2.column_dimensions['D'].width=24; s2.column_dimensions['E'].width=52

# ═══ SHEET 3: Audit Summary ═══
s3=wb.create_sheet('Audit Summary')
s3['A1']='2026 FINANCE AUDIT — Jan to Jun'; s3['A1'].font=Font(bold=True,size=15,color=NAVY)
def block(row,title,color,items):
    c=s3.cell(row=row,column=1,value=title); c.font=Font(bold=True,size=12,color=WHITE); c.fill=fill(color)
    s3.merge_cells(start_row=row,start_column=1,end_row=row,end_column=3)
    for i,it in enumerate(items,1):
        s3.cell(row=row+i,column=1,value=f'• {it}').font=Font(color='1f2937')
        s3.merge_cells(start_row=row+i,start_column=1,end_row=row+i,end_column=3)
    return row+len(items)+2
r=3
r=block(r,'WHAT WENT RIGHT',GREEN,[
 'EMI discipline: Rs 1.6L/mo paid every month, incl Rs 20k extra prepayment — debt actively being killed',
 'Sukanya Samriddhi (SSY) for Reha funded — Rs 1.5L/yr, strong long-term & tax-efficient',
 'PlayStation Plus cancelled — a recurring leak already killed',
 'Bills (Adani electricity) paid on time, no penalties',
])
r=block(r,'WHAT WENT WRONG',RED,[
 'Savings rate just 1.46% (per your own sheet) — almost no liquid surplus after everything',
 'NO emergency buffer — the direct cause of the mid-month Rs 50k crunch',
 'Income ramped only mid-year (Jan-May ~2.5L, Jun 3.2L) but spending stayed high',
 'Rs 2.9L of surprise expenses in Nov-Dec plan — no sinking fund for lumpy costs',
])
r=block(r,'MONEY LEAKAGES',ORANGE,[
 'Miscellaneous Rs 10,000/mo = Rs 1.2L/yr with ZERO visibility — the biggest untracked hole',
 'Big card spends: Rs 29,533 + Rs 12,600 + Rs 6,500 on YES Bank CC in June alone — discretionary, unexamined',
 '~8 credit cards open (HDFC/ICICI/SBI/RBL/YESx2/HSBC/StanChart/Axis) — annual fees stack up silently',
 'Claude Pro billed via Apple = ~Rs 300/mo markup vs direct billing',
 'Google storage 93% full — about to force a paid upgrade you can avoid by cleaning up',
])
r=block(r,'SAVINGS OPPORTUNITY (per year)',GOLD,[
 'Bill Claude direct (drop Apple markup): ~Rs 3,600/yr',
 'Clean inbox, skip Google One upgrade: ~Rs 1,560/yr',
 'Review/cut Netflix if underused: ~Rs 7,788/yr',
 'Track the Rs 10k/mo Misc + card spends: recover an estimated Rs 3,000-5,000/mo of leak',
 'TOTAL quick wins: ~Rs 50,000-70,000/yr — which is exactly one emergency buffer',
])
s3.column_dimensions['A'].width=100

os.makedirs(os.path.dirname(OUT),exist_ok=True)
wb.save(OUT)
print('Saved:',OUT)
print('H1 total expenses:',sum(totrow) if totrow else 'n/a')
