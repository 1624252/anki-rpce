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
    # Each concept yields a cloze + an mcq card, so every domain has >= 2.
    assert all(c.cards >= 2 for c in cov), "each domain gets cloze + mcq cards"
    assert rpce.coverage_pct(col) == 1.0


def test_starter_deck_has_multiple_formats_per_concept():
    col = getEmptyCol()
    rpce.build_starter_deck(col)

    # Same content surfaces in more than one format (cloze recall + applied MCQ).
    assert col.find_cards("tag:rpce::fmt::cloze"), "cloze cards exist"
    assert col.find_cards("tag:rpce::fmt::mcq"), "multiple-choice cards exist"


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
