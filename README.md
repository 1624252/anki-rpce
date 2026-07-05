# Speedrun for the RPCE

A study app (forked from Anki) for one exam: the **Registered Parliamentarian
Credentialing Examination (RPCE)** — the National Association of
Parliamentarians' credential over *Robert's Rules of Order Newly Revised, 12th
ed.* Section I is multiple choice; Section II is written performance scenarios;
you must clear 80% on each.

## Install

Download the pre-built installer for your OS from the
[**latest release**](https://github.com/1624252/anki-rpce/releases/latest) — no
build step needed. It's fully self-contained (Python, Qt, and the engine are
bundled), so **nothing is downloaded during install** and no dev tools are
needed.

| Desktop | Release asset                 | To install                            |
|---------|-------------------------------|---------------------------------------|
| Windows | `anki-26.05-win-x64.msi`      | double-click it (installs per-user, no admin prompt) |
| macOS   | `.dmg`                        | open it, drag to Applications         |
| Linux   | `.zip`                        | unzip, run the launcher inside        |

Then start **Speedrun for the RPCE**; it builds the RPCE deck on first launch.

> Direct link (Windows): <https://github.com/1624252/anki-rpce/releases/latest/download/anki-26.05-win-x64.msi>
>
> The Windows `.msi` is published. The `.dmg`/`.zip` can't be produced on
> Windows (Briefcase packages for the host OS), so build those on a Mac / Linux
> box and attach them to the release — see below.

## Install on phone (Android)

Download the app from the
[latest release](https://github.com/1624252/anki-rpce/releases/latest):
`speedrun-rpce-26.05-android.apk`. On the phone, open it — Android will ask you
to **allow installing from this source** the first time (tap *Settings → allow*,
then back and *Install*). Open **Speedrun for the RPCE**; sign in with the same
AnkiWeb account as the desktop to sync the same deck.

> Direct link: <https://github.com/1624252/anki-rpce/releases/latest/download/speedrun-rpce-26.05-android.apk>
>
> iPhone isn't available — an iOS build needs a Mac and an Apple developer
> account, which this project doesn't set up.

## Uninstall

- **Windows** — Settings → Apps → Installed apps → **Anki** → Uninstall
  (or `msiexec /x anki-<ver>-win-x64.msi`).
- **macOS** — drag the app from Applications to the Trash.
- **Linux** — delete the unzipped folder.
- **Android** — long-press the app icon → Uninstall (or Settings → Apps).

## Build the installers from source

Only needed to *produce* the files above. The packager (Briefcase) targets the
machine it runs on, so **build each platform's installer on that platform** (or
a CI runner per OS). Everywhere you need [Rustup](https://rustup.rs), a C
toolchain, and a few GB of free disk; clone into a short path without spaces.

```bash
git clone https://github.com/1624252/anki-rpce.git speedrun && cd speedrun
```

| Desktop | Also need | Build command               | Output in `out/installer/dist/` |
|---------|-----------|-----------------------------|---------------------------------|
| Windows | MSVC build tools, MSYS2  | `tools\build-installer.bat` | an `.msi` (e.g. `anki-26.05-win-x64.msi`) |
| macOS   | Xcode command-line tools | `./tools/build-installer`   | a `.dmg` |
| Linux   | standard build packages  | `./tools/build-installer`   | a `.zip` |

### Run from source (dev)

- **Desktop:** `just run` (or `.\run.bat`) — builds `pylib` + `qt` and launches.
- **Phone:** `./scripts/run-mobile.sh` — builds the JNI engine + APK and installs
  it on a connected device/emulator (needs the Android SDK + an AVD). The phone
  app is a WebView over the **same Rust engine** (`mobile/`), not a rewrite.

## License

This is a fork of [Anki](https://github.com/ankitects/anki) by Ankitects Pty Ltd,
**with credit to Anki**, distributed under **AGPL-3.0-or-later** (some upstream
Anki components are BSD-3-Clause). Source: <https://github.com/1624252/anki-rpce>.

## Architecture

One shared **Rust engine** (`rslib`, incl. FSRS) drives both apps. The desktop is
Anki's Python/Qt app with an RPCE layer in `qt/aqt/rpce.py`; the phone is a
WebView companion (`mobile/`) over the same engine via JNI. RPCE content, the
three score models, and the offline examiner live in `pylib/anki/rpce/`; cards
and progress **sync both ways** through Anki's sync. See `docs/rpce/PRD.md` §10
for the diagram and `docs/rpce/MODELS.md` for the memory / performance /
readiness models and the give-up rule.

### The Rust engine change

A real change in the shared Rust engine: **concept grouping** — after a card is
answered, other cards of the same concept are buried so a concept isn't re-shown
across question types (spec §7a). Notes, rationale ("why Rust, not Python"), undo
safety, tests, and the list of upstream files touched are in
**`docs/rpce/RUST_CHANGE_CONCEPT.md`** (a second change, the points-at-stake
queue, is documented in `docs/rpce/RUST_CHANGE.md`). 7 Rust unit tests +
1 Python-calling test.

## Re-runnable proofs (spec §7)

Every claim has a one-command, deterministic re-run:

| What | Command |
|------|---------|
| Rust change unit tests | `cargo test -p anki concept_bury` |
| Python calls the Rust change + full engine tests | `just test-py` |
| Two-way sync + conflict rule (§7b) | `just rpce-sync-test` |
| Coverage map / abstain (§7c) | shown on the dashboard; `just test-py` covers `scores` |
| Memory→performance paraphrase gap (§7d) | `just rpce-paraphrase` |
| AI card gold-set check + leakage scan (§7e/§7f) | `just rpce-eval` |
| AI card check: gold set ≥50 + 3-bucket classifier (§7f) | `just rpce-card-check` |
| Memory calibration Brier/log-loss/ECE + chart (§9.1) | `just rpce-calibration` |
| Study-feature 3-build test, equal study time (§8) | `just rpce-experiment` |
| Crash / offline (§7g) | `just rpce-crash` |
| Speed benchmark p50/p95/worst (§7h) | `just bench` (add `--cards 50000`) |

All results, with numbers and honest limitations, are consolidated in
**`docs/rpce/RESULTS.md`**. Per-model write-ups are in `docs/rpce/MODELS.md`.
