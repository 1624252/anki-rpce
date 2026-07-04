@echo off
REM Start the Android emulator for Speedrun for the RPCE.
REM Usage: start-emulator.bat [avd-name] [--no-wait]     (default AVD: rpce)
setlocal enabledelayedexpansion
pushd "%~dp0"

REM --- args: an AVD name and/or --no-wait, in any order ---
set "AVD=rpce"
set "NOWAIT="
:parse
if "%~1"=="" goto :endparse
if /I "%~1"=="--no-wait" (set "NOWAIT=1") else (set "AVD=%~1")
shift
goto :parse
:endparse

REM --- locate the SDK / adb / emulator ---
if not defined ANDROID_HOME set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
set "EMULATOR=%ANDROID_HOME%\emulator\emulator.exe"
if not exist "%ADB%" (
  where adb >nul 2>nul && set "ADB=adb"
)
if not exist "%EMULATOR%" (
  where emulator >nul 2>nul && set "EMULATOR=emulator"
)
if not exist "%EMULATOR%" if /I not "%EMULATOR%"=="emulator" (
  echo ERROR: emulator not found under %ANDROID_HOME%\emulator. Set ANDROID_HOME.
  popd & exit /b 1
)

REM --- already have a running device? then don't start another ---
"%ADB%" get-state 1>nul 2>nul
if not errorlevel 1 (
  echo A device/emulator is already running:
  "%ADB%" devices
  popd & exit /b 0
)

REM --- verify the AVD exists ---
"%EMULATOR%" -list-avds 2>nul | findstr /X /C:"%AVD%" >nul
if errorlevel 1 (
  echo ERROR: AVD "%AVD%" not found. Available AVDs:
  "%EMULATOR%" -list-avds
  popd & exit /b 1
)

REM --- launch (detached, so this script returns) ---
echo Starting emulator %AVD%...
start "" "%EMULATOR%" -avd %AVD%

if defined NOWAIT (
  echo Launched %AVD% ^(not waiting for boot^).
  popd & exit /b 0
)

"%ADB%" wait-for-device
echo Waiting for boot to complete...
:bootwait
set "BOOT="
for /f "tokens=* delims=" %%b in ('"%ADB%" shell getprop sys.boot_completed 2^>nul') do set "BOOT=%%b"
if not "!BOOT!"=="1" (
  ping -n 3 127.0.0.1 >nul
  goto :bootwait
)
echo Emulator %AVD% is booted and ready.
popd
endlocal
