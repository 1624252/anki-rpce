# Speedrun for the RPCE

A study app (forked from Anki) for one exam: the **Registered Parliamentarian
Credentialing Examination (RPCE)** — the National Association of
Parliamentarians' credential over *Robert's Rules of Order Newly Revised, 12th
ed.* Section I is multiple choice; Section II is written performance scenarios;
you must clear 80% on each.

## Build the installer from a clean checkout

Prerequisites (Windows): [Rustup](https://rustup.rs), the **MSVC build tools**,
**MSYS2**, and a few GB of free disk. Clone into a short path without spaces.

```bat
git clone <this-repo> speedrun && cd speedrun
tools\build-installer.bat
```

(macOS/Linux: `./tools/build-installer`.) The build downloads its own deps and
writes an installer to `out\installer\dist\`:

- **Windows** — an `.msi`
- **macOS** — a `.dmg`
- **Linux** — a tarball

## Install

Run the installer from `out\installer\dist\` on a clean machine (double-click the
`.msi`, or open the `.dmg` / extract the tarball) and launch **Speedrun for the
RPCE**. It needs no dev tools and builds the RPCE deck on first launch.
