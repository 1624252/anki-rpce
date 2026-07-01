# Speedrun for the RPCE

A study app (forked from Anki) for one exam: the **Registered Parliamentarian
Credentialing Examination (RPCE)** — the National Association of
Parliamentarians' credential over *Robert's Rules of Order Newly Revised, 12th
ed.* Section I is multiple choice; Section II is written performance scenarios;
you must clear 80% on each.

## Build the installer from a clean checkout

One command builds a native installer. Because the packager (Briefcase) targets
the machine it runs on, **build each platform's installer on that platform** (or
a CI runner per OS) — a Mac can't produce the Windows `.msi`, and vice versa.
Prerequisites everywhere: [Rustup](https://rustup.rs), a C toolchain, and a few
GB of free disk. Clone into a short path without spaces.

```bash
git clone <this-repo> speedrun && cd speedrun
```

| Desktop | Also need | Build command            | Output in `out/installer/dist/` |
|---------|-----------|--------------------------|---------------------------------|
| Windows | MSVC build tools, MSYS2 | `tools\build-installer.bat` | an `.msi` (e.g. `anki-26.05-win-x64.msi`) |
| macOS   | Xcode command-line tools | `./tools/build-installer` | a `.dmg` |
| Linux   | standard build packages  | `./tools/build-installer` | a `.zip` |

The build downloads its own remaining deps.

## Install

On a clean machine, from `out/installer/dist/`:

- **Windows** — double-click the `.msi`
- **macOS** — open the `.dmg` and drag the app to Applications
- **Linux** — unzip and run the launcher inside

Then start **Speedrun for the RPCE**. It needs no dev tools and builds the RPCE
deck on first launch.
