# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the canonical order of precedence and its dedicated question types
(ordering + multiselect), which replace the old precedence cloze (spec §15)."""

import base64
import json

from anki import rpce
from anki.rpce import knowledge as kb
from tests.shared import getEmptyCol


def test_canonical_order_matches_ranked_motions():
    assert kb.PRECEDENCE_ORDER == tuple(m.name for m in kb.ranked_motions())
    # Highest precedence first.
    assert kb.PRECEDENCE_ORDER[0] == "Fix the Time to Which to Adjourn"
    assert kb.PRECEDENCE_ORDER[-1] == "Postpone Indefinitely"


def test_is_ordered_by_precedence_verifies_any_subset():
    subset = ["Recess", "Amend", "Adjourn"]
    assert not kb.is_ordered_by_precedence(subset)
    assert kb.is_ordered_by_precedence(kb.canonical_order(subset))


def test_higher_and_lower_than_pivot_against_canon():
    pool = ["Adjourn", "Amend", "Lay on the Table", "Recess"]
    assert kb.motions_higher_than("Lay on the Table", pool) == ["Adjourn", "Recess"]
    assert kb.motions_lower_than("Lay on the Table", pool) == ["Amend"]


def _payload(col, cid):
    return json.loads(base64.b64decode(col.get_card(cid).note()["Payload"]))


def test_starter_deck_has_precedence_ordering_and_multiselect():
    col = getEmptyCol()
    rpce.build_starter_deck(col)

    order_cards = col.find_cards(f"tag:rpce::fmt::{rpce.KIND_ORDER}")
    multi_cards = col.find_cards(f"tag:rpce::fmt::{rpce.KIND_MULTI}")
    assert order_cards and multi_cards

    # Every ordering payload is a valid canonical order for its subset.
    for cid in order_cards:
        p = _payload(col, cid)
        assert len(p["order"]) >= 3
        assert kb.is_ordered_by_precedence(p["order"])

    # Every multiselect has a non-trivial correct subset (some but not all).
    for cid in multi_cards:
        p = _payload(col, cid)
        n = len(p["options"])
        assert 1 <= len(p["correct"]) < n


def test_no_precedence_cloze_survives():
    from anki.rpce import flashcards

    # The curated cloze content no longer teaches precedence as a fill-in blank.
    for f in flashcards.all_flashcards():
        assert "precedence" not in f.cloze.lower()

    col = getEmptyCol()
    rpce.build_starter_deck(col)
    seen = set()
    for cid in col.find_cards(f'note:"{rpce.CONCEPT_NOTETYPE}"'):
        note = col.get_card(cid).note()
        cp = note["ClozePayload"]
        if cp and cp not in seen:
            seen.add(cp)
            text = json.loads(base64.b64decode(cp))["text"]
            assert "precedence" not in text.lower()
