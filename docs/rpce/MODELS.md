# Model descriptions — Speedrun for the RPCE

The app answers three separate questions (spec §4) and never blends them into one
number. Each score ships with a point estimate, a likely range, the percent of
the exam covered, a confidence label, the time it was last updated, the main
reasons behind it, and a hard give-up rule. All three are pure functions in
`pylib/anki/rpce/{scores,metrics}.py`, so anyone can re-run them on held-out data
and get the same result.

## The give-up rule (written down)

No readiness score is shown until the collection has **≥ 200 graded reviews** and
**≥ 50% domain coverage** (and, for Section II, **≥ 100 graded scenarios**).
`GiveUpRule` in `scores.py`; below the line the dashboard shows "—" and states
exactly what data is missing (e.g. "16/200 graded reviews") rather than a number.
A confident number with nothing behind it is a guess in a nice font — so we show
nothing.

## 1. Memory — "can the student recall a fact taught right now?"

- **What it is.** The probability of recalling a reviewed card now. FSRS already
  models memory well, so we read its retrievability rather than reinventing it.
- **How.** `memory_score` averages per-card recall over reviewed cards (FSRS
  retrievability when FSRS is on; a Laplace-smoothed reps/lapses estimate
  otherwise). The **range** is the spread of that per-card distribution, not a
  fabricated interval.
- **Calibration (spec §9 step 1).** `memory_calibration` / `metrics` report
  **Brier score**, **log-loss**, and **ECE** of past predictions vs. actual
  recall on held-out reviews — when it says 80%, the student should recall ~80%
  of the time. Re-run it with `just rpce-calibration`, which writes the numbers +
  a reliability-diagram to `docs/rpce/artifacts/calibration.{svg,json}`; results
  and honesty caveats are in [`RESULTS.md`](./RESULTS.md).
- **Give up.** Abstains with no reviewed cards.

## 2. Performance — "can the student answer a NEW exam-style question?"

- **What it is.** The probability of getting a fresh, exam-style item right —
  including ones never seen. This is the memory→performance bridge, the point of
  the project.
- **How.** `performance_score` combines coverage and per-topic weakness across
  the seven RPCE domains; the range propagates that uncertainty.
- **Proving it's a real bridge (spec §7d).** `rpce_paraphrase.py` compares card
  recall against accuracy on 2 reworded questions per card and reports the
  **gap** (`metrics.paraphrase_gap`). A near-zero gap would mean performance just
  copies memory; we report the gap honestly rather than hide it.
- **Held-out (spec §9 step 2) + beats a simpler method.** Evaluated on held-back
  exam-style questions. `rpce_examiner_eval.py` (`just rpce-examiner-eval`) grades
  a held-out set of **reworded** answers — 42 correct paraphrases + 22 fluent
  wrong twins — where the AI examiner beats both simpler graders on accuracy and
  false-pass (100%/0% vs rubric 81%/23% vs keyword 67%/14%); grading verbatim
  answers can't tell graders apart (all ~100%). The gold-set checker
  (`rpce_gold_eval.py`) provides the ≥50-item gold set and a leakage scan so
  nothing from the test set leaks into training. Numbers + honesty notes in
  [`RESULTS.md`](./RESULTS.md).

## 3. Readiness — "what would the student score today, and how sure are we?"

- **Scale.** The RPCE is **pass/fail per section at 80%** (like USMLE Step 1, we
  do not invent a numeric score). Readiness is **P(pass Section I)** and
  **P(pass Section II ≥ 80%)**, each with a range.
- **How.** `section_readiness` maps the performance estimate through the 80%
  section bar with a logistic function; the range is the same mapping applied to
  the performance range. Section II additionally requires graded scenarios.
- **Confidence + reasons.** Every score carries a confidence label ("high/low
  confidence"), the coverage %, the last-updated time, and a plain-language "why
  this score" summarizing how prepared the student is.
- **Give up.** Abstains (shows "—") until the give-up rule above is met.

## Honesty

Per spec §9, we grade the *steps of the bridge*, not a made-up final number:
memory calibration (proven), performance on held-out questions, and a documented
score mapping with a range. Where we lack real student practice-test data to
validate the projected pass probability end-to-end, we say so rather than
present a polished number we can't back up.
