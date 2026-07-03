# RPCE Scoring Model

How the app turns a candidate's practice history into the three numbers it shows, when it refuses to show them, and the exact formulas. Grounded in the exam structure in `data/2026-4-22-Criteria-for-Credentialing-UPDATED-v1.md`: the RPCE has **Section I** (100 auto-scored multiple-choice questions) and **Section II** (written performance scenarios scored by examiners); the pass mark is **80% on each section**.

Same formulas run on desktop (`pylib/anki/rpce/scores.py`) and phone (`mobile/jni/src/lib.rs`); they read the same synced card/scenario data, so the numbers match across devices.

## Concepts and coverage

Every practice item (Review card, Section II scenario, Simulate decision) carries a **concept**. A concept is **one numbered RP performance expectation** (1.1, 1.2, … 7.43 — roughly 180 in total; see `CONCEPTS` in `pylib/anki/rpce/concepts.py`, built from `data/rpce_concepts.json`). Each concept has a domain (1–7), a short label, its RONR (12th ed.) citations, and a section weight.

- **Coverage(section)** = (concepts in that section with ≥ `MIN_ITEMS_PER_CONCEPT` graded items) / (total concepts in that section). This is the "percent of the exam covered so far" shown with every score.
- Section I concepts = all knowledge/recall concepts (the MCQ blueprint). Section II concepts = the concepts that have authored performance scenarios.

## The three scores

### 1. Memory — "will the candidate recall a fact we taught?"

Computed only over concepts/cards the candidate **has actually studied**.

- Per card: `r = (reps − lapses + 1) / (reps + 2)` (Laplace-smoothed recall; transparent and identical on both platforms). FSRS retrievability is shown separately as a calibration read-out, not folded into this score, so desktop and phone agree.
- Per concept: mean `r` over that concept's reviewed cards (reps > 0).
- **Memory point** = mean of per-card `r` over all reviewed cards.
- **Range** = 95% normal interval: `point ± 1.96·(σ/√n)` clamped to [0,1] (σ = population stdev of the recalls; if n = 1, σ treated as 0.5 = maximum uncertainty).

### 2. Performance — "will the candidate get a NEW, unseen exam-style question right?"

Generalization across the whole blueprint, so **unseen concepts count as 0** (incomplete coverage lowers the score — that is the honest signal).

- Per concept recall `c_i` = mean card recall for concept `i` (0 if unstudied).
- **Performance point** = `Σ wᵢ·cᵢ / Σ wᵢ` over ALL concepts in the section (weights `wᵢ` = concept weight), unseen `cᵢ = 0`.
- **Range** margin widens when coverage is low: `margin = 0.10 + 0.40·(1 − coverage)`, clamped to [0,1].

### 3. Readiness — projected section score, with a range (separate for Section I and Section II)

Readiness is the probability of clearing the 80% bar on that section, expressed on the real 0–100% scale plus a range — never a single "78% ready".

- Map the section's Performance estimate through the 80% bar with a logistic:
  `P(pass) = 1 / (1 + exp(−k·(perf − 0.80)))`, with `k = 12`.
- **Section I readiness**: `perf` = concept-weighted recall over Section-I (recall/MCQ) practice.
- **Section II readiness**: `perf` = concept-weighted **scenario pass rate** over graded Section II scenarios (fraction scoring ≥ the examiner pass threshold), unseen concepts 0.
- **Range**: push `perf_low` and `perf_high` through the same logistic → `[P(pass|perf_low), P(pass|perf_high)]`.
- The projected **percent score** shown to the candidate is `perf` itself (0–100%), with the range from `perf_low..perf_high`; the pass probability drives the "on track / not yet" verdict.

## What every score displays (spec §4 / §10)

1. **Point estimate** (e.g. "Section I projected: 84%").
2. **Likely range** (e.g. "79–89%").
3. **Percent of the exam covered so far** (concept coverage for that section).
4. **How-sure indicator** — `high` (≥200 data points AND ≥80% coverage), `medium` (≥50 AND ≥50%), `low` otherwise; always contains the word "confidence".
5. **Last updated** — timestamp recorded when the score is computed at a meaningful moment (dashboard open, after answering).
6. **Main reasons** — the drivers ("62% of topics covered; weakest area: Voting; 140 graded reviews").
7. **The give-up rule** — below the line, no number is shown (next section).

Example readiness display (the RPCE analogue of the MCAT example):

```
Projected Section I: 84%
Likely range: 79% to 89%
Confidence: low — you have covered only 42% of the Section I topics.
Covered: 42% of topics · 140 graded reviews · updated 2 min ago
```

## The give-up rule (write it down)

A score is shown only when there is enough data to be honest; otherwise the card shows **no number** and lists exactly what is still needed.

- **Memory / Performance / Section I readiness** — no score until **≥ 200 graded reviews** AND **≥ 50% Section I concept coverage**.
- **Section II readiness** — no score until **≥ 100 graded scenarios** AND **≥ 50% Section II concept coverage**.
- **Per-concept** sub-scores are hidden until that concept has **≥ `MIN_ITEMS_PER_CONCEPT` (5)** graded items.

Below the line the app abstains: it shows a dash with the full-uncertainty range (0–100%) and a "Data needed" list with concrete counts ("132 more graded reviews needed (68/200); Voting, Nominations 0% covered"). "A good system knows when it does not know."

Thresholds live in one place (`GiveUpRule`: `min_graded_reviews=200`, `min_coverage=0.5`, `min_scenarios=100`, `min_items_per_concept=5`) and are mirrored in the Rust engine.
