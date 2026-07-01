#!/usr/bin/env bash
# Rebuild the APK, ensure an emulator/device, install, and launch the MOBILE app.
#
#   ./scripts/run-mobile.sh           # build, install (keep data), launch
#   ./scripts/run-mobile.sh --fresh   # uninstall first so the deck re-imports
#
# Prereqs: Android SDK + an AVD, and Android Studio's bundled JDK (JBR). Set
# ANDROID_HOME (or ANDROID_SDK_ROOT). The Gradle wrapper handles Gradle itself
# (first run downloads it). Run from Git Bash on Windows, or a shell elsewhere.
# See docs/rpce/DEPLOYMENT.md §3 and mobile/README.md.
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

APP_ID=com.rpce.speedrun
FRESH=0
[ "${1:-}" = "--fresh" ] && FRESH=1

# --- locate the SDK + JBR, normalising Windows paths for Git Bash ------------
norm() { if command -v cygpath >/dev/null 2>&1; then cygpath "$1"; else echo "$1"; fi; }
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[ -n "$SDK" ] || { echo "ERROR: set ANDROID_HOME (or ANDROID_SDK_ROOT)."; exit 1; }
SDK="$(norm "$SDK")"
ADB="$SDK/platform-tools/adb"
EMU="$SDK/emulator/emulator"
# AGP 8.5 needs JDK 17-21; Android Studio's JBR is the safe default.
if [ -z "${JAVA_HOME:-}" ]; then
  for j in "/c/Program Files/Android/Android Studio/jbr" \
           "/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
           "$HOME/.local/share/JetBrains/Toolbox/apps/AndroidStudio/jbr"; do
    [ -d "$j" ] && { export JAVA_HOME="$j"; break; }
  done
fi
echo "==> SDK: $SDK"
echo "==> JAVA_HOME: ${JAVA_HOME:-<system default>}"

# --- build -------------------------------------------------------------------
echo "==> Building debug APK (first run downloads Gradle)…"
( cd mobile/app && ./gradlew :app:assembleDebug )
APK=mobile/app/app/build/outputs/apk/debug/app-debug.apk

# --- ensure a device ---------------------------------------------------------
if ! "$ADB" devices | grep -qw device; then
  AVD="$("$EMU" -list-avds | head -n1 || true)"
  [ -n "$AVD" ] || { echo "ERROR: no AVD found — create one in Android Studio."; exit 1; }
  echo "==> Starting emulator: $AVD"
  "$EMU" -avd "$AVD" -no-snapshot-load >/dev/null 2>&1 &
  "$ADB" wait-for-device
  echo "==> Waiting for boot…"
  until [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
fi

# --- install + launch --------------------------------------------------------
if [ "$FRESH" = "1" ]; then
  echo "==> Fresh install (clears data so the RPCE deck re-imports)…"
  "$ADB" uninstall "$APP_ID" >/dev/null 2>&1 || true
fi
echo "==> Installing…"
"$ADB" install -r "$APK"
echo "==> Launching…"
"$ADB" shell am start -n "$APP_ID/.MainActivity" >/dev/null
echo "Done — app running on the emulator/device."
