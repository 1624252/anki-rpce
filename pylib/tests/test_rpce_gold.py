# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the gold-set eval parser + evaluation (spec §7e/§7f/§9)."""

from anki.rpce import gold

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
    from anki.rpce import examiner

    leaks = examiner.find_leaks(train, [leaked_prompt], threshold=0.8)
    assert leaks, "an item copied from training must be flagged as a leak"
