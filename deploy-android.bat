@echo off
REM Build + deploy Speedrun for the RPCE to Android (debug APK).
REM Steps: regenerate bundled assets -> assembleDebug -> ensure device -> install -> launch.
REM Flags: --skip-assets (skip asset regen)   --no-emulator (fail instead of starting the AVD)
setlocal enabledelayedexpansion
pushd "%~dp0"

echo === Speedrun for the RPCE: Android deploy ===

REM --- parse flags ---
set "SKIP_ASSETS="
set "NO_EMULATOR="
:parse
if "%~1"=="" goto :endparse
if /I "%~1"=="--skip-assets" set "SKIP_ASSETS=1"
if /I "%~1"=="--no-emulator" set "NO_EMULATOR=1"
shift
goto :parse
:endparse

REM --- Python (built pyenv, falls back to PATH) ---
set "PY=out\pyenv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

REM --- JAVA_HOME: Android Studio's JBR (JDK 21); system Java is too new for AGP ---
if defined JAVA_HOME if exist "%JAVA_HOME%\bin\java.exe" goto :java_ok
for %%J in (
  "%ProgramFiles%\Android\Android Studio\jbr"
  "%ProgramW6432%\Android\Android Studio\jbr"
  "%LOCALAPPDATA%\Programs\Android Studio\jbr"
) do if exist "%%~J\bin\java.exe" (
  set "JAVA_HOME=%%~J"
  goto :java_ok
)
echo ERROR: Android Studio's JBR (JDK 21) not found. Set JAVA_HOME and retry.
popd & exit /b 1
:java_ok
echo JAVA_HOME=%JAVA_HOME%

REM --- Gradle 8.9 (no committed wrapper; use the downloaded dist, else PATH) ---
set "GRADLE="
if exist "%USERPROFILE%\.gradle-dist\gradle-8.9\bin\gradle.bat" set "GRADLE=%USERPROFILE%\.gradle-dist\gradle-8.9\bin\gradle.bat"
if not defined GRADLE (
  where gradle >nul 2>nul && set "GRADLE=gradle"
)
if not defined GRADLE (
  echo ERROR: gradle-8.9 not found ^(expected %USERPROFILE%\.gradle-dist\gradle-8.9\bin\gradle.bat^).
  popd & exit /b 1
)

REM --- Android SDK / adb / emulator ---
if not defined ANDROID_HOME set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
set "EMULATOR=%ANDROID_HOME%\emulator\emulator.exe"
if not exist "%ADB%" (
  where adb >nul 2>nul && set "ADB=adb"
)

set "APK=mobile\app\app\build\outputs\apk\debug\app-debug.apk"
set "PKG=com.rpce.speedrun"
set "AVD=rpce"

REM === 1) regenerate bundled assets (scenarios/simulations/concepts/quotes/render) ===
if defined SKIP_ASSETS (
  echo [1/4] Skipping asset regeneration ^(--skip-assets^).
) else (
  echo [1/4] Regenerating bundled assets...
  set "PYTHONPATH=out\pylib;pylib"
  set "PYTHONIOENCODING=utf-8"
  "%PY%" pylib\tools\rpce_export_assets.py mobile\app\app\src\main\assets
  if errorlevel 1 (echo asset export failed & popd & exit /b 1)
)

REM === 2) build the debug APK ===
echo [2/4] Building debug APK ^(assembleDebug^)...
call "%GRADLE%" --project-dir mobile/app :app:assembleDebug --no-daemon
if errorlevel 1 (echo gradle build failed & popd & exit /b 1)
if not exist "%APK%" (echo ERROR: APK not found at %APK% & popd & exit /b 1)

REM === 3) ensure a device/emulator is available ===
echo [3/4] Checking for a device...
"%ADB%" get-state 1>nul 2>nul
if errorlevel 1 (
  if defined NO_EMULATOR (echo No device connected ^(--no-emulator^). Aborting. & popd & exit /b 1)
  if not exist "%EMULATOR%" (echo No device connected and no emulator found. & popd & exit /b 1)
  echo Starting emulator %AVD%...
  start "" "%EMULATOR%" -avd %AVD%
  "%ADB%" wait-for-device
  echo Waiting for boot to complete...
  :bootwait
  set "BOOT="
  for /f "tokens=* delims=" %%b in ('"%ADB%" shell getprop sys.boot_completed 2^>nul') do set "BOOT=%%b"
  if not "!BOOT!"=="1" (
    ping -n 3 127.0.0.1 >nul
    goto :bootwait
  )
  echo Device booted.
)

REM === 4) install + launch ===
echo [4/4] Installing and launching %PKG%...
"%ADB%" install -r "%APK%"
if errorlevel 1 (echo adb install failed & popd & exit /b 1)
"%ADB%" shell monkey -p %PKG% -c android.intent.category.LAUNCHER 1 >nul 2>nul

echo.
echo Done: %PKG% built and deployed.
popd
endlocal
