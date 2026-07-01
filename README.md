# Speedrun for the RPCE

> **Exam: the Registered Parliamentarian Credentialing Examination (RPCE).**
> Administered by the National Association of Parliamentarians over *Robert's
> Rules of Order Newly Revised, 12th ed.* (RONR). It has two sections —
> **Section I** (objective / multiple-choice recall) and **Section II**
> (written performance scenarios graded by examiners) — and is **pass/section:
> you must score ≥ 80% on *each* section**. There is no scaled score, so this
> app predicts **P(pass each section)** with a range, never an invented number.

A desktop + mobile study app **forked from [Anki](./ANKI_README.md)**. Both apps
share **one Rust engine** (no scheduler rewrite) and measure three separate,
honest things — **Memory**, **Performance**, and **Readiness** — each shown with
a range, a confidence, the coverage so far, the main reasons behind it, and a
give-up rule that abstains when there isn't enough data.

Built on Anki by Ankitects. Licensed **AGPL-3.0-or-later** (some upstream parts
BSD-3-Clause); see [`LICENSE`](./LICENSE). Upstream Anki README:
[`ANKI_README.md`](./ANKI_README.md).

- **Product spec:** [`docs/rpce/spec.txt`](./docs/rpce/spec.txt)
- **Design / status:** [`docs/rpce/PRD.md`](./docs/rpce/PRD.md)
- **Full build & deploy guide:** [`docs/rpce/DEPLOYMENT.md`](./docs/rpce/DEPLOYMENT.md)
- **1000 practice questions (RONR-cited):** [`docs/rpce/rpce_practice_questions.md`](./docs/rpce/rpce_practice_questions.md)

---

## Prerequisites

Clone into a path **without spaces** (keep it short on Windows). You need
**Rustup**, **Ninja/N2** (`tools/install-n2`), **just** (`uv tool install just`),
and **Python 3.9+**. Platform setup: [Windows](./docs/windows.md) ·
[Mac](./docs/mac.md) · [Linux](./docs/linux.md). Full reference:
[`docs/development.md`](./docs/development.md).

---

## Testing on desktop

From the repo root:

```bash
just run          # or: .\run.bat  (Windows) · ./run  (macOS/Linux)
```

The first build compiles dependencies and may take a while, then the app opens.
On first launch it **auto-builds the RPCE deck** (all seven domains) — no setup
needed. Then:

1. **Study** — review flashcards. Each concept is one FSRS-scheduled card whose
   format rotates (cloze ⇄ interactive multiple-choice) each time it returns;
   after any format you rate with Anki's four buttons (Again/Hard/Good/Easy).
   Every answer shows a **RONR (12th ed.) citation + verbatim quote**.
2. **Section II** — type a ruling for a scenario and get graded, examiner-style
   feedback with the model ruling (offline placeholder grader — no AI key needed).
3. **Simulate** — run a scripted meeting as the parliamentarian; each response
   is graded with a debrief.
4. **Dashboard** — the home screen shows the three scores (each with a range +
   the reasons), the coverage map, the best next topic, and the learning phase.
   It **abstains** until there are enough graded reviews, ≥ 50% coverage, and
   (for Section II) graded scenarios.

> Tip: use a throwaway profile so you don't touch a real collection:
> `.\run.bat -- -p test` (or `just run -- -p test`).

Run the tests:

```bash
just test-rust                                   # incl. the Points-at-Stake queue
$env:PYTHONPATH="out\pylib"; $env:ANKI_TEST_MODE="1"   # (PowerShell)
out\pyenv\Scripts\python -m pytest pylib\tests\test_rpce*.py -q
```

---

## Testing on phone (Android emulator or device)

Assumes you already have **Android Studio + SDK/NDK** and an **emulator or a
connected phone** (`adb devices` lists it). The phone runs the **same Anki Rust
engine on-device** via a JNI bridge; the UI mirrors the desktop.

1. **Build the native engine into the app** (from the repo root):

   ```bash
   cargo ndk -t arm64-v8a -o mobile/app/app/src/main/jniLibs build -p speedrun_jni --release
   ```

   (Use the emulator/device's ABI: `arm64-v8a` for most phones and Apple-silicon
   emulators; `x86_64` for an Intel emulator image.)

2. **Bundle the deck + content assets** (once, or after content changes):

   ```bash
   set PYTHONPATH=out/pylib   # PowerShell: $env:PYTHONPATH="out\pylib"
   python pylib/tools/rpce_export_starter.py mobile/app/app/src/main/assets/rpce_starter.apkg
   python pylib/tools/rpce_export_assets.py   mobile/app/app/src/main/assets
   ```

3. **Install and run:**

   ```bash
   cd mobile/app
   ./gradlew assembleDebug
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```

   Or open `mobile/app/` in Android Studio, pick the emulator/device, and **Run**.

4. On first launch the app **imports the bundled RPCE deck** and starts a real
   review session on the shared engine. Try **Study flashcards**, **Section II
   practice**, **Meeting simulation**, and **Readiness** (three scores + ranges +
   reasons + the learning-phase nudge). It all works **offline** — no AI key.

**Sync between desktop and phone.** In the phone's **Sync** screen, sign in with
your **AnkiWeb** email + password and sync; sync the desktop the usual way.
Reviews flow both ways (see [`DEPLOYMENT.md`](./docs/rpce/DEPLOYMENT.md) §4 for a
self-hosted server and the conflict rule).

---

## Note on AI

The Section II / Simulation grader is currently an **offline placeholder**
(keyword overlap against the model ruling) — **no AI API calls** — while always
showing the model ruling with its RONR citation + verbatim quote. The grader
interface is ready for an LLM-backed examiner to drop in without UI changes.
