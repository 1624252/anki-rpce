# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Python-calling test for the RPCE concept-grouping bury (the Rust change).

Exercises the new `bury_concept_siblings` backend RPC end to end: studying one
card of a concept should bury the OTHER cards of that same concept (even on
different notes), while cards of a different concept are left alone.
"""

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SIBLING_BURIED
from tests.shared import getEmptyCol


def _add_card(col, front: str, tag: str):
    note = col.newNote()
    note["Front"] = front
    note["Back"] = "back"
    note.tags = [tag]
    col.addNote(note)
    return col.find_cards(f"nid:{note.id}")[0]


def _queue(col, cid: int) -> int:
    return col.get_card(cid).queue


def test_bury_concept_siblings_buries_same_concept_only():
    col = getEmptyCol()

    # Two separate notes share concept 42; a third note is a different concept.
    studied = _add_card(col, "cloze form", "rpce::concept::42")
    sibling = _add_card(col, "mcq form", "rpce::concept::42")
    other = _add_card(col, "unrelated concept", "rpce::concept::99")

    out = col._backend.bury_concept_siblings(card_id=studied)

    assert out.count == 1, "exactly one same-concept sibling is buried"
    assert _queue(col, sibling) == QUEUE_TYPE_SIBLING_BURIED, (
        "concept-42 sibling is buried"
    )
    assert _queue(col, other) == QUEUE_TYPE_NEW, "concept-99 card is untouched"
    # The studied card itself must stay in the queue.
    assert _queue(col, studied) == QUEUE_TYPE_NEW


def test_bury_concept_siblings_noop_without_concept_tag():
    col = getEmptyCol()

    untagged = _add_card(col, "a", "unrelated::tag")
    neighbor = _add_card(col, "b", "unrelated::tag")

    out = col._backend.bury_concept_siblings(card_id=untagged)

    assert out.count == 0, "a card with no concept tag buries nothing"
    assert _queue(col, neighbor) == QUEUE_TYPE_NEW
