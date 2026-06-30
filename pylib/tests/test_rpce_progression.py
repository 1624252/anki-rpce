# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the flashcards -> simulation learning-phase progression."""

from anki import rpce
from anki.rpce import progression, scores
from tests.shared import getEmptyCol


def _study(col, n):
    did = rpce.build_starter_deck(col)
    col.decks.set_current(did)
    col.reset()
    for _ in range(n):
        card = col.sched.getCard()
        if card is None:
            break
        col.sched.answerCard(card, 3)


def test_empty_collection_is_foundations():
    col = getEmptyCol()
    assert progression.current_phase(col).key == "foundations"


def test_transitions_to_application_then_mastery():
    col = getEmptyCol()
    _study(col, 8)  # full coverage + several reviews

    rule = dict(foundations_reviews=5, min_coverage=0.5, application_scenarios=2)

    # Enough reviews + coverage but no scenarios yet -> application.
    phase = progression.current_phase(col, **rule)
    assert phase.key == "application"

    # After grading scenarios, move to mastery.
    scores.record_scenario(col)
    scores.record_scenario(col)
    assert progression.current_phase(col, **rule).key == "mastery"


def test_low_coverage_stays_foundations_even_with_reviews():
    col = getEmptyCol()
    # No deck built -> 0% coverage -> foundations regardless of thresholds.
    phase = progression.current_phase(col, foundations_reviews=0, min_coverage=0.5)
    assert phase.key == "foundations"
