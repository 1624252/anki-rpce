# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the AI Examiner: grounding/citation, baseline, eval, leakage."""

from anki.rpce import examiner as ex
from anki.rpce import scenarios

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


def test_llm_examiner_grades_via_injected_call_and_cites():
    def fake_call(_prompt: str) -> str:
        return 'Sure: {"score": 4, "feedback": "Correct on the two-thirds vote."} done'

    examiner = ex.LLMExaminer(fake_call, pass_score=3.0)
    result = examiner.grade(
        "two-thirds vote, not debatable",
        "Previous Question requires a two-thirds vote and is not debatable.",
        CORPUS,
    )
    assert result.passed is True
    assert result.score == 4.0
    assert result.citation == "16:1-16:5"
    assert result.abstained is False


def test_llm_examiner_abstains_without_supporting_passage():
    examiner = ex.LLMExaminer(lambda _p: '{"score":5,"feedback":"x"}')
    result = examiner.grade("anything", "rule about xylophones not present", CORPUS)
    assert result.abstained is True


def test_llm_examiner_abstains_on_malformed_output():
    examiner = ex.LLMExaminer(lambda _p: "not json at all")
    result = examiner.grade(
        "two-thirds", "Previous Question requires a two-thirds vote.", CORPUS
    )
    assert result.abstained is True


def test_make_examiner_returns_auto_and_falls_back_offline(monkeypatch):
    from anki.rpce import ai

    # No key anywhere -> AutoExaminer must grade via the offline KeywordExaminer.
    monkeypatch.setattr(ai, "ai_configured", lambda: False)
    auto = ex.make_examiner()
    assert isinstance(auto, ex.AutoExaminer)
    r = auto.grade(
        "The Previous Question needs a two-thirds vote.",
        "Previous Question requires a two-thirds vote.",
        CORPUS,
    )
    assert auto.used == "offline" and not r.abstained and r.score > 0
    # Providing a call_fn opts straight into the LLM examiner.
    assert isinstance(ex.make_examiner(lambda _p: "{}"), ex.LLMExaminer)


def test_auto_examiner_falls_back_when_ai_call_fails(monkeypatch):
    from anki.rpce import ai

    # Key present but the API returns nothing (offline / rate-limited / bad
    # output) -> AutoExaminer still grades offline, never abstains (spec §7g).
    monkeypatch.setattr(ai, "ai_configured", lambda: True)
    monkeypatch.setattr(ai, "chat_json", lambda *a, **k: None)
    auto = ex.make_examiner()
    r = auto.grade(
        "The Previous Question needs a two-thirds vote.",
        "Previous Question requires a two-thirds vote.",
        CORPUS,
    )
    assert auto.used == "offline" and not r.abstained and r.score > 0


def test_offline_grader_distinguishes_second_polarity():
    """Spec §12: 'no second' must not match a positive 'second'. The offline
    grader keys on positive phrases (second / no debate / two-thirds)."""
    examiner = ex.BaselineExaminer(pass_score=2.5)
    corpus = "A Point of Order needs no second and is not debatable. 23:1."
    gold = "A Point of Order needs no second and is not debatable."
    right = examiner.grade("It needs no second and is not debatable.", gold, corpus)
    wrong = examiner.grade("It requires a second and is debatable.", gold, corpus)
    assert right.score > wrong.score
    assert right.passed and not wrong.passed


def test_positive_phrase_keywords_normalize():
    # 'two-thirds' is one positive keyword (not split on the hyphen).
    assert "twothirds" in ex._tokens("a two-thirds vote")
    assert "twothirds" in ex._tokens("two thirds")
    # 'no debate' and 'not debatable' collapse to the same positive keyword.
    assert ex._tokens("no debate") == ex._tokens("not debatable")
    # 'no second' is its own keyword, distinct from a positive 'second'.
    assert ex._tokens("no second") != ex._tokens("a second")


# --- KeywordExaminer: rubric grading (alias + stemmer + forbidden penalty) ---

# A Previous Question rubric authored explicitly for these tests.
_PQ_RUBRIC = ex.Rubric(
    (
        ex.RubricElement(
            "the motion",
            ("previousquestion",),
            weight=2.0,
            essential=True,
            expects="the Previous Question",
        ),
        ex.RubricElement(
            "the vote threshold",
            ("twothirds",),
            weight=2.0,
            essential=True,
            forbidden=("majority",),
            expects="two-thirds",
        ),
        ex.RubricElement(
            "the second", ("second",), forbidden=("nosecond",), expects="a second"
        ),
        ex.RubricElement(
            "debatability",
            ("nodebate",),
            forbidden=("debatable",),
            expects="not debatable",
        ),
    )
)
_PQ_GOLD = "The Previous Question needs a second, is not debatable, and requires a two-thirds vote."


def test_keyword_examiner_passes_a_correct_ruling_with_high_score():
    kw = ex.KeywordExaminer(pass_score=3.0)
    r = kw.grade(
        "The previous question needs a second, is not debatable, and takes a two-thirds vote.",
        _PQ_GOLD,
        CORPUS,
        _PQ_RUBRIC,
    )
    assert r.passed and not r.abstained
    assert r.score >= 4.5
    assert r.citation == "16:1-16:5"


def test_keyword_examiner_fails_wrong_threshold_on_forbidden_penalty():
    kw = ex.KeywordExaminer(pass_score=3.0)
    # Says "majority" for a two-thirds motion: lots of overlap, but the forbidden
    # twin + the missed essential threshold must sink it below a pass.
    wrong = kw.grade(
        "The previous question needs a second, is not debatable, and takes a majority vote.",
        _PQ_GOLD,
        CORPUS,
        _PQ_RUBRIC,
    )
    assert not wrong.passed
    assert wrong.score < 3.0
    assert "two-thirds" in wrong.feedback
    # An overlap-only grader would reward the shared words; the rubric grader
    # scores the wrong answer strictly below the correct one.
    right = kw.grade(
        "The previous question needs a second, is not debatable, and takes a two-thirds vote.",
        _PQ_GOLD,
        CORPUS,
        _PQ_RUBRIC,
    )
    assert wrong.score < right.score


def test_keyword_examiner_gives_partial_credit_with_breakdown():
    kw = ex.KeywordExaminer(pass_score=3.0)
    r = kw.grade(
        "The previous question requires a two-thirds vote.",
        _PQ_GOLD,
        CORPUS,
        _PQ_RUBRIC,
    )
    assert 0.0 < r.score < 5.0
    # Per-element breakdown names what was identified and what wasn't addressed.
    assert "the motion" in r.feedback
    assert "the vote threshold" in r.feedback
    assert "Didn't address" in r.feedback and "the second" in r.feedback


def test_keyword_examiner_empty_and_irrelevant_answers_score_low():
    kw = ex.KeywordExaminer(pass_score=3.0)
    empty = kw.grade("", _PQ_GOLD, CORPUS, _PQ_RUBRIC)
    assert empty.score == 0.0 and not empty.passed
    irrelevant = kw.grade("The weather is lovely today.", _PQ_GOLD, CORPUS, _PQ_RUBRIC)
    assert irrelevant.score == 0.0 and not irrelevant.passed


def test_keyword_examiner_abstains_without_supporting_passage():
    kw = ex.KeywordExaminer()
    r = kw.grade("two-thirds vote", "a rule about xylophones not in the corpus", CORPUS)
    assert r.abstained is True
    assert r.citation is None


def test_keyword_examiner_matches_synonyms_and_paraphrases():
    kw = ex.KeywordExaminer(pass_score=3.0)
    main_gold = "A main motion requires a second and a majority vote to adopt."
    rubric = ex.Rubric(
        (
            ex.RubricElement(
                "the second",
                ("second",),
                weight=2.0,
                essential=True,
                forbidden=("nosecond",),
                expects="a second",
            ),
            ex.RubricElement(
                "the vote threshold",
                ("majority",),
                weight=2.0,
                essential=True,
                forbidden=("twothirds",),
                expects="a majority",
            ),
        )
    )
    # "more than half" == majority; "seconded" == second (via the alias table).
    r = kw.grade(
        "It must be seconded and pass by more than half of the votes.",
        main_gold,
        CORPUS,
        rubric,
    )
    assert r.passed and r.score >= 4.0


def test_keyword_examiner_derives_rubric_when_none_supplied():
    # No explicit rubric: one is derived from the gold ruling, and the forbidden
    # twin still fires (majority when the gold says two-thirds).
    kw = ex.KeywordExaminer(pass_score=3.0)
    right = kw.grade("It requires a two-thirds vote.", _PQ_GOLD, CORPUS)
    wrong = kw.grade("It requires a majority vote.", _PQ_GOLD, CORPUS)
    assert right.score > wrong.score
    assert not wrong.passed


def test_light_stemmer_collapses_morphology():
    assert ex._stem("adjournment") == ex._stem("adjourned") == "adjourn"
    assert ex._stem("amendable") == ex._stem("amendment") == "amend"


def test_alias_table_folds_thresholds_and_phrases():
    seq = ex._canon_seq("a 2/3 vote on the previous question")
    assert "twothirds" in seq
    assert "previousquestion" in seq
    assert "majority" in ex._canon_seq("more than half of those voting")


def test_scenario_rubric_grades_the_curated_scenario():
    # An explicit Previous Question rubric fails a wrong-threshold answer (the
    # shared RUBRIC_PREVIOUS_QUESTION the simulation turns use).
    rubric = scenarios.RUBRIC_PREVIOUS_QUESTION
    gold = (
        "The Previous Question needs a second, is not debatable, and requires a "
        "two-thirds vote to adopt."
    )
    kw = ex.KeywordExaminer(pass_score=3.0)
    r = kw.grade(
        "The previous question just needs a majority vote.", gold, gold, rubric
    )
    assert not r.passed


def test_find_leaks_flags_near_duplicates_and_passes_when_clean():
    train = ["The Previous Question requires a two-thirds vote and is not debatable."]
    # Near-identical to a held-out item -> must be flagged.
    leaky_test = ["Previous Question requires a two-thirds vote and is not debatable!"]
    assert ex.find_leaks(train, leaky_test, threshold=0.8)

    clean_test = ["A committee reports its recommendations to the assembly."]
    assert ex.find_leaks(train, clean_test, threshold=0.8) == []
