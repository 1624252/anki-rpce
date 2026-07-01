# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Structured RONR (12th ed.) facts: the motions and their characteristics.

Prose cloze cards can't test things like *order of precedence* or *what vote a
motion needs* — there are too many combinations to fill a single blank. Those
belong in question types that give the candidate enough to answer: ranking and
ordering (precedence), and multiple choice (vote / debatable / second). This
module is the single source of truth for that structured knowledge and for the
Reference tab's tables. Each motion carries its RONR section so answers cite it
(the section never appears in a question stem or option — spec §7).

Characteristics follow RONR (12th ed.) §21–§37 and the tinted "Table of Rules
Relating to Motions". ``vote`` is what the motion itself needs to be adopted.
"""

from __future__ import annotations

from dataclasses import dataclass

VOTE_MAJORITY = "majority"
VOTE_TWO_THIRDS = "two-thirds"
VOTE_NONE = "none"  # decided by the chair, or a demand that needs no vote

#: Human-readable vote labels (used in options and the Reference tab).
VOTE_LABELS = {
    VOTE_MAJORITY: "Majority vote",
    VOTE_TWO_THIRDS: "Two-thirds vote",
    VOTE_NONE: "No vote (chair rules / demand)",
}

CLASS_PRIVILEGED = "privileged"
CLASS_SUBSIDIARY = "subsidiary"
CLASS_MAIN = "main"
CLASS_INCIDENTAL = "incidental"


@dataclass(frozen=True)
class Motion:
    name: str
    section: int  # RONR (12th ed.) section number → answer citation
    #: Rank in the order of precedence, 1 = highest. None = no fixed precedence
    #: (main motion is lowest; incidental motions have no rank).
    rank: int | None
    klass: str
    second: bool
    debatable: bool
    amendable: bool
    vote: str

    @property
    def citation(self) -> str:
        # A section-level citation (e.g. "21"); the exact paragraph quote is
        # attached from the corpus at generation time.
        return str(self.section)


# Order of precedence, highest → lowest (privileged, then subsidiary), then the
# main motion. Ranks are contiguous so ordering questions can shuffle a subset.
MOTIONS: tuple[Motion, ...] = (
    # Privileged
    Motion(
        "Fix the Time to Which to Adjourn",
        22,
        1,
        CLASS_PRIVILEGED,
        True,
        False,
        True,
        VOTE_MAJORITY,
    ),
    Motion("Adjourn", 21, 2, CLASS_PRIVILEGED, True, False, False, VOTE_MAJORITY),
    Motion("Recess", 20, 3, CLASS_PRIVILEGED, True, False, True, VOTE_MAJORITY),
    Motion(
        "Raise a Question of Privilege",
        19,
        4,
        CLASS_PRIVILEGED,
        False,
        False,
        False,
        VOTE_NONE,
    ),
    Motion(
        "Call for the Orders of the Day",
        18,
        5,
        CLASS_PRIVILEGED,
        False,
        False,
        False,
        VOTE_NONE,
    ),
    # Subsidiary
    Motion(
        "Lay on the Table", 17, 6, CLASS_SUBSIDIARY, True, False, False, VOTE_MAJORITY
    ),
    Motion(
        "Previous Question",
        16,
        7,
        CLASS_SUBSIDIARY,
        True,
        False,
        False,
        VOTE_TWO_THIRDS,
    ),
    Motion(
        "Limit or Extend Limits of Debate",
        15,
        8,
        CLASS_SUBSIDIARY,
        True,
        False,
        True,
        VOTE_TWO_THIRDS,
    ),
    Motion(
        "Postpone to a Certain Time",
        14,
        9,
        CLASS_SUBSIDIARY,
        True,
        True,
        True,
        VOTE_MAJORITY,
    ),
    Motion(
        "Commit or Refer", 13, 10, CLASS_SUBSIDIARY, True, True, True, VOTE_MAJORITY
    ),
    Motion("Amend", 12, 11, CLASS_SUBSIDIARY, True, True, True, VOTE_MAJORITY),
    Motion(
        "Postpone Indefinitely",
        11,
        12,
        CLASS_SUBSIDIARY,
        True,
        True,
        False,
        VOTE_MAJORITY,
    ),
    # Main
    Motion("Main Motion", 10, None, CLASS_MAIN, True, True, True, VOTE_MAJORITY),
    # Incidental (no fixed precedence; decided as they arise)
    Motion(
        "Point of Order", 23, None, CLASS_INCIDENTAL, False, False, False, VOTE_NONE
    ),
    Motion("Appeal", 24, None, CLASS_INCIDENTAL, True, True, False, VOTE_MAJORITY),
    Motion(
        "Suspend the Rules",
        25,
        None,
        CLASS_INCIDENTAL,
        True,
        False,
        False,
        VOTE_TWO_THIRDS,
    ),
    Motion(
        "Object to the Consideration of a Question",
        26,
        None,
        CLASS_INCIDENTAL,
        False,
        False,
        False,
        VOTE_TWO_THIRDS,
    ),
    Motion(
        "Division of the Assembly",
        29,
        None,
        CLASS_INCIDENTAL,
        False,
        False,
        False,
        VOTE_NONE,
    ),
)


def ranked_motions() -> list[Motion]:
    """Motions with a fixed order of precedence, highest → lowest."""
    return sorted((m for m in MOTIONS if m.rank is not None), key=lambda m: m.rank)


def by_name(name: str) -> Motion:
    for m in MOTIONS:
        if m.name == name:
            return m
    raise KeyError(name)


def yn(value: bool) -> str:
    return "Yes" if value else "No"


# --- Reference-tab tables (also exported to the phone as reference.json) ------


def precedence_table() -> list[dict]:
    """Order of precedence, highest → lowest (for the Reference tab)."""
    return [
        {"rank": m.rank, "name": m.name, "class": m.klass, "section": m.section}
        for m in ranked_motions()
    ]


def characteristics_table() -> list[dict]:
    """Second / debatable / amendable / vote for each motion (Reference tab)."""
    return [
        {
            "name": m.name,
            "class": m.klass,
            "second": yn(m.second),
            "debatable": yn(m.debatable),
            "amendable": yn(m.amendable),
            "vote": VOTE_LABELS[m.vote],
            "section": m.section,
        }
        for m in MOTIONS
    ]


def reference_tables() -> dict:
    """All reference data, for the desktop and the phone's Reference tab."""
    return {
        "precedence": precedence_table(),
        "characteristics": characteristics_table(),
        "voteLegend": VOTE_LABELS,
    }
