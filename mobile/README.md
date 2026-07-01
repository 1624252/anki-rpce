# Speedrun RPCE — Android companion

The phone companion reuses the **same Rust engine** as the desktop app (spec §3:
two apps, one engine), loaded through a thin JNI bridge — not a reimplemented
scheduler.

## What it does

Feature parity with the desktop, all on the shared engine:

- **Review loop** — opens the shared collection and runs real reviews (get next
  card → show answer → Again/Hard/Good/Easy) via the engine's scheduler; the
  same multi-format Transfer-Ladder cards (cloze + applied MCQ) as the desktop.
- **Three scores + give-up rule** — memory / performance / readiness with ranges
  and the honest **abstain** state, computed on-device from the collection (a
  faithful port of `anki.rpce.scores`).
- **Section II practice** — scenario prompts with the offline placeholder
  examiner (keyword-overlap grading + model-ruling debrief); increments the
  graded-scenario counter that feeds the give-up rule.
- **Two-way sync** — logs in to and syncs with AnkiWeb (or a self-hosted server);
  reviews and RPCE state (tags + config) flow both ways (see below).

## Layout

- `jni/` — the `speedrun_jni` Rust crate (`cdylib`). Links the shared `anki`
  engine and drives it through the same protobuf backend the desktop uses
  (`run_service_method`), exposing a small JSON API to Kotlin: open/import,
  review (`nextCard`/`answerCard`), `scores`, `recordScenario`, and sync
  (`syncLogin`/`syncCollection`/`fullSync`). No scheduler is reimplemented.
- `app/` — the Android (Gradle/Kotlin) project. `MainActivity` hosts a WebView
  (the deep-blue `assets/app.html` UI) and bridges its JS calls into the engine;
  the RPCE deck is seeded on first run by importing the bundled
  `assets/rpce_starter.apkg` (regenerate with
  `python pylib/tools/rpce_export_starter.py <out.apkg>`).

## Build the native engine for Android

From the repo root (Android SDK/NDK + `cargo-ndk` required — see
`docs/rpce/DEPLOYMENT.md` §3):

```bash
# arm64-v8a for real devices + x86_64 for the emulator (both ABIs the app packages).
cargo ndk -t arm64-v8a -t x86_64 -o mobile/app/app/src/main/jniLibs build -p speedrun_jni --release
```

This compiles the shared engine and copies `libspeedrun_jni.so` into
`mobile/app/app/src/main/jniLibs/<abi>/`. (Verified: the engine + JNI bridge
cross-compile cleanly for `aarch64-linux-android`.)

## Build & run the app

1. Open `mobile/app/` in **Android Studio** and let it sync Gradle (the plugin
   versions in `build.gradle.kts` may need matching to your install).
2. Run on an emulator or a connected device. The app shows the RPCE home screen
   (the same deep-blue themed readiness banner as the desktop, rendered in a
   WebView from `assets/app.html`) and loads the shared engine — its
   version/build hash appears in the "Engine ready" chip, confirming the engine
   runs on device.
3. Build a debug/installable APK from `mobile/app/`: `./gradlew :app:assembleDebug`
   (or `assembleRelease` + sign with your keystore), then
   `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

## Two-way sync by AnkiWeb account (spec §7b)

Sync uses your **AnkiWeb account** — no server IP/endpoint to configure.

- **Phone:** open **Sync**, enter your AnkiWeb **email + password**, tap **Sign
  in & sync**. The first join needs a full up/down (choose once); after that a
  normal sync merges automatically.
- **Desktop:** click **Sync** and sign in with the same AnkiWeb account.
- **Conflict rule (documented):** same-card-offline edits resolve by
  higher-`usn` / last-writer — Anki's built-in rule, inherited unchanged.

Both apps drive Anki's own sync client, so reviews and RPCE state (tags +
config) cross devices through the shared engine.

**Verified (spec §7b), reproducibly.** One command spins up a temporary local
server and runs the full round-trip — upload/download, a two-way merge (reviews
on each device reconcile with none lost or double-counted), and a
same-card-offline **conflict** that resolves to one consistent last-writer state:

```bash
just rpce-sync-test
# -> SYNC OK: two-way sync + conflict resolution verified.
```

Or drive it against a server you started yourself:

```bash
PYTHONPATH=out/pylib python pylib/tools/rpce_sync_test.py
```

**Self-hosted (optional).** For an offline/CI demo you can still point at a
self-hosted server instead of AnkiWeb by leaving the endpoint blank in code
(AnkiWeb) or running one locally:

```bash
PYTHONPATH=out/pylib SYNC_USER1="rpce:rpcepass" SYNC_BASE=./out/syncsrv \
  SYNC_HOST=0.0.0.0 SYNC_PORT=8083 \
  python -c "import anki.syncserver as s; s.run_sync_server()"
```

## Status

- **Done / verified:** shared engine cross-compiles for Android; JNI bridge
  drives the real protobuf backend; review loop, three scores + give-up rule,
  Section II practice, and two-way sync all run on-device (verified on the
  x86_64 emulator). The native `.so` libs are gitignored (regenerate with the
  `cargo ndk` command above).
- **Remaining (polish):** richer reviewer surfaces (media, typing answers),
  media sync, and a store-signed release build.
