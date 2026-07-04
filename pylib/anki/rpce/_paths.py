# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Locate the RPCE data files (corpus + authored JSON banks) at runtime.

The files live in the repo's top-level ``data/`` during development, but that
directory is NOT part of the shipped package. The desktop installer copies the
needed files into ``anki/rpce/data/`` beside this module (see
``qt/tools/build_installer.py`` ``bundle_rpce_data``), so both layouts resolve
through here. ``RPCE_DATA_DIR`` overrides the location for tests/custom setups.
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dirs() -> list[Path]:
    """Candidate data directories, most-specific first."""
    here = Path(__file__).resolve()
    dirs: list[Path] = []
    env = os.environ.get("RPCE_DATA_DIR")
    if env:
        dirs.append(Path(env))
    dirs.append(here.parents[3] / "data")  # dev: repo-root/data
    dirs.append(here.parent / "data")  # installed: anki/rpce/data (bundled)
    return dirs


def data_path(name: str) -> Path | None:
    """The first existing data file named ``name``, or ``None`` if not bundled."""
    for d in data_dirs():
        p = d / name
        if p.exists():
            return p
    return None
