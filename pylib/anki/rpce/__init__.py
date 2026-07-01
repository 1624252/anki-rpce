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

import base64
import json
import re
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


#: Notetype for every RPCE question. One note = one question of a given Kind
#: (cloze | mcq | order), fully described by a base64-JSON Payload the shared
#: renderer reads. PlainQ/PlainA are the no-JS fallback (and what the browser and
#: search show); Citation/Quote are the RONR (12th ed.) source shown with the
#: answer. Bumping the name triggers a clean deck rebuild on profile open.
QUESTION_NOTETYPE = "RPCE Q 1"

#: Question kinds (payload["kind"]).
KIND_CLOZE = "cloze"
KIND_MCQ = "mcq"
KIND_ORDER = "order"

_CLOZE_RE = re.compile(r"\{\{c\d+::(.*?)\}\}")


def payload_b64(payload: dict) -> str:
    """Encode a render payload as base64 JSON (safe in an HTML attribute)."""
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def hint_for(term: str) -> str:
    """A light hint so a cloze blank isn't guesswork (length + first letter)."""
    n = len(term.replace(" ", ""))
    return f"{n}-letter word starting '{term[0].lower()}'" if term else ""


def cloze_to_payload_text(cloze: str) -> tuple[str, list[dict]]:
    """Convert ``{{c1::term}}`` markup to ``[[i]]`` blanks + a hinted blanks list."""
    blanks: list[dict] = []

    def repl(m: re.Match) -> str:
        term = m.group(1)
        i = len(blanks)
        blanks.append({"a": term, "h": hint_for(term)})
        return f"[[{i}]]"

    return _CLOZE_RE.sub(repl, cloze), blanks


def _question_notetype(col: Collection):
    from . import render_js

    mm = col.models
    existing = mm.by_name(QUESTION_NOTETYPE)
    if existing is not None:
        return existing
    m = mm.new(QUESTION_NOTETYPE)
    for field in ("Kind", "Payload", "PlainQ", "PlainA", "Citation", "Quote"):
        mm.add_field(m, mm.new_field(field))
    tmpl = mm.new_template("Question")
    # The hidden payload feeds the interactive renderer (phone); PlainQ is the
    # no-JS fallback. The answer shows PlainA + the RONR citation/quote.
    tmpl["qfmt"] = (
        '<div class="rpce-plain">{{PlainQ}}</div>'
        '<div id="rpce-payload" data-kind="{{Kind}}" data-p="{{Payload}}" '
        'style="display:none"></div>'
    )
    tmpl["afmt"] = (
        "{{PlainA}}"
        "{{#Citation}}<div class=rpce-ref>"
        "<div class=rpce-cite>RONR (12th ed.) {{Citation}}</div>"
        "<div class=rpce-quote>&ldquo;{{Quote}}&rdquo;</div></div>{{/Citation}}"
    )
    m["css"] = render_js.RENDER_CSS + ".card{font-size:18px;color:#0a1f44}"
    mm.add_template(m, tmpl)
    mm.add(m)
    return mm.by_name(QUESTION_NOTETYPE)


def add_question_note(
    col: Collection,
    deck_id: int,
    *,
    payload: dict,
    plain_q: str,
    plain_a: str,
    domain: int,
    concept_id: str,
) -> None:
    """Add one question note from a render payload (kind lives in the payload)."""
    from .transfer_ladder import FORMAT_TAG_PREFIX, concept_tag

    model = _question_notetype(col)
    note = col.new_note(model)
    note["Kind"] = payload["kind"]
    note["Payload"] = payload_b64(payload)
    note["PlainQ"] = plain_q
    note["PlainA"] = plain_a
    note["Citation"] = payload.get("cite", "")
    note["Quote"] = payload.get("quote", "")
    note.tags = [
        domain_tag(domain),
        concept_tag(concept_id),
        f"{FORMAT_TAG_PREFIX}::{payload['kind']}",
    ]
    col.add_note(note, deck_id)


def build_starter_deck(col: Collection, name: str = "RPCE") -> int:
    """Build the offline starter deck: a cloze and an applied-MCQ question for
    each curated concept, covering all seven domains. Used as the no-corpus
    fallback and by tests; the full 1000-question deck is imported from the
    starter ``.apkg`` (see ``pylib/tools/rpce_export_starter.py``). Returns the
    deck id."""
    from . import flashcards

    deck_id = col.decks.id(name)
    assert deck_id is not None
    # FSRS on so the memory score uses real retrievability (spec §8).
    col.set_config("fsrs", True)
    _question_notetype(col)

    for card in flashcards.all_flashcards():
        text, blanks = cloze_to_payload_text(card.cloze)
        cid = str(card.concept_id)
        cloze_payload = {
            "kind": KIND_CLOZE,
            "text": text,
            "blanks": blanks,
            "cite": card.ref.section,
            "quote": card.ref.quote,
        }
        add_question_note(
            col,
            deck_id,
            payload=cloze_payload,
            plain_q="Fill the blank(s): " + _CLOZE_RE.sub("_____", card.cloze),
            plain_a=", ".join(b["a"] for b in blanks),
            domain=card.domain_code,
            concept_id=cid,
        )
        mcq_payload = {
            "kind": KIND_MCQ,
            "stem": card.mcq_question,
            "options": list(card.mcq_options),
            "answer": card.mcq_answer_index,
            "cite": card.ref.section,
            "quote": card.ref.quote,
        }
        add_question_note(
            col,
            deck_id,
            payload=mcq_payload,
            plain_q=card.mcq_question,
            plain_a=flashcards.mcq_back(card),
            domain=card.domain_code,
            concept_id=cid,
        )
    return deck_id
