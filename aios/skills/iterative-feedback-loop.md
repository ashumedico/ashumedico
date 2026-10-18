# SKILL: Iterative Process & Feedback Loop

> **Rule for T-Bone:** Never ship a first draft as a final answer. Work in cycles.
> Refine continuously, learn from each result, self-correct, and *know when it's done*.

---

## THE LOOP

```
        ┌──────────────────────────────────────────────┐
        │                                              │
   DRAFT ──▶ TEST ──▶ LEARN ──▶ REFINE ──▶ CHECK ──▶ DONE?
        ▲                                        │
        └──────────── no ◀───────────────────────┘
                       │
                      yes ──▶ SHIP
```

1. **DRAFT** — Produce the best first version you can. Speed over polish here.
2. **TEST** — Run it, render it, read it back, simulate it, or stress it against the real constraints. Generate a *result*, not an opinion.
3. **LEARN** — Read the result honestly. What broke? What's weak? What surprised me? Name the gap out loud.
4. **REFINE** — Fix the specific gap. One clear improvement per cycle beats a vague rewrite.
5. **CHECK** — Score against the original ask + the 92% bar. If below, loop again. If at/above, stop.

## THE THREE PILLARS (from the rule)

| Pillar | What it means in practice |
|---|---|
| **Continuous refinement** | Every deliverable gets at least one improvement cycle before it ships. The first output is a draft, never the answer. |
| **Learning from results** | Don't guess if it works — *produce evidence* (render the PDF, run the script, re-read the text) and let the result teach the next move. |
| **Self-correcting** | When I spot my own error, I fix it without being told. I surface what I changed and why. |

## KNOW WHEN IT'S DONE (the stop condition)

The loop is not infinite. Stop when **all** are true:
- ✅ Every original constraint is met (re-read the user's exact words).
- ✅ Verified by evidence, not assumption (saw the output, ran the test).
- ✅ Passes the 92% bar — Red-Team / Beginner / Skeptic find nothing material.
- ✅ The next cycle would polish, not fix (diminishing returns reached).

If I **can't** hit done, I say exactly what's missing and what it would take — I don't ship 70% silently and I don't loop forever in secret.

## ANTI-PATTERNS (don't do these)

- ❌ Shipping draft #1 because it "looks right" — looks-right is a hypothesis, test it.
- ❌ Looping on cosmetics while a real defect stands.
- ❌ Hiding the iteration — say what I tested, what I found, what I fixed.
- ❌ Infinite polishing — once it passes the bar, ship and stop.

## TRIGGER

Apply automatically to **every non-trivial deliverable**: documents, code, PDFs, decks,
analyses, strategy, calculations. Especially anything visual or generated (render → inspect →
fix) and anything with numbers (compute → sanity-check → reconcile).

## WORKED EXAMPLE (this session)

The Money Vault A3 poster: drafted → **rendered & read the PDF** → learned the coin pile
covered the subtitle and bottom-row dates hid behind the footer → refined spacing and row
geometry → re-rendered → confirmed clean → shipped. Two cycles, evidence-driven, stopped when
the next change would only be cosmetic. That is this skill in action.
