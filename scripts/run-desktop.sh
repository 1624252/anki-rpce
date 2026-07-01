#!/usr/bin/env bash
# Rebuild and launch the Speedrun (Anki) DESKTOP app.
#
#   ./scripts/run-desktop.sh            # build + run
#   ./scripts/run-desktop.sh -- -p test # pass args through (throwaway profile)
#
# Prereqs (see docs/rpce/DEPLOYMENT.md): Rustup, N2 (tools/install-n2), and on
# Windows MSVC build tools + MSYS2. Run from Git Bash on Windows, or a shell on
# macOS/Linux. This blocks while Anki is open (close Anki to return).
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

echo "==> Stopping any running desktop instance (best effort)…"
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -Command \
    "Get-Process python,anki -ErrorAction SilentlyContinue | Stop-Process -Force" \
    >/dev/null 2>&1 || true
fi

echo "==> Building + launching (first build downloads deps and is slow)…"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) MSYS2_ARG_CONV_EXCL='*' cmd.exe //c "run.bat $*" ;;
  *)                    ./run "$@" ;;
esac
