# Building & Running Speedrun (desktop + mobile)

This is the exact process used to build, deploy, and run the app on a Windows
dev machine. Two shell scripts wrap it so you don't have to remember the steps;
the manual steps are written out below each script in case you want to run them
by hand or something breaks.

Both apps share one Rust engine. The desktop is Anki (PyQt) built from source;
the mobile app is an Android WebView that loads the same engine through a JNI
bridge.

## One command each

From the repo root, in **Git Bash** (Windows) or a normal shell (macOS/Linux):

```bash
./scripts/run-desktop.sh          # build + launch the desktop app
./scripts/run-mobile.sh           # build APK, install on the emulator, launch
./scripts/run-mobile.sh --fresh   # same, but wipe app data first so the deck re-imports
```

`run-desktop.sh` stays running while Anki is open (close Anki to get your
prompt back). Use `--fresh` on mobile whenever the question set changes, because
the app only imports the deck on first launch.

---

## Prerequisites (one-time)

Desktop:
- **Rustup** (the toolchain in `rust-toolchain.toml` is fetched automatically).
- **N2** — `C:\msys64\usr\bin\bash.exe tools/install-n2` (installs to `~/.cargo/bin`).
- On Windows: **MSVC build tools** and **MSYS2** (`sh`, `git`, `rsync`).

Mobile:
- **Android Studio** + SDK, an **AVD** (emulator), and `platform-tools` (adb).
- `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) set to the SDK path.
- Gradle and the JDK are handled for you: the committed Gradle **wrapper**
  downloads Gradle on first run, and the scripts use Android Studio's bundled
  **JBR** (JDK 21) so you don't need a separate JDK. (AGP 8.5 needs JDK 17–21;
  the system JDK is often too new.)

---

## Desktop — what the script does

1. Stop any running instance (frees port 40000).
2. `./run.bat` (the canonical launcher; `just run` calls the same thing). It:
   - builds `pylib` + `qt` with the build runner (n2/ninja), then
   - launches Anki with `ANKIDEV=1`, web views on `http://localhost:40000`,
     and the Chromium remote debugger on `:8080`.
3. On first launch the RPCE deck is seeded automatically. If the shared starter
   deck (`mobile/app/app/src/main/assets/rpce_starter.apkg`) is present it is
   imported, so the desktop gets the **same deck as mobile** (same
   note GUIDs, so a later sync merges cleanly); otherwise it falls back to the
   curated seven-domain deck.

By hand:
```bash
./run.bat            # Windows (from Git Bash: cmd.exe //c run.bat)
# or ./run           on macOS/Linux
```

## Mobile — what the script does

1. Locate the SDK from `ANDROID_HOME`, and `JAVA_HOME` from Android Studio's JBR.
2. Build the debug APK: `cd mobile/app && ./gradlew :app:assembleDebug`.
   (The APK bundles the prebuilt engine `.so` and the starter deck `.apkg`.)
3. Ensure a device: if none is attached, start the first AVD and wait for boot.
4. `--fresh` only: `adb uninstall com.rpce.speedrun` (clears the old collection).
5. `adb install -r <apk>` then `adb shell am start -n com.rpce.speedrun/.MainActivity`.

By hand (from the repo root):
```bash
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
ADB="$ANDROID_HOME/platform-tools/adb"

( cd mobile/app && ./gradlew :app:assembleDebug )
"$ANDROID_HOME/emulator/emulator" -avd "$( "$ANDROID_HOME/emulator/emulator" -list-avds | head -1 )" &
"$ADB" wait-for-device
"$ADB" uninstall com.rpce.speedrun         # only if you want the deck re-imported
"$ADB" install -r mobile/app/app/build/outputs/apk/debug/app-debug.apk
"$ADB" shell am start -n com.rpce.speedrun/.MainActivity
```

### Regenerating the deck / native engine (only when content or engine changes)

```bash
# ~6,000+ RONR-grounded questions -> the phone starter deck (also read by the desktop)
PYTHONPATH=out/pylib out/pyenv/Scripts/python pylib/tools/rpce_export_starter.py \
  mobile/app/app/src/main/assets/rpce_starter.apkg

# rebuild the native engine for Android (needs cargo-ndk); .so is gitignored
cargo ndk -t arm64-v8a -t x86_64 -o mobile/app/app/src/main/jniLibs build -p speedrun_jni --release
```

---

## Troubleshooting (issues actually hit on Windows)

- **`CreateProcessA: The system cannot find the file specified`** during the
  build: n2 runs each edge via `CreateProcess`, which can't resolve a relative
  forward-slash exe path. Fixed in `build/ninja_gen/src/render.rs` (the `runner`
  variable now uses the native separator). If you see it again, regenerate the
  build file: `cargo run -p configure`.
- **`extract:uv … Access is denied (os error 5)`**: a transient antivirus lock
  on the freshly-extracted `uv.exe`. Re-run the build, or just the one step:
  `n2 -f out/build.ninja extract_uv`.
- **Gradle picks the wrong JDK** (build fails on a too-new Java): point it at the
  JBR — `export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"`.
- **Mobile changes don't show up**: the deck imports once, so run
  `./scripts/run-mobile.sh --fresh` after changing questions.
