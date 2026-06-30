# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the Section II scenario set and examiner integration."""

from anki import rpce
from anki.rpce import examiner, scenarios


def test_every_domain_has_at_least_one_scenario():
    for domain in rpce.DOMAINS:
        assert scenarios.scenarios_for(domain.code), (
            f"domain {domain.code} needs a scenario"
        )


def test_scenarios_have_prompt_and_gold_answer():
    for s in scenarios.all_scenarios():
        assert s.prompt.strip()
        assert s.gold_answer.strip()


def test_baseline_examiner_grades_a_scenario_answer():
    s = scenarios.scenarios_for(2)[0]  # Previous Question -> two-thirds vote
    ex = examiner.BaselineExaminer(pass_score=2.0)
    # A strong answer should score well against the gold ruling.
    good = ex.grade(
        "It needs a second, is not debatable, and takes a two-thirds vote.",
        s.gold_answer,
        corpus=s.gold_answer,  # use gold as a stand-in corpus for grounding
    )
    assert good.score > 0
    # A clearly wrong answer should score lower than the good one.
    weak = ex.grade("Just let them keep talking.", s.gold_answer, corpus=s.gold_answer)
    assert weak.score < good.score
