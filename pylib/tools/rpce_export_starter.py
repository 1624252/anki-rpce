#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Export the RPCE starter deck to a .apkg the phone bundles for offline review.

Builds the seven-domain starter deck in a throwaway collection and exports the
RPCE deck via the shared backend, so the Android companion can import a real,
reviewable deck on first run (before any sync).

Run from the repo root (needs the built pylib on the path):

    PYTHONPATH=out/pylib python pylib/tools/rpce_export_starter.py \
        mobile/app/app/src/main/assets/rpce_starter.apkg
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import anki.import_export_pb2 as pb
from anki.collection import Collection
from anki.rpce import build_starter_deck


def main(out_path: str) -> None:
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        col = Collection(str(Path(tmp) / "starter.anki2"))
        try:
            deck_id = build_starter_deck(col)
            col._backend.export_anki_package(
                out_path=str(out),
                options=pb.ExportAnkiPackageOptions(
                    with_scheduling=False,  # fresh scheduling on the phone
                    with_deck_configs=True,
                    with_media=False,
                    legacy=False,
                ),
                limit=pb.ExportLimit(deck_id=deck_id),
            )
        finally:
            col.close()
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: rpce_export_starter.py <out.apkg>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
