# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the three RPCE scores and the honest give-up / abstain rule."""

from anki import rpce
from anki.rpce import scores
from tests.shared import getEmptyCol


def test_readiness_snapshots_audit_trail_and_last_updated():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    assert scores.readiness_snapshots(col) == []
    assert scores.last_updated(col) is None

    ts = scores.record_readiness_snapshots(col)
    snaps = scores.readiness_snapshots(col)
    # One snapshot per section (I and II) is appended each time.
    assert len(snaps) == 2
    assert {s["section"] for s in snaps} == {"I", "II"}
    assert all("p_pass" in s and "confidence" in s and "ts" in s for s in snaps)
    assert scores.last_updated(col) == ts

    # A second recording appends, preserving the trail.
    scores.record_readiness_snapshots(col)
    assert len(scores.readiness_snapshots(col)) == 4


def test_memory_score_uses_fsrs_or_falls_back():
    col = getEmptyCol()
    _build_and_study(col, 5)
    mem = scores.memory_score(col)
    # Whether FSRS is on (real retrievability) or off (heuristic fallback), the
    # memory score is a valid probability with a range.
    assert mem.point is not None and 0.0 <= mem.point <= 1.0
    assert mem.low is not None and mem.high is not None


def test_every_score_explains_itself():
    """Spec §4: every score must show the main reasons behind the number."""
    col = getEmptyCol()
    _build_and_study(col, 7)
    summary = scores.readiness_summary(col)
    # Memory + performance carry a non-empty explanation.
    assert len(summary["memory"].explanation) > 20
    assert len(summary["performance"].explanation) > 20
    # Readiness carries its evidence/reasons whether it abstains or not.
    for sec in ("section_I", "section_II"):
        assert len(summary[sec].evidence) > 20


def test_empty_scores_still_explain_the_abstain():
    col = getEmptyCol()
    assert "study" in scores.memory_score(col).explanation.lower()
    assert scores.performance_score(col).explanation


def test_memory_calibration_none_or_well_formed():
    col = getEmptyCol()
    _build_and_study(col, 5)
    cal = scores.memory_calibration(col)
    # None when FSRS predictions aren't available; otherwise valid metrics.
    if cal is not None:
        assert cal["n"] >= 1
        assert 0.0 <= cal["brier"] <= 1.0
        assert cal["log_loss"] >= 0.0
        assert 0.0 <= cal["ece"] <= 1.0


def test_readiness_snapshots_are_capped():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    for _ in range(scores.MAX_SNAPSHOTS):  # 2 snapshots each -> well over the cap
        scores.record_readiness_snapshots(col)
    assert len(scores.readiness_snapshots(col)) == scores.MAX_SNAPSHOTS


def _build_and_study(col, n: int) -> None:
    """Build the starter deck, select it, and answer up to n cards 'Good'."""
    did = rpce.build_starter_deck(col)  # multi-format cards across all 7 domains
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

    # Loosened thresholds so the test doesn't need 200 real reviews. Concept
    # coverage now requires a card's 3 most-recent reviews to be Easy over the 210
    # PE concepts; the curated test deck isn't PE-tagged, so drop the coverage gate
    # here (coverage itself is exercised in test_concept_coverage_*).
    rule = scores.GiveUpRule(min_graded_reviews=5, min_coverage=0.0, min_scenarios=1)

    # Section I needs no scenarios -> should produce a number.
    sec1 = scores.readiness(col, "I", rule)
    assert sec1.abstained is False
    assert sec1.p_pass is not None
    assert 0.0 <= sec1.range_low <= sec1.p_pass <= sec1.range_high <= 1.0
    assert 0.0 <= sec1.pct_covered <= 1.0

    # Section II still abstains until a scenario is graded.
    assert scores.readiness(col, "II", rule).abstained is True
    scores.record_scenario(col)
    assert scores.readiness(col, "II", rule).abstained is False


def test_memory_score_reflects_review_history():
    col = getEmptyCol()
    _build_and_study(col, 7)

    mem = scores.memory_score(col)
    assert mem.point is not None
    # Recently passed cards recall well — high whether via real FSRS
    # retrievability (FSRS on) or the reps/lapses heuristic fallback.
    assert 0.6 <= mem.point <= 1.0


def test_readiness_summary_bundles_all_dashboard_data():
    col = getEmptyCol()
    summary = scores.readiness_summary(col)
    assert set(summary) == {
        "memory",
        "performance",
        "section_I",
        "section_II",
        "coverage",
        "confidence_label",
        "elaboration",
    }
    # Fresh collection abstains everywhere and lists all seven domains.
    assert summary["section_I"].abstained is True
    assert summary["section_II"].abstained is True
    assert len(summary["coverage"]) == 7


def test_summary_exposes_confidence_label_and_preparedness_elaboration():
    """Spec §10: the dashboard reads `confidence_label` (contains the word
    'confidence') and `elaboration` (preparedness prose) from the summary."""
    col = getEmptyCol()
    _build_and_study(col, 7)
    summary = scores.readiness_summary(col)
    assert "confidence" in summary["confidence_label"].lower()
    elab = summary["elaboration"]
    assert len(elab) > 20
    # Preparedness-focused, not a description of the calculation.
    assert any(w in elab.lower() for w in ("prepared", "recall", "memory", "study"))
    # Each score object also carries the fields the phone reads per-score.
    for key in ("memory", "performance"):
        assert "confidence" in summary[key].confidence_label.lower()
        assert summary[key].elaboration


def test_best_next_topic_follows_weight_times_gap():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    # Make domain 5 dominate the exam weight; with equal recall it has the
    # largest weight × gap, so it should be the recommended next topic.
    rpce.set_domain_weights(col, {d.code: 0.05 for d in rpce.DOMAINS} | {5: 0.7})

    assert scores.best_next_topic(col) == rpce.domain_by_code(5).name
