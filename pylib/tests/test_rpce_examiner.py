# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the AI Examiner: grounding/citation, baseline, eval, leakage."""

from anki.rpce import examiner as ex

# Small stand-in for the RONR corpus; the real app uses
# data/roberts_rules_of_order_12th_edition.md.
CORPUS = """\
The motion for the Previous Question requires a two-thirds vote and is not
debatable. See RONR (12th ed.) 16:1-16:5.

A main motion requires a second and a majority vote to adopt. 10:1.

Unrelated paragraph about scheduling and minutes with no citation here.
"""


def test_retrieve_grounds_in_corpus_with_citation():
    passages = ex.retrieve(CORPUS, "previous question two-thirds vote", k=1)
    assert passages, "should find a supporting passage"
    assert passages[0].citation == "16:1-16:5"


def test_retrieve_returns_nothing_for_unrelated_query():
    assert ex.retrieve(CORPUS, "xylophone quantum", k=1) == []


def test_baseline_passes_a_good_answer_and_cites():
    examiner = ex.BaselineExaminer(pass_score=3.0)
    result = examiner.grade(
        answer="The previous question needs a two-thirds vote and is not debatable.",
        gold_answer="Previous Question requires a two-thirds vote and is not debatable.",
        corpus=CORPUS,
    )
    assert result.passed is True
    assert result.abstained is False
    assert result.citation == "16:1-16:5"
    assert 0.0 <= result.score <= 5.0


def test_baseline_abstains_when_no_supporting_passage():
    examiner = ex.BaselineExaminer()
    result = examiner.grade(
        answer="something",
        gold_answer="a rule about xylophones not in the corpus",
        corpus=CORPUS,
    )
    assert result.abstained is True
    assert result.citation is None


def test_evaluate_reports_accuracy_against_cutoff():
    examiner = ex.BaselineExaminer(pass_score=2.0)
    gold = [
        ex.GoldItem(
            prompt="What vote does the Previous Question need?",
            gold_answer="Previous Question requires a two-thirds vote and is not debatable.",
            correct_answer="A two-thirds vote; it is not debatable.",
        ),
        ex.GoldItem(
            prompt="What does a main motion need?",
            gold_answer="A main motion requires a second and a majority vote.",
            correct_answer="It needs a second and a majority vote.",
        ),
    ]
    result = ex.evaluate(examiner, gold, CORPUS, accuracy_cutoff=0.5)
    assert result.total == 2
    assert result.accuracy >= 0.5
    assert result.passed_cutoff is True


def test_find_leaks_flags_near_duplicates_and_passes_when_clean():
    train = ["The Previous Question requires a two-thirds vote and is not debatable."]
    # Near-identical to a held-out item -> must be flagged.
    leaky_test = ["Previous Question requires a two-thirds vote and is not debatable!"]
    assert ex.find_leaks(train, leaky_test, threshold=0.8)

    clean_test = ["A committee reports its recommendations to the assembly."]
    assert ex.find_leaks(train, clean_test, threshold=0.8) == []
