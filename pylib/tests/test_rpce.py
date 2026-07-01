# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the RPCE content model (domains, tags, coverage, weights)."""

from anki import rpce
from tests.shared import getEmptyCol


def test_seven_domains_with_normalized_default_weights():
    assert len(rpce.DOMAINS) == 7
    total = sum(d.weight for d in rpce.DOMAINS)
    assert abs(total - 1.0) < 1e-9, "default domain weights should sum to 1.0"


def test_starter_deck_populates_every_domain():
    col = getEmptyCol()
    rpce.build_starter_deck(col)

    cov = rpce.coverage(col)
    assert len(cov) == 7
    # One concept card per domain (the same problem, one schedule).
    assert all(c.cards >= 1 for c in cov), "each domain gets a concept card"
    assert rpce.coverage_pct(col) == 1.0


def test_concept_becomes_cloze_and_mcq_questions():
    col = getEmptyCol()
    rpce.build_starter_deck(col)

    # Each curated concept yields two question notes: a cloze and an applied MCQ.
    from anki.rpce import flashcards

    assert col.card_count() == 2 * len(flashcards.all_flashcards())
    cids = col.find_cards("tag:rpce::concept::101")
    assert len(cids) == 2
    kinds = {col.get_card(c).note()["Kind"] for c in cids}
    assert kinds == {rpce.KIND_CLOZE, rpce.KIND_MCQ}
    for c in cids:
        note = col.get_card(c).note()
        assert note["Payload"], "render payload present"
        assert note["PlainQ"] and note["PlainA"], "no-JS fallback present"


def test_every_concept_card_carries_ronr_citation_and_quote():
    import re

    col = getEmptyCol()
    rpce.build_starter_deck(col)
    for cid in col.find_cards("deck:RPCE"):
        note = col.get_card(cid).note()
        assert re.fullmatch(r"\d+:\d+", note["Citation"]), note["Citation"]
        assert len(note["Quote"].strip()) > 20, note["Citation"]


def test_topic_weights_round_trip_through_config():
    col = getEmptyCol()
    # Override two domains; the rest keep their defaults.
    rpce.set_domain_weights(col, {1: 0.5, 2: 0.3})

    weights = rpce.topic_weights(col)
    assert weights[rpce.domain_tag(1)] == 0.5
    assert weights[rpce.domain_tag(2)] == 0.3
    # An unset domain falls back to its default weight.
    assert abs(weights[rpce.domain_tag(3)] - (1.0 / 7.0)) < 1e-9


def test_topic_weights_feed_points_at_stake_queue():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    rpce.set_domain_weights(col, {dom.code: 0.1 for dom in rpce.DOMAINS} | {7: 0.9})

    # Make every card due so the queue gathers them.
    col._backend.set_due_date(card_ids=col.find_cards(""), days="0", config_key=None)

    entries = col._backend.get_points_at_stake_queue(
        topic_weights=rpce.topic_weights(col),
        default_weight=0.0,
        limit=0,
    )
    assert entries, "queue should return due cards"
    # Domain 7 has the highest weight, so its card must rank first.
    assert entries[0].matched_tag == rpce.domain_tag(7)
