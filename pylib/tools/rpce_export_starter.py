#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Export the RPCE starter deck (+ shared web assets) the phone bundles.

Builds the full question bank in a throwaway collection and exports it as a
``.apkg`` the phone imports on first run and the desktop imports too (same note
GUIDs → clean sync). Every question is one note of a Kind (cloze | mcq | order)
described by a base64-JSON payload the shared renderer reads. Also writes, next
to the deck:

- ``rpce_render.js`` — the shared interactive renderer (single source in
  ``anki.rpce.render_js``), so the phone and desktop render identically.
- ``reference.json`` — the Reference-tab tables (order of precedence, motion
  characteristics) from ``anki.rpce.knowledge``.

Run from the repo root (built pylib on the path + the local RONR corpus):

    PYTHONPATH=out/pylib python pylib/tools/rpce_export_starter.py \
        mobile/app/app/src/main/assets/rpce_starter.apkg [count]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import anki.import_export_pb2 as pb
from anki.collection import Collection
from anki.rpce import add_question_note, build_starter_deck, knowledge, render_js

# The generator lives beside this tool (it reads the local RONR corpus).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rpce_generate_questions as gen  # noqa: E402

DEFAULT_COUNT = 1000


def add_generated_questions(col: Collection, deck_id: int, count: int) -> int:
    questions = gen.build(count)
    for q in questions:
        add_question_note(
            col,
            deck_id,
            payload=q.payload,
            plain_q=q.plain_q,
            plain_a=q.plain_a,
            domain=q.domain,
            concept_id=q.concept_id,
        )
    return len(questions)


def write_web_assets(assets_dir: Path) -> None:
    """Write the shared renderer + reference tables next to the deck."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "rpce_render.js").write_text(
        "/* Generated from anki.rpce.render_js — do not edit by hand. */\n"
        "var RPCE_CSS = "
        + json.dumps(render_js.RENDER_CSS)
        + ";\n"
        + render_js.RENDER_JS,
        encoding="utf-8",
    )
    (assets_dir / "reference.json").write_text(
        json.dumps(knowledge.reference_tables(), indent=1), encoding="utf-8"
    )


def main(out_path: str, count: int) -> None:
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        col = Collection(str(Path(tmp) / "starter.anki2"))
        try:
            deck_id = build_starter_deck(col)
            n = add_generated_questions(col, deck_id, count)
            total = len(col.find_cards('deck:"RPCE"'))
            col._backend.export_anki_package(
                out_path=str(out),
                options=pb.ExportAnkiPackageOptions(
                    with_scheduling=False,
                    with_deck_configs=True,
                    with_media=False,
                    legacy=False,
                ),
                limit=pb.ExportLimit(deck_id=deck_id),
            )
        finally:
            col.close()
    write_web_assets(out.parent)
    print(
        f"wrote {out} ({out.stat().st_size} bytes): "
        f"{n} generated questions, {total} cards total; "
        "plus rpce_render.js + reference.json"
    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("usage: rpce_export_starter.py <out.apkg> [count]", file=sys.stderr)
        sys.exit(2)
    count = int(sys.argv[2]) if len(sys.argv) == 3 else DEFAULT_COUNT
    main(sys.argv[1], count)
