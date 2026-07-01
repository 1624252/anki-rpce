# Speedrun for the RPCE

A study app (forked from Anki) for one exam: the **Registered Parliamentarian
Credentialing Examination (RPCE)** — the National Association of
Parliamentarians' credential over *Robert's Rules of Order Newly Revised, 12th
ed.* Section I is multiple choice; Section II is written performance scenarios;
you must clear 80% on each.

## Install

Run the pre-built installer for your OS — it's fully self-contained (Python, Qt,
and the engine are bundled), so **nothing is downloaded during install** and no
dev tools are needed. On Windows it installs per-user, so there's no admin
prompt.

| Desktop | Installer      | To install                                |
|---------|----------------|-------------------------------------------|
| Windows | `.msi`         | double-click it                           |
| macOS   | `.dmg`         | open it, drag the app to Applications     |
| Linux   | `.zip`         | unzip, run the launcher inside            |

Then start **Speedrun for the RPCE**; it builds the RPCE deck on first launch.

## Uninstall

- **Windows** — Settings → Apps → Installed apps → **Anki** → Uninstall
  (or `msiexec /x anki-<ver>-win-x64.msi`).
- **macOS** — drag the app from Applications to the Trash.
- **Linux** — delete the unzipped folder.

## Build the installers from source

Only needed to *produce* the files above. The packager (Briefcase) targets the
machine it runs on, so **build each platform's installer on that platform** (or
a CI runner per OS). Everywhere you need [Rustup](https://rustup.rs), a C
toolchain, and a few GB of free disk; clone into a short path without spaces.

```bash
git clone https://github.com/1624252/anki-rpce.git speedrun && cd speedrun
```

| Desktop | Also need | Build command               | Output in `out/installer/dist/` |
|---------|-----------|-----------------------------|---------------------------------|
| Windows | MSVC build tools, MSYS2  | `tools\build-installer.bat` | an `.msi` (e.g. `anki-26.05-win-x64.msi`) |
| macOS   | Xcode command-line tools | `./tools/build-installer`   | a `.dmg` |
| Linux   | standard build packages  | `./tools/build-installer`   | a `.zip` |
