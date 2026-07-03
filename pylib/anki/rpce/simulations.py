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
    #: The performance-expectation concept id this decision turn exercises (e.g.
    #: "3.29"), so simulations are labelled + counted by concept like Review and
    #: Section II. Empty on narrative turns and the legacy built-in sims.
    concept: str = ""

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
                expected=(("majority",), ("second", "germane")),
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
                # "no ... majority" conveys the ruling: a bare "no, majority"
                # answer reads correctly ("no — a majority is required").
                expected=(
                    ("no", "not", "cannot", "does not elect", "not elected"),
                    ("majority",),
                ),
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
                # "repeat ... majority" = repeat balloting until someone has a
                # majority; both concepts are required to convey the ruling.
                expected=(
                    ("repeat", "again", "another ballot", "re-ballot", "revote"),
                    ("majority",),
                ),
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
                expected=(
                    ("two-thirds", "2/3", "two thirds"),
                    ("notice", "previous notice", "noticed"),
                ),
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
                expected=(
                    ("no", "not in order", "out of order", "cannot", "exceed"),
                    ("scope", "notice"),
                ),
            ),
            SimTurn(
                "Chair",
                "The amendment to $150 is out of order — it exceeds the scope of the notice. "
                "We'll vote on the $75 amendment as noticed.",
            ),
        ),
    ),
    Simulation(
        5,
        2,
        "Reworking a proposal at the Riverside Garden Club",
        "You are the parliamentarian at the Riverside Garden Club. A main motion "
        '"that the Club hold its annual plant sale on the first Saturday of May" is '
        "pending and has been debated for a while.",
        (
            SimTurn(
                "Chair",
                "The motion to hold the plant sale on the first Saturday of May is open "
                "for debate.",
            ),
            SimTurn(
                "Member (Okafor)",
                "This needs more study than we can give it on the floor. I move to refer "
                "the motion to a three-member committee to work out the details.",
                prompt="Advise the chair: how is this motion to Commit/Refer handled, and what vote does it need?",
                gold="The motion to Commit or Refer needs a second and is debatable. It "
                "sends the pending question to a committee and is adopted by a majority "
                "vote. If it passes, the main motion goes to the committee instead of "
                "being decided now.",
                ref=refs.COMMIT,
                expected=(("commit", "refer", "committee"), ("majority", "second")),
            ),
            SimTurn(
                "Chair",
                "The motion to refer is defeated, so the main motion is again pending. "
                "Further debate?",
            ),
            SimTurn(
                "Member (Bianchi)",
                'I move to substitute the whole motion with "that the Club hold a fall '
                'harvest festival in October instead of a plant sale."',
                prompt="Advise the chair: is a substitute in order here, and how is it treated?",
                gold="A motion to substitute is a form of amendment and must be germane to "
                "the pending question. It needs a second, is fully debatable on the merits "
                "of both the original and the substitute, and is adopted by a majority "
                "vote.",
                ref=refs.SUBSTITUTE,
                expected=(("substitute", "amend"), ("majority", "germane", "debat")),
            ),
            SimTurn(
                "Chair",
                "The substitute is lost; the original motion stands. It's getting late.",
            ),
            SimTurn(
                "Member (Okafor)",
                "I move to postpone this motion to our next regular meeting.",
                prompt="Advise the chair: how is the motion to Postpone to a Certain Time handled?",
                gold="The motion to Postpone to a Certain Time needs a second, is debatable, "
                "and is adopted by a majority vote. It puts the question off to a definite "
                "later time — here the next regular meeting. (A two-thirds vote is needed "
                "only if it is made a special order.)",
                ref=refs.POSTPONE,
                expected=(("postpone", "put off", "defer"), ("majority", "second")),
            ),
            SimTurn(
                "Chair",
                "The motion is postponed to our next regular meeting. Thank you, "
                "parliamentarian.",
            ),
        ),
    ),
    Simulation(
        6,
        3,
        "Undoing a hasty vote at the Ridgeline Trail Alliance",
        "You are the parliamentarian at the Ridgeline Trail Alliance. Earlier in this "
        "same meeting the assembly adopted a motion to spend $2,000 on a trailhead "
        "sign. New information has just come to light.",
        (
            SimTurn(
                "Member (Nguyen)",
                "I move to spend an additional $800 on landscaping around the new sign.",
            ),
            SimTurn(
                "Chair",
                "That motion is out of order because we already adjourned that item.",
            ),
            SimTurn(
                "Member (Nguyen)",
                "I disagree with that ruling and I appeal from the decision of the chair!",
                prompt="Advise the chair: how is this Appeal handled, and who decides it?",
                gold="An Appeal requires a second. It takes the question away from the chair "
                "and gives it to the assembly, which decides by vote. A majority or a tie "
                "vote sustains the chair's ruling; the assembly, not the chair, has the "
                "final say.",
                ref=refs.APPEAL,
                expected=(
                    ("assembly", "member"),
                    ("second", "majority", "tie", "vote"),
                ),
            ),
            SimTurn(
                "Chair",
                "On the appeal, the assembly reverses my ruling. (to you) Now a member "
                "wants to revisit the $2,000 sign vote we adopted earlier tonight.",
            ),
            SimTurn(
                "Member (Alvarado)",
                "I voted for the $2,000, but the bids came in higher. I move to reconsider "
                "that vote.",
                prompt="Advise the chair: may this member move to Reconsider the vote?",
                gold="Yes. In an ordinary meeting the motion to Reconsider must be made the "
                "same day as the vote, and only by a member who voted on the prevailing "
                "side. Alvarado voted for the motion that was adopted, so he is on the "
                "prevailing side and may move it. It needs a second.",
                ref=refs.RECONSIDER,
                expected=(("prevailing", "voted", "winning side"),),
            ),
            SimTurn(
                "Member (Alvarado)",
                "Actually, rather than reconsider, could we just change the amount that's "
                "already on the books to $2,500?",
                prompt="Advise the chair: what motion is used to change a figure the assembly already adopted?",
                gold="That is the motion to Amend Something Previously Adopted, used to "
                "change part of an action already taken. Without previous notice it takes a "
                "two-thirds vote or a majority of the entire membership; with notice, a "
                "majority vote.",
                ref=refs.AMEND_PREVIOUSLY_ADOPTED,
                expected=(
                    (
                        "amend something previously adopted",
                        "previously adopted",
                        "amend",
                    ),
                ),
            ),
            SimTurn("Chair", "Understood. Thank you, parliamentarian."),
        ),
    ),
    Simulation(
        7,
        6,
        "The parliamentarian's proper role at the Metro Nonprofit Convention",
        "You have been engaged as the professional parliamentarian for the annual "
        "convention of the Metro Nonprofit Coalition. A contentious bylaws item is on "
        "the floor and tempers are rising.",
        (
            SimTurn(
                "Member (Delacroix)",
                "(to you) You clearly know the rules best — just tell us how to vote and "
                "rule on this point for us.",
                prompt="Advise: what is your proper role, and who actually rules?",
                gold="The parliamentarian's role during a meeting is purely advisory and "
                "consultative. Parliamentary law gives the chair alone the power to rule "
                "on questions of order; I advise the chair — usually privately — and the "
                "chair makes and states the ruling.",
                ref=refs.PARLIAMENTARIAN,
                expected=(("advis", "consult"), ("chair",)),
            ),
            SimTurn(
                "Chair",
                "(quietly, to you) You're also a dues-paying member of this Coalition. "
                "Can you just vote with us on this bylaws amendment to help it pass?",
                prompt="Advise: as the member serving as parliamentarian, may you vote and debate on this question?",
                gold="No. A member who serves as parliamentarian has the same duty as the "
                "chair to maintain impartiality, and so does not make motions, debate, or "
                "vote on questions — except on a ballot vote. I must forgo those rights "
                "while serving in this role.",
                ref=refs.PARLIAMENTARIAN_IMPARTIALITY,
                expected=(("impartial", "not vote", "cannot vote", "forgo"),),
            ),
            SimTurn(
                "Member (Delacroix)",
                "This amendment is a fraud and the member who wrote it is a liar!",
                prompt="Advise the chair: how should the chair handle this remark in debate?",
                gold="Debate must be directed to the measure, not the member. A member may "
                "not attack another's motives or use words like 'fraud' or 'liar' about a "
                "member. The chair must act at once to call the speaker to order and "
                "require decorum.",
                ref=refs.DECORUM,
                expected=(
                    (
                        "measure not the member",
                        "measure, not the member",
                        "motive",
                        "personalit",
                        "decorum",
                        "order",
                    ),
                ),
            ),
            SimTurn(
                "Chair",
                "The member will confine his remarks to the measure. Thank you, "
                "parliamentarian.",
            ),
        ),
    ),
)


#: Authored meeting simulations (data/rpce_simulations.json), covering every
#: performance-expectation concept in >=1 decision turn (docs/rpce Phase 4). Each
#: decision turn carries its concept id + a verbatim RONR quote. Loaded lazily.
_AUTHORED_SIMS: tuple[Simulation, ...] | None = None


def _load_authored_sims() -> tuple[Simulation, ...]:
    global _AUTHORED_SIMS
    if _AUTHORED_SIMS is not None:
        return _AUTHORED_SIMS
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "data" / "rpce_simulations.json"
    out: list[Simulation] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        base = 1000  # keep authored ids clear of the built-in sims
        for n, s in enumerate(data.get("simulations", [])):
            turns: list[SimTurn] = []
            for t in s["turns"]:
                prompt = t.get("prompt")
                if prompt:
                    sec = str(t.get("section", "") or "")
                    ref = refs.Ref(sec, t.get("quote", "")) if sec else None
                    turns.append(
                        SimTurn(
                            t.get("speaker", ""),
                            t.get("line", ""),
                            prompt=prompt,
                            gold=t.get("gold", ""),
                            ref=ref,
                            expected=tuple(tuple(g) for g in (t.get("expected") or ())),
                            concept=str(t.get("concept", "")),
                        )
                    )
                else:
                    turns.append(SimTurn(t.get("speaker", ""), t.get("line", "")))
            out.append(
                Simulation(
                    base + n,
                    int(s["domain"]),
                    s.get("title", ""),
                    s.get("setting", ""),
                    tuple(turns),
                )
            )
    except Exception as exc:  # never break Simulation mode over the authored file
        print(f"RPCE authored-simulation load error: {exc}")
    _AUTHORED_SIMS = tuple(out)
    return _AUTHORED_SIMS


def all_simulations() -> tuple[Simulation, ...]:
    # Ship the authored bank when present (67 sims, every concept, each <=10
    # turns); the legacy built-in SIMULATIONS remain only as the offline/test
    # fallback when the authored file is absent.
    authored = _load_authored_sims()
    return authored if authored else SIMULATIONS


def simulation_by_id(sim_id: int) -> Simulation:
    for sim in all_simulations():
        if sim.id == sim_id:
            return sim
    raise KeyError(f"unknown simulation id: {sim_id}")


def response_turns(sim: Simulation) -> list[SimTurn]:
    """The turns in ``sim`` that require a graded parliamentarian response."""
    return [t for t in sim.turns if t.needs_response]
