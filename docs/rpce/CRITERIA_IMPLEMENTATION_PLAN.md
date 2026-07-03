# RPCE Criteria Implementation Plan

Turns the transcribed criteria (`data/2026-4-22-Criteria-for-Credentialing-UPDATED-v1.md`) into concepts, questions, simulations, scenarios, and the three scores in `SCORING.md`. Everything ships on **both desktop (`qt/aqt/rpce.py`, `pylib/anki/rpce/*`) and mobile (`mobile/jni`, `mobile/app/.../app.html`, generated assets)**.

## Phase 0 — Concept registry (foundation for everything)

- New `pylib/anki/rpce/concepts.py`: a `Concept(id, name, domain, section_weight, ronr_refs, sections=("I","II"))` list built from the RP performance expectations — the ~44 named sub-topics in the criteria (Motions in General, Main Motion, Amend, Commit/Refer, Postpone Definitely, Limit/Extend Debate, Previous Question, Recess, Adjourn, Point of Order, Appeal, Suspend the Rules, Parliamentary Inquiry, Request for Information, Rescind/ASPA, Reconsider, Quorum, Order of Business, Orders of the Day, Agenda, Minutes, Recognition/Floor, Handling Motions, Debate, Meeting & Session, Motions Not in Order, Renewal, Previous Notice, Serve as Parliamentarian, Teaching, Ethics/Code, Consulting, Discipline, Answering Questions, Terminology, Bylaw Amendments, Special Rules of Order, Interpreting Bylaws, Reviewing Governing Docs, Higher Authorities, Boards, Committees, Rules in Boards/Committees, Tellers, Nominations, Elections, Voting).
- Each concept keeps a stable `id` (used as the `rpce::concept::<id>` tag), the RONR paragraphs the PE says to test, and the exam section(s) it feeds.
- Mirror the list into the Rust engine (`mobile/jni/src/lib.rs`) so coverage/scoring match.
- **Verify:** a test asserts every concept has ≥1 RONR ref and a valid domain, and that the desktop and Rust lists are identical.

## Phase 1 — Requirement (1): concepts as review-session types

- Tag every generated Review card with its concept (`rpce::concept::<id>`) and domain. Regenerate the starter deck so every card is labelled; import in place (with_scheduling=false) so progress is preserved.
- Review-session selection stays randomized; add optional "focus a concept" later.

## Phase 2 — Requirement (2): ≥5 questions per concept

- For each concept, author **≥5** questions (more where the PE lists many rules), **varying type**: cloze, multiple-choice, select-all, ordering. Target ≈ 44 × 5 = **220+** minimum; generate more for dense concepts (Amend, Previous Question, Voting, Bylaws).
- Every question cites the exact RONR (12th ed.) paragraph from the concept's `ronr_refs`, and tests what that PE says to test. Author (via subagents grounded in `data/roberts_rules_of_order_12th_edition.md`), then quality-gate: solvable cold, verbatim-verified citation, no spelling/"which section" tells.
- **Verify:** a test asserts every concept has ≥5 cards and every card's citation is verbatim in the corpus.

## Phase 3 — Requirement (4): rewrite Section II (≥500 scenarios)

- Scrap the current authored scenarios; author **≥500** performance-exam scenarios in the sample format (named person/org → "explain the recommended procedure" → multi-paragraph **model answer** → RONR citation note). Cover the full set of RP performance expectations, weighted toward Section-II-appropriate PEs.
- Add **Professional-Responsibility-style** scenarios (multi-question, cite Code sections) for the Ethics/Consulting/Discipline concepts, matching the second sample.
- Each scenario carries: concept id, RONR (or Code) citation + verbatim quote, model answer, and offline keyword groups. Candidate is **never required to cite**.
- **Offline grading:** keyword match with matched/missing key terms shown (word-boundary, multi-concept groups; a bare keyword list must score full marks — the existing `grade_sim_step`/`keyword_report` machinery, extended per concept).
- **AI grading (online):** an on/off toggle on the Section II page (only when a key is set). When on, feed the model the candidate answer + the **model answer's keywords + the RONR (12th ed.) citation**. Offline keyword grader is the always-available fallback.
- **AI feedback (requirement):** the AI must **directly address the candidate's own answer** — say specifically what they got wrong or left out, quoting/referring to their wording — **and then show the model answer**. Score on requirements, not prose.
- **Verify:** ≥500 scenarios, all concepts represented, all citations verbatim; jsdom/py tests for matched/missing and the AI-feedback shape (addresses-answer + model-answer present).

## Phase 4 — Requirement (3): simulations cover every concept

- Keep adding meeting simulations until **every concept appears in ≥1 simulation**. Each simulation has **≤10** decision turns (fewer is fine). Randomized on entry (already done).
- Each decision's **model answer cites RONR (12th ed.)**; the candidate is not required to cite. Step grading uses the concept's keyword groups.
- **Verify:** a test asserts the union of concepts across all sims == the concept set, and no sim exceeds 10 decision turns.

## Phase 5 — Requirement (5): label everything + the three scores

- **Labelling:** Review cards, Section II scenarios, and Simulate turns all carry a concept (Phases 1/3/4). The session-complete page and dashboard group by concept.
- **Concept coverage (not domain):** replace the dashboard's "Domain coverage" with **"Concept coverage"** = fraction of concepts with ≥5 graded items (per `SCORING.md`); update desktop + mobile.
- **Three scores** exactly as `SCORING.md` specifies: **Memory**, **Performance**, and **Readiness for Section I and Section II separately** — each with point, range, concept-coverage %, confidence, last-updated, reasons, and the give-up rule. Rip out the old two-section readiness wording and implement the Section-I/Section-II split with the logistic-on-Performance model.
- Use the criteria to inform weights (Section I = 100 MCQ across the blueprint; Section II = performance scenarios) and the 80%-per-section pass bar.
- **Verify:** on a seeded collection, all scores render with concept coverage; below the give-up line they abstain with a concrete "data needed" list.

## Give-up rule (implemented from `SCORING.md`)

No Memory/Performance/Section-I score until ≥200 graded reviews AND ≥50% Section-I concept coverage; no Section-II score until ≥100 graded scenarios AND ≥50% Section-II concept coverage; per-concept hidden until ≥5 items. One `GiveUpRule` source, mirrored in Rust.

## Cross-cutting

- **Both platforms** every phase: desktop Python + Qt, and mobile Rust engine + `app.html` + regenerated `scenarios.json` / `simulations.json` / `rpce_render.js`.
- Deck content changes bump `RPCE_DECK_VERSION` and re-import in place (preserve scheduling).
- Sequence: Phase 0 → 1 → (2, 3, 4 in parallel via subagents) → 5. Each phase committed, tested, and deployed to desktop + emulator before the next.
