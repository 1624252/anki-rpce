# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for Simulation mode (scripted meetings graded by the examiner)."""

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


def test_response_turns_cite_ronr_with_a_quote():
    import re

    for sim in simulations.all_simulations():
        for turn in simulations.response_turns(sim):
            assert turn.ref is not None, turn.prompt
            assert re.fullmatch(r"\d+:\d+", turn.ref.section), turn.ref.section
            assert len(turn.ref.quote.strip()) > 20


def test_narration_turns_are_not_graded():
    sim = simulations.simulation_by_id(1)
    narration = [t for t in sim.turns if not t.needs_response]
    assert narration, "a meeting has spoken lines that are not response points"
    for turn in narration:
        assert turn.prompt is None


def test_examiner_grades_a_good_response_as_passing():
    # A response that matches the model ruling should pass the placeholder grader.
    turn = simulations.response_turns(simulations.simulation_by_id(1))[0]
    result = PlaceholderExaminer().grade(turn.gold, turn.gold, turn.gold)
    assert result.passed and not result.abstained


def test_simulation_by_id_unknown_raises():
    with pytest.raises(KeyError):
        simulations.simulation_by_id(9999)
