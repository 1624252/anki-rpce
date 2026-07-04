# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the gold-set eval parser + evaluation (spec §7e/§7f/§9)."""

from pathlib import Path

import pytest

from anki.rpce import examiner, gold, gold_rubrics

# The official sample-question file (resolved from the repo root). Some tests
# need the real gold set; they skip cleanly when it isn't present.
_GOLD_DATA = (
    Path(__file__).resolve().parents[2] / "data" / "RPCE-Sample-Questions-v4-100625.md"
)

# A tiny sample in the official questions' format.
_SAMPLE = """
### Domain 1: Motions in General and Main Motions

**1.** A main motion needs what to be adopted?

   A. A second and a majority vote
   B. Only the mover's support
   C. A two-thirds vote
   D. Unanimous consent

**2.** What ends debate immediately?

   A. A majority vote to adjourn
   B. The Previous Question by a two-thirds vote
   C. A point of order
   D. A single objection

---

**Answer Key for Practice Questions**

1. The correct answer is A. See RONR (12th ed.) 10:11.
2. The correct answer is B. See RONR (12th ed.) 16:1.
"""


def test_parse_gold_extracts_questions_and_correct_answers():
    gs = gold.parse_gold(_SAMPLE)
    assert len(gs) == 2
    q1 = gs[0]
    assert "main motion" in q1.prompt.lower()
    assert q1.correct == "A second and a majority vote"
    assert len(q1.distractors) == 3
    assert "Only the mover's support" in q1.distractors


def test_evaluate_gold_passes_known_correct_and_flags_clean():
    ev = gold.evaluate_gold(_SAMPLE)
    # The examiner passes the known-correct answers (they match the rubric).
    assert ev.total == 2
    assert ev.accuracy == 1.0
    # Distractors should rarely pass; this tiny set stays under the cutoff.
    assert ev.false_pass_rate <= ev.false_pass_cutoff
    # Our study content doesn't contain these gold prompts verbatim.
    assert ev.leaks == 0
    assert ev.ok


def test_leakage_is_caught_when_a_gold_item_is_in_training():
    # A gold prompt that is a near-copy of training content must be flagged.
    train = gold.training_texts()
    leaked_prompt = train[0]

    leaks = examiner.find_leaks(train, [leaked_prompt], threshold=0.8)
    assert leaks, "an item copied from training must be flagged as a leak"


@pytest.mark.skipif(not _GOLD_DATA.exists(), reason="official gold data not present")
def test_every_gold_question_has_a_unique_authored_rubric():
    qs = gold.parse_gold(_GOLD_DATA.read_text(encoding="utf-8"))
    assert len(qs) == 36
    # Every parsed question is covered by an authored rubric.
    for q in qs:
        assert gold_rubrics.authored_rubric(q.correct) is not None, q.correct[:60]
    # Each key anchors to exactly one question (no cross-question collisions).
    for key, _ in gold_rubrics._GOLD_RUBRICS:
        hits = [q for q in qs if key.lower() in q.correct.lower()]
        assert len(hits) == 1, f"key {key!r} matched {len(hits)} questions"


@pytest.mark.skipif(not _GOLD_DATA.exists(), reason="official gold data not present")
def test_gold_tuned_rubrics_beat_the_untuned_offline_grader():
    text = _GOLD_DATA.read_text(encoding="utf-8")
    # Same deterministic offline grader; only the authored rubrics differ.
    tuned = gold.evaluate_gold(
        text, examiner.KeywordExaminer(), use_authored_rubrics=True
    )
    untuned = gold.evaluate_gold(text, examiner.KeywordExaminer())
    assert tuned.accuracy == 1.0
    # Authored rubrics discriminate every distractor on the fitted set.
    assert tuned.false_pass_rate == 0.0
    assert tuned.false_pass_rate < untuned.false_pass_rate
    assert tuned.ok
