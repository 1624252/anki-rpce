@echo off
REM One-shot release: build the Windows MSI + Android APK locally, push a
REM v<version>-rpce tag (GitHub Actions creates the release), then upload both
REM artifacts to it.
REM
REM   Usage:  release.bat <version> [--check]      e.g.  release.bat 0.1.2
REM   --check  validate config + toolchain and print the plan, then stop.
REM
REM Requires: GH_TOKEN = a GitHub PAT with 'repo' + 'workflow' scopes.
REM   PowerShell:  $env:GH_TOKEN = "ghp_xxx"; .\release.bat 0.1.2
REM   cmd.exe   :  set "GH_TOKEN=ghp_xxx" && release.bat 0.1.2
setlocal enabledelayedexpansion
pushd "%~dp0"

if "%~1"=="" (
  echo Usage: release.bat ^<version^> [--check]   e.g. release.bat 0.1.2
  popd & exit /b 1
)
set "VER=%~1"
set "CHECK="
if /I "%~2"=="--check" set "CHECK=1"

REM --- release identity (matches prior releases) ---
set "OWNER=1624252"
set "REPO=anki-rpce"
set "ANKIVER=26.05"
set "TAG=v%VER%-rpce"
set "MSI=out\installer\dist\speedrun-rpce-%ANKIVER%-win-x64.msi"
set "MSINAME=speedrun-rpce-%ANKIVER%-win-x64.msi"
set "APK=mobile\app\app\build\outputs\apk\release\app-release.apk"
set "APKNAME=speedrun-rpce-%ANKIVER%-android.apk"

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

where curl >nul 2>nul || (echo ERROR: curl not found on PATH. & popd & exit /b 1)

echo === Release plan ===
echo   version : %VER%
echo   tag     : %TAG%
echo   repo    : %OWNER%/%REPO%
echo   MSI     : %MSI%
echo   APK     : %APK% -^> %APKNAME%
echo   JAVA_HOME=%JAVA_HOME%
echo   GRADLE=%GRADLE%

if defined CHECK (
  if not defined GH_TOKEN echo WARNING: GH_TOKEN not set ^(required for a real run^).
  echo --check: validated config + toolchain; not building or pushing.
  popd & exit /b 0
)

if not defined GH_TOKEN (
  echo ERROR: GH_TOKEN is not set in the environment.
  echo   PowerShell:  $env:GH_TOKEN = "ghp_xxx"
  echo   cmd.exe   :  set "GH_TOKEN=ghp_xxx"
  echo   then re-run:  release.bat %VER%
  echo   ^(the PAT needs 'repo' + 'workflow' scopes^)
  popd & exit /b 1
)

REM --- require a clean, committed tree (untracked files are ignored) ---
git diff --quiet
if errorlevel 1 (echo ERROR: unstaged changes present. Commit or stash first. & popd & exit /b 1)
git diff --cached --quiet
if errorlevel 1 (echo ERROR: staged-but-uncommitted changes present. Commit first. & popd & exit /b 1)

REM --- refuse to reuse a version ---
git rev-parse "%TAG%" >nul 2>nul && (echo ERROR: tag %TAG% already exists locally. Pick a new version. & popd & exit /b 1)

echo.
echo === [1/6] Building wheels (RELEASE=2) ===
set "RELEASE=2"
call tools\ninja.bat wheels
if errorlevel 1 (echo wheels build failed & popd & exit /b 1)
set "AQTWHL="
for %%f in (out\wheels\aqt-*.whl) do set "AQTWHL=%%f"
set "ANKIWHL="
for %%f in (out\wheels\anki-*.whl) do set "ANKIWHL=%%f"
if not defined AQTWHL (echo aqt wheel not found in out\wheels & popd & exit /b 1)
if not defined ANKIWHL (echo anki wheel not found in out\wheels & popd & exit /b 1)

echo.
echo === [2/6] Building + packaging the Windows MSI ===
"%PY%" qt\tools\build_installer.py --version %ANKIVER% build --aqt_wheel "%AQTWHL%" --anki_wheel "%ANKIWHL%"
if errorlevel 1 (echo installer build failed & popd & exit /b 1)
"%PY%" qt\tools\build_installer.py --version %ANKIVER% package
if errorlevel 1 (echo installer package failed & popd & exit /b 1)
if not exist "%MSI%" (echo MSI not found at %MSI% & popd & exit /b 1)

echo.
echo === [3/6] Building the Android APK ===
set "PYTHONPATH=out\pylib;pylib"
set "PYTHONIOENCODING=utf-8"
"%PY%" pylib\tools\rpce_export_assets.py mobile\app\app\src\main\assets
if errorlevel 1 (echo asset export failed & popd & exit /b 1)
call "%GRADLE%" --project-dir mobile/app :app:assembleRelease --no-daemon
if errorlevel 1 (echo APK build failed & popd & exit /b 1)
if not exist "%APK%" (echo signed release APK not found at %APK% ^(is mobile\app\keystore.properties present?^) & popd & exit /b 1)

echo.
echo === [4/6] Pushing commit + tag %TAG% (triggers the RPCE Release workflow) ===
set "REMOTE=https://x-access-token:%GH_TOKEN%@github.com/%OWNER%/%REPO%.git"
git push "%REMOTE%" HEAD:main
if errorlevel 1 (echo git push main failed & popd & exit /b 1)
git tag "%TAG%"
if errorlevel 1 (echo tag create failed & popd & exit /b 1)
git push "%REMOTE%" "refs/tags/%TAG%"
if errorlevel 1 (echo tag push failed ^(already released?^) & popd & exit /b 1)

echo.
echo === [5/6] Waiting for GitHub Actions to create the release ===
set "REL=%TEMP%\rpce_rel_%VER%.json"
set /a TRIES=0
:waitrel
curl -s -H "Authorization: Bearer %GH_TOKEN%" "https://api.github.com/repos/%OWNER%/%REPO%/releases/tags/%TAG%" > "%REL%"
"%PY%" -c "import json,sys;d=json.load(open(r'%REL%'));sys.exit(0 if d.get('id') else 1)" 2>nul
if not errorlevel 1 goto :haverel
set /a TRIES+=1
if %TRIES% GEQ 45 (echo Release not created after ~3 min. Check the Actions tab. & popd & exit /b 1)
ping -n 5 127.0.0.1 >nul
goto :waitrel
:haverel
REM Read the release id: run python directly (for /f mangles quoted commands),
REM writing the id to a temp file we slurp with set /p.
"%PY%" -c "import json;print(json.load(open(r'%REL%'))['id'])" > "%TEMP%\rpce_rid.txt" 2>nul
set "RID="
set /p RID=<"%TEMP%\rpce_rid.txt"
if not defined RID (echo could not read release id & popd & exit /b 1)
echo Release id %RID%.

echo.
echo === [6/6] Uploading MSI + APK ===
set "UP=https://uploads.github.com/repos/%OWNER%/%REPO%/releases/%RID%/assets"
set "CODEFILE=%TEMP%\rpce_code.txt"
curl -s -o nul -w "%%{http_code}" -H "Authorization: Bearer %GH_TOKEN%" -H "Content-Type: application/octet-stream" --data-binary "@%MSI%" "%UP%?name=%MSINAME%" > "%CODEFILE%"
set "MCODE=" & set /p MCODE=<"%CODEFILE%"
echo   MSI -^> HTTP %MCODE%
curl -s -o nul -w "%%{http_code}" -H "Authorization: Bearer %GH_TOKEN%" -H "Content-Type: application/octet-stream" --data-binary "@%APK%" "%UP%?name=%APKNAME%" > "%CODEFILE%"
set "ACODE=" & set /p ACODE=<"%CODEFILE%"
echo   APK -^> HTTP %ACODE%
if not "%MCODE%"=="201" echo WARNING: MSI upload returned %MCODE% ^(asset may already exist for this tag^).
if not "%ACODE%"=="201" echo WARNING: APK upload returned %ACODE% ^(asset may already exist for this tag^).

echo.
echo Done: https://github.com/%OWNER%/%REPO%/releases/tag/%TAG%
popd
endlocal
