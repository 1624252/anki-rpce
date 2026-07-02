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
from .examiner import Rubric
from .scenarios import (
    RUBRIC_MAIN_MOTION,
    RUBRIC_PLURALITY,
    RUBRIC_POINT_OF_ORDER,
    RUBRIC_PREVIOUS_QUESTION,
    RUBRIC_QUORUM,
)


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
    #: Per-element grading rubric for this decision point (shared with the
    #: matching Section II scenario); ``None`` -> derived from ``gold``.
    rubric: Rubric | None = None
    #: Simulation is SHORT / step-by-step: the key concept(s) this step tests, as
    #: groups of accepted synonyms. Graded leniently by ``grade_sim_step`` — a
    #: brief correct reply gets full credit. ``()`` -> any non-empty reply passes.
    expected: tuple[tuple[str, ...], ...] = ()

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
                "opens it to debate.",
                ref=refs.MAJORITY,
                rubric=RUBRIC_MAIN_MOTION,
                expected=(("second",),),
            ),
            SimTurn("Member (Chen)", "Second!"),
            SimTurn(
                "Chair",
                "It is moved and seconded to spend $500 on new signage. Is there any debate?",
            ),
            SimTurn(
                "Member (Park)",
                "I move to amend by striking out '$500' and inserting '$750'.",
                prompt="Advise the chair: how is this amendment handled, and what vote does it need?",
                gold="The amendment needs a second and must be germane to the motion. It is "
                "debatable and is adopted by a majority vote — even though the main motion "
                "might require a different threshold, an amendment needs only a majority.",
                ref=refs.PRECEDENCE,
                expected=(("majority", "second", "germane"),),
            ),
            SimTurn("Member (Chen)", "Second the amendment!"),
            SimTurn(
                "Chair",
                "The amendment carries. The motion now reads 'spend $750 on new signage.' "
                "Further debate?",
            ),
            SimTurn(
                "Member (Ramos)",
                "We've heard enough — I move the previous question!",
                prompt="Advise the chair: how is the motion for the Previous Question handled?",
                gold="The Previous Question needs a second, is not debatable, and requires a "
                "two-thirds vote to adopt. If it passes, debate ends immediately and the "
                "assembly votes on the pending motion.",
                ref=refs.PREVIOUS_QUESTION,
                rubric=RUBRIC_PREVIOUS_QUESTION,
                expected=(("two-thirds", "2/3", "two thirds"),),
            ),
            SimTurn("Member (Chen)", "Second!"),
            SimTurn(
                "Chair",
                "The previous question is adopted by more than two-thirds; debate is closed. "
                "(to you) What vote is now needed to adopt the main motion itself?",
                prompt="Advise the chair: what vote adopts this main motion?",
                gold="A main motion is adopted by a majority vote unless a special rule or the "
                "bylaws require more. Here a majority of the votes cast decides it.",
                ref=refs.MAJORITY,
                expected=(("majority",),),
            ),
            SimTurn("Chair", "The motion is adopted. Thank you, parliamentarian."),
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
                rubric=RUBRIC_QUORUM,
                expected=(("quorum",),),
            ),
            SimTurn(
                "Chair",
                "Thank you. Members have arrived and we now have a quorum. Proceed.",
            ),
            SimTurn(
                "Member (Ito)",
                "Point of order! I don't think the last speaker was recognized.",
                prompt="Advise the chair: how is a Point of Order handled?",
                gold="A Point of Order needs no second, is not debatable, and is raised at the "
                "time of the breach. The chair rules on the point; the chair's ruling may be "
                "challenged by an Appeal.",
                ref=refs.POINT_OF_ORDER,
                rubric=RUBRIC_POINT_OF_ORDER,
                expected=(("rule", "rules", "ruling", "decide", "decides"),),
            ),
            SimTurn(
                "Chair",
                "(quietly, to you) I'm inclined to rule the point well taken — but should I "
                "make this ruling, or should you as the parliamentarian?",
                prompt="Advise: who rules on the point — you or the chair?",
                gold="The chair rules, not the parliamentarian. The parliamentarian only "
                "advises the chair (usually privately); the chair then states the ruling to "
                "the assembly.",
                ref=refs.PARLIAMENTARIAN,
                expected=(("chair", "advis"),),
            ),
            SimTurn("Chair", "Understood. I rule the point well taken."),
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
                "First ballot: Alvarez 40, Brooks 35, Cho 20. Alvarez has the most votes.",
            ),
            SimTurn(
                "Chair",
                "(to you) Alvarez has a plurality. Can I declare Alvarez elected?",
                prompt="Advise the chair: is a plurality enough to elect here?",
                gold="No. Unless the bylaws provide otherwise, election requires a majority — "
                "more than half of the votes cast. A plurality does not elect.",
                ref=refs.PLURALITY,
                rubric=RUBRIC_PLURALITY,
                expected=(("majority",),),
            ),
            SimTurn(
                "Chair",
                "We balloted again: Alvarez 48, Brooks 42, Cho 5 — still no one over half. "
                "(to you) What do we do now?",
                prompt="Advise the chair: what happens when no candidate has a majority?",
                gold="Balloting is simply repeated until one candidate receives a majority. "
                "Candidates are not dropped unless the bylaws so provide, and members may "
                "change their votes on each ballot.",
                ref=refs.PLURALITY,
                expected=(("majority", "repeat", "again", "another"),),
            ),
            SimTurn(
                "Chair",
                "Third ballot: Alvarez has 51 of 95 votes — a majority. Alvarez is elected.",
            ),
        ),
    ),
    Simulation(
        4,
        7,
        "A dues increase at the Historical Society",
        "You are the parliamentarian at the Historical Society. A bylaw amendment to "
        "raise annual dues from $50 to $75 was submitted in writing at last month's "
        "regular meeting, and is now up for consideration.",
        (
            SimTurn(
                "Chair",
                "Next: the bylaw amendment to raise dues from $50 to $75, noticed last month.",
            ),
            SimTurn(
                "Member (Vance)",
                "Let's just pass it with a simple majority and move on.",
                prompt="Advise the chair: what vote does adopting this bylaw amendment require?",
                gold="Amending the bylaws takes a two-thirds vote, and it is in order now only "
                "because previous notice was given at the last regular meeting. A simple "
                "majority is not sufficient.",
                ref=refs.BYLAWS_AMENDMENT,
                expected=(("two-thirds", "2/3", "two thirds"),),
            ),
            SimTurn(
                "Member (Ruiz)",
                "I move to amend the amendment — make the new dues $150 instead of $75.",
                prompt="Advise the chair: is amending the figure up to $150 in order?",
                gold="No. An amendment to a bylaw amendment cannot exceed the scope of the "
                "notice. Members were noticed of an increase to $75, so a higher figure like "
                "$150 is out of order; a figure between the current $50 and the noticed $75 "
                "would be in order.",
                ref=refs.SCOPE_OF_NOTICE,
                expected=(("scope", "notice"),),
            ),
            SimTurn(
                "Chair",
                "The amendment to $150 is out of order — it exceeds the scope of the notice. "
                "We'll vote on the $75 amendment as noticed.",
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
