# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""RONR (12th ed.) citations + verbatim quotes for the built-in content.

Every practice item — flashcard, Section II scenario, and simulation turn — must
answer with an **exact section citation** and a **relevant verbatim quote** from
that section (project rule; spec §6/§9). These pairs are transcribed directly
from the corpus in ``data/roberts_rules_of_order_12th_edition.md`` (short cited
excerpts; an inline cross-reference parenthetical is elided with "…").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ref:
    section: str  # e.g. "44:1"
    quote: str  # verbatim excerpt from that section

    def cite(self) -> str:
        return f"RONR (12th ed.) §{self.section}"


# --- One Ref per concept, reused across every mode. ---

MAJORITY = Ref(
    "44:1",
    "The basic requirement for approval of an action or choice by a deliberative "
    "assembly, except where a rule provides otherwise, is a majority vote.",
)
PREVIOUS_QUESTION = Ref(
    "16:1",
    "The Previous Question is the motion used to bring the assembly to an immediate "
    "vote on one or more pending questions; its adoption does this with certain "
    "exceptions.",
)
PRECEDENCE = Ref(
    "5:8",
    "A secondary motion thus takes precedence over the main motion; and a main motion "
    "takes precedence over nothing and yields to all applicable secondary motions.",
)
POINT_OF_ORDER = Ref(
    "23:1",
    "When a member thinks that the rules of the assembly are being violated, he can "
    'make a Point of Order (or "raise a question of order," as it is sometimes '
    "expressed), thereby calling upon the chair for a ruling and an enforcement of the "
    "regular rules.",
)
QUORUM = Ref(
    "40:1",
    "A quorum in an assembly is the number of members … who must be present in order "
    "that business can be validly transacted.",
)
PLURALITY = Ref(
    "44:11",
    "A plurality vote is the largest number of votes to be given any candidate or "
    "proposition when three or more choices are possible; the candidate or proposition "
    "receiving the largest number of votes has a plurality.",
)
PARLIAMENTARIAN = Ref(
    "47:46",
    "The parliamentarian is a consultant, commonly a professional, who advises the "
    "president and other officers, committees, and members on matters of parliamentary "
    "procedure.",
)
BYLAWS_AMENDMENT = Ref(
    "56:67",
    "These bylaws may be amended at any regular meeting of the Society by a two-thirds "
    "vote, provided that the amendment has been submitted in writing at the previous "
    "regular meeting.",
)
SCOPE_OF_NOTICE = Ref(
    "57:11",
    "If the bylaws require previous notice for their amendment … no amendment to a "
    "bylaw amendment is in order that increases the modification of the article or "
    "provision to be amended.",
)
COMMIT = Ref(
    "13:1",
    "The subsidiary motion to Commit or Refer is generally used to send a pending "
    "question to a relatively small group of selected persons—a committee—so that the "
    "question may be carefully investigated and put into better condition for the "
    "assembly to consider.",
)
POSTPONE = Ref(
    "14:1",
    "The subsidiary motion to Postpone to a Certain Time (or Postpone Definitely, or "
    "Postpone) is the motion by which action on a pending question can be put off, "
    "within limits, to a definite session, day, meeting, or hour, or until after a "
    "certain event.",
)
SUBSTITUTE = Ref(
    "12:70",
    "A primary amendment to substitute is treated similarly to a motion to strike out "
    "and insert … It is open to debate at all times while it is pending with no "
    "secondary amendment pending; and such debate may go fully into the merits of both "
    "the original text and the substitute.",
)
APPEAL = Ref(
    "24:1",
    "But any two members have the right to Appeal from his decision on such a question. "
    'By one member making (or "taking") the appeal and another seconding it, the '
    "question is taken from the chair and vested in the assembly for final decision.",
)
RECONSIDER = Ref(
    "37:10",
    "The motion to Reconsider can be made only by a member who voted with the prevailing "
    "side. In other words, a reconsideration can be moved only by one who voted aye if "
    "the motion involved was adopted, or no if the motion was lost.",
)
AMEND_PREVIOUSLY_ADOPTED = Ref(
    "35:1",
    "Amend Something Previously Adopted is the motion that can be used if it is desired "
    "to change only a part of the text, or to substitute a different version.",
)
DECORUM = Ref(
    "43:21",
    "When a question is pending, a member can condemn the nature or likely consequences "
    "of the proposed measure in strong terms, but he must avoid personalities, and under "
    "no circumstances can he attack or question the motives of another member. The "
    "measure, not the member, is the subject of debate.",
)
PARLIAMENTARIAN_IMPARTIALITY = Ref(
    "47:55",
    "A member of an assembly who acts as its parliamentarian has the same duty as the "
    "presiding officer to maintain a position of impartiality, and therefore does not "
    "make motions, participate in debate, or vote on any question except in the case of "
    "a ballot vote.",
)
