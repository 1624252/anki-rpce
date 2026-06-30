# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the Transfer Ladder format-rotation logic (Spiky POV 1)."""

import pytest

from anki.rpce import transfer_ladder as tl


def test_rungs_ascend_in_transfer_demand():
    assert tl.RUNGS == ("cloze", "mcq", "scenario", "advising")


def test_high_mastery_advances_to_next_format():
    assert tl.next_rung("cloze", mastery=0.9) == "mcq"
    assert tl.next_rung("mcq", mastery=0.9) == "scenario"
    assert tl.next_rung("scenario", mastery=0.9) == "advising"
    # Top rung holds (nothing higher to climb to).
    assert tl.next_rung("advising", mastery=0.99) == "advising"


def test_low_mastery_holds_and_lapse_drops_a_rung():
    assert tl.next_rung("scenario", mastery=0.5) == "scenario"  # hold
    assert tl.next_rung("scenario", mastery=0.9, lapsed=True) == "mcq"  # drop
    assert tl.next_rung("cloze", mastery=0.2, lapsed=True) == "cloze"  # floor


def test_recommended_rung_starts_at_cloze_then_progresses():
    assert tl.recommended_rung([]) == "cloze"
    # Strong recall on cloze => advance to mcq, not repeat cloze.
    assert tl.recommended_rung([("cloze", 0.95)]) == "mcq"
    # A failed scenario (recall < 0.5) re-scaffolds to mcq.
    assert tl.recommended_rung([("scenario", 0.3)]) == "mcq"


def test_does_not_repeat_format_when_progressing():
    history = [("cloze", 0.95)]
    proposed = tl.recommended_rung(history)
    assert not tl.is_format_repeat(history, proposed), "should vary the format"


def test_format_tag_validation():
    assert tl.format_tag("scenario") == "rpce::fmt::scenario"
    assert tl.concept_tag(7) == "rpce::concept::7"
    with pytest.raises(ValueError):
        tl.format_tag("essay")


def test_rung_of_tags():
    assert tl.rung_of_tags(["rpce::domain::1", "rpce::fmt::scenario"]) == "scenario"
    assert tl.rung_of_tags(["rpce::domain::1"]) is None
    assert tl.rung_of_tags(["rpce::fmt::bogus"]) is None


def test_record_review_tallies_by_rung():
    from tests.shared import getEmptyCol

    col = getEmptyCol()
    assert tl.record_review(col, ["rpce::fmt::cloze"]) == "cloze"
    assert tl.record_review(col, ["rpce::fmt::cloze"]) == "cloze"
    assert tl.record_review(col, ["rpce::fmt::mcq"]) == "mcq"
    # A card with no format tag is not tallied.
    assert tl.record_review(col, ["rpce::domain::2"]) is None
    tally = col.get_config(tl.FORMAT_REVIEWS_KEY)
    assert tally == {"cloze": 2, "mcq": 1}
