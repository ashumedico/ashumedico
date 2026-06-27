#!/usr/bin/env python3
"""Menopur history — cited timeline PDF (A4, clean reference style)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

NAVY=HexColor('#0d1b4c'); BLUE=HexColor('#1565c0'); TEAL=HexColor('#00897b')
GREEN=HexColor('#2e7d32'); RED=HexColor('#c62828'); GOLD=HexColor('#b8860b')
GREY=HexColor('#6b7280'); LGREY=HexColor('#f4f7fb'); WHITE=HexColor('#ffffff')
LBLUE=HexColor('#e3f2fd'); LGREEN=HexColor('#e8f5e9'); DARK=HexColor('#1f2937')

ss=getSampleStyleSheet()
def S(n,**k): return ParagraphStyle(n,parent=ss['Normal'],**k)
title=S('t',fontSize=22,textColor=NAVY,fontName='Helvetica-Bold',alignment=TA_CENTER,spaceAfter=2*mm)
sub=S('s',fontSize=11,textColor=BLUE,alignment=TA_CENTER,spaceAfter=1*mm)
meta=S('m',fontSize=8.5,textColor=GREY,alignment=TA_CENTER,spaceAfter=3*mm)
h=S('h',fontSize=14,textColor=NAVY,fontName='Helvetica-Bold',spaceBefore=5*mm,spaceAfter=2*mm)
h2=S('h2',fontSize=11,textColor=TEAL,fontName='Helvetica-Bold',spaceBefore=3*mm,spaceAfter=1*mm)
body=S('b',fontSize=9.5,textColor=DARK,leading=14,spaceAfter=2*mm)
small=S('sm',fontSize=8,textColor=GREY,leading=11,spaceAfter=2*mm)
cell=S('c',fontSize=8,textColor=DARK,leading=10)
cellb=S('cb',fontSize=8,textColor=NAVY,fontName='Helvetica-Bold',leading=10)
hdr=S('hd',fontSize=8,textColor=WHITE,fontName='Helvetica-Bold',leading=10)
ref=S('r',fontSize=7.5,textColor=DARK,leading=10,spaceAfter=1*mm)

out='aios/ledger/menopur-history-timeline.pdf'
os.makedirs(os.path.dirname(out),exist_ok=True)
doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=15*mm,rightMargin=15*mm,topMargin=14*mm,bottomMargin=14*mm)
E=[]

E.append(Paragraph("The Story of Menopur (Menotropin) on Earth",title))
E.append(Paragraph("A cited chronological history & evolution of highly purified hMG (HP-hMG)",sub))
E.append(Paragraph("INN: menotropin · Brand: Menopur (Ferring) · Compiled 2026-06-27 · Medical Affairs reference",meta))
E.append(HRFlowable(width="100%",thickness=1.5,color=NAVY,spaceAfter=3*mm))
E.append(Paragraph("<b>Evidence note.</b> Built from primary sources (Human Reproduction, Fertility &amp; Sterility, "
    "Cochrane, Hum Reprod Open, PMC). 3 claims passed full adversarial verification; others are direct quoted "
    "extractions from primary journals but the automated cross-check was cut short by a token limit "
    "(<b>[sourced]</b>). Unconfirmed items are flagged <b>[GAP]</b>. Verify against source before external use.",small))

E.append(Paragraph("The Narrative",h))
paras=[
 ("The problem hMG solved.","For most of history there was no way to stimulate the ovaries. The breakthrough came from the urine of postmenopausal women, rich in FSH and LH. hMG (INN menotropin) was first extracted around 1949–50; the first preparation (Pergonal, Serono) followed. <b>[GAP: exact year varies by source]</b>"),
 ("1961 — the door opens.","Bruno Lunenfeld's group delivered the first child after hMG ovarian stimulation in 1961, the event that opened the path to controlled ovarian stimulation — the foundation of modern IVF. <b>[VERIFIED]</b>"),
 ("Late-1980s safety reckoning.","Human <i>pituitary</i> gonadotropin (HPG) was withdrawn in the late 1980s after a link to Creutzfeldt–Jakob disease, leaving urinary hMG dominant — but early hMG carried many unknown urinary proteins, making quality control almost impossible. <b>[VERIFIED]</b>"),
 ("Purification → Menopur.","Ferring developed highly purified hMG (HP-hMG = Menopur), standardised to 75 IU FSH + 75 IU LH activity per vial, the LH activity supplied mainly by hCG. This 1:1 FSH:LH-activity design is Menopur's signature vs pure recombinant FSH. <b>[sourced]</b>"),
 ("The evidence era (2006–2020).","Tested head-to-head vs recombinant FSH in MERiT (2006), Coomarasamy (2008), Cochrane (2011), MEGASET (2012) and MEGASET-HR (2020): Menopur is at least as effective for live birth, with signals of better embryo quality and, in high responders, less OHSS and pregnancy loss."),
 ("The convenience era (2018–21+).","The latest chapter is delivery: Menopur moved from powder-for-reconstitution to a stable liquid pre-filled pen (31G needle), shown bioequivalent to the powder. <b>[VERIFIED]</b>"),
 ("Where it stands today.","Cochrane evidence and guidelines treat rFSH and HP-hMG as broadly equivalent for live birth; choice is driven by patient profile, OHSS risk, convenience and cost — Menopur's edge being its LH activity and OHSS profile in high responders."),
]
for t,txt in paras:
    E.append(Paragraph(f"<b>{t}</b> {txt}",body))

E.append(PageBreak())
E.append(Paragraph("Year-by-Year Timeline",h))
tl=[["Year","Milestone","Source / status"],
 ["~1949–50","hMG (menotropin) first extracted from postmenopausal urine; Pergonal/Serono lineage","PMC6616070 · [GAP] year"],
 ["1961","First child after hMG stimulation (Lunenfeld) — birth of controlled ovarian stimulation","VERIFIED · Lunenfeld 2012"],
 ["Late 1980s","Pituitary gonadotropin (HPG) withdrawn after CJD link; urinary hMG dominant","VERIFIED · Lunenfeld 2012"],
 ["1990s–2000s","Purification → HP-hMG / Menopur; 75 IU FSH + 75 IU LH activity (LH from hCG)","sourced · PMC8594316; FDA"],
 ["2006","MERiT RCT (Andersen) — HP-hMG vs rFSH, long agonist","sourced · Hum Reprod"],
 ["2007","Ziebe embryo-quality analysis of MERiT","sourced · Hum Reprod"],
 ["2008","Coomarasamy meta-analysis — hMG live-birth edge","sourced · Hum Reprod/RBMO"],
 ["2011","Cochrane (van Wely) — rFSH vs urinary, no live-birth difference","sourced · CD005354.pub2"],
 ["2012","MEGASET RCT (Devroey) — antagonist, single blastocyst","sourced · Fertil Steril"],
 ["2019","Bordewijk meta-analysis — near-equivalent dosing","sourced · Hum Reprod Open"],
 ["2020","MEGASET-HR RCT (Witz) — high responders; less OHSS","sourced · Fertil Steril"],
 ["2018–21","Liquid pen formulation; bioequivalent to powder","VERIFIED · PMC8594316"],
 ["2025–26","rFSH ≈ HP-hMG for live birth; choice by profile/OHSS/cost","Cochrane + guidelines"],
]
rows=[[Paragraph(c,hdr if i==0 else (cellb if j==0 else cell)) for j,c in enumerate(r)] for i,r in enumerate(tl)]
t=Table(rows,colWidths=[20*mm,98*mm,42*mm])
tstyle=[('BACKGROUND',(0,0),(-1,0),NAVY),('GRID',(0,0),(-1,-1),0.4,GREY),
 ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
 ('LEFTPADDING',(0,0),(-1,-1),4)]
for i in range(1,len(tl)):
    tstyle.append(('BACKGROUND',(0,i),(-1,i),LGREY if i%2 else WHITE))
for hi in (2,3,12):  # VERIFIED rows tint
    tstyle.append(('BACKGROUND',(0,hi),(-1,hi),LGREEN))
t.setStyle(TableStyle(tstyle)); E.append(t)
E.append(Paragraph("<b>[GAP] not confirmed this run:</b> exact US FDA approval date, EU approval dates, and label/"
 "indication change history of Menopur. (A Menopur+Bravelle mixed-protocol FDA approval appears only in a "
 "low-reliability press release — verify on FDA/DailyMed.)",small))

E.append(PageBreak())
E.append(Paragraph("The Pivotal Trials",h))
trials=[
 ("MERiT — 2006 · Andersen et al., Hum Reprod 21(12):3217",
  "Randomized, assessor-blind, multinational RCT. <b>731</b> IVF women (HP-hMG 363 / rFSH 368), long GnRH agonist. "
  "Primary endpoint ongoing pregnancy: <b>27% vs 22%</b>, OR 1.25 (95% CI 0.89–1.75) — non-inferiority established, "
  "superiority not concluded."),
 ("Ziebe (MERiT embryo quality) — 2007 · Hum Reprod 22(9):2404",
  "Top-quality embryos/oocyte higher with HP-hMG: <b>11.3% vs 9.0% (P=0.044)</b> local, NS central. Among top-quality "
  "embryos, live birth/ongoing pregnancy <b>48% vs 32% (P=0.038)</b> — signal of better implantation capacity."),
 ("Coomarasamy meta-analysis — 2008 · Hum Reprod 23(2):310",
  "7 RCTs, <b>2159 women</b>, hMG vs rFSH, long agonist. Live birth <b>RR 1.18 (95% CI 1.02–1.38, P=0.03)</b> — ~4% absolute edge for hMG."),
 ("Cochrane review — 2011 · van Wely, CD005354.pub2",
  "<b>42 RCTs, 9606 couples</b>. No significant live-birth difference: <b>OR 0.97 (95% CI 0.87–1.08)</b>. Choose by availability, convenience, cost."),
 ("MEGASET — 2012 · Devroey et al., Fertil Steril",
  "Open-label, assessor-blind, <b>749 women</b>, 25 centres/7 countries, GnRH antagonist, single-blastocyst transfer. "
  "Ongoing pregnancy <b>30% vs 27%</b> (non-inferior). Cumulative live birth (incl. frozen ≤1 yr) <b>40% vs 38%</b>."),
 ("MEGASET-HR — 2020 · Witz et al., Fertil Steril",
  "<b>620 predicted high responders (AMH ≥5 ng/mL)</b>, antagonist ART/ICSI. Ongoing pregnancy (fresh) <b>35.5% vs 30.7%</b> "
  "(non-inferior). <b>OHSS 9.7% vs 21.4%</b>; early pregnancy loss 14.5% vs 25.5%. Cumulative live birth similar (50.6% vs 51.5%)."),
 ("Bordewijk meta-analysis — 2019 · Hum Reprod Open hoz008",
  "28 RCTs, <b>7553 women</b>. Total gonadotrophin dose differed only marginally (MD −37 IU) — near-equivalent dosing."),
]
for ti,tx in trials:
    E.append(Paragraph(ti,h2)); E.append(Paragraph(tx+" <font color='#6b7280'>[sourced, not cross-verified]</font>",body))

E.append(Paragraph("Composition &amp; Mechanism",h))
E.append(Paragraph("Menotropin (Menopur, HP-hMG) = highly purified urinary preparation, <b>75 IU FSH + 75 IU LH activity "
 "per vial (1:1)</b>; the LH activity is supplied mainly by hCG (~10 IU hCG per 75 IU FSH) plus low native LH. FSH drives "
 "follicular recruitment; hCG-driven LH activity supports theca-cell androgen production and steroidogenesis — the basis "
 "for interest in LH activity in selected patients. <b>[sourced; exact hCG:FSH ratio not cross-verified — GAP]</b>",body))

E.append(PageBreak())
E.append(Paragraph("References",h))
refs=[
 "1. Lunenfeld B. Gonadotropin stimulation: past, present and future. Reprod Med Biol. 2012. doi:10.1007/s12522-011-0097-2",
 "2. History of hMG/menotropin development. PMC6616070",
 "3. Andersen AN, et al. (MERiT). Hum Reprod. 2006;21(12):3217",
 "4. Ziebe S, et al. (MERiT embryo quality). Hum Reprod. 2007;22(9):2404",
 "5. Coomarasamy A, et al. Meta-analysis hMG vs rFSH. Hum Reprod. 2008;23(2):310",
 "6. van Wely M, et al. Cochrane CD005354.pub2. 2011",
 "7. Devroey P, et al. (MEGASET). Fertil Steril. 2012",
 "8. Witz C, et al. (MEGASET-HR). Fertil Steril. 2020",
 "9. Bordewijk EM, et al. Hum Reprod Open. 2019;hoz008",
 "10. HP-hMG liquid pen bioequivalence. PMC8594316",
 "11. Menopur (menotropins) US FDA label — DailyMed (setid 22c8db95…)",
]
for r in refs: E.append(Paragraph(r,ref))

doc.build(E)
print("Saved:",out)
