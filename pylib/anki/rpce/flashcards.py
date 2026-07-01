# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Multi-format flashcard content for the RPCE deck.

Each concept is taught in **more than one format** (Spiky POV 1 + different
learning styles): a **cloze** recall card and an **applied multiple-choice**
card for the same fact. Section II adds the free-text **scenario** (see
`scenarios.py`). Content is conservative, well-established RONR fundamentals so
it can ship offline; richer/AI-generated content is layered later (and must
pass the gold-set checker first).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import refs

_CLOZE_RE = re.compile(r"\{\{c\d+::(.*?)\}\}")


@dataclass(frozen=True)
class Flashcard:
    domain_code: int
    concept_id: int
    #: Cloze text using Anki {{c1::...}} deletions.
    cloze: str
    mcq_question: str
    mcq_options: tuple[str, ...]
    mcq_answer_index: int
    #: RONR (12th ed.) citation + verbatim quote backing this concept.
    ref: refs.Ref


FLASHCARDS: tuple[Flashcard, ...] = (
    Flashcard(
        1,
        101,
        "A main motion needs a {{c1::second}} and a {{c2::majority}} vote to be adopted.",
        "What is required to adopt a main motion?",
        (
            "A second and a majority vote",
            "Only the mover's support",
            "A two-thirds vote",
            "Unanimous consent",
        ),
        0,
        refs.MAJORITY,
    ),
    Flashcard(
        2,
        102,
        "The Previous Question (to close debate) requires a {{c1::two-thirds}} vote and is {{c2::not debatable}}.",
        "What vote does the motion for the Previous Question require?",
        ("A majority", "Two-thirds", "Unanimous consent", "One-third"),
        1,
        refs.PREVIOUS_QUESTION,
    ),
    # Order-of-precedence example (Spiky idea): MCQ is appropriate once the
    # learner has practised the full precedence chart in recall form first.
    Flashcard(
        2,
        103,
        "In order of precedence, the motion to {{c1::Adjourn}} ranks higher than the motion to {{c2::Lay on the Table}}.",
        "Which of these privileged/subsidiary motions takes precedence (is decided first)?",
        ("Lay on the Table", "Postpone Indefinitely", "Adjourn", "Amend"),
        2,
        refs.PRECEDENCE,
    ),
    Flashcard(
        3,
        104,
        "A Point of Order is {{c1::not debatable}}, needs {{c2::no second}}, and is decided by the {{c3::chair}}.",
        "How is a Point of Order handled?",
        (
            "Debated and voted on by the assembly",
            "Ruled on by the chair; no second, not debatable",
            "Referred to a committee",
            "Postponed to the next meeting",
        ),
        1,
        refs.POINT_OF_ORDER,
    ),
    Flashcard(
        4,
        105,
        "Business cannot be transacted without a {{c1::quorum}} present.",
        "What must be present before the assembly transacts substantive business?",
        (
            "A quorum",
            "The full membership",
            "A parliamentarian",
            "Unanimous attendance",
        ),
        0,
        refs.QUORUM,
    ),
    Flashcard(
        5,
        106,
        "Unless the bylaws say otherwise, election requires a {{c1::majority}} of the votes cast, not a plurality.",
        "With bylaws silent, what is needed to be elected?",
        (
            "A plurality",
            "A majority of votes cast",
            "Two-thirds",
            "The most nominations",
        ),
        1,
        refs.PLURALITY,
    ),
    Flashcard(
        6,
        107,
        "The parliamentarian {{c1::advises}} impartially; the {{c2::chair}} makes the rulings.",
        "What is the parliamentarian's role during a meeting?",
        (
            "To rule on points of order",
            "To advise impartially while the chair rules",
            "To vote on close questions",
            "To chair the meeting",
        ),
        1,
        refs.PARLIAMENTARIAN,
    ),
    Flashcard(
        7,
        108,
        "Amending the bylaws generally requires {{c1::previous notice}} and a {{c2::two-thirds}} vote.",
        "What is generally required to amend the bylaws?",
        (
            "A majority vote with no notice",
            "Previous notice and a two-thirds vote",
            "Unanimous consent",
            "Board approval only",
        ),
        1,
        refs.BYLAWS_AMENDMENT,
    ),
)


def flashcards_for(domain_code: int) -> list[Flashcard]:
    return [f for f in FLASHCARDS if f.domain_code == domain_code]


def all_flashcards() -> tuple[Flashcard, ...]:
    return FLASHCARDS


def cloze_answer(card: Flashcard) -> str:
    """The cloze sentence with all deletions revealed."""
    return _CLOZE_RE.sub(r"\1", card.cloze)


def cloze_question(card: Flashcard) -> str:
    """The cloze sentence with deletions blanked out."""
    return _CLOZE_RE.sub("[…]", card.cloze)


def mcq_back(card: Flashcard) -> str:
    """Rendered answer text for a multiple-choice card."""
    letter = "ABCD"[card.mcq_answer_index]
    return f"{letter}) {card.mcq_options[card.mcq_answer_index]}"


def mcq_front(card: Flashcard) -> str:
    """Rendered question + lettered options for a multiple-choice card."""
    lines = [card.mcq_question, ""]
    for i, opt in enumerate(card.mcq_options):
        lines.append(f"{'ABCD'[i]}) {opt}")
    return "\n".join(lines)
