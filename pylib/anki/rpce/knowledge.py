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


# --- Canonical order of precedence (persisted so any subset can be verified) --
#
# Precedence is NOT a cloze fact (too many valid orderings/combinations to fill a
# blank). This tuple is the single persisted source of truth, highest → lowest;
# ordering / which-ranks-higher questions grade any random subset against it.
PRECEDENCE_ORDER: tuple[str, ...] = tuple(m.name for m in ranked_motions())


def precedence_index(name: str) -> int:
    """Position of a ranked motion in the canonical order (0 = highest)."""
    return PRECEDENCE_ORDER.index(name)


def canonical_order(names: list[str]) -> list[str]:
    """The given motions sorted by canonical precedence (highest first)."""
    return sorted(names, key=precedence_index)


def is_ordered_by_precedence(names: list[str]) -> bool:
    """True if ``names`` are already in canonical precedence order (highest first).
    Verifies an arbitrary subset without assuming which motions it contains."""
    idx = [precedence_index(n) for n in names]
    return idx == sorted(idx)


def motions_higher_than(pivot: str, pool: list[str]) -> list[str]:
    """Names in ``pool`` that outrank ``pivot`` (take precedence over it)."""
    p = precedence_index(pivot)
    return [n for n in pool if precedence_index(n) < p]


def motions_lower_than(pivot: str, pool: list[str]) -> list[str]:
    """Names in ``pool`` that yield to ``pivot`` (lower precedence)."""
    p = precedence_index(pivot)
    return [n for n in pool if precedence_index(n) > p]


# Names like "Adjourn" read fine as "the motion to Adjourn"; these do not
# ("the motion to Main Motion"), so a question stem refers to them naturally.
_PHRASE_OVERRIDE = {
    "Main Motion": "a main motion",
    "Previous Question": "the motion for the Previous Question",
    "Point of Order": "a Point of Order",
    "Appeal": "an Appeal",
    "Object to the Consideration of a Question": (
        "an Objection to the Consideration of a Question"
    ),
    "Division of the Assembly": "a Division of the Assembly",
}


def motion_phrase(name: str) -> str:
    """How to refer to a motion inside a question stem, in natural English."""
    return _PHRASE_OVERRIDE.get(name, f"the motion to {name}")


#: Hint for a needs-a-second MCQ. Positive framing ("second"), never the answer.
SECOND_HINT = "a second — or no second?"


def characteristic_mcq(motion: Motion, which: str) -> dict:
    """Build an applied MCQ about one motion attribute, from the motion data.

    ``which`` is ``second`` | ``debatable`` | ``amendable`` | ``vote``. The
    second card carries a HINT; the debatable card uses the short
    "Debatable / Not debatable" wording (spec §16). Returns the render-payload
    fields (stem/options/answer, plus ``hint`` where set); the caller adds the
    citation + quote.
    """
    phrase = motion_phrase(motion.name)
    if which == "second":
        return {
            "stem": f"Does {phrase} require a second?",
            "options": ["Requires a second", "No second required"],
            "answer": 0 if motion.second else 1,
            "hint": SECOND_HINT,
        }
    if which == "debatable":
        # Short "debatable / not debatable" form (shorter than a full sentence).
        return {
            "stem": f"{motion.name}: debatable or not debatable?",
            "options": ["Debatable", "Not debatable"],
            "answer": 0 if motion.debatable else 1,
        }
    if which == "amendable":
        return {
            "stem": f"Can {phrase} be amended?",
            "options": ["Amendable", "Not amendable"],
            "answer": 0 if motion.amendable else 1,
        }
    if which == "vote":
        opts = [VOTE_LABELS[VOTE_MAJORITY], VOTE_LABELS[VOTE_TWO_THIRDS], VOTE_LABELS[VOTE_NONE]]
        return {
            "stem": f"What vote does {phrase} require to be adopted?",
            "options": opts,
            "answer": opts.index(VOTE_LABELS[motion.vote]),
        }
    raise ValueError(f"unknown characteristic: {which}")


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
