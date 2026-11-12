---
name: financial-freedom
description: How to turn a salaried household's income into passive income on safe assets — backup first, debt-free fastest, then a corpus that pays living costs. Use for any money-planning task — budgets, prepay-vs-invest, emergency fund, FIRE or "freedom number", "make money from money", the Paisa Manager Freedom tab — and before stating any date or rupee figure about getting debt-free or financially free. Indian context: new tax regime, PPF/SSY/VPF, home loans. Not financial advice.
---

# FINANCIAL FREEDOM — money that works, in the right order

> "Turn this system to money making from money. Passive income from current income,
> debt-free ASAP, a backup, and financial freedom for both of us."

Freedom is a **date**, not a feeling. The job is to compute that date honestly, show which
lever moves it most, and say exactly where this month's spare rupee goes. A plan that
can't name this month's allocation is a wish.

---

## 1 · The waterfall: every spare rupee, in this order

```
take-home  −  living  −  EMIs  −  commitments (SSY etc.)  =  surplus
surplus  →  1. backup (emergency fund) until it hits target
         →  2. prepay the HIGHEST-RATE loan (avalanche), then the next
         →  3. freedom corpus (safe assets)
```

- **Backup first, always.** Prepaying a loan is irreversible — the bank won't hand the money
  back in an emergency. Without a backup, one bad month means a card that revolves at ~42% a year,
  which undoes years of prepaying at 7–8%.
- **Avalanche, not snowball.** Order prepayments by **rate**, never by rupees saved. A long
  loan always shows a bigger "interest saved" headline because the money compounds for longer —
  that number misleads. The return on a prepaid rupee is the loan's rate. Say what the gap
  is worth in rupees a year (₹1L × rate difference); when it's small, liquidity outranks it.
- **A short month draws on the backup.** Never model a negative surplus as zero.

## 2 · Prepay or invest? Compare after tax, not headline rates

| Use of a rupee | Return to compare |
|---|---|
| Prepay a self-occupied home loan (new regime: no s.24(b) interest deduction) | full loan rate, risk-free, tax-free |
| PPF / SSY / VPF (EEE) | headline rate, tax-free — capped (PPF ₹1.5L/yr; PF interest is tax-free only on employee contributions up to ₹2.5L/yr) |
| FD / debt fund at the 30% slab | rate × 0.7 |
| Arbitrage fund | taxed as equity — check the current STCG/LTCG rates before quoting |

With **safe assets only**, a loan at 7–8% beats almost every taxed alternative. That is why
debt-free comes before the corpus — not a moral rule, just arithmetic. Re-check scheme rates every
quarter (small-savings rates reset quarterly) and quote the quarter.

## 3 · The four numbers a CA reads first

| Number | Formula | Bands |
|---|---|---|
| **FOIR** | EMIs ÷ household take-home | ≤ 40% comfortable · 40–50% watch · > 50% lenders stop |
| **Emergency cover** | backup ÷ fixed monthly outflow | < 1 mo act · 1–3 watch · ≥ 3 (6 for single income) |
| **Safe to spend till next salary** | known bank cash − floor − bills due − other dues before payday | < 0 act |
| **Interest share of EMI** | Σ(outstanding × rate/12) ÷ Σ EMI | > 50% means the early years mostly feed the bank |

Absent is not zero: an unknown balance shows **?**, an unknown credit stays out of income until
tagged (it could be a refund, a loan or money coming back), and a net worth isn't stated while
any balance is missing — list what's missing instead.

## 4 · The freedom maths

- **Freedom number** = annual living × (1 ÷ SWR). Living excludes EMIs (they end) but includes
  school fees ÷ 12 and insurance ÷ 12.
- **SWR for India: 3–3.5%**, not the US 4% — inflation runs ~5–6%.
- **Real return decides how long a corpus lasts.** On safe assets real ≈ 1%. At 1% real and 3.5%
  withdrawals a corpus lasts ~34 years, not forever: `n = −ln(1 − r/s) ÷ ln(1+r)`. Say so; never
  write "forever" unless r ≥ s.
- **Freedom requires debt-free.** A corpus that covers living while EMIs still run is not freedom.
- Simulate **month by month**: salary and living step up once a year; interest accrues monthly;
  stop at the first month the corpus × SWR ÷ 12 ≥ living, after debt is gone. Cap at 50 years and
  say "50+ yrs", never a fake date.

## 5 · Rank the levers by measured effect, not by intuition

Re-run the plan with one change at a time and sort by years saved. On a typical salaried Indian
household with safe assets the order comes out:

1. **Salary growth** (+2%/yr) — usually the biggest; career moves are a finance lever.
2. **Living cost** (−₹10k/mo) — works twice: more surplus *and* a smaller freedom number.
3. **Extra income** (+₹25k/mo).
4. **Return** (+1%) — the smallest. Chasing yield on safe assets barely moves the date.

If the ranking ever flips, say why. Name the cross-domain lever: the biggest money move is often
in `@positioning-strategist`'s territory, not in the portfolio.

## 6 · Divergence — offer all three, recommend one

- **Obvious:** waterfall + avalanche on safe assets (the default above).
- **Contrarian:** once debt-free, a growth sleeve (index funds) — real return 4–6% instead of ~1% —
  cuts years off. Only if the person lifts "safe assets only"; surface the trade-off, never slip it in.
- **10x:** raise the salary trajectory (role change, second income) or a tax-exempt income source
  (agricultural income is exempt). Usually worth more than every portfolio tweak combined.

## 7 · Data rules (inherits `/real-money-only`, `/data-integrity`)

- Every input is tagged with where it came from: **verified** (statement, payslip, bank alert),
  **stated** (the person said it), **plan** (an assumption) — and assumptions sit in one editable
  place, never buried in code.
- Missing starting balances count as ₹0 **and the page says so** ("dates are conservative").
- Derive every printed number from the model; never hand-type a figure into prose.
- Cross-check the simulator against a closed form before shipping: EMI-only payoff months must
  equal `−ln(1 − rP/E) ÷ ln(1+r)`, rounded up.
- No personal rupee figure ever goes into this repo (it is public). Personal data lives in the
  app's private database and the git-ignored ledger.

## 8 · Where it runs

The **Paisa Manager** artifact (private) implements this skill: a *Freedom* tab with the three
milestones (backup → debt-free → free), this month's waterfall, passive income vs living, the
freedom number with its true lifetime, the ranked levers, and one editable *Assumptions* card.
The *Balance* tab carries the CA check (section 3); the *Loans* tab shows the interest/principal
split, payoff dates and the prepay-by-rate rule. Every add or edit previews which figures move
before you save.

When the person asks "what do I do this month?", answer from the waterfall — one line per bucket
— then one **Next:** action.

*Planning maths, not financial advice.*
