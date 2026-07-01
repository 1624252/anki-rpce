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
- **Two-way sync** — logs in to and syncs with a self-hosted Anki sync server;
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
# arm64 device/emulator. Adds more ABIs by repeating -t (armeabi-v7a, x86_64).
cargo ndk -t arm64-v8a -o mobile/app/app/src/main/jniLibs build -p speedrun_jni --release
```

This compiles the shared engine and copies `libspeedrun_jni.so` into
`mobile/app/app/src/main/jniLibs/<abi>/`. (Verified: the engine + JNI bridge
cross-compile cleanly for `aarch64-linux-android`.)

## Build & run the app

1. Open `mobile/app/` in **Android Studio** and let it sync Gradle (the plugin
   versions in `build.gradle.kts` may need matching to your install).
2. Run on an emulator or a connected device. The app shows the RPCE home screen
   (the same deep-blue themed readiness banner as the desktop, rendered in a
   WebView from `assets/home.html`) and loads the shared engine — its
   version/build hash appears in the "Engine ready" chip, confirming the engine
   runs on device.
3. Build a debug/installable APK: `./gradlew assembleDebug` (or `assembleRelease`
   + sign with your keystore), then `adb install -r app-debug.apk`.

## Two-way sync (spec §7b)

Both apps point at the **same self-hosted Anki sync server**, so reviews sync
both ways. Start the server from the repo root:

```bash
PYTHONPATH=out/pylib SYNC_USER1="rpce:rpcepass" SYNC_BASE=./out/syncsrv \
  SYNC_HOST=0.0.0.0 SYNC_PORT=8083 \
  python -c "import anki.syncserver as s; s.run_sync_server()"
```

- **Phone:** open **Sync**, endpoint `http://10.0.2.2:8083/` (the emulator's
  route to the host; use the host LAN IP on a real device), user `rpce` /
  `rpcepass`, **Log in & sync**. The first join needs a full up/down (choose
  once); after that a normal sync merges automatically.
- **Desktop:** point Anki at the same server via *Preferences → Syncing →
  self-hosted sync server* (`http://127.0.0.1:8083/`), then Sync.
- **Conflict rule (documented):** same-card-offline edits resolve by
  higher-`usn` / last-writer — Anki's built-in rule, inherited unchanged.

**Verified round-trip:** a phone review session (4 reviews + 1 graded scenario)
uploaded to the server was then downloaded by a second engine, arriving intact
(RPCE deck, 23 cards, 4 revlog rows, scenario counter = 1) — reviews and RPCE
state (tags + config) cross devices through the shared engine.

## Status

- **Done / verified:** shared engine cross-compiles for Android; JNI bridge
  drives the real protobuf backend; review loop, three scores + give-up rule,
  Section II practice, and two-way sync all run on-device (verified on the
  x86_64 emulator). The native `.so` libs are gitignored (regenerate with the
  `cargo ndk` command above).
- **Remaining (polish):** richer reviewer surfaces (media, typing answers),
  media sync, and a store-signed release build.
