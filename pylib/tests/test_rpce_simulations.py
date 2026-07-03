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


# --- AI generation grounded in the quote bank ---------------------------------

_QUOTES = [
    {"section": "6:1", "quote": "A main motion brings business before the assembly."},
    {"section": "44:1", "quote": "The basic requirement is a majority vote."},
]


def _fake_reply(monkeypatch, obj):
    from anki.rpce import ai

    monkeypatch.setattr(ai, "chat_json", lambda *a, **k: obj)


def test_generate_simulation_attaches_bank_quote_by_id(monkeypatch):
    from anki.rpce import ai

    # The model picks Q2 but supplies a WRONG cite/quote — we must override with
    # our verbatim bank quote for Q2 (traceable source).
    _fake_reply(
        monkeypatch,
        {
            "title": "T",
            "setting": "S",
            "turns": [
                {"speaker": "Chair", "line": "Order."},
                {
                    "decision": "What vote adopts this?",
                    "gold": "A majority.",
                    "quote_id": "Q2",
                    "cite": "99:9",
                    "quote": "WRONG",
                },
            ],
        },
    )
    obj = ai.generate_simulation(_QUOTES)
    dec = [t for t in obj["turns"] if t.get("decision")][0]
    assert dec["cite"] == "44:1"
    assert dec["quote"] == _QUOTES[1]["quote"]


def test_generate_simulation_bad_quote_id_falls_back_to_first(monkeypatch):
    from anki.rpce import ai

    _fake_reply(
        monkeypatch,
        {
            "title": "T",
            "setting": "S",
            "turns": [{"decision": "d", "gold": "g", "quote_id": "Q99"}],
        },
    )
    obj = ai.generate_simulation(_QUOTES)
    dec = [t for t in obj["turns"] if t.get("decision")][0]
    assert dec["cite"] == "6:1"  # first supplied quote


def test_generate_simulation_no_quotes_returns_none():
    from anki.rpce import ai

    assert ai.generate_simulation([]) is None


def test_generate_simulation_malformed_reply_returns_none(monkeypatch):
    from anki.rpce import ai

    _fake_reply(monkeypatch, {"title": "T"})  # no turns
    assert ai.generate_simulation(_QUOTES) is None


def test_continue_simulation_resolves_quote_and_adjourn(monkeypatch):
    from anki.rpce import ai

    _fake_reply(
        monkeypatch,
        {
            "turns": [{"decision": "d", "gold": "g", "quote_id": "Q1"}],
            "adjourned": True,
        },
    )
    obj = ai.continue_simulation("history", "ruling", _QUOTES)
    assert obj["adjourned"] is True
    assert obj["turns"][0]["cite"] == "6:1"
