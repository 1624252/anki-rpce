# Development Plan — Speedrun for the RPCE

How we build the app defined in [`PRD.md`](./PRD.md), in the order the spec
([`spec.txt`](./spec.txt) §6) demands: **make the apps work → add AI → prove it.**
Each milestone lists its spec/PRD anchor, the work, and the proof artifact.

> **Reality check.** This is a multi-session build. The forked desktop app and
> the Android companion both build and run today on **one shared Rust engine**;
> the RPCE features were layered on incrementally. The phone is a thin
> Kotlin/WebView shell over that engine via a JNI bridge (not an AnkiDroid fork),
> so its largest external dependency is the Android SDK/NDK + `cargo-ndk`.
> Milestones are tagged **[done]**, **[partial]**, or **[todo]**.

---

## Guiding constraints (from spec §2, non-negotiable)

- A **real change inside Anki's Rust core** (not just Python screens).
- **Two apps, one shared engine**, with reviews syncing both ways.
- **Three separate scores** (memory, performance, readiness), each with a range.
- **Held-out, re-runnable** model testing.
- **One study feature**, tested by turning it off and on.
- **Every AI output** is source-traced, eval-checked, and beats a baseline.
- The app **abstains** when it lacks data.
- **Installable desktop + phone builds** that both run with **AI off**.
- License: **AGPL-3.0-or-later**, credit to Anki.

---

## Milestones

### M0 — Forked desktop app builds & runs · spec §6 (Wed), "Get Anki Building First"

- **Work:** verify the fork compiles from source on this machine; launch the desktop app; confirm a review loop on a deck.
- **Proof:** running app + commit hash. Build via `tools\ninja pylib qt` then `.\run.bat` (no `just` yet on this box).
- **Status:** **[done]** — builds and launches (Anki 26.05, mediasrv on `127.0.0.1:40000`).

### M1 — Rust engine change: Points-at-Stake Queue · spec §7a, PRD §7.5

- **Work:** new review order in `rslib` sorting due cards by `domain exam-weight × student weakness`; new protobuf message in `proto/`; expose via `_backend.py`; consume in the desktop queue.
- **Tests:** ≥3 Rust unit tests + 1 Python-calling test; undo works; no collection corruption.
- **Deliverables:** one-page "why Rust" note + list of touched upstream files (merge difficulty).
- **Proof:** the diff, green tests, a review session ordered by the new queue.
- **Status:** **[done]** — `get_points_at_stake_queue` RPC implemented in `rslib`; 6 Rust unit tests + 2 Python-calling tests pass; clippy clean; read-only so undo-safe. See [`RUST_CHANGE.md`](./RUST_CHANGE.md).

### M2 — RPCE content model · PRD §11b, spec §7c

- **Work:** add custom tables (`domains`, `card_topic`, `performance_items`, `attempts`, `coverage`, `readiness_snapshots`, `ai_outputs`) in the collection DB so they sync; seed the seven Performance-Expectation domains with exam weights; build/import the RPCE deck and tag each card to a domain.
- **Proof:** coverage map over all seven domains rendered on the dashboard.
- **Status:** **[done]** — implemented sync-safe via native **tags** (`rpce::domain::N`) + **collection config** weights instead of custom tables (Anki sync would not carry custom tables). `anki.rpce` module: 7 domains, `topic_weights`, `coverage`, `build_starter_deck`; 4 tests pass and feed the M1 queue.

### M3 — Memory score + Honest Readiness Panel (abstain) · spec §4, §9 Step 1, PRD §7.4, §8

- **Work:** calibrated memory score from FSRS/`revlog`; Svelte dashboard showing three score slots each with a range, evidence, coverage %, "how sure", last-updated; **abstain** below the give-up line.
- **Proof:** calibration chart + Brier/log-loss on held-out reviews; abstain state visible until thresholds met.
- **Status:** **[done]** — scoring + honesty logic in `anki.rpce.scores`; the **home banner is the dashboard** (`qt/aqt/rpce.py`), reached from the **Dashboard** toolbar tab (no dropdown menu). It shows the three scores each with a range **and the main reasons behind it**, coverage map, best-next-topic, and abstain state; the deck auto-builds on first open. FSRS-calibrated memory + Brier/log-loss are wired.

### M4 — Transfer Ladder (study feature) · SPOV 1, PRD §7.1

- **Work:** per-concept format rotation (cloze → applied MCQ → free-text scenario → advising) layered on FSRS due-ordering via `paraphrase_group`/`format_rung`.
- **Proof:** a concept resurfaces in a different format; data recorded for the M9 experiment.
- **Status:** **[done]** — ladder logic in `anki.rpce.transfer_ladder` (rung order, advance/hold/drop, recommended rung, no-repeat) **and** reviewer wiring: a `reviewer_did_answer_card` hook tallies each review by format rung (`rung_of_tags`/`record_review`). 8 tests pass.

### M5 — Phone companion (Android) · spec §3, §6 (Wed mobile)

- **Work:** AnkiDroid-based app reusing the shared Rust core (build native libs for Android targets); load the RPCE deck; run a real review on the shared engine.
- **Proof:** screen recording of a review session on a device/emulator.
- **Status:** **[done]** — the shared `anki` engine cross-compiles for Android (`arm64-v8a` + `x86_64`); the **`speedrun_jni`** crate exposes a 12-function JSON API over the same protobuf backend the desktop uses (open/import, `nextCard`/`answerCard`, `deckCounts`, `scores`, `recordScenario`, `syncLogin`/`syncCollection`/`fullSync`). `MainActivity` hosts the themed WebView (`assets/app.html`) with the review loop, the three scores + give-up rule, Section II + Simulation practice (offline placeholder grader), and the Reference tab — verified on the x86_64 emulator. Native `.so` libs are gitignored; `scripts/run-mobile.sh` builds them with `cargo-ndk` when missing. Remaining: a store-signed release build.

### M6 — Two-way sync + conflict rule · spec §3, §7b, §6 (Fri)

- **Work:** self-hosted Anki sync server; both apps sync; documented higher-`usn`/last-writer conflict rule.
- **Proof:** 10 phone + 10 desktop offline reviews reconcile to 20 (none lost/doubled); same-card conflict resolves correctly.
- **Status:** **[done]** — both apps drive Anki's own sync client over the shared engine (AnkiWeb by default; self-hosted for local/CI); RPCE state syncs natively as tags + config. Conflict rule: higher-`usn` / last-writer. Verified reproducibly by `pylib/tools/rpce_sync_test.py` — one command **`just rpce-sync-test`** spins up a temp local server and proves upload/download, a two-way merge (reviews reconcile, none lost/doubled), and a same-card-offline conflict resolving to one consistent last-writer state. Remaining (phone polish): abort/progress UI, media sync, self-hosted-endpoint field, credential persistence.

### M7 — AI Examiner + safety · spec §6 (Fri), §7e, §7f, PRD §7.3, §9

- **Work:** grade Section II free-text **for accuracy** (no candidate citations required) with retrieval over `data/roberts_rules_of_order_12th_edition.md`; every AI reply cites that text or abstains; AI-off fallback.
- **Tests:** gold set (≥50 from `data/RPCE-Sample-Questions-v4-100625.md`) with pre-set cutoff; beats keyword/vector baseline; leakage scanner clean.
- **Proof:** eval numbers + baseline side-by-side; app still scores with AI off.
- **Status:** **[done (AI-off)]** — `anki.rpce.examiner`: corpus retrieval + RONR citation; offline `BaselineExaminer`/`PlaceholderExaminer` (AI-off fallback + baseline, what the app grades with today); a scaffolded **`LLMExaminer` + `make_examiner()` factory gated behind an API key** (`RPCE_AI_KEY`/`OPENAI_API_KEY`) — the only missing piece is the key. `evaluate` (gold-set vs cutoff) + `find_leaks` (leakage). Section II + Simulation screens (desktop **and** phone) grade offline. Gold set wired from `data/` via `anki.rpce.gold` + **`just rpce-eval`** (36 Q / 7 domains, 100% accuracy, 12% false-pass < 20% cutoff, leakage-clean). No live AI calls in the app.

### M8 — Performance & readiness models · spec §4, §9 Steps 2–3, §7d, PRD §8

- **Work:** performance model P(correct on new item) from mastery/difficulty/timing/coverage; readiness = P(pass each section ≥80%) with range; paraphrase test.
- **Proof:** held-out accuracy + reported paraphrase gap; readiness range with confidence.
- **Status:** **[partial]** — `anki.rpce.metrics`: Brier, log-loss, reliability bins, ECE (calibration, §9 Step 1) + `paraphrase_gap` (§7d); 6 tests. Performance/readiness scoring already in M3. Remaining: feed real FSRS predictions + reworded-question results into the metrics on held-out data.

### M9 — Study-feature experiment · spec §8, PRD §9

- **Work:** three builds at equal study time — full (rotation on) / ablation (rotation off) / plain Anki; pre-state the metric.
- **Proof:** fair 3-way comparison with a range; null results reported honestly.
- **Status:** **[partial]** — `anki.rpce.experiment`: pre-registered metric, 3-way `compare` with 95% intervals, feature-effect (full−ablation) and vs-plain, and honest-null handling (`feature_helped=None` when the interval straddles 0); 5 tests. Remaining: run the three real builds and collect learner results.

### M10 — Packaging, benchmarks & robustness · spec §6 (Sun), §7g, §7h, §10, PRD §14

- **Work:** desktop installer (Briefcase/`tools\build-installer`) + signed Android APK; one-command `bench`; crash/offline tests.
- **Proof:** clean-device install recordings for both; p50/p95/worst-case numbers; zero corrupted collections in the crash test.
- **Status:** **[partial]** — one-command **`just bench`** done (`pylib/tools/rpce_bench.py`): p50/p95/worst for next-card, answer (button ack), and the points-at-stake queue, with spec targets flagged (all well under on a 2k deck). Desktop installer recipe exists (`tools/build-installer`). Remaining: signed APK, 50k-card run, crash/offline test runs.

---

## Sequencing & dependencies

```mermaid
flowchart LR
  M0[M0 build/run] --> M1[M1 Rust queue]
  M1 --> M2[M2 content model]
  M2 --> M3[M3 memory + readiness panel]
  M3 --> M4[M4 Transfer Ladder]
  M1 --> M5[M5 phone]
  M5 --> M6[M6 sync]
  M2 --> M7[M7 AI Examiner]
  M3 --> M8[M8 perf + readiness models]
  M4 --> M9[M9 study experiment]
  M8 --> M9
  M6 --> M10[M10 package + prove]
  M7 --> M10
  M9 --> M10
```

---

## Working agreement

- **Commit after each meaningful step** (conventional commits).
- **Run checks before marking a milestone done:** `tools\ninja check` (or `just check` once installed); language-specific `test-rust` / `test-py` / `test-ts`.
- **Keep docs current:** update [`DEPLOYMENT.md`](./DEPLOYMENT.md) and the PRD whenever behavior changes.
- **No copyrighted source / secrets / personal data** committed (PDFs and `data/` stay gitignored).
- **Flag spec gaps:** if something can't meet a spec requirement, note it rather than fake it.
