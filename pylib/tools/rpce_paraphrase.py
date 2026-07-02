#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""§7d paraphrase test — memory vs. performance, re-runnable and deterministic.

"This proves you measure performance, not just memory." For each concept we
hold a **recall** signal (memory: does the studied card come back?) next to
**accuracy on two exam-style reworded questions** (performance: does the idea
transfer to new wording?), and report the **gap** via
:func:`anki.rpce.metrics.paraphrase_gap`.

Honesty note: this is a deterministic harness over an **authored** dataset, not
real learner data. Two things are held apart on purpose:

- ``recall`` is an **authored memory-model baseline** — a stand-in for FSRS
  retrievability of the studied card. It is a fixed number per card, NOT
  measured from any student.
- the **reworded accuracy** is *computed*: each authored candidate answer is
  graded by the offline :class:`~anki.rpce.examiner.KeywordExaminer` (the AI-off
  rubric grader) against the card's model answer. This half re-runs identically
  on any machine, with AI on or off.

A clear positive gap (memory > performance) is the expected §7d signal: knowing
a card is not the same as applying the concept to fresh wording. A near-zero
gap is the red flag — it means the "performance" number is just echoing memory.

    just rpce-paraphrase
    # or: PYTHONPATH=out/pylib python pylib/tools/rpce_paraphrase.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


def _bootstrap_paths() -> None:
    """Make the built ``anki`` package importable when run from the repo root."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    built = os.path.join(repo, "out", "pylib")
    if os.path.isdir(built):
        sys.path.insert(0, built)
    os.environ.setdefault("ANKI_TEST_MODE", "1")


@dataclass(frozen=True)
class Paraphrase:
    """One exam-style reworded question + the candidate answer we grade for it."""

    question: str
    answer: str


@dataclass(frozen=True)
class ParaCard:
    """A studied concept with its model answer, an authored memory baseline, and
    two reworded questions testing the same idea in new words."""

    id: str
    domain: int
    concept: str
    #: Model ruling the examiner grades against (also the grounding corpus).
    gold_answer: str
    #: Authored memory-model baseline (0..1). NOT a measured learner value.
    recall: float
    paraphrases: tuple[Paraphrase, Paraphrase]


# --- Authored dataset: 32 concepts, each with two reworded questions. ---------
#
# Grounded in RONR (12th ed.) fundamentals and the official RPCE sample
# questions (data/RPCE-Sample-Questions-v4-100625.md). Each candidate answer is
# a fixed string so the harness is fully reproducible. Some reworded answers are
# deliberately correct and some carry a plausible-but-wrong twin (e.g. the wrong
# vote threshold), modelling a learner who recognises the card yet fumbles the
# transfer — which is exactly what a memory-vs-performance gap should surface.

DATASET: tuple[ParaCard, ...] = (
    ParaCard(
        "d1-main-adopt",
        1,
        "Adopting a main motion",
        "A main motion requires a second and a majority vote to be adopted.",
        0.90,
        (
            Paraphrase(
                "How many votes carry an ordinary main motion, and does it need a second?",
                "A main motion needs a second and a majority vote to be adopted.",
            ),
            Paraphrase(
                "Restate what it takes to approve a basic main motion.",
                "A main motion is adopted by a two-thirds vote once it has a second.",
            ),
        ),
    ),
    ParaCard(
        "d1-negative-motion",
        1,
        "Motion in the negative is proper",
        "A motion that the assembly not take an action is a proper main motion; it "
        "records the position of the assembly for the minutes.",
        0.85,
        (
            Paraphrase(
                "Is a motion 'that we not give the money' a proper motion?",
                "Yes, a motion that the assembly not take an action is a proper main "
                "motion recording its position.",
            ),
            Paraphrase(
                "Can a member move to decline to act, or must someone just vote no?",
                "A motion that the assembly not take an action is proper; it records the "
                "assembly position in the minutes.",
            ),
        ),
    ),
    ParaCard(
        "d1-ratify",
        1,
        "Ratify prior action",
        "The assembly adopts the motion to Ratify to confirm action taken earlier "
        "without proper authority.",
        0.80,
        (
            Paraphrase(
                "Bylaw changes were made at an unauthorised meeting — what fixes them?",
                "The assembly must adopt a motion to Ratify to confirm the action taken "
                "earlier without proper authority.",
            ),
            Paraphrase(
                "How does a group validate business it transacted improperly?",
                "Nothing is needed; action taken earlier stands on its own.",
            ),
        ),
    ),
    ParaCard(
        "d1-modify-own",
        1,
        "Modifying one's own motion",
        "Before the chair states the question, the maker may request permission to "
        "modify or withdraw his own motion.",
        0.95,
        (
            Paraphrase(
                "The mover wants to reword his motion — what may he do before it is stated?",
                "Before the chair states the question the maker may request permission to "
                "modify his own motion.",
            ),
            Paraphrase(
                "Can a member change the wording of a motion he just made?",
                "The maker may request permission to modify or withdraw the motion before "
                "the chair states the question.",
            ),
        ),
    ),
    ParaCard(
        "d1-postpone-carries",
        1,
        "Postponement carries pending motions",
        "When a main motion is postponed, the subsidiary motions pending with it go to "
        "the next meeting as well.",
        0.85,
        (
            Paraphrase(
                "A postponed main motion had an amendment and a referral pending — what returns?",
                "The main motion returns together with the amendment and the motion to "
                "refer that were pending with it.",
            ),
            Paraphrase(
                "Do secondary motions survive when the main motion is postponed?",
                "No, the assembly starts over on secondary motions; only the main motion "
                "returns.",
            ),
        ),
    ),
    ParaCard(
        "d2-previous-question",
        2,
        "Previous Question",
        "The Previous Question requires a two-thirds vote and is not debatable.",
        0.90,
        (
            Paraphrase(
                "What threshold ends debate through the Previous Question?",
                "The Previous Question needs a two-thirds vote and is not debatable.",
            ),
            Paraphrase(
                "Is the motion to close debate itself debatable, and what vote passes it?",
                "The previous question is not debatable and passes on a majority vote.",
            ),
        ),
    ),
    ParaCard(
        "d2-amend",
        2,
        "Motion to Amend",
        "The subsidiary motion to Amend is debatable and requires a majority vote.",
        0.85,
        (
            Paraphrase(
                "What vote does a motion to amend take, and may it be debated?",
                "The motion to amend is debatable and requires a majority vote.",
            ),
            Paraphrase(
                "How is a primary amendment decided?",
                "A motion to amend is debatable and is adopted by a majority vote.",
            ),
        ),
    ),
    ParaCard(
        "d2-amend-germane",
        2,
        "Amendments must be germane",
        "A primary amendment must be germane to the main motion it proposes to change.",
        0.80,
        (
            Paraphrase(
                "May an amendment introduce an unrelated subject?",
                "No, a primary amendment must be germane to the main motion.",
            ),
            Paraphrase(
                "What limits the subject matter of an amendment?",
                "An amendment can raise any subject the mover wishes.",
            ),
        ),
    ),
    ParaCard(
        "d2-lay-on-table",
        2,
        "Lay on the Table",
        "The motion to Lay on the Table is not debatable and requires a majority vote.",
        0.85,
        (
            Paraphrase(
                "What vote sets a question aside by laying it on the table, and is it debatable?",
                "Lay on the Table is not debatable and takes a majority vote.",
            ),
            Paraphrase(
                "How is a motion to lay on the table handled?",
                "It is not debatable and is adopted by a majority vote.",
            ),
        ),
    ),
    ParaCard(
        "d2-suspend-rules",
        2,
        "Suspend the Rules",
        "The motion to Suspend the Rules is not debatable and generally requires a "
        "two-thirds vote.",
        0.80,
        (
            Paraphrase(
                "What vote is usually needed to suspend the rules, and is it debatable?",
                "Suspending the rules is not debatable and generally needs a two-thirds vote.",
            ),
            Paraphrase(
                "How much support does a motion to suspend the rules require?",
                "A motion to suspend the rules is not debatable and needs only a majority vote.",
            ),
        ),
    ),
    ParaCard(
        "d3-point-of-order",
        3,
        "Point of Order",
        "A Point of Order is not debatable, needs no second, and is decided by the chair.",
        0.90,
        (
            Paraphrase(
                "Who rules on a point of order, and does it need a second?",
                "A point of order needs no second and is ruled on by the chair; it is not "
                "debatable.",
            ),
            Paraphrase(
                "Describe how a point of order is disposed of.",
                "A point of order is debatable and decided by a vote of the assembly after "
                "a second.",
            ),
        ),
    ),
    ParaCard(
        "d3-appeal",
        3,
        "Appeal from the chair's ruling",
        "An Appeal is debatable and is decided by a majority vote of the assembly, not "
        "by the chair alone.",
        0.85,
        (
            Paraphrase(
                "A member disagrees with the chair's ruling — who decides, and what vote?",
                "An appeal lets the assembly decide by a majority vote; it is debatable.",
            ),
            Paraphrase(
                "Can the chair's ruling be overturned, and by whom?",
                "The chair's ruling is final and an appeal is not debatable.",
            ),
        ),
    ),
    ParaCard(
        "d3-suspend-cannot-deny-speech",
        3,
        "Limits on suspending the rules",
        "The rules may not be suspended to deny a particular member the right to speak "
        "in debate.",
        0.80,
        (
            Paraphrase(
                "May the assembly suspend the rules to silence one named member?",
                "No, the rules may not be suspended to deny a particular member the right "
                "to speak in debate.",
            ),
            Paraphrase(
                "Can a two-thirds vote strip one member of the floor for the meeting?",
                "The rules cannot be suspended to take away a member's right to speak in "
                "debate.",
            ),
        ),
    ),
    ParaCard(
        "d3-reconsider-timing",
        3,
        "Reconsider — who and when",
        "A motion to Reconsider may be made only by a member who voted on the "
        "prevailing side, and only within the time limits.",
        0.75,
        (
            Paraphrase(
                "Who is entitled to move to reconsider a vote?",
                "Only a member who voted on the prevailing side may move to reconsider, "
                "and only within the time limits.",
            ),
            Paraphrase(
                "May anyone move to reconsider at any later meeting?",
                "Any member may move to reconsider at any time.",
            ),
        ),
    ),
    ParaCard(
        "d3-point-of-order-minutes",
        3,
        "Recording a point-of-order ruling",
        "The chair's ruling on a point of order, with the reasons, should be entered in "
        "the minutes.",
        0.80,
        (
            Paraphrase(
                "Should a ruling on a point of order be written into the minutes?",
                "Yes, the ruling on a point of order and its reasons should be recorded in "
                "the minutes.",
            ),
            Paraphrase(
                "Does the secretary record the chair's point-of-order ruling?",
                "No, rulings on points of order are never included in the minutes.",
            ),
        ),
    ),
    ParaCard(
        "d4-quorum",
        4,
        "Quorum",
        "Business cannot be validly transacted without a quorum present.",
        0.90,
        (
            Paraphrase(
                "What must be present before the assembly transacts substantive business?",
                "A quorum must be present before business can be validly transacted.",
            ),
            Paraphrase(
                "May a body act with only a handful of members in the room?",
                "No, business cannot be transacted without a quorum present.",
            ),
        ),
    ),
    ParaCard(
        "d4-quorum-in-bylaws",
        4,
        "Setting the quorum",
        "The members set their own quorum in the bylaws; RONR does not fix the number "
        "for them.",
        0.75,
        (
            Paraphrase(
                "How should a new society determine what its quorum will be?",
                "The members decide the quorum and put that number in their bylaws.",
            ),
            Paraphrase(
                "Where does a group's quorum requirement come from?",
                "RONR provides the standard quorum number that every society uses.",
            ),
        ),
    ),
    ParaCard(
        "d4-unanimous-consent",
        4,
        "Unanimous consent",
        "By unanimous consent the chair may adopt a routine action without a formal "
        "vote, but a single objection defeats it.",
        0.80,
        (
            Paraphrase(
                "How may the chair dispose of an uncontroversial matter without a vote?",
                "The chair may ask for unanimous consent and adopt it if no member objects.",
            ),
            Paraphrase(
                "Does unanimous consent prove that every member agrees?",
                "Yes, unanimous consent means we know that every member agrees with the "
                "decision.",
            ),
        ),
    ),
    ParaCard(
        "d4-correct-minutes",
        4,
        "Correcting the minutes",
        "Minutes are usually corrected by unanimous consent when there is no "
        "disagreement about the change.",
        0.80,
        (
            Paraphrase(
                "A member's name was left out of the minutes — how is that fixed?",
                "The chair usually asks for unanimous consent to make the correction.",
            ),
            Paraphrase(
                "What is the usual way to amend the minutes for a small error?",
                "The chair corrects the minutes by unanimous consent.",
            ),
        ),
    ),
    ParaCard(
        "d4-previous-question-recognized",
        4,
        "Moving the Previous Question",
        "A member must be recognised and obtain the floor before moving the Previous "
        "Question.",
        0.75,
        (
            Paraphrase(
                "May a member call the previous question while another has the floor?",
                "No, a member must be recognised and hold the floor before moving the "
                "Previous Question.",
            ),
            Paraphrase(
                "Can the chair order the previous question on his own?",
                "The chair may declare the previous question whenever debate has run long "
                "enough.",
            ),
        ),
    ),
    ParaCard(
        "d5-majority-elect",
        5,
        "Election by majority",
        "Unless the bylaws provide otherwise, election requires a majority of the votes "
        "cast, not a plurality.",
        0.90,
        (
            Paraphrase(
                "With the bylaws silent, what is needed to be elected?",
                "Election requires a majority of the votes cast, not a plurality.",
            ),
            Paraphrase(
                "Does the candidate with the most votes always win?",
                "Yes, whoever gets the most votes is elected by plurality.",
            ),
        ),
    ),
    ParaCard(
        "d5-division",
        5,
        "Division of the assembly",
        "On a call for a Division, the chair must retake the voice vote as a standing "
        "vote.",
        0.80,
        (
            Paraphrase(
                "A member calls 'Division!' after a close voice vote — what must the chair do?",
                "The chair must retake the vote as a standing vote.",
            ),
            Paraphrase(
                "What does a demand for a division require of the chair?",
                "The chair simply repeats the voice vote, listening more carefully.",
            ),
        ),
    ),
    ParaCard(
        "d5-majority-of-votes-cast",
        5,
        "Majority of votes cast",
        "A majority means more than half of the votes cast; abstentions are not counted "
        "as votes.",
        0.85,
        (
            Paraphrase(
                "With 12 members and a 5-to-4 result, was a majority motion adopted?",
                "Yes, five is more than half of the nine votes cast, so a majority "
                "adopted it.",
            ),
            Paraphrase(
                "Do abstentions count against reaching a majority?",
                "Yes, abstentions are counted as no votes when figuring the majority.",
            ),
        ),
    ),
    ParaCard(
        "d5-change-ballot",
        5,
        "Changing a ballot vote",
        "A ballot vote is secret, so a member may not change it once the ballot is "
        "deposited.",
        0.75,
        (
            Paraphrase(
                "May a member retrieve and re-mark a ballot already dropped in the box?",
                "No, the ballot vote is secret, so a deposited ballot may not be changed.",
            ),
            Paraphrase(
                "Can a voter fix a ballot before the result is announced?",
                "Yes, a member may change a vote at any time before the result is announced.",
            ),
        ),
    ),
    ParaCard(
        "d5-tie-vote",
        5,
        "Effect of a tie",
        "A motion requiring a majority is lost on a tie vote, because a tie is not more "
        "than half.",
        0.85,
        (
            Paraphrase(
                "What happens to a majority motion when the vote is tied?",
                "The motion is lost, because a tie is not a majority.",
            ),
            Paraphrase(
                "Does a tie carry an ordinary motion?",
                "On a tie the motion is lost since a tie is not more than half.",
            ),
        ),
    ),
    ParaCard(
        "d6-parliamentarian-advises",
        6,
        "Parliamentarian advises, chair rules",
        "The parliamentarian advises impartially while the chair makes the rulings.",
        0.90,
        (
            Paraphrase(
                "What is the parliamentarian's role during a meeting?",
                "The parliamentarian advises impartially and the chair makes the rulings.",
            ),
            Paraphrase(
                "Does the parliamentarian decide points of order?",
                "The parliamentarian advises impartially; the chair rules.",
            ),
        ),
    ),
    ParaCard(
        "d6-regular-meeting-notice",
        6,
        "Notice of regular meetings",
        "When the bylaws fix the dates of regular meetings, separate notice of those "
        "meetings is not required.",
        0.75,
        (
            Paraphrase(
                "The bylaws list the regular meeting dates — is notice still required?",
                "No, because the bylaws already inform members when regular meetings are "
                "held, notice is not required.",
            ),
            Paraphrase(
                "Must a society mail notice before each scheduled regular meeting?",
                "Yes, notice must be sent ten days before each regular meeting.",
            ),
        ),
    ),
    ParaCard(
        "d6-scope-of-notice",
        6,
        "Scope of an amendment under notice",
        "An amendment to a noticed change may not exceed the scope of the notice given.",
        0.75,
        (
            Paraphrase(
                "Notice raised dues from $60 to $100; is an amendment to $190 in order?",
                "No, an amendment may not exceed the scope of the notice, so $190 is out "
                "of order.",
            ),
            Paraphrase(
                "Can a noticed dues change be amended to any amount at the meeting?",
                "Yes, once notice is given the assembly may set the dues at any amount.",
            ),
        ),
    ),
    ParaCard(
        "d6-decorum-attack",
        6,
        "Decorum in debate",
        "A member must confine debate to the merits and may not attack another member's "
        "motives; the chair calls the offender to order.",
        0.80,
        (
            Paraphrase(
                "A speaker keeps insulting members who disagree — what should the chair do?",
                "The chair calls the member to order because debate must stay on the "
                "merits, not attack motives.",
            ),
            Paraphrase(
                "Is name-calling in debate acceptable as the speaker's opinion?",
                "The chair should call the member to order; debate must address the "
                "question, not personal motives.",
            ),
        ),
    ),
    ParaCard(
        "d7-board-small-rules",
        7,
        "Small-board rules",
        "In a small board the chair may debate and vote, and motions need not be "
        "seconded.",
        0.80,
        (
            Paraphrase(
                "Which formalities relax for a small board?",
                "In a small board the chair may debate and vote, and a second is not "
                "required.",
            ),
            Paraphrase(
                "Under small-board rules, does every motion still need a second?",
                "Yes, motions still require a second even under small-board rules.",
            ),
        ),
    ),
    ParaCard(
        "d7-ex-officio-quorum",
        7,
        "Ex-officio member outside the society",
        "An ex-officio member who is not under the society's authority is not counted "
        "in the quorum but keeps the right to speak and vote.",
        0.70,
        (
            Paraphrase(
                "How is an outside ex-officio board member treated for quorum and rights?",
                "He is not counted in the quorum but has full rights to speak and to vote.",
            ),
            Paraphrase(
                "Does an ex-officio member count toward quorum?",
                "Yes, an ex-officio member is counted toward quorum like any other member.",
            ),
        ),
    ),
    ParaCard(
        "d7-bylaws-amendment",
        7,
        "Amending the bylaws",
        "Amending the bylaws generally requires previous notice and a two-thirds vote.",
        0.85,
        (
            Paraphrase(
                "What is generally required to amend the bylaws?",
                "Amending the bylaws generally requires previous notice and a two-thirds "
                "vote.",
            ),
            Paraphrase(
                "Can the bylaws be changed on a simple majority with no warning?",
                "Yes, a majority vote with no notice is enough to amend the bylaws.",
            ),
        ),
    ),
)


@dataclass
class CardResult:
    """Per-card outcome: which reworded questions passed and the resulting
    performance accuracy, held against the authored memory baseline."""

    card: ParaCard
    passed: list[bool]
    reworded_accuracy: float

    @property
    def recall(self) -> float:
        return self.card.recall


def corpus() -> str:
    """Grounding corpus for the examiner — the model answers themselves, so
    retrieval always finds a supporting passage (never a spurious abstain)."""
    return "\n\n".join(c.gold_answer for c in DATASET)


def run(grader=None):
    """Grade every reworded question with the offline rubric grader and pair each
    card's authored recall with its computed reworded accuracy.

    Returns ``(results, gap)`` where ``gap`` is a
    :class:`anki.rpce.metrics.ParaphraseGap`."""
    from anki.rpce import examiner as ex_mod
    from anki.rpce import metrics

    grader = grader or ex_mod.KeywordExaminer()
    text = corpus()
    results: list[CardResult] = []
    pairs: list[tuple[float, float]] = []
    for card in DATASET:
        flags: list[bool] = []
        for p in card.paraphrases:
            r = grader.grade(p.answer, card.gold_answer, text)
            flags.append(bool(r.passed and not r.abstained))
        acc = sum(flags) / len(flags)
        results.append(CardResult(card, flags, acc))
        pairs.append((card.recall, acc))
    return results, metrics.paraphrase_gap(pairs)


#: Below this the gap is a §7d red flag — the "performance" number is just
#: echoing memory rather than measuring transfer to new wording.
MIN_GAP = 0.05


def main() -> int:
    _bootstrap_paths()
    results, gap = run()

    print(f"§7d paraphrase test — {len(DATASET)} concepts, 2 reworded questions each")
    print("(deterministic harness over an AUTHORED dataset — not real learner data;")
    print(" recall = authored memory baseline, reworded accuracy = offline grader)\n")

    print(f"{'concept':38} {'recall':>7} {'reworded':>9}  questions")
    for res in results:
        marks = " ".join("PASS" if ok else "FAIL" for ok in res.passed)
        print(
            f"{res.card.concept[:38]:38} {res.recall:7.2f} "
            f"{res.reworded_accuracy:9.2f}  {marks}"
        )

    print(
        f"\nAggregate over {len(results)} concepts "
        f"({sum(len(r.passed) for r in results)} reworded questions):"
    )
    print(f"  mean recall (memory baseline):    {gap.mean_recall:.3f}")
    print(f"  mean reworded accuracy (perf.):   {gap.mean_reworded_accuracy:.3f}")
    print(f"  memory-vs-performance gap:        {gap.gap:+.3f}")

    if gap.gap < MIN_GAP:
        print(
            f"\nRED FLAG: gap {gap.gap:+.3f} < {MIN_GAP:.2f} — the performance model is "
            "essentially mirroring memory (spec §7d)."
        )
        return 1
    print(
        f"\nOK: a clear positive gap ({gap.gap:+.3f}) shows recognising a studied card "
        "is\nnot the same as applying the concept to reworded questions (spec §7d)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
