# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Card-quality checker (spec §7f "the AI card check").

Given generated cards (question + answer + citation + quote), bins each into
THREE buckets against a PRE-SET, blocking cutoff:

1. **CORRECT_USEFUL** — verified correct *and* clears the teaching-quality bar,
2. **WRONG**          — a wrong fact (worst): the answer/citation check fails,
3. **BAD_TEACHING**   — correct but vague, trivial, or a near-duplicate.

The correctness check reuses the examiner's verification primitives (its
canonicalization + forbidden-twin discrimination) and the **verbatim-citation**
rule that :mod:`tests.test_rpce_refs` enforces (every cited quote must appear
verbatim in the RONR corpus). Bad-teaching is a set of documented heuristics.
Everything here is offline + deterministic, so the counts re-run identically.

The cutoff is stated **in code, before any results** (:data:`WRONG_CUTOFF`,
:data:`BAD_TEACHING_RATIO_CUTOFF`) and blocks a failing batch (``report.ok``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from . import examiner

# --- pre-set, blocking cutoff (chosen BEFORE looking at any results) ---------
#
# A batch is shippable only when it contains NO wrong facts and at most
# BAD_TEACHING_RATIO_CUTOFF of the cards need teaching-quality rework. A single
# wrong fact is disqualifying (a confidently wrong card is the dangerous error).
WRONG_CUTOFF = 0
BAD_TEACHING_RATIO_CUTOFF = 0.30

# Near-duplicate stems above this token-Jaccard are "the same card twice".
NEAR_DUP_THRESHOLD = 0.6
# An answer whose content tokens overlap its cited quote below this fraction is
# not grounded in the source it cites (part of the answer/citation check).
GROUND_FLOOR = 0.5


class Bucket(Enum):
    CORRECT_USEFUL = 1
    WRONG = 2
    BAD_TEACHING = 3


@dataclass
class Card:
    """One generated card: a question, its answer, and the RONR citation+quote
    the answer is drawn from."""

    question: str
    answer: str  # answer core (the word/phrase or correct option)
    citation: str  # "section:paragraph", e.g. "44:1"
    quote: str  # the cited verbatim RONR excerpt
    kind: str = ""  # "cloze" / "mcq" / ... from the bank tag
    options: tuple[str, ...] = ()


@dataclass
class CardVerdict:
    card: Card
    bucket: Bucket
    reason: str


# --- correctness: the answer/citation check (bucket 2 = WRONG) ---------------

# Discriminative twins from the examiner: asserting one when the source says the
# other is a wrong fact (wrong threshold / wrong second / wrong debatability).
_TWINS: tuple[tuple[str, str], ...] = (
    ("twothirds", "majority"),
    ("majority", "twothirds"),
    ("second", "nosecond"),
    ("nosecond", "second"),
    ("debatable", "nodebate"),
    ("nodebate", "debatable"),
)


def _normalize_corpus(text: str) -> str:
    """Fold markdown/typographic noise so a cited quote can be matched as a
    verbatim substring — same normalization the refs verbatim test uses."""
    text = re.sub(r"<a id=[^>]*></a>", " ", text)  # anchors
    # Keep the VISIBLE text of an inline link (the generated bank renders a
    # cross-ref like "([**27**](#sec-27))" as the plain "(27)"), then drop the
    # markdown emphasis markers so both sides match.
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("*", "")
    text = text.replace("‘", "'").replace("’", "'")  # curly single
    text = text.replace("“", '"').replace("”", '"')  # curly double
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def citation_is_verbatim(quote: str, corpus_norm: str) -> bool:
    """True if the cited quote appears verbatim in the (normalized) corpus.

    An empty corpus means "not checkable" -> treated as verbatim (the caller
    skips the citation check when no corpus is supplied)."""
    if not corpus_norm:
        return True
    needle = _normalize_corpus(quote).strip(" .;,")
    return bool(needle) and needle in corpus_norm


def answer_contradicts_quote(answer: str, quote: str) -> bool:
    """True if the answer asserts a discriminative twin the quote contradicts
    (e.g. answer says two-thirds, the cited quote says majority)."""
    a = set(examiner._canon_seq(answer))
    q = set(examiner._canon_seq(quote))
    return any(tok in a and twin in q for tok, twin in _TWINS)


def answer_grounded(answer: str, quote: str) -> bool:
    """True if the answer's content tokens are largely present in its cited
    quote (the answer is actually backed by the source it cites). Uses the
    examiner's canonicalized tokens, so synonyms/morphology count ("debatable"
    grounds "debate", "amendable" grounds "amend"). An answer with no content
    tokens is not judged ungrounded (handled by the vague check)."""
    a = set(examiner._canon_seq(answer))
    if not a:
        return True
    q = set(examiner._canon_seq(quote))
    return len(a & q) / len(a) >= GROUND_FLOOR


def wrong_reason(card: Card, corpus_norm: str) -> str | None:
    """Return why the card is a wrong fact, or ``None`` if it verifies."""
    if not citation_is_verbatim(card.quote, corpus_norm):
        return "citation not verbatim in corpus"
    if answer_contradicts_quote(card.answer, card.quote):
        return "answer contradicts the cited quote"
    if not answer_grounded(card.answer, card.quote):
        return "answer not grounded in the cited quote"
    return None


# --- teaching quality: heuristics (bucket 3 = BAD_TEACHING) -------------------

# Single-word answers that ARE specific enough to teach: the examiner's
# parliamentary vocabulary. A one-word cloze answer outside this set (e.g.
# "difference", "after") is a low-value fill-in-the-blank.
_SPECIFIC = set(examiner._PROTECTED) | {t for t, _, _ in examiner._MOTION_TOKENS}


def is_vague(card: Card) -> bool:
    """Vague/trivial: a cloze whose answer is a single generic (non-parliamentary)
    word carries little teaching value. MCQs are exempt — their distractors give
    the card discriminating value even with a one-word key."""
    if "cloze" not in card.kind:
        return False
    canon = set(examiner._canon_seq(card.answer))
    if len(canon) >= 2:
        return False
    return not (canon & _SPECIFIC)


def is_trivially_guessable(card: Card) -> bool:
    """Given away by its own stem, or a sub-4-option MCQ (violates R5): the
    answer text appears verbatim in the question, or there are too few options."""
    if card.options and len(card.options) < 4:
        return True
    ans = card.answer.strip().lower()
    return bool(ans) and ans in card.question.lower()


def near_duplicate(card: Card, others: list[Card]) -> bool:
    """True if another card's stem is a near-duplicate (token Jaccard >= the
    threshold) — the same fact asked twice. Reuses the gold-eval Jaccard."""
    return any(
        examiner.jaccard(card.question, o.question) >= NEAR_DUP_THRESHOLD
        for o in others
        if o is not card
    )


def bad_teaching_reason(card: Card, others: list[Card]) -> str | None:
    """Return why the card teaches badly, or ``None`` if it clears the bar."""
    if is_vague(card):
        return "vague/trivial (single generic-word cloze)"
    if is_trivially_guessable(card):
        return "trivially guessable (answer in stem or <4 options)"
    if near_duplicate(card, others):
        return "near-duplicate of another card"
    return None


# --- classification + report --------------------------------------------------


def classify_one(card: Card, corpus_norm: str, others: list[Card]) -> CardVerdict:
    """Bin one card. WRONG dominates (a wrong fact is disqualifying regardless of
    teaching quality); then BAD_TEACHING; else CORRECT_USEFUL."""
    wrong = wrong_reason(card, corpus_norm)
    if wrong:
        return CardVerdict(card, Bucket.WRONG, wrong)
    bad = bad_teaching_reason(card, others)
    if bad:
        return CardVerdict(card, Bucket.BAD_TEACHING, bad)
    return CardVerdict(card, Bucket.CORRECT_USEFUL, "verified correct and specific")


@dataclass
class CardCheckReport:
    total: int
    correct_useful: int
    wrong: int
    bad_teaching: int
    wrong_cutoff: int
    bad_teaching_ratio_cutoff: float
    verdicts: list[CardVerdict] = field(default_factory=list)

    @property
    def bad_teaching_ratio(self) -> float:
        return self.bad_teaching / self.total if self.total else 0.0

    @property
    def ok(self) -> bool:
        """Passes the pre-set, blocking cutoff: no wrong facts AND the
        bad-teaching share is within tolerance."""
        return (
            self.wrong <= self.wrong_cutoff
            and self.bad_teaching_ratio <= self.bad_teaching_ratio_cutoff
        )


def classify(cards: list[Card], corpus: str = "") -> CardCheckReport:
    """Classify a batch of cards into the three buckets against the pre-set
    cutoff. ``corpus`` (raw RONR markdown) enables the verbatim-citation check;
    omit it to skip that check (contradiction + grounding still run)."""
    corpus_norm = _normalize_corpus(corpus) if corpus else ""
    verdicts = [classify_one(c, corpus_norm, cards) for c in cards]
    counts = {b: 0 for b in Bucket}
    for v in verdicts:
        counts[v.bucket] += 1
    return CardCheckReport(
        total=len(cards),
        correct_useful=counts[Bucket.CORRECT_USEFUL],
        wrong=counts[Bucket.WRONG],
        bad_teaching=counts[Bucket.BAD_TEACHING],
        wrong_cutoff=WRONG_CUTOFF,
        bad_teaching_ratio_cutoff=BAD_TEACHING_RATIO_CUTOFF,
        verdicts=verdicts,
    )


# --- parser for the generated practice-question bank --------------------------

_Q_START = re.compile(r"^\*\*(\d+)\.\*\*", re.M)
_TAG = re.compile(r"`\[[^·]*·\s*([^\]]+)\]`")
_OPTION = re.compile(r"^\s*([A-D])\.\s+(.*\S)\s*$", re.M)
# "*Answer:* <core>  See RONR (12th ed.) §S:P — “quote”"
_ANSWER = re.compile(
    r"\*Answer:\*\s*(?P<core>.*?)\s*See RONR \(12th ed\.\)\s*§(?P<sec>\d+:\d+)"
    r"\s*[—-]\s*[“\"](?P<quote>.*?)[”\"]\s*$",
    re.S,
)


def _answer_core(raw: str) -> str:
    """The answer word/phrase: drop the appended cloze sentence (after ' — '),
    any trailing period, and a leading MCQ letter ('D) ')."""
    core = re.split(r"\s[—-]\s", raw, maxsplit=1)[0].strip().rstrip(".")
    return re.sub(r"^[A-D]\)\s*", "", core).strip()


def parse_generated_bank(text: str, limit: int | None = None) -> list[Card]:
    """Parse cards from the generated practice-question markdown
    (``docs/rpce/rpce_practice_questions.md``) — the "one real source" run."""
    cards: list[Card] = []
    starts = list(_Q_START.finditer(text))
    for i, m in enumerate(starts):
        block = text[
            m.end() : starts[i + 1].start() if i + 1 < len(starts) else len(text)
        ]
        am = _ANSWER.search(block)
        if not am:
            continue
        tag = _TAG.search(block)
        kind_raw = tag.group(1).strip().lower() if tag else ""
        kind = (
            "cloze"
            if "cloze" in kind_raw
            else "mcq"
            if "multiple-choice" in kind_raw
            else kind_raw
        )
        opts = tuple(o.group(2).strip() for o in _OPTION.finditer(block[: am.start()]))
        # Stem = text after the tag up to the first option / the answer line.
        stem_src = block[: am.start()]
        if tag:
            stem_src = stem_src[tag.end() :]
        first_opt = _OPTION.search(block[: am.start()])
        if first_opt:
            stem_src = stem_src[: stem_src.find(opts[0])] if opts else stem_src
        stem = " ".join(stem_src.split()).strip()
        cards.append(
            Card(
                question=stem,
                answer=_answer_core(am.group("core")),
                citation=am.group("sec"),
                quote=am.group("quote").strip(),
                kind=kind,
                options=opts,
            )
        )
        if limit is not None and len(cards) >= limit:
            break
    return cards
