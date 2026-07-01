#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Export the RPCE starter deck to a .apkg the phone bundles for offline review.

Builds the RPCE deck in a throwaway collection and exports it via the shared
backend, so the Android companion can import a real, reviewable deck on first
run (before any sync). The deck is the seven curated domain concepts **plus**
all of the RONR-grounded generated practice questions
(`data/rpce_generated_questions.md`, via `rpce_generate_questions.build`), so
the phone ships the full question bank offline. Each generated question becomes
one card carrying its exact RONR (12th ed.) citation + verbatim quote.

Run from the repo root (needs the built pylib on the path and the local RONR
corpus under `data/`):

    PYTHONPATH=out/pylib python pylib/tools/rpce_export_starter.py \
        mobile/app/app/src/main/assets/rpce_starter.apkg [count]
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

import anki.import_export_pb2 as pb
from anki.collection import Collection
from anki.rpce import (
    MCQ_OPTION_SEP,
    TRANSFER_NOTETYPE,
    build_starter_deck,
    domain_tag,
)
from anki.rpce.transfer_ladder import concept_tag, format_tag

# The question generator lives beside this tool (it reads the local RONR corpus).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rpce_generate_questions as gen  # noqa: E402

#: Default number of generated questions to bundle (the full generated set).
DEFAULT_COUNT = 1000


def _br(text: str) -> str:
    """Corpus stems use newlines; the card template renders HTML."""
    return text.replace("\n", "<br>")


def _fields_for(q: gen.Question) -> dict[str, str]:
    """Render one generated question into RPCE Concept notetype fields.

    The applied multiple-choice format fills the interactive MCQ fields; cloze
    recall fills the cloze fields. The default card template shows
    ``ClozeQ``/``ClozeA``, so both formats populate those too and render on the
    phone without the desktop's format-rotation hook. For MCQ, ``ClozeQ`` also
    carries a base64 payload the phone reads to render tappable options.
    """
    if q.options:  # applied multiple-choice
        idx = "ABCD".index(q.answer)
        # Machine-readable payload so the phone can render tappable options and
        # score the pick; a plain-text list is kept as a no-JS fallback.
        payload = base64.b64encode(
            json.dumps(
                {
                    "opts": list(q.options),
                    "idx": idx,
                    "cite": q.citation,
                    "quote": q.quote,
                }
            ).encode()
        ).decode()
        fallback = "<br>".join(f"{L}) {o}" for L, o in zip("ABCD", q.options))
        answer = (
            f'Correct: {q.answer}) <span class="cloze-reveal">{q.options[idx]}</span>'
        )
        return {
            "ClozeQ": (
                _br(q.stem)
                + f'<div class="mcq-fallback">{fallback}</div>'
                + f'<div class="mcq-data" data-p="{payload}" style="display:none"></div>'
            ),
            "ClozeA": answer,
            "MCQQ": _br(q.stem),
            "MCQA": answer,
            "MCQOptions": MCQ_OPTION_SEP.join(q.options),
            "MCQIdx": str(idx),
            "rung": "mcq",
        }
    # cloze recall — the answer fills the blank in place: the same sentence with
    # the emphasised term restored and highlighted (not shown as a separate line).
    term = q.answer
    blanked = q.quote.replace(term, "_____", 1)
    filled = q.quote.replace(term, f'<span class="cloze-reveal">{term}</span>', 1)
    return {
        "ClozeQ": _br(blanked),
        "ClozeA": _br(filled),
        "MCQQ": "",
        "MCQA": "",
        "MCQOptions": "",
        "MCQIdx": "",
        "rung": "cloze",
    }


def add_generated_questions(col: Collection, deck_id: int, count: int) -> int:
    """Add the RONR-grounded generated questions to the deck (one card each)."""
    model = col.models.by_name(TRANSFER_NOTETYPE)
    assert model is not None  # build_starter_deck created it
    questions = gen.build(count)
    for q in questions:
        f = _fields_for(q)
        note = col.new_note(model)
        note["Concept"] = q.concept_id
        note["Domain"] = str(q.domain)
        note["ClozeQ"] = f["ClozeQ"]
        note["ClozeA"] = f["ClozeA"]
        note["MCQQ"] = f["MCQQ"]
        note["MCQA"] = f["MCQA"]
        note["MCQOptions"] = f["MCQOptions"]
        note["MCQIdx"] = f["MCQIdx"]
        note["Citation"] = q.citation
        note["Quote"] = q.quote
        note.tags = [
            domain_tag(q.domain),
            concept_tag(q.concept_id),
            format_tag(f["rung"]),
        ]
        col.add_note(note, deck_id)
    return len(questions)


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
                    with_scheduling=False,  # fresh scheduling on the phone
                    with_deck_configs=True,
                    with_media=False,
                    legacy=False,
                ),
                limit=pb.ExportLimit(deck_id=deck_id),
            )
        finally:
            col.close()
    print(
        f"wrote {out} ({out.stat().st_size} bytes): "
        f"{n} generated questions, {total} cards total"
    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("usage: rpce_export_starter.py <out.apkg> [count]", file=sys.stderr)
        sys.exit(2)
    count = int(sys.argv[2]) if len(sys.argv) == 3 else DEFAULT_COUNT
    main(sys.argv[1], count)
