# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Hand-authored grading rubrics for the official gold-set sample questions.

**Methodology note (read before quoting any number).** These rubrics are
authored *against the gold set itself* — one per official sample question,
picking the phrase that distinguishes the keyed-correct option from its
distractors. That makes the resulting false-pass rate a **fitted** result, not
a held-out one: it shows how well a carefully authored offline rubric *can*
discriminate on these exact items, and it does **not** predict performance on
unseen questions. The held-out number remains the AI examiner's. The eval
labels this grader "Rubric (gold-tuned)" and prints the caveat for that reason.

Each entry is ``(key, Rubric)``. ``key`` is a verbatim, globally-unique
substring of the keyed-correct option, used only to attach the rubric to the
right parsed question. The rubric's essential element carries the correct
ruling's discriminating phrase(s) (matched through the same alias table +
stemmer the offline grader uses), plus ``forbidden`` twins for the classic
wrong rationales a distractor asserts.
"""

from __future__ import annotations

from .examiner import Rubric, RubricElement


def _essential(
    name: str,
    accepted: tuple[str, ...],
    *,
    forbidden: tuple[str, ...] = (),
    expects: str = "",
) -> Rubric:
    """A single-element rubric: the one point that must be present to pass."""
    return Rubric(
        (
            RubricElement(
                name,
                accepted,
                weight=1.0,
                forbidden=forbidden,
                essential=True,
                expects=expects,
            ),
        )
    )


# Ordered to match ``parse_gold`` (Domains 1-7, questions in document order).
# The key is the lookup anchor; the accepted phrase is what the grader matches.
_GOLD_RUBRICS: tuple[tuple[str, Rubric], ...] = (
    # --- Domain 1: Motions in General and Main Motions -----------------------
    (
        "not doing anything will accomplish the same thing",
        _essential(
            "the ruling",
            ("accomplish the same thing",),
            expects="a motion not to act is improper — inaction achieves the same end",
        ),
    ),
    (
        "as if they had never been considered",
        _essential(
            "the ruling",
            ("never been considered",),
            expects="the invalid amendments are treated as if never considered",
        ),
    ),
    (
        "request permission to modify his motion",
        _essential(
            "the remedy",
            ("permission to modify",),
            expects="request permission to modify the motion",
        ),
    ),
    (
        "only when no other motion is pending",
        _essential(
            "the distinction",
            ("no other motion is pending",),
            expects="an incidental main motion can be made only when nothing is pending",
        ),
    ),
    (
        "the motion to Refer, and the Amendment",
        _essential(
            "what carries over",
            ("motion to refer",),
            expects="the main motion and every adhering secondary motion carry over",
        ),
    ),
    # --- Domain 2: Subsidiary and Privileged Motions -------------------------
    (
        "strike out '$100' and insert '$50'",
        _essential(
            "the germane amendment",
            ("insert 50",),
            expects="strike out $100 and insert $50",
        ),
    ),
    (
        "assembly has already voted to include",
        _essential(
            "the ruling",
            ("already voted to include",),
            expects="the amendment is out of order — the assembly already voted to include it",
        ),
    ),
    (
        "The merits of holding such a drive at all",
        _essential(
            "not debatable now",
            ("merits of holding",),
            expects="the merits of the main motion may not be debated while Commit is pending",
        ),
    ),
    (
        "membership can simply vote 'no' on the original motion",
        _essential(
            "the ruling",
            ("simply vote",),
            expects="an amendment inserting 'not' is out of order — members can just vote no",
        ),
    ),
    (
        "If the amendment is adopted, the main motion will read",
        _essential(
            "the chair states it",
            ("amendment is adopted",),
            expects="the chair restates the multi-part amendment and puts the question",
        ),
    ),
    # --- Domain 3: Incidental Motions / Bring Again Before the Assembly -------
    (
        "Any member can make the motion.",
        _essential(
            "who may make it",
            ("any member can make",),
            expects="any member may make the motion to Amend Something Previously Adopted",
        ),
    ),
    (
        "rules may not be suspended to deny any particular member",
        _essential(
            "the ruling",
            ("suspended to deny",),
            forbidden=("abused", "warned"),
            expects="rules may not be suspended to deny a member the right to speak",
        ),
    ),
    (
        "The reasons for a ruling on a point of order should be in the minutes",
        _essential(
            "recorded in the minutes",
            ("reasons for a ruling",),
            expects="the reasons for a ruling on a point of order belong in the minutes",
        ),
    ),
    (
        "should not have taken a voice vote because the motion needed 2/3",
        _essential(
            "the vote threshold",
            ("twothirds",),
            expects="suspending the rules needed a two-thirds vote, not a voice vote",
        ),
    ),
    (
        "the time limits for making that motion to reconsider have expired",
        _essential(
            "the ruling",
            ("time limits",),
            forbidden=("majority",),
            expects="the reconsider time limit has expired — withdraw only by unanimous consent",
        ),
    ),
    # --- Domain 4: Organization and Conduct of Meetings ----------------------
    (
        "everyone agrees with the decision that was made",
        _essential(
            "the NOT-true statement",
            ("everyone agrees with the decision",),
            expects="unanimous consent does NOT prove everyone agrees",
        ),
    ),
    (
        "usually ask for unanimous consent to make the change",
        _essential(
            "the usual method",
            ("consent to make the change",),
            expects="the chair usually corrects the minutes by unanimous consent",
        ),
    ),
    (
        "The members decide what they wish to have as the quorum",
        _essential(
            "how quorum is set",
            ("members decide",),
            forbidden=("majority of the fixed",),
            expects="the members set the quorum number in their bylaws",
        ),
    ),
    (
        "The chair asks for a second to the motion on the Previous Question",
        _essential(
            "the correct response",
            ("second",),
            expects="the Previous Question needs a second",
        ),
    ),
    (
        "Adoption of a special rule of order is required to regularly include",
        _essential(
            "what is required",
            ("special rule of order",),
            forbidden=("custom",),
            expects="a special rule of order is required to change the content of the minutes",
        ),
    ),
    # --- Domain 5: Voting, Nominations and Elections -------------------------
    (
        "less than two thirds in the affirmative and the motion is lost",
        _essential(
            "the vote threshold",
            ("twothirds",),
            expects="the Previous Question needs two-thirds — 73 to 72 fails",
        ),
    ),
    (
        "repeat the voting with a standing vote",
        _essential(
            "the response to Division",
            ("standing vote",),
            expects="Division is answered by retaking the vote as a standing vote",
        ),
    ),
    (
        "a vote to specifically authorize their use is not required",
        _essential(
            "the NOT-accurate statement",
            ("specifically authorize",),
            expects="a vote to authorize keypads IS required — this option is the inaccurate one",
        ),
    ),
    (
        "Yes, a majority voted in favor of the motion",
        _essential(
            "the ruling",
            ("majority voted in favor",),
            expects="5 to 4 is a majority of those voting — the motion is adopted",
        ),
    ),
    (
        "the ballot vote is secret so it is not allowed",
        _essential(
            "the ruling",
            ("secret",),
            expects="a secret ballot cannot be changed after it is cast",
        ),
    ),
    # --- Domain 6: Being a Professional Parliamentarian ----------------------
    (
        "She can Renew the issue explaining why the renovations",
        _essential(
            "the NOT-proper answer",
            ("renew the issue",),
            expects="an original main motion cannot simply be 'renewed' in the same session",
        ),
    ),
    (
        "Notice of the September meeting is required",
        _essential(
            "which meeting needs notice",
            ("september",),
            expects="only the September meeting (after a gap) needs notice",
        ),
    ),
    (
        "two-thirds vote of the members to authorize its introduction",
        _essential(
            "the vote threshold",
            ("twothirds",),
            expects="a motion outside the object needs a two-thirds vote to introduce",
        ),
    ),
    (
        "substantially different because of the change in circumstances",
        _essential(
            "the ruling",
            ("substantially different",),
            expects="changed circumstances make it a substantially different question",
        ),
    ),
    (
        "call the member to order and ask the assembly if he should be allowed",
        _essential(
            "the response",
            ("call the member to order",),
            expects="the chair calls the member to order for attacking motives",
        ),
    ),
    # --- Domain 7: Boards and Committees / Bylaws ----------------------------
    (
        "legitimate method for electing a committee member",
        _essential(
            "the ruling",
            ("legitimate method",),
            expects="a ballot vote is a legitimate method to elect a committee member",
        ),
    ),
    (
        "not counted in determining the quorum, but she has full rights to speak",
        _essential(
            "ex-officio rights",
            ("full rights to speak",),
            expects="an ex-officio member is uncounted for quorum but has full speak/vote rights",
        ),
    ),
    (
        "Motions require a second.",
        _essential(
            "the NOT-applicable rule",
            ("second",),
            expects="in a small board motions need NOT be seconded — this rule doesn't apply",
        ),
    ),
    (
        "custom falls to the ground if a proper Point of Order is raised",
        _essential(
            "the ruling",
            ("falls to the ground",),
            expects="a custom contrary to RONR falls when a point of order is raised",
        ),
    ),
    (
        "To raise the dues to $95 a year",
        _essential(
            "the in-scope amendment",
            ("95",),
            expects="only $95 stays within the noticed $60-$100 range",
        ),
    ),
    (
        "the motion creating the committee, or subsequent instructions adopted",
        _essential(
            "the authorization",
            ("subsequent instructions",),
            expects="the committee may meet electronically if its authorizing motion allows it",
        ),
    ),
)


def authored_rubric(correct_answer: str) -> Rubric | None:
    """Return the hand-authored rubric for a gold question, matched by the
    unique key substring of its keyed-correct option. ``None`` when no authored
    rubric covers the answer (the grader then derives one, as before)."""
    low = correct_answer.lower()
    for key, rubric in _GOLD_RUBRICS:
        if key.lower() in low:
            return rubric
    return None
