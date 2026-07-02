# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Section II scenario prompts for performance practice.

A small, deliberately conservative built-in set covering each of the seven
Performance-Expectation domains, using well-established RONR fundamentals so the
performance/debrief workflow can be exercised offline. These are clearly
*samples*; the production set is drawn from the official RPCE sample questions
(`data/RPCE-Sample-Questions-v4-100625.md`) and SME-authored items, and any
AI-generated additions must pass the gold-set checker first.

Gold answers state the correct *ruling/reasoning* (what the examiner grades on)
and every model answer carries an exact RONR (12th ed.) section citation plus a
verbatim quote from that section (`ref`); the candidate is not required to cite.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import refs
from .examiner import Rubric, RubricElement


@dataclass(frozen=True)
class Scenario:
    domain_code: int
    prompt: str
    #: The model ruling/reasoning the answer is graded against (accuracy).
    gold_answer: str
    #: RONR (12th ed.) citation + verbatim quote shown with the model answer.
    ref: refs.Ref
    #: Per-element grading rubric for the offline examiner. Optional: when
    #: absent the examiner derives one from ``gold_answer``.
    rubric: Rubric | None = None


# --- Curated rubrics (shared with the matching simulation turns) -------------
#
# Core elements (correct motion + vote threshold + required chair action) are
# essential and weighted heaviest; each carries its wrong-answer twin as a
# forbidden term so a confidently wrong ruling is penalised, not rewarded.

RUBRIC_MAIN_MOTION = Rubric(
    (
        RubricElement("the second", ("second",), weight=2.0, essential=True,
                      forbidden=("nosecond",), expects="a second"),
        RubricElement("the vote threshold", ("majority",), weight=2.0, essential=True,
                      forbidden=("twothirds",), expects="a majority vote"),
        RubricElement("stating the question / opening debate",
                      ("state", "open debate", "debate"), weight=1.0),
    )
)

RUBRIC_PREVIOUS_QUESTION = Rubric(
    (
        RubricElement("the motion", ("previousquestion",), weight=2.0, essential=True,
                      expects="the Previous Question"),
        RubricElement("the vote threshold", ("twothirds",), weight=2.0, essential=True,
                      forbidden=("majority",), expects="two-thirds"),
        RubricElement("the second", ("second",), forbidden=("nosecond",),
                      expects="a second"),
        RubricElement("debatability", ("nodebate",), forbidden=("debatable",),
                      expects="not debatable"),
    )
)

RUBRIC_POINT_OF_ORDER = Rubric(
    (
        RubricElement("the motion", ("pointoforder",), weight=2.0, essential=True,
                      expects="a Point of Order"),
        RubricElement("the second", ("nosecond",), forbidden=("second",),
                      expects="no second"),
        RubricElement("debatability", ("nodebate",), forbidden=("debatable",),
                      expects="not debatable"),
        RubricElement("the chair rules (may be appealed)",
                      ("rule", "chair", "appeal"), weight=1.0),
    )
)

RUBRIC_QUORUM = Rubric(
    (
        RubricElement("the quorum requirement", ("quorum",), weight=3.0,
                      essential=True, expects="a quorum must be present"),
        RubricElement("defined by the bylaws", ("bylaw",), weight=1.0),
    )
)

RUBRIC_PLURALITY = Rubric(
    (
        RubricElement("the majority requirement", ("majority",), weight=2.0,
                      essential=True, forbidden=("twothirds",),
                      expects="a majority — more than half"),
        RubricElement(
            "that a plurality does not elect",
            ("plurality does not elect", "balloting continues", "continue balloting",
             "majority required", "not elected"),
            weight=2.0, essential=True,
            forbidden=("plurality elects", "plurality is enough", "plurality wins"),
            expects="a plurality does not elect",
        ),
    )
)

RUBRIC_PARLIAMENTARIAN = Rubric(
    (
        RubricElement(
            "that the parliamentarian only advises, impartially",
            ("advise", "advises", "impartial", "impartially", "neutral",
             "does not rule", "not take sides"),
            weight=2.0, essential=True,
            forbidden=("take sides", "rule which", "which side is right"),
            expects="impartial, private advice — not a ruling",
        ),
        RubricElement("that the chair makes the rulings",
                      ("chair rules", "chair makes", "chair, not"), weight=1.0),
    )
)

RUBRIC_BYLAWS_AMENDMENT = Rubric(
    (
        RubricElement("the vote threshold", ("twothirds",), weight=2.0, essential=True,
                      forbidden=("majority",), expects="two-thirds"),
        RubricElement("previous notice", ("notice",), weight=2.0, essential=True,
                      expects="previous notice"),
    )
)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        1,
        'A member says "I move that we donate $500 to the scholarship fund." '
        "No one has said anything else yet. As chair, what do you do before debate?",
        "A main motion requires a second before it can be considered. The chair "
        "calls for a second; if seconded, the chair states the question and opens "
        "it to debate. A main motion is adopted by a majority vote.",
        refs.MAJORITY,
        rubric=RUBRIC_MAIN_MOTION,
    ),
    Scenario(
        2,
        "Debate has gone on for a long time and a member moves the Previous "
        "Question to end debate and vote now. How do you handle it?",
        "The Previous Question needs a second, is not debatable, and requires a "
        "two-thirds vote to adopt. If it passes, debate ends immediately and the "
        "assembly votes on the pending question.",
        refs.PREVIOUS_QUESTION,
        rubric=RUBRIC_PREVIOUS_QUESTION,
    ),
    Scenario(
        3,
        "While a motion is pending, a member believes the chair has violated the "
        'rules and says "Point of Order." What is the correct handling?',
        "A Point of Order is an incidental motion: it needs no second, is not "
        "debatable, and is raised at the time of the breach. The chair rules on "
        "the point; the chair's ruling may be challenged by an Appeal.",
        refs.POINT_OF_ORDER,
        rubric=RUBRIC_POINT_OF_ORDER,
    ),
    Scenario(
        4,
        "A meeting is scheduled to begin but only a few members are present. A "
        "member wants to start adopting motions. What must you confirm first?",
        "Business cannot be transacted without a quorum present. The chair must "
        "confirm a quorum (as defined by the bylaws) before the assembly takes "
        "any substantive action.",
        refs.QUORUM,
        rubric=RUBRIC_QUORUM,
    ),
    Scenario(
        5,
        "An election for president is held with three candidates and the bylaws "
        "are silent on the threshold. One candidate gets the most votes but not "
        "half. Is that candidate elected?",
        "No. Unless the bylaws provide otherwise, election requires a majority "
        "(more than half) of the votes cast. A plurality does not elect; balloting "
        "continues until a candidate has a majority.",
        refs.PLURALITY,
        rubric=RUBRIC_PLURALITY,
    ),
    Scenario(
        6,
        "During a contentious meeting, the chair asks the parliamentarian to tell "
        "the assembly which side is right. How should the parliamentarian respond?",
        "The parliamentarian advises impartially and privately; they do not rule "
        "or take sides. The chair, not the parliamentarian, makes rulings. The "
        "parliamentarian should give neutral procedural advice to the chair.",
        refs.PARLIAMENTARIAN,
        rubric=RUBRIC_PARLIAMENTARIAN,
    ),
    Scenario(
        7,
        "A member wants to amend the organization's bylaws at the next meeting. "
        "What conditions generally must be met to adopt the amendment?",
        "Amending bylaws generally requires previous notice and a two-thirds vote "
        "(or whatever the bylaws themselves specify). Both the notice requirement "
        "and the higher voting threshold must be satisfied.",
        refs.BYLAWS_AMENDMENT,
        rubric=RUBRIC_BYLAWS_AMENDMENT,
    ),
)


def scenarios_for(domain_code: int) -> list[Scenario]:
    return [s for s in SCENARIOS if s.domain_code == domain_code]


def all_scenarios() -> tuple[Scenario, ...]:
    return SCENARIOS
