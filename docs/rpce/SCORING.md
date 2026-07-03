# RPCE Scoring Model

How the app turns a candidate's practice history into the three numbers it shows, when it refuses to show them, and the exact formulas. Grounded in the exam structure in `data/2026-4-22-Criteria-for-Credentialing-UPDATED-v1.md`: the RPCE has **Section I** (100 auto-scored multiple-choice questions) and **Section II** (written performance scenarios scored by examiners); the pass mark is **80% on each section**.

Same formulas run on desktop (`pylib/anki/rpce/scores.py`) and phone (`mobile/jni/src/lib.rs`); they read the same synced card/scenario data, so the numbers match across devices.

## Concepts and coverage

Every practice item (Review card, Section II scenario, Simulate decision) carries a **concept**. A concept is **one numbered RP performance expectation** (1.1, 1.2, … 7.43 — **210** in total; see `CONCEPTS` in `pylib/anki/rpce/concepts.py`, built from `data/rpce_concepts.json`). Each concept has a domain (1–7), a short label, its RONR (12th ed.) citations, and a section weight.

### Coverage = mastered concepts

**Coverage** is the fraction of the 210 performance-expectation concepts the candidate has **mastered** — the "percent of the exam covered so far" shown with every score.

A concept counts as **mastered** once **one of its cards has its 2 most-recent reviews both a pass (Good or Easy) with the most recent rated Easy**. In other words: you have to have recently, consistently aced a question of that concept — not just seen it, and not just one lucky Easy.

- Formally, over the card's most-recent `COVERAGE_RECENT_N = 2` reviews (newest first): the newest is **Easy** (ease 4) **and** every one is at least **Good** (ease ≥ 3).
- **Why the last 2, not a longer all-Easy streak?** The concept-sibling burying (the fork's `BuryConceptSiblings`) buries a concept's other cards as soon as you answer one, so a given card is usually reviewed only once or twice before its siblings go away. An "N most-recent all Easy" rule with N ≥ 3 was therefore unreachable and left coverage stuck at 0%. Two recent passes ending in Easy is both attainable and a genuine mastery signal, and it rises naturally as more concepts are aced.
- Implemented identically on both platforms: `concepts_mastered` / `concept_coverage_pct` in `pylib/anki/rpce/scores.py` and `concept_coverage` in `mobile/jni/src/lib.rs` (constants `COVERAGE_RECENT_N`, Easy = 4, Good = 3).

Section I concepts = all knowledge/recall concepts (the MCQ blueprint); Section II concepts = the concepts that have authored performance scenarios. `MIN_ITEMS_PER_CONCEPT` (5) is a separate threshold — it gates when a *per-concept sub-score* is shown, not coverage (see the give-up rule below).

## The three scores

### 1. Memory — "will the candidate recall a fact we taught?"

Computed only over concepts/cards the candidate **has actually studied**.

- Per card: `r = (reps − lapses + 1) / (reps + 2)` (Laplace-smoothed recall; transparent and identical on both platforms). FSRS retrievability is shown separately as a calibration read-out, not folded into this score, so desktop and phone agree.
- Per concept: mean `r` over that concept's reviewed cards (reps > 0).
- **Memory point** = mean of per-card `r` over all reviewed cards.
- **Range** = 95% normal interval: `point ± 1.96·(σ/√n)` clamped to [0,1] (σ = population stdev of the recalls; if n = 1, σ treated as 0.5 = maximum uncertainty).

### 2. Performance — "will the candidate get a NEW exam-style question right?"

A **concept-weighted projection** of first-attempt accuracy across the whole blueprint. It is NOT an average of what you've drilled (that's Memory) — it measures how often you get a question **right the first time you see it** (a new question), projected over every concept, with concepts you've never practised counting as **0** (a new concept you'd likely miss). So it estimates your score on fresh exam questions.

- Per-concept first-attempt accuracy `cᵢ` = fraction of concept `i`'s cards answered correctly (ease ≥ Good) on their **earliest** review.
- Per-concept weight `wᵢ` = its domain's exam weight, split evenly across that domain's concepts (so each domain keeps its exam weight; there is no per-concept weight in the registry).
- **Performance point** = `Σ wᵢ·cᵢ / Σ wᵢ` over ALL 210 concepts, where `cᵢ = 0` for any concept never practised.
- Abstains (no number) until at least one question has been answered.
- **Range** margin widens when coverage is low: `margin = 0.10 + 0.40·(1 − coverage)`, clamped to [0,1].

### 3. Predicted Section I / Section II — projected section score, with a range

The predicted section score is the same **concept-weighted first-attempt projection** as Performance (§2), expressed on the real 0–100% scale plus a range — a projection to exam day across the whole blueprint. (The registry does not tag concepts by section, so both sections project over the full concept set; Section II additionally requires graded scenarios before it shows a number — see the give-up rule.)

- The projected **percent score** shown is the projection `perf` itself (0–100%), with its range.
- A logistic maps `perf` through the 80% bar to a pass probability for the "on track / not yet" verdict: `P(pass) = 1 / (1 + exp(−k·(perf − 0.80)))`, `k = 12`; the range endpoints go through the same logistic.

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
