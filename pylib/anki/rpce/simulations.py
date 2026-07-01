# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Simulation mode — a scripted meeting the candidate runs as parliamentarian.

Embodies the Dual-Mode Hybrid Engine (SPOV 2) and the "feedback is the active
ingredient" insight (Insight 4): instead of a single free-text prompt, a
simulation plays out a **meeting** turn by turn — other members and the chair
speak, and at decision points the candidate must **respond as the
parliamentarian**. Each response is graded for accuracy against a model ruling
by the AI examiner (offline placeholder until a key is configured), with an
immediate debrief.

Content is conservative, well-established RONR fundamentals so it ships offline;
richer/AI-authored simulations must pass the gold-set checker first.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import refs


@dataclass(frozen=True)
class SimTurn:
    """One line in the meeting. If ``prompt`` is set, the candidate must respond
    (as parliamentarian) and the response is graded against ``gold``."""

    speaker: str
    line: str
    prompt: str | None = None
    gold: str | None = None
    #: RONR (12th ed.) citation + verbatim quote shown with the model ruling.
    ref: refs.Ref | None = None

    @property
    def needs_response(self) -> bool:
        return self.prompt is not None and self.gold is not None


@dataclass(frozen=True)
class Simulation:
    id: int
    domain_code: int
    title: str
    setting: str
    turns: tuple[SimTurn, ...]


SIMULATIONS: tuple[Simulation, ...] = (
    Simulation(
        1,
        1,
        "New business at the Lakeside Association",
        "You are the parliamentarian at the monthly meeting of the Lakeside "
        "Community Association. The chair turns to new business.",
        (
            SimTurn("Chair", "We'll now move to new business."),
            SimTurn(
                "Member (Ramos)",
                "I move that the Association spend $500 on new signage.",
            ),
            SimTurn(
                "Chair",
                "(turning to you) Before I do anything, what needs to happen with this motion?",
                prompt="Advise the chair: what must happen before this main motion is debated?",
                gold="A main motion requires a second before it is considered. The chair "
                "should call for a second; if seconded, the chair states the question and "
                "opens it to debate. A main motion is adopted by a majority vote.",
                ref=refs.MAJORITY,
            ),
            SimTurn("Member (Chen)", "Second!"),
            SimTurn(
                "Chair",
                "It is moved and seconded that the Association spend $500 on new signage. "
                "Is there any debate?",
            ),
            SimTurn(
                "Member (Ramos)",
                "We've heard enough — I move the previous question!",
                prompt="Advise the chair: how is the motion for the Previous Question handled?",
                gold="The Previous Question needs a second, is not debatable, and requires a "
                "two-thirds vote to adopt. If it passes, debate ends immediately and the "
                "assembly votes on the pending motion.",
                ref=refs.PREVIOUS_QUESTION,
            ),
        ),
    ),
    Simulation(
        2,
        4,
        "A thin house at the Booster Club",
        "The Booster Club meeting is scheduled to start, but only a few members "
        "are present. A member is eager to get going.",
        (
            SimTurn(
                "Member (Doyle)",
                "There aren't many of us, but let's just start adopting motions.",
                prompt="Advise the chair: what must be confirmed before the assembly transacts business?",
                gold="Business cannot be transacted without a quorum present. The chair must "
                "confirm that a quorum, as defined by the bylaws, is present before the "
                "assembly takes any substantive action.",
                ref=refs.QUORUM,
            ),
            SimTurn(
                "Chair",
                "Thank you. We do have a quorum. Proceed.",
            ),
            SimTurn(
                "Member (Ito)",
                "Point of order! I don't think the last speaker was recognized.",
                prompt="Advise the chair: how is a Point of Order handled?",
                gold="A Point of Order needs no second, is not debatable, and is raised at the "
                "time of the breach. The chair rules on the point; the chair's ruling may be "
                "challenged by an Appeal.",
                ref=refs.POINT_OF_ORDER,
            ),
        ),
    ),
    Simulation(
        3,
        5,
        "A close election at the Arts Guild",
        "The Arts Guild is electing its president. The bylaws require a ballot "
        "vote but are silent on the threshold. Three candidates are running.",
        (
            SimTurn(
                "Teller",
                "The results are: Alvarez 40, Brooks 35, Cho 20. Alvarez has the most votes.",
            ),
            SimTurn(
                "Chair",
                "(to you) Alvarez has a plurality. Can I declare Alvarez elected?",
                prompt="Advise the chair: is a plurality enough to elect here?",
                gold="No. Unless the bylaws provide otherwise, election requires a majority — "
                "more than half of the votes cast. A plurality does not elect; balloting "
                "continues until a candidate has a majority.",
                ref=refs.PLURALITY,
            ),
        ),
    ),
)


def all_simulations() -> tuple[Simulation, ...]:
    return SIMULATIONS


def simulation_by_id(sim_id: int) -> Simulation:
    for sim in SIMULATIONS:
        if sim.id == sim_id:
            return sim
    raise KeyError(f"unknown simulation id: {sim_id}")


def response_turns(sim: Simulation) -> list[SimTurn]:
    """The turns in ``sim`` that require a graded parliamentarian response."""
    return [t for t in sim.turns if t.needs_response]
