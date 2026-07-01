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
        return f"RONR (12th ed.) {self.section}"


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
