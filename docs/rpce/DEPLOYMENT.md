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

The desktop app adds an **RPCE menu** (left of Help) with two actions:

1. **RPCE ▸ Build starter deck** — seeds a deck with cards tagged to all seven
   Performance-Expectation domains (`rpce::domain::N`). Placeholder content so you
   have something to review; replace with RONR-grounded cards over time.
2. **RPCE ▸ Readiness dashboard…** — shows the three scores (memory, performance,
   readiness per section) each with a range, the coverage map across the seven
   domains, the best next topic, and the **abstain** state with what data is
   still missing (until the give-up thresholds are met).

Try it: *Build starter deck*, study a few cards, then open the dashboard — it
stays in **abstain** until there are enough graded reviews, ≥50% coverage, and
(for Section II) graded scenarios.

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

The phone companion is built on **AnkiDroid**, reusing the **same Rust core** via
the protobuf/FFI boundary (no scheduler rewrite — spec §3). iOS (Rust C-FFI +
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

### 3c. JNI bridge + app scaffold

A `speedrun_jni` crate (`mobile/jni`) links the shared engine and exposes JNI
entry points; a minimal Android Studio app (`mobile/app`) loads it. Build the
native lib straight into the app and verify:

```bash
cargo ndk -t arm64-v8a -o mobile/app/app/src/main/jniLibs build -p speedrun_jni --release
```

See **[`../../mobile/README.md`](../../mobile/README.md)** for the full phone
build/run guide.

### 3d. Full review/sync UI _(planned)_

The remaining phone work is the review/sync surface over this engine (reuse
AnkiDroid's review screens), then:

1. Open `mobile/app/` in Android Studio and sync Gradle.
2. Select an emulator or connected device and **Run**, or build a debug APK (`./gradlew assembleDebug`).
3. Load the RPCE deck and run a review on the shared engine; show the three scores with ranges and the give-up rule (spec §6 Friday).

### 3e. Signed APK for sideload testing _(planned)_

```bash
./gradlew assembleRelease     # then sign with your keystore (apksigner)
```

Install on a clean device:

```bash
adb install -r app-release.apk
```

This signed APK is the deliverable you sideload to test on a real device.

> **AI-off / offline:** with no network or no AI key, the phone degrades AI
> cleanly to off and still runs reviews and shows a score (spec §7g).

---

## 4. Sync between desktop & phone _(planned)_

Speedrun uses a **self-hosted Anki sync server** so reviews flow both
ways.

1. Start a sync server (run locally for testing). Anki ships a built-in server; see **[`../syncserver/`](../syncserver)** / the Docker setup under `../docker/` for a containerized option.
2. In **both** apps, set the sync endpoint to your server's URL and log in with the same account.
3. Review cards on each device, then sync.

**Conflict rule (documented):** if the _same card_ is reviewed offline on both
devices, the merge resolves by higher-`usn` / last-writer. Test it: review 10
cards offline on the phone and 10 different cards on desktop, reconnect, and
confirm all 20 land once with none lost or doubled (spec §7b).

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
- **Grounding:** retrieval runs over `data/roberts_rules_of_order_12th_edition.md`
  (regenerate per §1); every reply cites that text or abstains. Candidates are
  **not** required to cite — grading is on accuracy.

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

These cover the queue, content model, three scores + abstain rule, Transfer
Ladder, AI examiner/baseline/eval/leakage, calibration metrics, and the
study-feature experiment (40 tests total with the Rust ones).

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
- [ ] **RPCE ▸ Build starter deck** seeds all seven domains
- [ ] **RPCE ▸ Readiness dashboard…** shows three scores + coverage map and **abstains** until thresholds are met
- [ ] `cargo ndk -t arm64-v8a build -p anki --lib --features rustls` cross-compiles the engine for Android
- [ ] `just bench` reports p50/p95/worst under spec targets
- [ ] RPCE Rust + Python tests pass
- [ ] `tools/build-installer` produces an installer that runs on a clean VM
- [ ] AI-off baseline examiner grades + cites/abstains offline
- [ ] _(planned)_ Phone app shell runs a review on the shared engine
- [ ] _(planned)_ A card reviewed on the phone appears on desktop after sync
- [ ] _(planned)_ Offline-then-sync works; same-card conflict resolves per the documented rule
- [ ] _(planned)_ LLM-backed examiner grades with an API key (AI-off still scores)
