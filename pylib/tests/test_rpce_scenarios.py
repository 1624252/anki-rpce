# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the Section II scenario set and examiner integration."""

import re

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


def test_every_scenario_cites_ronr_with_a_quote():
    import re

    # RONR citations are section:paragraph, allowing a range "15-16" and a
    # sub-item that may be a number or a letter (e.g. "10:26(4)", "6:15-16",
    # "50:13(d)"). A scenario either carries a full RONR citation (section +
    # verbatim quote) OR is grounded in a professional-practice concept that RONR
    # does not cover (Code of Professional Responsibility, fees, adult-learning /
    # SMART goals), in which case it has no RONR section and no quote — forcing a
    # RONR cite there would be a fabrication.
    pat = re.compile(r"\d+:\d+(?:-\d+)?(?:\([0-9a-z]+\))?")
    for s in scenarios.all_scenarios():
        if s.ref.section:
            assert pat.fullmatch(s.ref.section), s.ref.section
            assert len(s.ref.quote.strip()) > 20, s.ref.section
        else:
            # RONR-less scenarios must still be concept-tagged (labelled/scored
            # by concept) and carry no quote.
            assert s.concept, "RONR-less scenario must still name its concept"
            assert not s.ref.quote.strip()


def test_every_scenario_is_concept_tagged():
    # Section II is labelled + scored by concept (docs/rpce/SCORING.md).
    for s in scenarios.all_scenarios():
        assert re.fullmatch(r"\d+\.\d+", s.concept), s.concept


def test_scenario_bank_is_large_and_covers_concepts():
    # Spec (4): at least 500 scenarios. We author 3 per concept.
    all_s = scenarios.all_scenarios()
    assert len(all_s) >= 500, len(all_s)
    per = {}
    for s in all_s:
        per[s.concept] = per.get(s.concept, 0) + 1
    assert len(per) >= 200, len(per)  # essentially every concept represented


def test_baseline_examiner_grades_a_scenario_answer():
    # Self-contained gold ruling (Previous Question) so the test is independent
    # of which authored scenario happens to be first.
    gold = (
        "The Previous Question needs a second, is not debatable, and requires a "
        "two-thirds vote to adopt."
    )
    ex = examiner.BaselineExaminer(pass_score=2.0)
    # A strong answer should score well against the gold ruling.
    good = ex.grade(
        "It needs a second, is not debatable, and takes a two-thirds vote.",
        gold,
        corpus=gold,  # use gold as a stand-in corpus for grounding
    )
    assert good.score > 0
    # A clearly wrong answer should score lower than the good one.
    weak = ex.grade("Just let them keep talking.", gold, corpus=gold)
    assert weak.score < good.score
