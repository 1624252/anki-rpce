# Speedrun RPCE — Android companion

The phone companion reuses the **same Rust engine** as the desktop app (spec §3:
two apps, one engine), loaded through a thin JNI bridge — not a reimplemented
scheduler.

## Layout

- `jni/` — the `speedrun_jni` Rust crate (`cdylib`). Links the shared `anki`
  engine (including the RPCE points-at-stake queue) and exposes JNI entry points
  (currently `NativeBridge.engineInfo()`).
- `app/` — a minimal Android Studio (Gradle/Kotlin) project that loads
  `libspeedrun_jni.so` and calls into the engine.

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

## Status & remaining work

- **Done / verified:** the shared engine cross-compiles for Android; the JNI
  bridge links it and is callable from Kotlin; the app loads the lib and renders
  the themed RPCE home screen (deep-blue banner matching desktop).
- **Remaining (larger):** the full review/sync UI — reusing AnkiDroid's review
  surfaces over this engine — so the companion runs real RPCE reviews and
  two-way syncs with desktop (spec §3, §7b). The native libs are gitignored
  (regenerate with the command above).
