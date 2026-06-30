# Deploying & Testing Speedrun (Desktop + Phone)

This guide explains how to build, run, and package **Speedrun for the RPCE** on
**desktop** and on a **phone**, plus how to set up sync and the optional AI
layer so you can test the full flow. It complements the PRD (see
[`PRD.md`](./PRD.md) §14 Deployment) and the spec ([`spec.txt`](./spec.txt) §6).

> **Status legend** — each step is tagged so you know what is runnable today:
> **[works now]** uses the upstream Anki toolchain in this repo and runs today ·
> **[RPCE]** depends on the RPCE features/deck being wired up · **[plan]** is the
> intended path per the spec/PRD and may not be fully wired yet.
>
> If a **[RPCE]**/**[plan]** step doesn't behave as written, that's a gap to fix —
> please flag it and we'll resolve it.

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

**[RPCE]** The AI grounding and the gold set read the transcribed corpus in
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

### 2a. Run in development **[works now]**

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

### 2b. Load the RPCE deck **[RPCE]**

1. Launch the desktop app (§2a).
2. Import the RPCE deck (`File ▸ Import`) if it isn't bundled, or open the profile that already contains it.
3. The seven Performance-Expectation domains and card→domain tags load with the deck; the dashboard (three scores + coverage map) reads from there.

> Tip: use a throwaway profile for testing — start with `just run -- -p test` so you don't touch your real collection.

### 2c. Build a clean-machine installer **[works now]**

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

### 3a. Toolchain **[plan]**

- **Android Studio** (latest) with an SDK + an emulator image, **or** a physical device with USB debugging.
- Rust Android targets for the shared core:

```bash
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android
```

### 3b. Build & run **[plan]**

1. Build the shared Rust backend for Android (produces the native libs the app loads).
2. Open the AnkiDroid-based companion project in Android Studio.
3. Select an emulator or connected device and **Run**, or from the CLI build a debug APK with the project's Gradle wrapper (`./gradlew assembleDebug`).
4. Load the RPCE deck and run a review — it executes on the shared engine, and shows the three scores with ranges and the give-up rule (spec §6 Friday).

### 3c. Signed APK for sideload testing **[plan]**

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

## 4. Sync between desktop & phone

**[plan]** Speedrun uses a **self-hosted Anki sync server** so reviews flow both
ways.

1. Start a sync server (run locally for testing). Anki ships a built-in server; see **[`../syncserver/`](../syncserver)** / the Docker setup under `../docker/` for a containerized option.
2. In **both** apps, set the sync endpoint to your server's URL and log in with the same account.
3. Review cards on each device, then sync.

**Conflict rule (documented):** if the *same card* is reviewed offline on both
devices, the merge resolves by higher-`usn` / last-writer. Test it: review 10
cards offline on the phone and 10 different cards on desktop, reconnect, and
confirm all 20 land once with none lost or doubled (spec §7b).

---

## 5. Optional AI layer

**[plan]** The AI Examiner (Section II grading + debrief) is **optional**; both
apps must still score with it off.

- **Enable:** provide your LLM provider API key via the environment/local config the AI service reads (e.g. an `.env` entry or an exported `*_API_KEY`). Never commit the key.
- **Grounding:** retrieval runs over `data/roberts_rules_of_order_12th_edition.md`; every AI reply cites that text or abstains.
- **Disable (AI-off):** unset the key (or toggle AI off in settings). The app falls back to rubric self-scoring and still produces all three scores.

---

## 6. Verify your build (tests & benchmarks)

```bash
just check          # format + full build + lint + tests (run before shipping)
just test-rust      # Rust unit tests (incl. the Points-at-Stake Queue)
just test-py        # Python tests (incl. the Python-calling engine test)
just test-ts        # TypeScript/Svelte tests
just lint           # clippy + mypy + ruff + eslint + svelte + tsc
```

**[RPCE]** Performance targets (spec §10) are reported by a one-command
benchmark on the 50,000-card deck:

```bash
just bench          # prints p50 / p95 / worst-case per action
```

---

## 7. Quick test checklist

- [ ] `just run` launches the desktop app **[works now]**
- [ ] RPCE deck loads; dashboard shows three scores + coverage map **[RPCE]**
- [ ] `tools/build-installer` produces an installer that runs on a clean VM **[works now]**
- [ ] Phone build runs a review on the shared engine **[plan]**
- [ ] A card reviewed on the phone appears on desktop after sync **[plan]**
- [ ] Offline-then-sync works; same-card conflict resolves per the documented rule **[plan]**
- [ ] AI Examiner grades a Section II answer with a RONR citation; **AI-off still scores** **[plan]**
- [ ] `just check` is green **[works now]**

---

*If any step marked **[RPCE]** or **[plan]** does not work as written, it's a
known gap between the current build and the PRD/spec — please report it so we can
close it.*
