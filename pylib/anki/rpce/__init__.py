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


#: Name of the notetype that carries every format of one concept in one note.
#: (Versioned: bumping the name triggers a clean deck rebuild on profile open.)
#: v2 adds the RONR (12th ed.) Citation + Quote shown with every answer.
TRANSFER_NOTETYPE = "RPCE Concept 2"

#: Delimiter separating the individual MCQ options within the MCQOptions field.
MCQ_OPTION_SEP = "||"


def _transfer_notetype(col: Collection):
    """Get (or create) the single-card, multi-format concept notetype.

    A concept is **one problem** for spaced repetition: one note → one card →
    one FSRS schedule (Spiky POV 1 / spec §7.1). The card carries every format
    of the concept in its fields; the Transfer Ladder rotates which format is
    *shown* each repetition (`transfer_ladder.rung_for_reps`), so the same
    problem never appears in the same shape twice in a row while repeating on a
    single schedule — exactly as the algorithm repeats one problem.
    """
    from . import transfer_ladder

    mm = col.models
    existing = mm.by_name(TRANSFER_NOTETYPE)
    if existing is not None:
        return existing
    m = mm.new(TRANSFER_NOTETYPE)
    # MCQQ = stem; MCQA = correct-answer text; MCQOptions = the options joined by
    # MCQ_OPTION_SEP; MCQIdx = index of the correct option (for interactive MCQ).
    # Citation/Quote = the RONR (12th ed.) section and verbatim excerpt shown
    # with every answer (project accuracy rule; spec §6/§9).
    for field in (
        "Concept",
        "Domain",
        "ClozeQ",
        "ClozeA",
        "MCQQ",
        "MCQA",
        "MCQOptions",
        "MCQIdx",
        "Citation",
        "Quote",
    ):
        mm.add_field(m, mm.new_field(field))
    tmpl = mm.new_template("Concept")
    # Default rendering (used where the desktop format-rotation hook is absent,
    # e.g. the phone): the cloze recall prompt. Every answer carries the RONR
    # citation + verbatim quote.
    tmpl["qfmt"] = "{{ClozeQ}}"
    tmpl["afmt"] = (
        "{{FrontSide}}<hr id=answer>{{ClozeA}}"
        "{{#Citation}}<div class=rpce-ref>"
        "<div class=rpce-cite>RONR (12th ed.) {{Citation}}</div>"
        "<div class=rpce-quote>&ldquo;{{Quote}}&rdquo;</div></div>{{/Citation}}"
    )
    m["css"] = (
        ".card{font-size:18px;color:#0a1f44}"
        # Revealed cloze blank — a distinct color so the answer stands out.
        f".cloze-reveal{{color:{transfer_ladder.CLOZE_REVEAL_COLOR};font-weight:700}}"
        ".rpce-ref{margin-top:18px;padding:14px 16px;border-left:4px solid #2f6fed;"
        "background:#eef4ff;border-radius:10px;text-align:left}"
        ".rpce-cite{font-weight:700;color:#1b3faa;font-size:15px}"
        ".rpce-quote{margin-top:6px;font-style:italic;color:#0a1f44;font-size:16px}"
    )
    mm.add_template(m, tmpl)
    mm.add(m)
    return mm.by_name(TRANSFER_NOTETYPE)


def build_starter_deck(col: Collection, name: str = "RPCE") -> int:
    """Create the starter deck with **one card per concept** (same problem,
    one schedule), each carrying multiple formats that rotate on review.

    Each concept becomes a single ``RPCE Transfer`` note tagged with its domain
    (`rpce::domain::N`) and concept (`rpce::concept::C`). The cloze recall and
    applied multiple-choice forms live in that one note's fields; the desktop
    rotates between them per repetition (Spiky POV 1). Section II free-text
    scenarios are practised separately. Returns the deck id.
    """
    from . import flashcards
    from .transfer_ladder import concept_tag

    deck_id = col.decks.id(name)
    assert deck_id is not None
    # Enable FSRS so the memory score uses real retrievability (spec §8), not
    # only the reps/lapses heuristic fallback.
    col.set_config("fsrs", True)
    model = _transfer_notetype(col)

    for card in flashcards.all_flashcards():
        note = col.new_note(model)
        note["Concept"] = str(card.concept_id)
        note["Domain"] = str(card.domain_code)
        note["ClozeQ"] = flashcards.cloze_question(card)
        note["ClozeA"] = flashcards.cloze_answer(card)
        note["MCQQ"] = card.mcq_question
        note["MCQA"] = flashcards.mcq_back(card)
        note["MCQOptions"] = MCQ_OPTION_SEP.join(card.mcq_options)
        note["MCQIdx"] = str(card.mcq_answer_index)
        note["Citation"] = card.ref.section
        note["Quote"] = card.ref.quote
        note.tags = [domain_tag(card.domain_code), concept_tag(card.concept_id)]
        col.add_note(note, deck_id)

    return deck_id
