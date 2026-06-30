# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Learning-phase progression: flashcards first, then simulation.

Implements the scaffolding-by-expertise idea (Insight 3 / app design): start
with recall flashcards to build durable memory, then transition to
simulation-based Section II practice with debriefing as experience grows. The
phase is derived from the learner's own history (reviews, coverage, graded
scenarios), so the app nudges the right activity at the right time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import coverage_pct
from .scores import graded_reviews, graded_scenarios

if TYPE_CHECKING:
    from anki.collection import Collection


@dataclass
class Phase:
    key: str  # foundations | application | mastery
    title: str
    focus: str  # the recommended activity


def current_phase(
    col: Collection,
    *,
    foundations_reviews: int = 50,
    min_coverage: float = 0.5,
    application_scenarios: int = 5,
) -> Phase:
    """Recommend the learner's current phase and focus activity.

    - **Foundations:** not enough recall reps or coverage → drill flashcards.
    - **Application:** recall established → keep flashcards, add scenarios.
    - **Mastery:** enough scenarios graded → lead with simulation.
    """
    reviews = graded_reviews(col)
    scenarios = graded_scenarios(col)
    cov = coverage_pct(col)

    if reviews < foundations_reviews or cov < min_coverage:
        return Phase(
            "foundations",
            "Foundations",
            "Build recall with flashcards (cloze + multiple-choice) across all domains.",
        )
    if scenarios < application_scenarios:
        return Phase(
            "application",
            "Application",
            "Keep flashcards going and begin Section II scenario practice with debriefs.",
        )
    return Phase(
        "mastery",
        "Mastery",
        "Lead with Section II scenarios; use flashcards to plug weak spots.",
    )
