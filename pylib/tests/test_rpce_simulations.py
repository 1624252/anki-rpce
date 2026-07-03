# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for Simulation mode (scripted meetings graded by the examiner)."""

import re

import pytest

from anki.rpce import DOMAINS, simulations
from anki.rpce.examiner import PlaceholderExaminer


def _domain_codes():
    return {d.code for d in DOMAINS}


def test_every_simulation_is_well_formed():
    sims = simulations.all_simulations()
    assert sims, "there should be at least one simulation"
    for sim in sims:
        assert sim.domain_code in _domain_codes()
        assert sim.title and sim.setting
        assert sim.turns, "a simulation has turns"
        # Every simulation needs at least one graded response point.
        assert simulations.response_turns(sim), "needs a parliamentarian response"


def test_response_turns_carry_prompt_and_gold():
    for sim in simulations.all_simulations():
        for turn in simulations.response_turns(sim):
            assert turn.needs_response
            assert turn.prompt and turn.gold


def test_response_turns_cite_ronr_or_are_ronr_less():
    import re

    for sim in simulations.all_simulations():
        for turn in simulations.response_turns(sim):
            if turn.ref is not None and turn.ref.section:
                # section:paragraph, optionally with sub-item/range detail
                # (e.g. "24:3(2)", "35:2(3-5)", "16:5(8)n15").
                assert re.match(r"\d+:\d+", turn.ref.section), turn.ref.section
                assert len(turn.ref.quote.strip()) > 20
            else:
                # Professional-practice concepts RONR does not cover carry no cite;
                # they must still be concept-tagged.
                assert turn.concept, turn.prompt


def test_every_sim_at_most_10_turns_and_concept_tagged():
    for sim in simulations.all_simulations():
        assert len(sim.turns) <= 10, (sim.id, len(sim.turns))
        for turn in simulations.response_turns(sim):
            assert re.fullmatch(r"\d+\.\d+", turn.concept), turn.concept


def test_narration_turns_are_not_graded():
    sim = simulations.all_simulations()[0]
    narration = [t for t in sim.turns if not t.needs_response]
    for turn in narration:
        assert turn.prompt is None


def test_examiner_grades_a_good_response_as_passing():
    # A response that matches the model ruling should pass the placeholder grader.
    turn = simulations.response_turns(simulations.all_simulations()[0])[0]
    result = PlaceholderExaminer().grade(turn.gold, turn.gold, turn.gold)
    assert result.passed and not result.abstained


def test_simulation_by_id_unknown_raises():
    with pytest.raises(KeyError):
        simulations.simulation_by_id(9999)
