@echo off
REM Speedrun-for-RPCE pre-uninstall cleanup.
REM
REM On a genuine uninstall, remove the per-user study data so a later reinstall
REM starts fresh (collection + AnkiWeb account live in %APPDATA%\Anki2, RPCE
REM config in %USERPROFILE%\.rpce, neither of which the MSI tracks as installed
REM files). The WiX PreUninstallAction is conditioned
REM   REMOVE="ALL" AND NOT UPGRADINGPRODUCTCODE
REM so this runs only on a real uninstall, NOT during a version upgrade (an
REM upgrade keeps the user's data). For the default per-user install it runs in
REM the uninstalling user's context, so APPDATA/USERPROFILE resolve to them.
REM
REM Always exit 0: cleanup must never block/fail the uninstall (e.g. a locked
REM file if the app is still running).

if defined APPDATA (
  if exist "%APPDATA%\Anki2" rmdir /s /q "%APPDATA%\Anki2"
)
if defined USERPROFILE (
  if exist "%USERPROFILE%\.rpce" rmdir /s /q "%USERPROFILE%\.rpce"
)

exit /b 0
