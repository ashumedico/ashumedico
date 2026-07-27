# AIOS Work Log — Aashish Rajput
_Master index of everything built. Branch: `claude/aios-v2-scaffolder-warqsk` · PR #1_

---

## 💰 MONEY & FINANCE

### Debt-kill strategy & trackers
| Deliverable | Path | What |
|---|---|---|
| Debt Freedom Mission | `aios/ledger/debt-freedom-mission.pdf` | 12-page goal-tracker, snowball kill plan |
| Money Vault poster (A3) | `aios/ledger/money-vault-mission-A3.pdf` | Cartoon board-game milestone map |
| Daily Freedom Tracker (A3) | `aios/ledger/daily-freedom-tracker-A3.pdf` | One tick-box per day to debt-free |
| Loan 1 & 2 payoff graph | `aios/ledger/loan-1-2-payoff.png` | L2 dies ~Jan 2032, L1 ~Jun 2040 |
| Money Map (year-wise) | `aios/ledger/finance-year-wise-graph.png` | Salary vs expenses vs loan, +5%/6% growth |
| 50/30/20 allocation | `aios/ledger/allocation-50-30-20.png` | Wealth-vs-debt crossover ~Aug 2032 |
| Loan prepayment log | `aios/ledger/loan2-prepayment-log.md` | Real prepayments; corrected rates 7.1%/7.85% |

### Budget system (50 : 30 : 20 on ₹3.2L/mo)
| Deliverable | Path |
|---|---|
| Budget plan (Excel-grid PDF) | `aios/ledger/2026-budget-plan-50-30-20.pdf` |
| Monthly budget Jul–Dec | `aios/ledger/monthly-budget-jul-dec-2026.pdf` |
| Monthly household pages (18) | `aios/ledger/monthly-household-budget-2026-2027.pdf` |
| 2026 Daily Spend Tracker | `aios/ledger/2026-daily-spend-tracker.pdf` |
| Expense sheet as PDF | `aios/ledger/2026-expense-sheet.pdf` |
| **Rule:** daily discretionary limit **≈ ₹1,063/day** (groceries + eating out + fuel) | |

### Audit & investment
| Deliverable | Path | Key finding |
|---|---|---|
| Finance Audit (Jan–Jun) | `aios/ledger/2026-finance-audit-jan-jun.xlsx` | Real spend ~₹1.2–2L/mo on **cards**, not the sheet |
| 20-year investment graph | `aios/ledger/investment-20yr.png` | SIP+SSY ~₹6.3 Cr by 2046 (before PF/NPS) |
| Financial advisor (portable) | `aios/skills/financial-advisor-copilot.md` + `financial-calculator.py` |
| **Open:** PF & NPS to be added · YES •2154 confirmed **paid in full (not revolving)** | |

---

## 🧬 MEDICAL AFFAIRS

| Deliverable | Path | What |
|---|---|---|
| Copilot MA agent | `.github/copilot-instructions.md` + `.github/copilot/*.prompt.md` | Auto-loaded MA context + 8 task prompts |
| `@insight-architect` agent | `.claude/agents/insight-architect.md` | Insight-driven KOL plans (questions before experts) |
| `/insight-gathering` skill | `.claude/skills/insight-gathering/SKILL.md` | KIQ/KIT method + output template |
| Insight-plan prompt (portable) | `.github/copilot/insight-plan.prompt.md` | Web-informed v2 system prompt |
| `/ma-deliverable` skill | `.claude/skills/ma-deliverable/SKILL.md` | Draft → red-team → verify → 92% loop |
| Menopur/POR narrative | `aios/projects/menopur-por-scientific-narrative.md` | Verified 94/100 via self-correcting loop |
| Menopur history & timeline | `aios/ledger/menopur-history-timeline.pdf` | Cited deep-research (MERiT→MEGASET-HR) |
| Menopur India/APAC insight plan | `aios/projects/menopur-insight-plan.md` | Live plan; pursue-first = POSEIDON question |

---

## 🧠 AIOS KERNEL (system upgrades)

- **v4.0 Fable-class kernel** — `CLAUDE.md` + `.claude/agents/t-bone.md`
- New standing directives: **13** iterative feedback loop · **14** brevity + one next action · **15** state purpose+why · **16** lock the frame before building · **17** never fake closure
- `aios/skills/iterative-feedback-loop.md` — the Draft→Test→Learn→Refine→Check skill
- `@thai-tutor` — `.claude/agents/thai-tutor.md` (learn Thai in Hi/Mr/En)
- Council now **18 agents**

---

## 🛡️ PRIVACY (data-broker removal)

| Deliverable | Path / link |
|---|---|
| Removal tracker | `aios/projects/privacy-data-removal.md` |
| Dashboard (live) | https://claude.ai/code/artifact/ef9bc2a3-21d5-43c0-8ec0-d71bd07d3cea · `aios/dashboards/privacy-dashboard.html` |
| **Status:** 7 removal emails **sent 10 Jul** (RocketReach, ZoomInfo, Apollo, Lusha, The Org, ContactOut, SignalHire) · weekly recheck armed |

---

## 📈 TRADING — NSE F&O OI Scanner (recovered + hardened)

Rebuilt from your desktop shortcuts (was only on `C:\claude\`, never in git). Now in `nse-oi-scanner/`:
| File | Role |
|---|---|
| `scanner.py` | Futures OI-change buildup (day-open baseline, market-hours guard, retries, ban-list, volume-confirm) |
| `option_chain.py` | **PCR · Max Pain · Support/Resistance walls · call/put-writing** |
| `chart_action.py` | **Chartonix layer** — trend (Bullish+Sideways) · R1/R2 · S1/S2 · 3–5 continuation · 60%-body breakout |
| `signal_engine.py` | **3-layer confluence** (OI × option chain × chart action) → **1 CE + 1 PE + 1 Future** w/ entry/stop/target + why |
| `charts.py` | **3 annotated charts** — candlesticks, levels marked, entry/stop/target bands, "WHY THIS TRADE" box |
| `rrg.py` | **Relative Rotation Graph** — 2×2 Leading/Weakening/Lagging/Improving vs NIFTY, with tails |
| `app.py` | Streamlit dashboard (localhost:8501) — now shows the 3 ideas + RRG |
| `fyers_auth.py` · `alerts.py` | Daily token · optional Telegram |
| `install.bat` · `run_*.bat` | **4 desktop icons** (auto-refresh) — incl. new **Trade Signals + RRG** |
| **To go live (your side):** clone to `C:\claude\`, add Fyers keys, run `install.bat`, then the icons | |

**v3.0 (this session):** revalidation layer requested from the "Chartonix / Chart Action Analyzer" screenshots —
scanner signals are now cross-checked against support/resistance + trend + 60%-body breakout before any
recommendation. Emits exactly **one CE, one PE, one Future**, each with an annotated chart that marks the
levels and justifies the trade. Plus an **RRG** (leading/lagging rotation vs NIFTY). All verified in `--dry-run`
(synthetic data — live numbers need your Fyers feed on your PC).

---

## 🧭 UNIVERSAL TRADING SKILL (Fable-class 24/7 OS)

`/universal-trading` — `.claude/skills/universal-trading/` — one doctrine for every market task,
modelled on the **24/7 AI Trader · Fable 5** architecture (seb.ai) and fused with your own stack:
| Stage | Module | Output |
|---|---|---|
| Research | `fno_universe · scanner · option_chain` | universe + PCR/Max-Pain/walls bias |
| Scan | `scanner · rrg` | OI buildup + RRG rotation (fresh longs/shorts) |
| Signal | `signal_engine · chart_action` | 5 setup archetypes, 3-lens confluence score |
| Trade Plan | `signal_engine · charts` | Entry · Target · Stop · Invalidation + R:R |
| Risk | `references/risk-gate.md` | 5-check hard gate → PASS/BLOCK |
| Monitor | `report · app · alerts` | one-page desk, cadence, invalidation |
- References: `setups.md` (archetype detection), `risk-gate.md` (position/exposure/drawdown/vol/max-loss).
- Pairs with `@edge-seeker`. Verified against the built modules; not financial advice.

---

## ⏰ AUTOMATIONS (session-limited crons, 7-day expiry)

- **10 PM daily expense check** — scans day's payments, asks about unclear ones, reconciles vs ₹1,063/day
- **Sunday 9 AM privacy recheck** — re-searches 8 broker sites, re-sends ignored requests
- 8 diet-plan meal reminders (from `aios/projects/diet-plan-60day.md`)
- Gmail **Budget Tracker 2026** labels (Home Loan / Electricity / Investments)

---

## 🎯 OPEN LOOPS (waiting on you)
1. **Run the scanner** on your PC (5-min setup) → then tune universe/thresholds on live OI.
2. **Send PF & NPS** balances + monthly contributions → completes the 20-yr wealth graph.
3. **Print** the budget + daily tracker; tick nightly.
4. Reconcile the rebuilt scanner with your original `C:\claude\` logic.

_Not financial/medical advice where applicable; decisions are yours. Compliance: UCPMP/OPPI, INN names._
