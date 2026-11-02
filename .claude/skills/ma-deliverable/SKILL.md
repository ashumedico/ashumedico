---
name: ma-deliverable
description: Produce a Medical Affairs deliverable (Menopur/Rekovelle scientific narrative, slide kit, claim set, KOL/advisory content, value story) through the self-correcting council loop — draft → compliance red-team → refine → verify to 92% — so what reaches the user is MLR-ready, not a first draft. Use whenever the task is office/MA content for RMMH products.
---

# /ma-deliverable — Self-Correcting MA Content Loop

Runs Standing Directive 13 (iterative feedback loop) automatically on any Medical Affairs
deliverable. The user receives a verified artifact + a 6-line journey, never a raw draft.

## INPUT
A request like: "core claims for Rekovelle AMH-based dosing", "advisory-board narrative on
Menopur in POR", "compliance-safe slide kit on individualised FSH dosing".

If product/audience/context is ambiguous, ask **one** sharp question, then proceed.

## THE LOOP (execute in order)

1. **DRAFT** — Write v1 to `aios/projects/<slug>.md`. Use `@evidence-sculptor` for scientific
   narratives/slide kits; draft directly for short claim sets. Mark every data point that needs
   a real citation as `[Ref: … — to attach]`. Never fabricate trial statistics.

2. **TEST (red-team)** — Launch `@compliance-redteam` on the file. It audits UCPMP/OPPI: INN-first
   naming, absolute/superlative claims, uncited figures, comparative-claim integrity (e.g. a trial's
   population must match the claim), fair balance/safety, off-label/blanket-switching, promotional tone.
   It returns findings by severity + PASS / FIX-REQUIRED.

3. **LEARN + REFINE** — Edit the file to close **every** finding. Hedge mechanism claims, strip
   absolutes, attach or flag references, add proportionate safety, make MSL guidance reactive.

4. **CHECK (verify)** — Launch `@verifier`. It re-scores against the original ask + confirms each
   red-team finding is CLOSED, runs Red-Team / Skeptic / Beginner critics, returns a score /100.

5. **DECIDE**
   - Score **≥ 92** → polish trivial deterministic items, **STOP**. Do not re-verify polish.
   - Score **< 92** → take the verifier's exact minimal fixes, loop back to step 3 (max ~3 cycles).
   - If the only gap is real citations / PI the user must supply → **STOP** and say so; the document
     self-gates against external use until they're attached.

6. **SHIP** — Commit + push the verified artifact. Report the journey in ≤6 lines (per Directive 14).

## OUTPUT FORMAT (what the user sees)
```
<deliverable name> — <SHIP score>/100
Red-team: <n CRITICAL / n MAJOR caught>  →  all CLOSED
Gap I can't close: <real refs / PI, or "none">
Next: <one action>
```

## GUARDRAILS
- INN (generic) name first at first mention. No "best/only/guarantees/safest".
- Every efficacy/comparative claim is evidence-bound with population + endpoint + source, or it's cut.
- A cited trial must actually match the claim's population (referencing integrity).
- Proportionate safety/fair balance always present. MSLs are reactive, never recommend prescribing.
- Anything promotional re-routes through `@compliance-redteam` before external use.

## STOP CONDITION (Directive 13)
Done when: all constraints met · every finding CLOSED · ≥92 · next cycle only polishes.
Not done → state exactly what's missing. Never ship 70% silently; never loop forever.

## REFERENCE RUN
First execution: Menopur/POR narrative — v1 (6 CRITICAL) → v2 (all closed) → verifier 94/100 SHIP.
Saved at `aios/projects/menopur-por-scientific-narrative.md`.
