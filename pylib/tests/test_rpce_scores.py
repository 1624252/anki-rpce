# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the three RPCE scores and the honest give-up / abstain rule."""

from anki import rpce
from anki.rpce import scores
from tests.shared import getEmptyCol


def _build_and_study(col, n: int) -> None:
    """Build the starter deck, select it, and answer up to n cards 'Good'."""
    did = rpce.build_starter_deck(col, cards_per_domain=1)  # 7 cards, all domains
    col.decks.set_current(did)
    col.reset()
    for _ in range(n):
        card = col.sched.getCard()
        if card is None:
            break
        col.sched.answerCard(card, 3)  # 3 == Good


def test_memory_and_readiness_abstain_on_empty_collection():
    col = getEmptyCol()

    assert scores.memory_score(col).confidence == scores.CONFIDENCE_ABSTAIN
    snap = scores.readiness(col, "I")
    assert snap.abstained is True
    assert snap.p_pass is None
    assert "graded reviews" in snap.evidence


def test_readiness_unlocks_when_give_up_rule_met():
    col = getEmptyCol()
    _build_and_study(col, 7)

    # Loosened thresholds so the test doesn't need 200 real reviews.
    rule = scores.GiveUpRule(min_graded_reviews=5, min_coverage=0.5, min_scenarios=1)

    # Section I needs no scenarios -> should produce a number.
    sec1 = scores.readiness(col, "I", rule)
    assert sec1.abstained is False
    assert sec1.p_pass is not None
    assert 0.0 <= sec1.range_low <= sec1.p_pass <= sec1.range_high <= 1.0
    assert sec1.pct_covered == 1.0

    # Section II still abstains until a scenario is graded.
    assert scores.readiness(col, "II", rule).abstained is True
    scores.record_scenario(col)
    assert scores.readiness(col, "II", rule).abstained is False


def test_memory_score_reflects_review_history():
    col = getEmptyCol()
    _build_and_study(col, 7)

    mem = scores.memory_score(col)
    assert mem.point is not None
    # One Good answer => recall estimate (1-0+1)/(1+2) ≈ 0.667 per card.
    assert 0.6 <= mem.point <= 0.72


def test_readiness_summary_bundles_all_dashboard_data():
    col = getEmptyCol()
    summary = scores.readiness_summary(col)
    assert set(summary) == {
        "memory",
        "performance",
        "section_I",
        "section_II",
        "coverage",
    }
    # Fresh collection abstains everywhere and lists all seven domains.
    assert summary["section_I"].abstained is True
    assert summary["section_II"].abstained is True
    assert len(summary["coverage"]) == 7


def test_best_next_topic_follows_weight_times_gap():
    col = getEmptyCol()
    rpce.build_starter_deck(col, cards_per_domain=1)
    # Make domain 5 dominate the exam weight; with equal recall it has the
    # largest weight × gap, so it should be the recommended next topic.
    rpce.set_domain_weights(col, {d.code: 0.05 for d in rpce.DOMAINS} | {5: 0.7})

    assert scores.best_next_topic(col) == rpce.domain_by_code(5).name
