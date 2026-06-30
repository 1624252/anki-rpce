# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Section II scenario prompts for performance practice.

A small, deliberately conservative built-in set covering each of the seven
Performance-Expectation domains, using well-established RONR fundamentals so the
performance/debrief workflow can be exercised offline. These are clearly
*samples*; the production set is drawn from the official RPCE sample questions
(`data/RPCE-Sample-Questions-v4-100625.md`) and SME-authored items, and any
AI-generated additions must pass the gold-set checker first.

Gold answers state the correct *ruling/reasoning* (what the examiner grades on);
RONR citations are added by the examiner from the corpus, not required of the
candidate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    domain_code: int
    prompt: str
    #: The model ruling/reasoning the answer is graded against (accuracy).
    gold_answer: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        1,
        "A member says 'I move that we donate $500 to the scholarship fund.' "
        "No one has said anything else yet. As chair, what do you do before debate?",
        "A main motion requires a second before it can be considered. The chair "
        "calls for a second; if seconded, the chair states the question and opens "
        "it to debate. A main motion is adopted by a majority vote.",
    ),
    Scenario(
        2,
        "Debate has gone on for a long time and a member moves the Previous "
        "Question to end debate and vote now. How do you handle it?",
        "The Previous Question needs a second, is not debatable, and requires a "
        "two-thirds vote to adopt. If it passes, debate ends immediately and the "
        "assembly votes on the pending question.",
    ),
    Scenario(
        3,
        "While a motion is pending, a member believes the chair has violated the "
        "rules and says 'Point of Order.' What is the correct handling?",
        "A Point of Order is an incidental motion: it needs no second, is not "
        "debatable, and is raised at the time of the breach. The chair rules on "
        "the point; the chair's ruling may be challenged by an Appeal.",
    ),
    Scenario(
        4,
        "A meeting is scheduled to begin but only a few members are present. A "
        "member wants to start adopting motions. What must you confirm first?",
        "Business cannot be transacted without a quorum present. The chair must "
        "confirm a quorum (as defined by the bylaws) before the assembly takes "
        "any substantive action.",
    ),
    Scenario(
        5,
        "An election for president is held with three candidates and the bylaws "
        "are silent on the threshold. One candidate gets the most votes but not "
        "half. Is that candidate elected?",
        "No. Unless the bylaws provide otherwise, election requires a majority "
        "(more than half) of the votes cast. A plurality does not elect; balloting "
        "continues until a candidate has a majority.",
    ),
    Scenario(
        6,
        "During a contentious meeting, the chair asks the parliamentarian to tell "
        "the assembly which side is right. How should the parliamentarian respond?",
        "The parliamentarian advises impartially and privately; they do not rule "
        "or take sides. The chair, not the parliamentarian, makes rulings. The "
        "parliamentarian should give neutral procedural advice to the chair.",
    ),
    Scenario(
        7,
        "A member wants to amend the organization's bylaws at the next meeting. "
        "What conditions generally must be met to adopt the amendment?",
        "Amending bylaws generally requires previous notice and a two-thirds vote "
        "(or whatever the bylaws themselves specify). Both the notice requirement "
        "and the higher voting threshold must be satisfied.",
    ),
)


def scenarios_for(domain_code: int) -> list[Scenario]:
    return [s for s in SCENARIOS if s.domain_code == domain_code]


def all_scenarios() -> tuple[Scenario, ...]:
    return SCENARIOS
