# Deploying & Testing Speedrun (Desktop + Phone)

This guide explains how to build, run, and package **Speedrun for the RPCE** on
**desktop** and on a **phone**, plus how to set up sync and the optional AI
layer so you can test the full flow. It complements the PRD (see
[`PRD.md`](./PRD.md) §14 Deployment) and the spec ([`spec.txt`](./spec.txt) §6).
Sections marked _(planned)_ are not built yet.

---

## 0. Prerequisites (all platforms)

Clone into a path **without spaces** (and keep it short on Windows). You need:

- **Rustup** — <https://rustup.rs/>. The version pinned in `rust-toolchain.toml` is fetched automatically.
- **N2 or Ninja** — install N2 with `tools/install-n2` (on Windows: `C:\msys64\usr\bin\bash.exe tools/install-n2`).
- **just** (recommended command runner) — `uv tool install just` or `brew install just`.
- **Python 3.9+** — for the corpus pipeline and to run wheels.

Platform-specific setup: **[Windows](../windows.md)** (Rust + MSVC build tools + MSYS2 `git`/`rsync`), **[Mac](../mac.md)**, **[Linux](../linux.md)**.

See **[`../development.md`](../development.md)** for the full upstream build reference.

---

## 1. Prepare the RPCE corpus & deck

The AI grounding and the gold set read the transcribed corpus in
`data/` (kept out of version control — regenerate locally):

```bash
cd data
pip install pymupdf
# Robert's Rules of Order, 12th ed. -> roberts_rules_of_order_12th_edition.md
python convert_ronr.py "_12THE~1.PDF" "roberts_rules_of_order_12th_edition.md"
# RPCE sample questions -> RPCE-Sample-Questions-v4-100625.md (gold set source)
python convert_rpce.py
```

This produces `data/roberts_rules_of_order_12th_edition.md` (RONR retrieval
source) and `data/RPCE-Sample-Questions-v4-100625.md` (gold-set source), plus
rendered images under `data/images/`. The source PDFs are copyrighted and stay
local (see `data/README.md`).

Then generate the RONR-grounded content (all deterministic and reproducible):

```bash
# ~6,000+ RONR-cited practice questions (2-5 from every substantive paragraph)
# -> docs/rpce/rpce_practice_questions.md
python pylib/tools/rpce_generate_questions.py
# Bundle the phone's Section II + Simulation JSON (mirrors the Python data)
PYTHONPATH=out/pylib python pylib/tools/rpce_export_assets.py mobile/app/app/src/main/assets
# Bundle the phone's starter deck (RPCE Concept notetype, FSRS on, citations)
PYTHONPATH=out/pylib python pylib/tools/rpce_export_starter.py mobile/app/app/src/main/assets/rpce_starter.apkg
```

Every generated answer carries an exact `RONR (12th ed.) X:Y` citation and a
**verbatim quote** from that section (checked against the corpus by
`test_rpce_refs`); nothing is fabricated (spec §7).

---

## 2. Desktop

### 2a. Run in development

From the repo root:

```bash
just run
```

(or directly: `.\run.bat` on Windows, `./run` on macOS/Linux).

The first build downloads and compiles dependencies and may take a while, then
Anki launches. Web views are served at `http://localhost:40000/_anki/pages/`.

For an optimized build:

```bash
just run-optimized
```

For live web-UI iteration (macOS/Linux), run `just web-watch` in a second
terminal.

### 2b. Use the RPCE features in the app

Everything is on the **top toolbar tabs** — there is no separate RPCE menu.
The RPCE deck is **built automatically** the first time you open the app (seeded
with cards tagged to all seven Performance-Expectation domains, `rpce::domain::N`).

- **Study** — review the concept flashcards. Each concept is one FSRS-scheduled
  card whose format rotates (cloze ↔ interactive MCQ) each repetition; every
  answer shows a RONR (12th ed.) citation + verbatim quote.
- **Section II** — free-text performance scenarios graded with examiner-style
  feedback (offline placeholder examiner).
- **Simulate** — a scripted meeting you run as the parliamentarian; each response
  is graded with a debrief.
- **Dashboard** — the home banner itself: the three scores (memory, performance,
  readiness per section) each with a range **and the main reasons behind it**,
  the coverage map across the seven domains, the best next topic, and the
  **abstain** state with what data is still missing (until the give-up
  thresholds are met).

Try it: study a few cards, then look at the home banner — it stays in
**abstain** until there are enough graded reviews, ≥50% coverage, and (for
Section II) graded scenarios.

> Tip: use a throwaway profile for testing — start with `.\run.bat -- -p test`
> (or `just run -- -p test`) so you don't touch your real collection.

### 2c. Build a clean-machine installer

```bash
tools/build-installer        # .\tools\build-installer on Windows
```

Output lands in `out/installer/dist`:

- **Windows:** an **MSI** installer.
- **macOS:** a **.dmg**.
- **Linux:** a tarball.

Install it on a clean VM to verify it runs without dev tools — this is the
spec's "runs on a clean machine" proof.

---

## 3. Phone (Android first)

The phone companion **runs Anki's own Rust backend on the device** (spec §3's
"run Anki's Rust backend on the device" option — no scheduler rewrite). A
`speedrun_jni` crate links the shared engine and a Kotlin `MainActivity` drives
it from a themed WebView (`assets/app.html`) via a JSON bridge. The same engine
that powers the desktop schedules reviews on the phone. iOS (Rust C-FFI +
TestFlight) is future and out of MVP scope.

### 3a. Toolchain

Already installed and verified on this machine:

- **Android Studio** + SDK at `%LOCALAPPDATA%\Android\Sdk` with **NDK 26.1.10909125**, platform-tools, build-tools 34.0.0, platform android-34, cmake, and an emulator. `ANDROID_HOME` / `ANDROID_SDK_ROOT` / `ANDROID_NDK_HOME` are set as user env vars.
- Rust Android targets + `cargo-ndk`:

```bash
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android
cargo install cargo-ndk
```

### 3b. Cross-compile the shared engine

The shared Anki Rust engine (including the RPCE points-at-stake queue) builds
for Android — verified:

```bash
cargo ndk -t arm64-v8a build -p anki --lib --features rustls   # exit 0
```

> Use the `rustls` feature on Android (not `native-tls`/OpenSSL). The output lands
> in `target/aarch64-linux-android/`.

### 3c. JNI bridge + native lib

The `speedrun_jni` crate (`mobile/jni`) links the shared engine and exposes JSON
entry points (open collection, next/answer card, deck counts, the three scores,
record scenario, and sync). Build the native lib straight into the app:

```bash
cargo ndk -t arm64-v8a -o mobile/app/app/src/main/jniLibs build -p speedrun_jni --release
```

See **[`../../mobile/README.md`](../../mobile/README.md)** for the full phone
build/run guide.

### 3d. Build & run the app

The companion UI is implemented (`mobile/app`, `assets/app.html`) and mirrors the
desktop's Blue-on-White theme and logo. It has the **review loop**, the **three
scores** (each with a range + the main reasons + the give-up rule), **Section II**
scenario practice, and **Simulation** mode — all on the shared engine, verified on
an emulator.

1. Ensure the assets are bundled (§1): `rpce_starter.apkg`, `scenarios.json`,
   `simulations.json`, plus the native lib from §3c.
2. Open `mobile/app/` in Android Studio and sync Gradle (or use `./gradlew`).
3. Start a device: pick one in Android Studio's **Device Manager** and hit ▶, or
   launch the bundled `rpce` AVD from the CLI (see **Emulator from the CLI** below).
4. Select an emulator or connected device and **Run**, or build a debug APK:
   `./gradlew assembleDebug` → `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

> **`./gradlew` needs JDK 21 (AGP 8.5.2).** The system JDK is too new. Point
> `JAVA_HOME` at Android Studio's bundled JBR before building from the CLI:
> `JAVA_HOME="C:\Program Files\Android\Android Studio\jbr" ./gradlew :app:assembleDebug --no-daemon`.

#### Emulator from the CLI

The SDK tools live under `%LOCALAPPDATA%\Android\Sdk` (already on `ANDROID_HOME`):
`emulator\emulator.exe` starts virtual devices, `platform-tools\adb.exe` talks to
running ones. This box ships one AVD, `rpce`.

```powershell
$sdk = "$env:LOCALAPPDATA\Android\Sdk"
& "$sdk\emulator\emulator.exe" -list-avds          # -> rpce
& "$sdk\emulator\emulator.exe" -avd rpce           # launch (own terminal, or Start-Process to background)

$adb = "$sdk\platform-tools\adb.exe"
& $adb wait-for-device                             # window appears before Android is ready
& $adb shell getprop sys.boot_completed            # prints 1 once fully booted
& $adb devices                                      # emulator-5554  device  = ready

& $adb install -r mobile\app\app\build\outputs\apk\debug\app-debug.apk
& $adb -s emulator-5554 emu kill                    # shut it down
```

On first launch the app imports the bundled RPCE deck and starts a real review
session; open **Readiness** for the three scores.

### 3e. Signed APK for sideload testing

```bash
./gradlew assembleRelease     # then sign with your keystore (apksigner)
adb install -r app-release.apk
```

This signed APK is the deliverable you sideload to test on a real device.

> **AI-off / offline:** the Section II / Simulation grader is an **offline
> placeholder** (keyword overlap) — no network or AI key is needed; the phone
> runs reviews and shows a score fully offline (spec §7g).

---

## 4. Sync between desktop & phone

Reviews flow both ways over Anki's sync protocol. Two options:

- **AnkiWeb account (default):** in the phone's **Sync** screen, enter your
  AnkiWeb email + password and tap **Sign in & sync**; sync the desktop the usual
  way. Leave the endpoint blank to use AnkiWeb.
- **Self-hosted server:** run Anki's built-in sync server (see
  **[`../syncserver/`](../syncserver)** or the Docker setup under `../docker/`),
  then point both apps at its URL.

A reproducible round-trip test is scripted in
`pylib/tools/rpce_sync_test.py` (device A + device B against a local server). Run
it end-to-end with one command — **`just rpce-sync-test`** — which spins up a
temporary local sync server, drives the exact backend calls both apps use, and
prints `SYNC OK` on success (upload/download, a two-way merge with none
lost/doubled, and a same-card conflict resolved by the rule below).

**Conflict rule (documented):** if the _same card_ is reviewed offline on both
devices, the merge resolves by Anki's higher-`usn` / last-writer rule. Verified:
review 10 cards offline on one side and 10 different cards on the other,
reconnect, and all 20 land once with none lost or doubled (spec §7b).

**Full-sync direction (cross-device install):** because each app seeds its own
deck, the *first* sync between a device and an account is a forced full sync
(schemas differ) that can't merge. The direction is chosen so a device joining an
account **adopts** it instead of overwriting it:

- empty account → the device **uploads** (seeds it);
- an account that already holds another device's data → a device that has not yet
  synced it **downloads** (adopts it), and only a device that already owns the
  account uploads on a conflict (so a content re-seed still propagates).

This is why installing the desktop (MSI) and signing into an account you already
use on another device pulls that data down rather than wiping it. Proven by
Phase 5 of `just rpce-sync-test`; the pure rule is unit-tested in
`qt/tests/test_rpce_sync.py`.

---

## 5. AI Examiner layer

The AI Examiner (Section II grading + debrief) is **optional**; both apps must
still score with it off.

- **AI-off baseline:** `anki.rpce.examiner.BaselineExaminer` grades
  answers offline by keyword overlap and grounds feedback in the RONR corpus via
  `retrieve(...)`, citing a passage or **abstaining** when none is found. This is
  both the AI-off fallback and the baseline an LLM must beat (spec §7f). The
  eval harness (`evaluate`) and leakage scanner (`find_leaks`) also run offline.
- **LLM grader _(planned)_:** an LLM-backed grader implements the same `Examiner`
  interface. Provide the provider API key via env/local config (never commit it);
  with no key, the app uses the baseline above.
- **In-app grader:** the desktop and phone Section II / Simulation screens use an
  **offline placeholder** grader (keyword overlap) — no API calls yet — while
  still showing the model ruling with its RONR citation + verbatim quote.
- **Grounding:** retrieval runs over `data/roberts_rules_of_order_12th_edition.md`
  (regenerate per §1); every reply cites that text or abstains. Candidates are
  **not** required to cite — grading is on accuracy.
- **Gold-set eval:** `just rpce-eval` scores the examiner against the official
  RPCE sample questions (accuracy + false-pass rate vs. a preset cutoff) and runs
  the leakage scan; a failing card is blocked (spec §7e/§7f).

---

## 6. Verify your build (tests & benchmarks)

```bash
just check          # format + full build + lint + tests (run before shipping)
just test-rust      # Rust unit tests (incl. the Points-at-Stake Queue)
just test-py        # Python tests (incl. the Python-calling engine test)
just test-ts        # TypeScript/Svelte tests
just lint           # clippy + mypy + ruff + eslint + svelte + tsc
```

The RPCE Rust + Python tests directly (no `just` needed):

```bash
cargo test -p anki points_at_stake          # 6 Rust unit tests for the queue
# Python (PowerShell): point at the built package and run the rpce tests
$env:PYTHONPATH="out\pylib"; $env:ANKI_TEST_MODE="1"
out\pyenv\Scripts\python -m pytest -p no:cacheprovider pylib\tests\test_points_at_stake.py pylib\tests\test_rpce*.py -q
```

These cover the queue, content model (one FSRS-scheduled card per concept),
the three scores + ranges + **per-score explanations** + abstain rule, the
readiness audit trail, Transfer-Ladder format rotation, RONR citation/verbatim
quotes in every mode, Simulation mode, the AI examiner/baseline/eval/leakage,
FSRS calibration metrics, and the study-feature experiment (70+ Python RPCE
tests plus the Rust queue tests).

Performance targets (spec §10) are reported by a one-command benchmark:

```bash
just bench                      # quick check (2,000-card deck)
just bench --cards 50000        # spec reference size
```

It prints p50 / p95 / worst-case for next-card, answer (button ack), and the
points-at-stake queue, flagging any result over its spec target.

---

## 7. Quick test checklist

- [ ] `just run` / `.\run.bat` launches the desktop app
- [ ] The RPCE deck is auto-built on first open (all seven domains seeded)
- [ ] Toolbar tabs work: **Study**, **Section II**, **Simulate**, **Dashboard**
- [ ] The home banner shows three scores + ranges + reasons + coverage map and **abstains** until thresholds are met
- [ ] `cargo ndk -t arm64-v8a build -p anki --lib --features rustls` cross-compiles the engine for Android
- [ ] `just bench` reports p50/p95/worst under spec targets
- [ ] RPCE Rust + Python tests pass
- [ ] Every answer (Study, Section II, Simulate) shows a RONR citation + verbatim quote
- [ ] `just rpce-eval` runs the gold-set eval + leakage scan
- [ ] `tools/build-installer` produces an installer that runs on a clean VM
- [ ] AI-off baseline examiner grades + cites/abstains offline
- [ ] Phone app runs a review + shows the three scores on the shared engine
- [ ] Phone Section II + Simulation grade responses offline
- [ ] A card reviewed on the phone appears on desktop after sync (and the reverse)
- [ ] Offline-then-sync works; same-card conflict resolves per the documented rule
- [ ] `just rpce-sync-test` prints `SYNC OK` (two-way merge + conflict, temp local server)
- [ ] _(planned)_ LLM-backed examiner grades with an API key (AI-off still scores)
