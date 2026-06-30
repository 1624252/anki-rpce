# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""RPCE content model: the seven Performance-Expectation domains.

Design choice (sync-safe): rather than add custom SQLite tables (which Anki's
sync protocol would not carry), domain membership is stored as native Anki
**tags** (`rpce::domain::N`) on notes, and editable domain **weights** live in
the collection **config** — both of which sync natively between desktop and
phone. This module is the single source of truth for the domains, the tag
scheme, coverage, and the tag→weight map consumed by the Rust points-at-stake
queue (see `get_points_at_stake_queue`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.collection import Collection

#: Tag namespace marking a card's domain, e.g. ``rpce::domain::2``.
TAG_PREFIX = "rpce::domain"
#: Collection-config key holding ``{domain_code: weight}`` overrides.
CONFIG_KEY = "rpce:domain_weights"


@dataclass(frozen=True)
class Domain:
    code: int
    name: str
    #: Default exam-blueprint weight. NAP does not publish exact percentages,
    #: so these default to an equal split and are overridable via
    #: :func:`set_domain_weights` once real weights are known.
    weight: float


_EQUAL = 1.0 / 7.0

#: The seven Registered Parliamentarian Performance-Expectation domains.
DOMAINS: tuple[Domain, ...] = (
    Domain(1, "Motions in General and Main Motions", _EQUAL),
    Domain(2, "Subsidiary and Privileged Motions", _EQUAL),
    Domain(
        3,
        "Incidental Motions and Motions that Bring a Question Again Before the Assembly",
        _EQUAL,
    ),
    Domain(4, "Organization and Conduct of Meetings", _EQUAL),
    Domain(5, "Voting, Nominations, and Elections", _EQUAL),
    Domain(
        6,
        "Being and Serving as a Professional Parliamentarian and Teaching Parliamentary Procedure",
        _EQUAL,
    ),
    Domain(7, "Boards and Committees, and Writing and Interpreting Bylaws", _EQUAL),
)


def domain_tag(code: int) -> str:
    """Return the note tag for a domain code."""
    return f"{TAG_PREFIX}::{code}"


def domain_by_code(code: int) -> Domain:
    for d in DOMAINS:
        if d.code == code:
            return d
    raise KeyError(f"unknown RPCE domain code: {code}")


def set_domain_weights(col: Collection, weights: dict[int, float]) -> None:
    """Persist editable per-domain weights to the (syncing) collection config."""
    col.set_config(CONFIG_KEY, {str(k): float(v) for k, v in weights.items()})


def topic_weights(col: Collection) -> dict[str, float]:
    """Return the ``tag -> weight`` map for the points-at-stake queue.

    Uses config overrides where present, otherwise each domain's default.
    """
    overrides = col.get_config(CONFIG_KEY, None)
    out: dict[str, float] = {}
    for d in DOMAINS:
        weight = d.weight
        if isinstance(overrides, dict):
            raw = overrides.get(str(d.code))
            if raw is not None:
                weight = float(raw)
        out[domain_tag(d.code)] = weight
    return out


@dataclass
class DomainCoverage:
    code: int
    name: str
    weight: float
    cards: int


def coverage(col: Collection) -> list[DomainCoverage]:
    """Count the cards tagged to each domain (drives the coverage map)."""
    weights = topic_weights(col)
    result: list[DomainCoverage] = []
    for d in DOMAINS:
        count = len(col.find_cards(f"tag:{domain_tag(d.code)}"))
        result.append(
            DomainCoverage(d.code, d.name, weights[domain_tag(d.code)], count)
        )
    return result


def coverage_pct(col: Collection) -> float:
    """Fraction of the seven domains that have at least one card (0.0–1.0)."""
    cov = coverage(col)
    covered = sum(1 for c in cov if c.cards > 0)
    return covered / len(cov)


def build_starter_deck(col: Collection, name: str = "RPCE") -> int:
    """Create the starter deck with **multiple flashcard formats per concept**.

    For each concept we add a **cloze** recall card and an applied
    **multiple-choice** card (same fact, different formats / learning styles —
    Spiky POV 1). Section II free-text scenarios are practised separately. Cards
    are tagged with their domain (`rpce::domain::N`), concept
    (`rpce::concept::C`), and format rung (`rpce::fmt::cloze|mcq`). Returns the
    deck id.
    """
    from . import flashcards
    from .transfer_ladder import concept_tag, format_tag

    deck_id = col.decks.id(name)
    assert deck_id is not None
    basic = col.models.by_name("Basic")
    cloze_model = col.models.by_name("Cloze")
    if basic is None or cloze_model is None:
        raise RuntimeError("Basic/Cloze notetypes not found")

    for card in flashcards.all_flashcards():
        base_tags = [domain_tag(card.domain_code), concept_tag(card.concept_id)]

        # Cloze recall card.
        cloze_note = col.new_note(cloze_model)
        cloze_note["Text"] = card.cloze
        cloze_note.tags = [*base_tags, format_tag("cloze")]
        col.add_note(cloze_note, deck_id)

        # Applied multiple-choice card (same concept, different format).
        mcq_note = col.new_note(basic)
        mcq_note["Front"] = flashcards.mcq_front(card)
        mcq_note["Back"] = flashcards.mcq_back(card)
        mcq_note.tags = [*base_tags, format_tag("mcq")]
        col.add_note(mcq_note, deck_id)

    return deck_id
