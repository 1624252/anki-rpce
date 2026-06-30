# Product Requirements Document — "Speedrun for the RPCE"

**A desktop + mobile study app, forked from Anki, for one graduate-level exam: the NAP Registered Parliamentarian Credentialing Exam (RPCE).**

| | |
| --- | --- |
| **Owner** | Project owner |
| **Status** | Draft v1 (MVP definition) |
| **Exam (locked)** | RPCE — NAP Registered Parliamentarian Credentialing Exam |
| **License** | AGPL-3.0-or-later, with credit to Anki (Ankitects). Some upstream parts are BSD-3-Clause. |
| **Source corpus** | *Robert's Rules of Order Newly Revised, 12th ed.* (RONR) + NAP RP Performance Expectations + Joint Code of Professional Responsibility |

---

## 1. Summary

Speedrun is not "another flashcard app." A credentialing exam asks for more than memory: a
candidate must **apply** rules to scenarios they have never seen, work **fast enough** under a
hard time limit, and honestly know **whether they are ready**. Speedrun is built by forking
Anki so it inherits Anki's proven memory engine (FSRS) and its shared Rust core, then adds the
two harder bridges the spec demands: **memory → performance** (answering new questions) and
**performance → readiness** (a calibrated pass-probability with a range, not a guess in a nice font).

We pick **one** exam and build the whole product for it: the **RPCE**. The RPCE is uniquely
well-suited to this thesis because it is *already split into the two halves we must model*:

- **Section I** — 100 multiple-choice questions, 3 hours, auto-scored. → maps to **spaced retrieval** (memory + applied MCQ performance).
- **Section II** — written performance scenarios, 3 hours, scored by trained examiners. → maps to **scenario + immediate AI debrief** (applied performance).
- A candidate must score **80% on *each* section independently** (proctored via ExamSoft/Examplify).

Because the exam is pass/per-section (not a scaled score), **readiness is modeled as a
probability of clearing the 80% bar on each section** — never an invented point score.

---

## 2. Problems We Solve (and the evidence behind them)

Grounded in the RPCE BrainLift research insights:

1. **The "simulation vs. flashcards" false binary (Insight 1).** Existing prep picks one. Flashcards build durable recall but not applied judgment; simulation builds judgment but decays without spaced re-exposure. **We build a hybrid** whose two modes mirror the two exam sections.
2. **Recall practice breeds false mastery (SPOV 1).** Drilling one question format trains pattern-matching to the *format*, not the *concept*. A real meeting never presents a rule in the tidy shape a flashcard did. **We rotate formats** (cloze recall → applied MCQ → free-text scenario) over the same content to force transfer.
3. **Feedback is the active ingredient (Insight 4).** Simulation *with* debrief beats simulation alone; the incumbent's feedback is delayed and instructor-mediated. **We give immediate, per-item AI debrief.**
4. **The AI should be an examiner, not a tutor (SPOV 3).** Candidates already passed the RONRIB membership exam (high prior knowledge) and the corpus (RONR 12th ed.) is closed and citable. An AI inventing facts is actively harmful (see NAPMobile's wrong answers). **The AI grades and probes Section II answers against the Performance Expectations and demands RONR citations** — it does not lecture facts.
5. **Nobody offers an honest readiness signal (Insight 10).** NAP has content but no adaptivity or readiness score; NAPMobile is a plain (sometimes wrong) quiz bank. **We show a calibrated readiness range with its evidence — and abstain when we lack data.**

**The honesty rule (hard requirement from spec §1).** Speedrun may not show a readiness number
unless it also shows: the evidence behind it, what data is still missing, how accurate past
predictions were, the *range* of likely outcomes, and the single best next thing to study.

---

## 3. User Persona (start niche)

We deliberately start with **one** narrow user, not "test-prep students" in general.

### Primary persona — "the working-adult RP candidate"

- **Who:** A 30–55-year-old working professional embedded in a governance setting — association staff, an HOA/union/church board officer, or an attorney who advises boards.
- **Prior knowledge:** **High.** The candidate has *already passed* the NAP membership (RONRIB) exam, so they know the basics and need *application and reflection*, not more worked examples (Insight 3).
- **Goal:** Pass **both** RPCE sections (≥80% each) within a quarterly window, while holding a full-time job — so they study in two places: at a desk in the evening and **on their phone between meetings**.
- **Pain today:** Lecture/cohort prep is scheduled and passive; the official app is a flat quiz bank with occasional wrong answers; no tool tells them honestly whether they are ready or which domain is their weakest.
- **Definition of success:** "I know my real weak spot today, I can practice Section II scenarios and get graded like an examiner would, and the app tells me — with a confidence range — when I'm actually ready, instead of guessing."

### Secondary / later personas (not the MVP focus)

- A PRP candidate (next credential up) reusing the simulation engine — *future*, validates lifecycle but out of MVP scope.
- A board member who only wants to run meetings (the commercial-course audience) — *explicitly not us*; they want basic motions, not exam rigor.

---

## 4. User Stories

### 4a. Stories we ARE focused on (MVP)

- As **the candidate**, I want to **review RPCE flashcards scheduled by spaced repetition** so that **I retain RONR facts without re-studying everything every night.**
- As **the candidate**, I want the **same fact to resurface in different formats** (recall, applied MCQ, scenario) so that **I prove I can apply it, not just recognize the wording.**
- As **the candidate**, I want to **answer free-text Section II scenarios and get immediate, examiner-style feedback with RONR citations** so that **I learn to justify rulings the way the graders expect.**
- As **the candidate**, I want to **see three separate scores — memory, performance, readiness — each with a range** so that **I'm not misled by a single blended number.**
- As **the candidate**, I want the app to **refuse to show a readiness score until it has enough data** so that **I trust it when it finally does.**
- As **the candidate**, I want a **coverage map of all seven Performance Expectation domains** so that **I can see which high-weight domain I've barely touched.**
- As **the candidate**, I want to **review on my phone offline, then sync to my desktop** so that **I can study between meetings and pick up where I left off at my desk.**
- As **the candidate**, I want **timed practice that mirrors the 3-hour limit** so that **I build pacing, not just untimed knowledge.**

### 4b. Stories we are NOT focused on (out of scope for MVP)

- As a casual user, I want to learn the *basics* of running a meeting. *(Wrong audience — that's the commercial-course market.)*
- As a candidate, I want the app to *take the proctored exam for me* or integrate with ExamSoft. *(Not possible/allowed; Examplify is a locked-down environment.)*
- As a candidate, I want a single "78% ready" gamified number. *(Banned by the honesty rule.)*
- As a user, I want AI to *teach me new parliamentary facts conversationally.* *(The AI is an examiner, not a tutor.)*
- As a PRP candidate, I want the two-day live-simulation exam modeled. *(Future.)*

---

## 5. MVP Definition

The MVP is sequenced to the spec's deadlines: **make the apps work → add AI → prove it.**

### 5a. In scope (MVP)

**Engine & platforms**
- Forked Anki building from source (AGPL-3.0-or-later, credit to Anki).
- **One real change inside Anki's Rust core** (not just Python screens): a **topic-aware / points-at-stake review queue** that orders due cards by `domain exam-weight × student weakness`, exposed via a new protobuf message and callable from Python. Ships with ≥3 Rust unit tests + 1 Python-calling test, undo-safe, no collection corruption.
- **Desktop app** (Anki's Python/Qt + Svelte) running a review loop on the RPCE deck.
- **Phone companion** that builds and runs on a real device/emulator, loads the RPCE deck, runs real reviews on the *shared* Rust engine, and **two-way syncs** with desktop (offline → reconnect, no lost/double-counted reviews; documented conflict rule).

**Learning content**
- RPCE deck mapped to the **seven Performance Expectation domains**, each card tagged to a domain (and, where possible, a specific PE).
- **Format rotation** for a given concept: cloze recall, applied MCQ, free-text scenario.
- **Section II scenario practice** with **AI examiner grading** against the Performance Expectations, demanding RONR citations, with immediate debrief.

**The three scores (each with a range + give-up rule)**
- **Memory:** P(recall a taught fact now) — from FSRS, **calibrated** (calibration chart + Brier/log-loss on held-out reviews).
- **Performance:** P(correct on a *new* exam-style item), incl. unseen ones (uses topic mastery, item difficulty, timing, coverage).
- **Readiness:** **P(pass each section ≥80%)** with a likely range and a confidence note — pass-probability framing, *no invented scaled score*.
- **Give-up rule (stated):** *No readiness shown until ≥200 graded reviews, ≥50% domain coverage across all seven domains, and ≥10 graded Section II scenarios.* Below the line, the app abstains.

**AI safety & evidence**
- Every AI output traces to a **named source** (an RONR 12th-ed. citation / a Performance Expectation / the Joint Code section).
- **Pre-release eval** on a held-out gold set (50 Q&A pairs): accuracy + wrong-answer rate, with a cutoff set *before* looking.
- **Beats a baseline** (keyword or vector search over the RONR corpus) shown side-by-side.
- **Leakage check** script: flags any test item (or near-copy) that slipped into training data.
- **AI-off mode:** both apps still give a score with AI switched off.

**One study feature, tested (spec §8)**
- **Hypothesis:** *"Rotating question format over the same content (varied practice) raises accuracy on new, reworded scenario questions at equal study time, vs. repeating a single format."*
- Tested with three builds at equal study time: full app (rotation on) / ablation (rotation off) / plain unmodified Anki. Main metric stated ahead of time; range reported; null results reported honestly.
- **Paraphrase test:** 30 cards → 2 reworded exam-style questions each; report the recall-vs-reworded gap to prove performance ≠ memory.

**Packaging**
- Desktop installer that runs on a clean machine; signed phone build (APK / TestFlight or sideload). Both run with AI off.

### 5b. Out of scope (MVP)

- ExamSoft/Examplify integration or any proctoring.
- The PRP two-day live simulation; voice/real-time multi-user mock meetings.
- AI-generated *new* study content shipped to users without passing the gold-set checker.
- Native rewrite of the scheduler in JS/Swift (spec forbids it — must share the Rust engine).
- A scaled/blended single readiness number.
- Real-student score-validation against actual practice-test outcomes (Step 4 "bonus" only — we grade the *bridge*, not a made-up final number).

---

## 6. Domain Building (RPCE specifics that drive the product)

| Attribute | Value | Product implication |
| --- | --- | --- |
| Sections | Section I (100 MCQ, auto-scored) + Section II (written performance) | Two engine modes, scored independently |
| Pass bar | **80% on *each* section** | Readiness = two pass-probabilities, not one |
| Time | 3 hrs per section (7 hrs total, ≤1 hr break, upload ≤8 hrs) | Timed practice is a first-class feature |
| Domains | **7 Performance Expectations** (Main motions; Subsidiary/Privileged; Incidental & bring-again; Org/Conduct of meetings; Voting/Nominations/Elections; Professionalism/Teaching; Boards/Committees & Bylaws) | Coverage map + topic weights keyed to these 7 |
| Corpus | RONR 12th ed. (closed, citable) + Joint Code of Professional Responsibility | AI must cite; grounds the leakage/eval design |
| Candidate | Already passed RONRIB membership exam | High prior knowledge → reflection > worked examples |
| Cadence | Quarterly 7-day windows; RP renews every 2 years | Spaced retrieval extends usefulness past exam day |

---

## 7. Tech Stack

- **Core engine:** Anki's **Rust** backend (`rslib`), forked. Our Rust change (topic-aware queue) lives here so it ships to **both** desktop and phone. Protobuf for the Rust↔client boundary.
- **Desktop client:** Anki's **Python + PyQt (aqt)** shell with **Svelte/TypeScript** webviews for dashboards (three scores, coverage map).
- **Mobile client:** **AnkiDroid** (Kotlin, AGPL) for Android, reusing the shared Rust backend; **iOS** via Anki's Rust C-interface (FFI). MVP targets Android first.
- **Sync:** self-hosted **Anki sync server** (HTTP), reused so reviews flow both ways; documented last-writer / higher-`usn` conflict rule for the same-card-offline case.
- **Local storage:** **SQLite** — Anki's `collection.anki2` on each device, plus our custom tables (§8).
- **AI layer:** an LLM API (examiner grading + scenario debrief) behind a thin service, with **retrieval over the RONR markdown corpus** (the existing `convert_ronr.py` output) for citation grounding. **Baseline** = keyword/vector search for the side-by-side. All AI is **optional** (app fully works AI-off).
- **Source corpus pipeline:** existing Python converters (`convert_ronr.py`, `convert_rpce.py`) using `pymupdf` → faithful Markdown + rendered rubric images. *Source PDFs are copyrighted and stay out of version control.*
- **Quality:** Rust unit tests + Python integration test for the engine change; held-out eval harness (re-runnable, deterministic seed); leakage scanner; **linters** (`ruff` for Python, Anki's `./ninja format`/`fix`, `cargo clippy`) wired into CI.

---

## 8. Data Schema

**Where it lives:** each device holds a local **SQLite** collection (`collection.anki2`); changes
sync via the Anki sync server. The **RONR corpus** ships as a read-only bundled asset (Markdown +
images). **Eval/gold sets and held-out reviews live in the repo, never synced into the trained
model** (enforced by the leakage check).

### 8a. Reused Anki tables (unchanged)
- `notes`, `cards`, `notetypes`, `decks` — content + scheduling fields (FSRS stability/difficulty).
- `revlog` — the review log; **the raw material for the memory model and calibration**.
- `col` / `graves` — collection config, deletions for sync.

### 8b. New tables (our additions; live in the same collection DB so they sync)

```text
domains
  id              INTEGER PK            -- 1..7 (the seven Performance Expectations)
  name            TEXT                  -- e.g. "Subsidiary and Privileged Motions"
  exam_weight     REAL                  -- share of the exam blueprint (sums to 1.0)

card_topic                              -- maps Anki cards/notes to a domain (+ optional PE)
  note_id         INTEGER FK -> notes
  domain_id       INTEGER FK -> domains
  pe_code         TEXT NULL             -- finer Performance-Expectation tag

performance_items                       -- exam-style MCQ + Section II scenario prompts
  id              INTEGER PK
  domain_id       INTEGER FK -> domains
  kind            TEXT                  -- 'mcq' | 'scenario' | 'professional_responsibility'
  prompt          TEXT
  gold_answer     TEXT                  -- correct answer / model rubric
  ronr_citation   TEXT                  -- e.g. "RONR (12th ed.) 12:70-71" (source-of-truth)
  paraphrase_group INTEGER NULL         -- items sharing the same idea (for the paraphrase test)
  split           TEXT                  -- 'train' | 'heldout' | 'gold'  (leakage control)

attempts                                -- every graded answer the student gives
  id              INTEGER PK
  item_id         INTEGER FK -> performance_items NULL   -- null if a plain card review
  card_id         INTEGER FK -> cards NULL
  response        TEXT
  correct         INTEGER               -- 0/1 for MCQ
  ai_score        REAL NULL             -- 0..5 examiner score for scenarios
  ai_feedback     TEXT NULL
  latency_ms      INTEGER               -- timing -> pacing signal
  ts              INTEGER               -- epoch ms

coverage                                -- derived per domain (cached for the dashboard)
  domain_id       INTEGER FK -> domains
  cards_present   INTEGER
  pct_covered     REAL                  -- vs. blueprint; drives the abstain rule

readiness_snapshots                     -- audit trail of every readiness computation
  id              INTEGER PK
  section         TEXT                  -- 'I' | 'II'
  p_pass          REAL NULL             -- P(>=80%); NULL when abstaining
  range_low       REAL NULL
  range_high      REAL NULL
  confidence      TEXT                  -- 'abstain' | 'low' | 'medium' | 'high'
  pct_covered     REAL
  evidence        TEXT                  -- top reasons / best-next-topic
  abstained       INTEGER               -- 1 if give-up rule triggered
  ts              INTEGER

ai_outputs                              -- traceability for every AI generation/grade
  id              INTEGER PK
  attempt_id      INTEGER FK -> attempts NULL
  source_citation TEXT                  -- named RONR / Joint-Code source (required)
  model           TEXT
  passed_eval     INTEGER               -- did it clear the gold-set cutoff?
  ts              INTEGER
```

**Notes on the design**
- `performance_items.split` + `paraphrase_group` directly enable the **paraphrase test** and the **leakage check** without extra plumbing.
- `readiness_snapshots` stores the *whole* honest payload (point, range, confidence, coverage, evidence, abstain flag) so the UI can always show "what produced this number," and so we can later measure how accurate past predictions were.
- `attempts.latency_ms` is what lets the performance/readiness models account for the **time-pressure** skill the RPCE specifically tests.

---

## 9. Success Metrics

- **Engine:** Rust change works end-to-end on desktop *and* phone; all tests green; undo + crash tests show **zero corrupted collections**.
- **Sync:** 10 phone + 10 desktop offline reviews reconcile to 20, none lost/doubled; same-card conflict resolves to a documented, correct winner.
- **Memory model:** calibration chart + Brier/log-loss on held-out reviews.
- **Performance model:** accuracy on held-out exam-style items; reported **paraphrase gap** (proves it's not just copying memory).
- **AI:** gold-set accuracy + wrong-answer rate above a pre-set cutoff; beats keyword/vector baseline; leakage scan clean.
- **Study feature:** fair 3-way comparison (on/ablation/plain Anki) at equal study time, with a pre-stated metric and honest reporting of null results.
- **Performance targets (from spec §10):** button-press ack p95 < 50 ms; next card p95 < 100 ms; dashboard first load p95 < 1 s.

---

## 10. Key Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Anki won't build / mobile build slips (spec's #1 day-one risk) | Get fork building + tiny Rust change + phone build working **before** any feature work. |
| AI invents parliamentary facts (NAPMobile failure mode) | AI is examiner-only, every output cites RONR; gold-set checker blocks failing cards. |
| Readiness looks confident but is a guess | Hard give-up rule + full evidence payload; pass-probability with range, never a scaled number. |
| Test data leaks into training | Automated leakage scanner; `split` column enforced; that score zeroes if violated. |
| Performance model just mirrors memory | Paraphrase test reports the gap explicitly. |
| Copyrighted source material | PDFs + generated MD/images excluded from version control; regenerated locally. |

---

*Sources: project `spec.txt`; `rpce_brainlift.md` (SPOVs + Insights 1–10); `data/RPCE-Sample-Questions-v4-100625.md` (seven domains, Section II + professional-responsibility samples); `data/README.md` (corpus pipeline). Built on Anki by Ankitects — AGPL-3.0-or-later.*
