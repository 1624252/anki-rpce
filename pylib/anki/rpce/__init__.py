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


#: Notetype for every stand-alone RPCE question. One note = one question of a
#: given Kind (cloze | mcq | multi | order), fully described by a base64-JSON
#: Payload the shared renderer reads. PlainQ/PlainA are the no-JS fallback (and
#: what the browser and search show); Citation/Quote are the RONR (12th ed.)
#: source shown with the answer. Used for the generated bank and the precedence
#: question types. Bumping the name triggers a clean deck rebuild on profile open.
QUESTION_NOTETYPE = "RPCE Q 1"

#: Notetype for a taught *concept*: one note carries every format that teaches
#: it (a cloze recall card + applied-MCQ card, plus second/debatable
#: characteristic cards where the concept is a motion). Each format is its own
#: card **template**, so the cards are Anki **siblings** of one note — Anki
#: buries siblings and spaces them, so two formats of the same concept never show
#: back-to-back (spec §14). One concept = one note keeps GUIDs stable for sync.
CONCEPT_NOTETYPE = "RPCE Concept 1"

#: Deck content version. Bump when regenerating so the desktop re-seeds from the
#: refreshed starter deck (notes carry an ``rpce::ver::N`` tag; see _on_profile_open).
RPCE_DECK_VERSION = "13"

#: Question kinds (payload["kind"]).
KIND_CLOZE = "cloze"
KIND_MCQ = "mcq"
KIND_MULTI = "multi"
KIND_ORDER = "order"

_CLOZE_RE = re.compile(r"\{\{c\d+::(.*?)\}\}")


def payload_b64(payload: dict) -> str:
    """Encode a render payload as base64 JSON (safe in an HTML attribute)."""
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def stable_guid(key: str) -> str:
    """A deterministic note GUID from a stable key, so re-seeding the generated
    deck updates the same notes (clean two-way sync) instead of duplicating."""
    import hashlib

    digest = hashlib.sha256(key.encode("utf-8")).digest()[:9]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def hint_for(term: str) -> str:
    """Cloze blanks carry NO hint: the defining sentence + citation carry the
    recall, and any hint tends to give the answer away (the candidate asked us
    to remove them). Kept as a function so callers stay unchanged; always "".
    """
    return ""


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
        "<div class=rpce-cite>RONR (12th ed.) &sect;{{Citation}}</div>"
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
    note.guid = stable_guid(f"q|{concept_id}|{payload['kind']}|{plain_q}")
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
        f"rpce::ver::{RPCE_DECK_VERSION}",
    ]
    col.add_note(note, deck_id)


#: Concept-note format → (payload field, plain-question field, plain-answer
#: field, payload kind). Each format is one card template; a concept note only
#: generates the cards whose payload field is filled (Anki skips empty fronts).
#: Two-option MCQs (second/debatable) were dropped — those facts are covered in
#: cloze form + the Reference tables (spec: no 2-answer multiple choice).
_CONCEPT_FORMATS: tuple[tuple[str, str, str, str, str], ...] = (
    ("cloze", "ClozePayload", "ClozeQ", "ClozeA", KIND_CLOZE),
    ("mcq", "McqPayload", "McqQ", "McqA", KIND_MCQ),
)

_CONCEPT_FIELDS: tuple[str, ...] = ("Concept", "Citation", "Quote") + tuple(
    f for _, pf, qf, af, _k in _CONCEPT_FORMATS for f in (pf, qf, af)
)


def _concept_notetype(col: Collection):
    """One notetype, one card template per format; the cards of a concept are
    siblings of a single note so Anki buries/spaces them (spec §14)."""
    from . import render_js

    mm = col.models
    existing = mm.by_name(CONCEPT_NOTETYPE)
    if existing is not None:
        return existing
    m = mm.new(CONCEPT_NOTETYPE)
    for field in _CONCEPT_FIELDS:
        mm.add_field(m, mm.new_field(field))
    ref = (
        "{{#Citation}}<div class=rpce-ref>"
        "<div class=rpce-cite>RONR (12th ed.) &sect;{{Citation}}</div>"
        "<div class=rpce-quote>&ldquo;{{Quote}}&rdquo;</div></div>{{/Citation}}"
    )
    for name, pf, qf, af, kind in _CONCEPT_FORMATS:
        tmpl = mm.new_template(name)
        # {{#pf}} gates card generation: no payload → empty front → no card.
        tmpl["qfmt"] = (
            f"{{{{#{pf}}}}}"
            f'<div class="rpce-plain">{{{{{qf}}}}}</div>'
            f'<div id="rpce-payload" data-kind="{kind}" data-p="{{{{{pf}}}}}" '
            f'style="display:none"></div>{{{{/{pf}}}}}'
        )
        tmpl["afmt"] = f"{{{{#{pf}}}}}{{{{{af}}}}}{ref}{{{{/{pf}}}}}"
        mm.add_template(m, tmpl)
    m["css"] = render_js.RENDER_CSS + ".card{font-size:18px;color:#0a1f44}"
    mm.add(m)
    return mm.by_name(CONCEPT_NOTETYPE)


def add_concept_note(
    col: Collection,
    deck_id: int,
    *,
    concept_id: str,
    domain: int,
    cite: str,
    quote: str,
    formats: dict[str, tuple[dict, str, str]],
) -> None:
    """Add one concept note whose formats become sibling cards.

    ``formats`` maps a format key (``cloze`` | ``mcq`` | ``second`` |
    ``debatable``) to ``(payload, plain_q, plain_a)``. The GUID is derived from
    the concept id so re-seeding updates the same note (clean sync)."""
    from .transfer_ladder import concept_tag

    model = _concept_notetype(col)
    note = col.new_note(model)
    note.guid = stable_guid(f"concept|{concept_id}")
    note["Concept"] = concept_id
    note["Citation"] = cite
    note["Quote"] = quote
    for _name, pf, qf, af, _kind in _CONCEPT_FORMATS:
        entry = formats.get(_name)
        if entry is None:
            continue
        payload, plain_q, plain_a = entry
        note[pf] = payload_b64(payload)
        note[qf] = plain_q
        note[af] = plain_a
    # One note = one concept; no single format tag (formats are per-card).
    note.tags = [
        domain_tag(domain),
        concept_tag(concept_id),
        f"rpce::ver::{RPCE_DECK_VERSION}",
    ]
    col.add_note(note, deck_id)


def _characteristic_payload(char: dict, cite: str, quote: str) -> dict:
    """A render payload for a motion-characteristic MCQ (from knowledge)."""
    payload = {
        "kind": KIND_MCQ,
        "stem": char["stem"],
        "options": list(char["options"]),
        "answer": char["answer"],
        "cite": cite,
        "quote": quote,
    }
    if char.get("hint"):
        payload["hint"] = char["hint"]
    return payload


def _mcq_plain(char: dict) -> tuple[str, str]:
    """No-JS question/answer text for a characteristic MCQ (with any hint)."""
    q = char["stem"]
    if char.get("hint"):
        q += f" (Hint: {char['hint']})"
    a = f"{'ABCD'[char['answer']]}) {char['options'][char['answer']]}"
    return q, a


def _precedence_notes(col: Collection, deck_id: int) -> None:
    """Add dedicated motion-precedence questions (ordering + multiselect), graded
    against the canonical order in :mod:`knowledge` — never cloze (spec §15).

    Ordering: put a random subset in order of precedence. Multiselect: which of a
    set rank higher / lower than a pivot. Both are verified against
    :data:`knowledge.PRECEDENCE_ORDER` for any subset, so they stay correct."""
    from . import knowledge as kb
    from . import refs

    ref = refs.PRECEDENCE
    ranked = [m.name for m in kb.ranked_motions()]

    def order_q(subset: list[str], n: int) -> None:
        ordered = kb.canonical_order(subset)
        assert kb.is_ordered_by_precedence(ordered)  # self-check against canon
        payload = {
            "kind": KIND_ORDER,
            "prompt": "Put these motions in order of precedence "
            "(top = higher, bottom = lower).",
            "order": ordered,
            "cite": ref.section,
            "quote": ref.quote,
        }
        add_question_note(
            col,
            deck_id,
            payload=payload,
            plain_q=payload["prompt"],
            plain_a=" → ".join(ordered),
            domain=2,
            concept_id=f"prec-order-{n}",
        )

    def multi_q(pivot: str, pool: list[str], direction: str, n: int) -> None:
        winners = (
            kb.motions_higher_than(pivot, pool)
            if direction == "higher"
            else kb.motions_lower_than(pivot, pool)
        )
        correct = [i for i, name in enumerate(pool) if name in winners]
        verb = (
            "rank higher than (take precedence over)"
            if direction == "higher"
            else "rank lower than (yield to)"
        )
        stem = f"Select ALL of these motions that {verb} {kb.motion_phrase(pivot)}."
        payload = {
            "kind": KIND_MULTI,
            "stem": stem,
            "options": list(pool),
            "correct": correct,
            "cite": ref.section,
            "quote": ref.quote,
        }
        add_question_note(
            col,
            deck_id,
            payload=payload,
            plain_q=stem,
            plain_a=", ".join(pool[i] for i in correct) or "(none)",
            domain=2,
            concept_id=f"prec-{direction}-{n}",
        )

    order_q(ranked[0:5], 1)  # the five privileged motions
    order_q(ranked[5:10], 2)  # a subsidiary window
    multi_q(
        "Postpone to a Certain Time",
        ["Amend", "Recess", "Commit or Refer", "Previous Question", "Postpone Indefinitely"],
        "higher",
        1,
    )
    multi_q(
        "Recess",
        ["Adjourn", "Amend", "Lay on the Table", "Fix the Time to Which to Adjourn"],
        "lower",
        1,
    )


def build_starter_deck(
    col: Collection, name: str = "RPCE", fallback_precedence: bool = True
) -> int:
    """Build the offline starter deck. Each curated concept becomes ONE note with
    sibling cards (a cloze recall card + an applied-MCQ card, plus second/
    debatable characteristic cards for motions), so two formats of a concept
    never show back-to-back (spec §14). Adds dedicated motion-precedence question
    types (ordering + multiselect, spec §15). Covers all seven domains; used as
    the no-corpus fallback and by tests (the full deck ships as an ``.apkg`` —
    see ``pylib/tools/rpce_export_starter.py``). Returns the deck id."""
    from . import flashcards
    from . import knowledge as kb

    deck_id = col.decks.id(name)
    assert deck_id is not None
    # FSRS on so the memory score uses real retrievability (spec §8).
    col.set_config("fsrs", True)
    # No daily study cap — a candidate should be able to drill every due card,
    # not hit Anki's default 20-new/200-review/day limit. Syncs via deck config.
    try:
        conf = col.decks.config_dict_for_deck_id(deck_id)
        conf["new"]["perDay"] = 9999
        conf["rev"]["perDay"] = 9999
        # NO_SORT: keep the deck's built-in add-order, which the exporter lays out
        # round-robin by question type. A uniform RANDOM_CARD order over-showed the
        # most common type (too many MCQs); add-order interleaving gives each type
        # a roughly equal chance early in a session while staying sync-stable
        # (positions come from add-order on import, identical on every device).
        conf["newSortOrder"] = 1  # NEW_CARD_SORT_ORDER_NO_SORT
        col.decks.update_config(conf)
    except Exception as exc:  # never block deck build over limits
        print(f"RPCE deck-config error: {exc}")
    _concept_notetype(col)
    _question_notetype(col)

    for card in flashcards.all_flashcards():
        text, blanks = cloze_to_payload_text(card.cloze)
        cid = str(card.concept_id)
        cite, quote = card.ref.section, card.ref.quote
        formats: dict[str, tuple[dict, str, str]] = {
            "cloze": (
                {
                    "kind": KIND_CLOZE,
                    "text": text,
                    "blanks": blanks,
                    "cite": cite,
                    "quote": quote,
                },
                "Fill the blank(s): " + _CLOZE_RE.sub("_____", card.cloze),
                ", ".join(b["a"] for b in blanks),
            ),
            "mcq": (
                {
                    "kind": KIND_MCQ,
                    "stem": card.mcq_question,
                    "options": list(card.mcq_options),
                    "answer": card.mcq_answer_index,
                    "cite": cite,
                    "quote": quote,
                },
                card.mcq_question,
                flashcards.mcq_back(card),
            ),
        }
        # Motion concepts also get second/debatable characteristic cards (§16):
        # the second card carries a hint; debatable uses short wording.
        if card.motion_name:
            motion = kb.by_name(card.motion_name)
            for which in ("second", "debatable"):
                char = kb.characteristic_mcq(motion, which)
                q, a = _mcq_plain(char)
                formats[which] = (_characteristic_payload(char, cite, quote), q, a)
        add_concept_note(
            col,
            deck_id,
            concept_id=cid,
            domain=card.domain_code,
            cite=cite,
            quote=quote,
            formats=formats,
        )

    # Precedence (ordering + multiselect) questions ship via the generated
    # data/rpce_precedence_questions.json, loaded and round-robined WITH the
    # authored MCQ/cloze so every type is interleaved (rpce_export_starter.py).
    # The tiny offline fallback (no apkg) still seeds a couple directly.
    if fallback_precedence:
        _precedence_notes(col, deck_id)
    return deck_id
