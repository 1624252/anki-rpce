# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Transfer Ladder — the RPCE study feature (Spiky POV 1).

"Consistency is a trap": practising one format breeds false mastery, so the
same concept should resurface in *escalating* formats rather than the same
shape twice. The rungs, low → high transfer demand:

    cloze recall → applied MCQ → free-text scenario → advising prompt

A concept's cards share a ``rpce::concept::<id>`` tag; each card's format is a
``rpce::fmt::<rung>`` tag. As mastery of a concept rises the ladder prefers a
*higher* rung than last time (forcing transfer, fading scaffolding — Insight 3);
a lapse drops it back a rung. The recall-vs-reworded gap this produces is what
the M9 study-feature experiment measures (spec §7d, §8).
"""

from __future__ import annotations

#: Format rungs in ascending order of transfer demand.
RUNGS: tuple[str, ...] = ("cloze", "mcq", "scenario", "advising")

CONCEPT_TAG_PREFIX = "rpce::concept"
FORMAT_TAG_PREFIX = "rpce::fmt"

#: Mastery at/above which the ladder advances to the next rung.
ADVANCE_THRESHOLD = 0.85


def concept_tag(concept_id: int | str) -> str:
    return f"{CONCEPT_TAG_PREFIX}::{concept_id}"


def format_tag(rung: str) -> str:
    if rung not in RUNGS:
        raise ValueError(f"unknown rung: {rung}")
    return f"{FORMAT_TAG_PREFIX}::{rung}"


def next_rung(current: str, mastery: float, lapsed: bool = False) -> str:
    """Pick the next rung for a concept given current rung and mastery.

    - On a lapse, drop one rung (re-scaffold).
    - At/above the advance threshold, climb one rung (force transfer).
    - Otherwise hold and keep practising the current rung.
    """
    if current not in RUNGS:
        raise ValueError(f"unknown rung: {current}")
    idx = RUNGS.index(current)
    if lapsed:
        return RUNGS[max(0, idx - 1)]
    if mastery >= ADVANCE_THRESHOLD and idx < len(RUNGS) - 1:
        return RUNGS[idx + 1]
    return current


def recommended_rung(history: list[tuple[str, float]]) -> str:
    """Recommend the rung to surface next for a concept.

    `history` is an ordered list of ``(rung, recall)`` for past attempts on the
    concept. Starts at ``cloze``; otherwise advances from the most recent rung
    based on its recall, treating recall below 0.5 as a lapse.
    """
    if not history:
        return RUNGS[0]
    last_rung, last_recall = history[-1]
    return next_rung(last_rung, last_recall, lapsed=last_recall < 0.5)


def is_format_repeat(history: list[tuple[str, float]], proposed: str) -> bool:
    """True if `proposed` repeats the immediately preceding rung (which the
    Transfer Ladder avoids whenever mastery allows progression)."""
    return bool(history) and history[-1][0] == proposed
