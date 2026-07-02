#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Generate varied, answerable RPCE practice questions (spec §7).

Every question shows enough to answer it and cites its RONR (12th ed.) section
**only in the answer** (never in a stem or option — a guard rejects leaks). For
broad coverage the generator emits **2–5 questions from every substantive corpus
paragraph**, drawing answer spans from more than italics alone:

- **bold defined terms** (RONR bolds the term it defines, e.g. **The Board.**),
- *italic emphases*,
- **voting thresholds** (majority / two-thirds / …),
- **numbers & durations** (e.g. "ten minutes", "three days"),
- a **key-phrase fallback** so a paragraph is never skipped for lack of markup.

Question types (the shared renderer draws each identically on desktop + phone):

- **cloze**  — fill a key span blanked from a real RONR sentence; the blank
  carries a hint (length + first letter, or "a voting threshold") so it stays
  answerable (spec §7.1).
- **mcq**    — applied multiple choice grounded in the corpus, always with at
  least four options, exactly one correct. EVERY substantive paragraph yields at
  least one MCQ (a guaranteed section-stripped fallback covers the few that no
  marked-up span fits). Short-option knowledge MCQs are padded to four.
- **multi**  — select ALL that apply (e.g. all motions ranking higher than X);
  the answer carries a LIST of citations, one per relevant motion.
- **order**  — put a random set of motions in order of precedence (top = higher).
- motion **characteristics** (vote / debatable / second / amendable) and
  **classification** (which class a motion belongs to), plus **precedence**
  ranking, from :mod:`anki.rpce.knowledge`.

Precedence and characteristic questions come from structured knowledge (a motion
bank + the saved order of precedence) because prose cloze can't test them — too
many combinations to fill one blank. Each such answer is backed by a verbatim
quote from the motion's own section that *supports the trait asked*. The corpus
is read from ``data/roberts_rules_of_order_12th_edition.md``. Deterministic
(fixed seed), so the deck and the doc reproduce exactly.

Usage (from the repo root):

    python pylib/tools/rpce_generate_questions.py [count] [out.md]
    # count 0 (default) = full coverage → docs/rpce/rpce_practice_questions.md
"""

from __future__ import annotations

import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # pylib on path
from anki.rpce import knowledge as kb  # noqa: E402

CORPUS = Path("data/roberts_rules_of_order_12th_edition.md")
SEED = 20260701
#: Target questions per substantive paragraph (spec: "2–5 from each paragraph").
PER_PARA = 5

_PARA_RE = re.compile(
    r'(?:<a id="pg-\d+"></a>)*<a id="p-(\d+)-(\d+)"></a>\*([\d]+:[\d]+[^*]*)\*\s*(.*)'
)
_TAG_RE = re.compile(r'<a id="[^"]*"></a>')
_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:#|https?)[^)]*\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_EMPH_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_MULTISPACE_RE = re.compile(r"\s+")
_FOOTNOTE_RE = re.compile(r"^>\s*")

# A RONR section reference (e.g. "10:5", "§23", "Section 4"). Never allowed in a
# question stem or option — it belongs only in the answer citation.
_SECTION_RE = re.compile(r"\b\d+:\d+\b|§|\bRONR\b|\bsections?\s+\d+", re.I)

# Sentences about order of precedence can't be a fair fill-in-the-blank (too many
# possible motions) — those go to ranking/ordering/select-all, never cloze/MCQ.
_PRECEDENCE_RE = re.compile(r"\bprecedence\b|\byield(s|ed)?\b|\boutrank", re.I)

# Strip inline RONR section references so a leaking sentence can still seed an
# MCQ stem (the section stays in the answer's quote, never in the stem).
_PAREN_RE = re.compile(r"\(([^()]*)\)")
_SEE_REF_RE = re.compile(r"\bsee(?:\s+also)?\b[^.;)]*\d+:\d+[^.;)]*", re.I)
_EMPTY_PAREN_RE = re.compile(r"\(\s*[,;.\s]*\)")

# Plausible parliamentary noun phrases, a last-resort pad so a forced MCQ always
# reaches four options even when the corpus term pool is thin.
_GENERIC_DISTRACTORS = [
    "a quorum",
    "the bylaws",
    "a standing rule",
    "previous notice",
    "the agenda",
    "a ballot vote",
    "the minutes",
    "adjournment",
    "the presiding officer",
    "a special committee",
    "the parliamentary authority",
    "a point of order",
]

# Voting thresholds usable as answer spans (word -> option label).
_VOTE_LABEL = {
    "majority": "A majority vote",
    "two-thirds": "A two-thirds vote",
    "three-fourths": "A three-fourths vote",
    "unanimous": "A unanimous (general consent) vote",
    "plurality": "A plurality",
}
_VOTE_RE = re.compile(
    r"\b(majority|two-thirds|three-fourths|unanimous|plurality)\b", re.I
)
_NUMTIME_RE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
    r"(?:minutes?|hours?|days?|weeks?|months?|years?|members?|votes?)\b",
    re.I,
)

# Words too generic to be a fair key-phrase fallback answer.
_COMMON = {
    "assembly",
    "meeting",
    "member",
    "members",
    "motion",
    "motions",
    "question",
    "questions",
    "chairman",
    "president",
    "society",
    "committee",
    "business",
    "however",
    "therefore",
    "because",
    "generally",
    "usually",
    "certain",
    "another",
    "through",
    "without",
    "against",
    "between",
    "further",
    "meetings",
}

DOMAIN_NAMES = {
    1: "Motions in General and Main Motions",
    2: "Subsidiary and Privileged Motions",
    3: "Incidental Motions and Motions that Bring a Question Again Before the Assembly",
    4: "Organization and Conduct of Meetings",
    5: "Voting, Nominations, and Elections",
    6: "Being and Serving as a Professional Parliamentarian and Teaching Parliamentary Procedure",
    7: "Boards and Committees, and Writing and Interpreting Bylaws",
}

# Motion class -> Performance-Expectation domain (for coverage tagging).
_CLASS_DOMAIN = {
    kb.CLASS_MAIN: 1,
    kb.CLASS_PRIVILEGED: 2,
    kb.CLASS_SUBSIDIARY: 2,
    kb.CLASS_INCIDENTAL: 3,
}


def domain_for_section(sec: int) -> int:
    if sec in (6, 10):
        return 1
    if 11 <= sec <= 22:
        return 2
    if 23 <= sec <= 37:
        return 3
    if sec in (44, 45, 46):
        return 5
    if 49 <= sec <= 60:
        return 7
    if sec in (61, 62, 63):
        return 6
    return 4


def clean(text: str) -> str:
    text = text.replace("\ufffd?T", "\u2019").replace("\ufffd?o", "\u201c")
    text = text.replace("\ufffd", "")
    text = _FOOTNOTE_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = text.replace("**", "").replace("*", "").replace("_", "")
    text = _MULTISPACE_RE.sub(" ", text).strip()
    return text


def first_sentence(text: str, limit: int = 300) -> str:
    parts = [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(\u201c])", text)]
    chosen = next((s for s in parts if len(s) >= 60), None)
    if chosen is None:
        chosen = max(parts, key=len) if parts else text.strip()
    if len(chosen) > limit:
        chosen = chosen[:limit].rsplit(" ", 1)[0] + "\u2026"
    return chosen.strip()


def sentences(text: str) -> list[str]:
    """Split cleaned paragraph text into substantive sentences."""
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", text) if len(s.strip()) >= 40]


def mentions_section(*texts: str) -> bool:
    return any(_SECTION_RE.search(t) for t in texts if t)


# --- answer-span extraction ---------------------------------------------------


def _bold_terms(body: str) -> list[str]:
    """Defined terms RONR sets in bold (e.g. **The Board.** → 'Board'); numeric
    cross-reference bolds (e.g. **49**) drop out because they carry no letters."""
    out = []
    for raw in _BOLD_RE.findall(body):
        t = clean(raw).strip().strip(".")
        t = re.sub(r"^\(?(?:[a-zA-Z]|\d{1,2})[.)]\s+", "", t)  # drop "b. " / "(3) "
        t = re.sub(r"^(?:The|A|An)\s+", "", t)
        out.append(t)
    return out


def _span_ok(term: str) -> bool:
    t = term.strip()
    return bool(
        3 <= len(t) <= 40
        and re.search(r"[A-Za-z]", t)  # rejects bare section numbers
        and len(t.split()) <= 4
        and not mentions_section(t)
    )


def _sentences_with(text: str, term: str) -> list[tuple[str, str]]:
    """Every (sentence, exact-cased match) where ``term`` occurs as a whole word,
    so a maker can skip sentences that would leak a section and use the next."""
    pat = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    out = []
    for s in sentences(text):
        m = pat.search(s)
        if m:
            out.append((s, m.group(0)))
    return out


def _keyphrase(text: str) -> str | None:
    """A distinctive long word to fall back on when a paragraph has no marked-up
    term — keeps every substantive paragraph answerable."""
    words = re.findall(r"[A-Za-z][A-Za-z\-]{6,19}", text)
    cand = [w for w in words if w.lower() not in _COMMON]
    return max(cand, key=len) if cand else None


@dataclass
class Para:
    citation: str
    section: int
    domain: int
    text: str
    emphases: list[str] = field(default_factory=list)
    bold: list[str] = field(default_factory=list)


def parse_corpus() -> list[Para]:
    paras: list[Para] = []
    for raw in CORPUS.read_text(encoding="utf-8").splitlines():
        m = _PARA_RE.match(raw.strip())
        if not m:
            continue
        sec = int(m.group(1))
        citation = m.group(3).strip()
        body = m.group(4)
        italic_src = _BOLD_RE.sub(" ", body)
        emphases = [clean(e) for e in _EMPH_RE.findall(italic_src)]
        text = clean(body)
        if len(text) < 90 or ":" not in citation:
            continue
        emph = [
            e2
            for e in emphases
            if (e2 := e.strip(" ,.;:\u2014")) and _span_ok(e2) and e2 in text
        ]
        bold = [
            b2
            for b in _bold_terms(body)
            if (b2 := b.strip(" ,.;:\u2014"))
            and _span_ok(b2)
            and re.search(r"\b" + re.escape(b2) + r"\b", text, re.I)
        ]
        paras.append(Para(citation, sec, domain_for_section(sec), text, emph, bold))
    return paras


def section_quotes(paras: list[Para]) -> dict[int, tuple[str, str]]:
    """First substantive (citation, quote) found for each RONR section."""
    out: dict[int, tuple[str, str]] = {}
    for p in paras:
        if p.section not in out:
            out[p.section] = (p.citation, first_sentence(p.text))
    return out


def section_sentences(paras: list[Para]) -> dict[int, list[tuple[str, str]]]:
    """Every (citation, sentence) per section, to find a trait-supporting quote."""
    out: dict[int, list[tuple[str, str]]] = {}
    for p in paras:
        for s in sentences(p.text):
            out.setdefault(p.section, []).append((p.citation, s))
    return out


def supporting_quote(
    section: int,
    keywords: list[str],
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
    motion_name: str = "",
) -> tuple[str, str]:
    """A (citation, quote) from ``section`` whose sentence supports the trait
    (contains a keyword; prefers ones naming the motion). Falls back to the
    section's first substantive sentence, so the citation stays exact."""
    kw = [k.lower() for k in keywords]
    name_toks = [t for t in motion_name.lower().split() if t not in _COMMON]
    best: tuple[str, str] | None = None
    best_score = 0
    for cite, s in sents.get(section, []):
        if mentions_section(s) or len(s) > 260:
            continue
        sl = s.lower()
        score = (2 if any(k in sl for k in kw) else 0) + (
            1 if any(t in sl for t in name_toks) else 0
        )
        if score > best_score:
            best, best_score = (cite, s), score
    if best is not None:
        return best
    return secq.get(section, (str(section), ""))


@dataclass
class Question:
    domain: int
    kind: str  # cloze | mcq | multi | order
    concept_id: str
    label: str  # human category label (for the doc)
    payload: dict  # full render payload, incl. cite + quote
    plain_q: str  # no-JS / doc question text
    plain_a: str  # no-JS / doc answer text
    cite: str
    quote: str


# --- corpus-grounded questions (any answer span) ------------------------------


def _cloze_hint(kind: str, term: str) -> str:
    """Keep a blank answerable without giving the word away (spec §7.1)."""
    if kind == "vote":
        return "a voting threshold"
    if kind == "number":
        return "a number or length of time"
    words = term.split()
    if len(words) > 1:
        return f"{len(words)} words, starts \u201c{term[0]}\u201d"
    return f"{len(term)} letters, starts \u201c{term[0]}\u201d"


def _vote_key(text: str) -> str | None:
    m = _VOTE_RE.search(text)
    return m.group(0).lower() if m else None


def _pick_distractors(
    answer: str, pool: list[str], rng: random.Random, n: int = 3
) -> list[str] | None:
    """Three plausible wrong options: same shape (single word vs phrase) and
    similar length to the answer, so the MCQ isn't given away by an odd fragment."""
    al = answer.lower()
    multiword = " " in answer.strip()

    def ok(t: str) -> bool:
        tl = t.lower()
        if tl == al or tl in al or al in tl or mentions_section(t):
            return False
        return len(t) >= 5 or " " in t  # drop tiny lowercase fragments

    cands = [t for t in pool if ok(t)]
    same = [t for t in cands if (" " in t) == multiword]
    prefer = same if len(same) >= n else cands
    prefer.sort(key=lambda t: abs(len(t) - len(answer)))
    near = prefer[: max(n * 8, 24)] or cands
    return rng.sample(near, n) if len(near) >= n else None


def _mcq_options(
    answer: str, pool: list[str], rng: random.Random, n: int = 4
) -> tuple[list[str], int]:
    """``n`` unique options including ``answer`` — always succeeds (spec §7 4b:
    an MCQ never has fewer than four options). Prefers same-shape corpus terms,
    then any pool term, then a generic parliamentary phrase as a last resort."""
    al = answer.lower()
    picks = _pick_distractors(answer, pool, rng, n - 1) or []
    if len(picks) < n - 1:  # relax the shape/length preference
        cand = [
            t
            for t in pool
            if t.lower() != al
            and al not in t.lower()
            and t.lower() not in al
            and not mentions_section(t)
        ]
        rng.shuffle(cand)
        picks = cand[: n - 1]
    opts, seen = [answer], {al}
    for t in [*picks, *_GENERIC_DISTRACTORS]:
        if len(opts) >= n:
            break
        if t.lower() not in seen:
            seen.add(t.lower())
            opts.append(t)
    rng.shuffle(opts)
    return opts, opts.index(answer)


def _pad_to_four(
    options: list[str], correct: str, rng: random.Random, distractors: list[str]
) -> tuple[list[str], int]:
    """Pad a short option list up to four with the given plausible distractors,
    shuffle, and return (options, answer-index). Used for the motion-trait MCQs
    whose natural form has only two choices (spec §7 4b)."""
    opts, seen = list(options), {o.lower() for o in options}
    for d in distractors:
        if len(opts) >= 4:
            break
        if d.lower() not in seen and d.lower() != correct.lower():
            seen.add(d.lower())
            opts.append(d)
    rng.shuffle(opts)
    return opts, opts.index(correct)


def _citation_only(inner: str) -> bool:
    """True if a parenthetical is nothing but a cross-reference, e.g. ``(23–33)``
    or ``(4:45, 10:1323)`` — safe to drop entirely from an MCQ stem."""
    t = re.sub(r"\b(?:see|also|and)\b", "", inner, flags=re.I)
    t = _SECTION_RE.sub("", t)
    t = re.sub(r"[\d:,;.–—()\s\-]", "", t)
    return t.strip() == ""


def _strip_sections(text: str) -> str:
    """Remove inline RONR references (``(4:45)``, ``see 18:8``, ``§``, ``sections
    4``) so even a section-citing sentence can seed a fair MCQ stem. The section
    stays in the answer's verbatim quote — never in the stem."""
    t = _PAREN_RE.sub(lambda m: "" if _citation_only(m.group(1)) else m.group(0), text)
    t = _SEE_REF_RE.sub("", t)
    t = _SECTION_RE.sub("", t)
    t = _EMPTY_PAREN_RE.sub("", t)
    t = re.sub(r",\s*([.;])", r"\1", t)
    t = re.sub(r"\s+([.;,])", r"\1", t)
    return _MULTISPACE_RE.sub(" ", t).strip(" ,;")


#: Words that name a motion — never blanked in a precedence sentence (that would
#: make an unfair which-motion fill-in). Used only by the last-resort fallback.
_MOTION_WORDS = {w.lower() for m in kb.MOTIONS for w in m.name.split()}


def _blank_term(text: str) -> str | None:
    """A distinctive word to blank in a fallback stem, skipping motion names and
    precedence verbs so the item stays a fair vocabulary fill-in."""

    def usable(w: str) -> bool:
        wl = w.lower()
        return (
            wl not in _MOTION_WORDS
            and not _PRECEDENCE_RE.search(w)
            and not mentions_section(w)
        )

    words = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z\-]{6,19}", text)
        if w.lower() not in _COMMON and usable(w)
    ]
    if not words:  # relax the length floor
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{4,}", text) if usable(w)]
    return max(words, key=len) if words else None


def _sentence_ok(kind: str, sentence: str) -> bool:
    if mentions_section(sentence) or _PRECEDENCE_RE.search(sentence):
        return False
    if kind == "vote" and len({w.lower() for w in _VOTE_RE.findall(sentence)}) != 1:
        return False  # ambiguous when a sentence lists several thresholds
    return True


def make_cloze_span(p: Para, cid: str, kind: str, term: str) -> Question | None:
    sentence = exact = None
    for cand, matched in _sentences_with(p.text, term):
        if _sentence_ok(kind, cand):
            sentence, exact = cand, matched
            break
    if not sentence or exact is None:
        return None
    text = sentence.replace(exact, "[[0]]", 1)
    blanks = [{"a": exact, "h": _cloze_hint(kind, exact)}]
    plain_q = "Fill the blank: " + re.sub(r"\[\[\d+\]\]", "_____", text)
    payload = {
        "kind": "cloze",
        "text": text,
        "blanks": blanks,
        "cite": p.citation,
        "quote": sentence,
    }
    return Question(
        p.domain,
        "cloze",
        cid,
        "Cloze recall",
        payload,
        plain_q,
        f"{exact} \u2014 \u201c{sentence}\u201d",
        p.citation,
        sentence,
    )


def make_mcq_span(
    p: Para, cid: str, kind: str, term: str, term_pool: list[str], rng: random.Random
) -> Question | None:
    sentence = exact = None
    for cand, matched in _sentences_with(p.text, term):
        if _sentence_ok(kind, cand):
            sentence, exact = cand, matched
            break
    if not sentence or exact is None:
        return None
    stem = f"Fill in the blank: {sentence.replace(exact, '_____', 1)}"
    if mentions_section(stem):
        return None
    if kind == "vote":
        key = _vote_key(exact)
        if key is None or key not in _VOTE_LABEL:
            return None
        options = [
            _VOTE_LABEL[k]
            for k in ("majority", "two-thirds", "three-fourths", "unanimous")
        ]
        correct = _VOTE_LABEL[key]
        if correct not in options:
            options[-1] = correct
        rng.shuffle(options)
        answer = options.index(correct)
    else:
        distractors = _pick_distractors(exact, term_pool, rng)
        if distractors is None:
            return None
        options = [exact, *distractors]
        rng.shuffle(options)
        answer = options.index(exact)
    payload = {
        "kind": "mcq",
        "stem": stem,
        "options": options,
        "answer": answer,
        "cite": p.citation,
        "quote": sentence,
    }
    return Question(
        p.domain,
        "mcq",
        cid,
        "Applied multiple-choice",
        payload,
        stem,
        f"{'ABCD'[answer]}) {options[answer]}",
        p.citation,
        sentence,
    )


def make_mcq_fallback(
    p: Para, cid: str, term_pool: list[str], rng: random.Random
) -> Question | None:
    """A guaranteed applied MCQ for a paragraph that yielded none — so EVERY
    substantive paragraph has at least one multiple-choice item (spec §7 1).
    First retries every candidate span; then blanks a key phrase from a
    section-stripped sentence and pads to four options."""
    for kind, term in candidate_spans(p):
        q = make_mcq_span(p, cid, kind, term, term_pool, rng)
        if q is not None:
            return q
    # Blank a neutral key phrase from a section-stripped sentence. Pass 1 avoids
    # precedence prose; pass 2 allows it (blanking only a non-motion word).
    for allow_precedence in (False, True):
        for s in sentences(p.text):
            if not allow_precedence and _PRECEDENCE_RE.search(s):
                continue
            stem_src = _strip_sections(s)
            if len(stem_src) < 40 or mentions_section(stem_src):
                continue
            term = _blank_term(stem_src)
            if not term:
                continue
            pat = re.compile(r"\b" + re.escape(term))
            if not pat.search(stem_src):
                continue
            options, answer = _mcq_options(term, term_pool, rng)
            stem = "Fill in the blank: " + pat.sub("_____", stem_src, count=1)
            if mentions_section(stem):
                continue
            payload = {
                "kind": "mcq",
                "stem": stem,
                "options": options,
                "answer": answer,
                "cite": p.citation,
                "quote": s,
            }
            return Question(
                p.domain,
                "mcq",
                cid,
                "Applied multiple-choice",
                payload,
                stem,
                f"{'ABCD'[answer]}) {options[answer]}",
                p.citation,
                s,
            )
    return None


def candidate_spans(p: Para) -> list[tuple[str, str]]:
    """Ordered (kind, term) answer spans for a paragraph, best first, de-duped."""
    spans: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(kind: str, term: str) -> None:
        key = term.lower()
        if _span_ok(term) and key not in seen:
            seen.add(key)
            spans.append((kind, term))

    for b in p.bold:
        add("term", b)
    for e in p.emphases:
        add("term", e)
    for v in sorted({w.lower() for w in _VOTE_RE.findall(p.text)}):
        add("vote", v)
    for m in _NUMTIME_RE.finditer(p.text):
        add("number", m.group(0))
    # Key-phrase fallbacks from clean (non-leaking) sentences, so a paragraph is
    # covered even when its marked-up spans sit in a cross-referencing sentence.
    for s in sentences(p.text):
        if len(spans) >= 6:
            break
        if _sentence_ok("term", s):
            kp = _keyphrase(s)
            if kp:
                add("term", kp)
    return spans


def build_corpus(
    paras: list[Para], term_pool: list[str], rng: random.Random, per_para: int
) -> list[Question]:
    """2–5 varied questions from every substantive paragraph. Types alternate
    across distinct spans; a second pass backfills the opposite type so even a
    one-span paragraph yields both a cloze and an applied MCQ (Transfer Ladder)."""
    out: list[Question] = []
    for cn, p in enumerate(paras, 1):
        cid = f"C{cn:04d}"
        spans = candidate_spans(p)
        plan: list[tuple[str, str, str]] = []
        for i, (kind, term) in enumerate(spans):
            plan.append(("cloze" if i % 2 == 0 else "mcq", kind, term))
        for i, (kind, term) in enumerate(spans):
            plan.append(("mcq" if i % 2 == 0 else "cloze", kind, term))
        made = made_mcq = 0
        per_sentence: dict[str, int] = {}  # ≤2 blanks from any one sentence
        for typ, kind, term in plan:
            if made >= per_para:
                break
            q = (
                make_cloze_span(p, cid, kind, term)
                if typ == "cloze"
                else make_mcq_span(p, cid, kind, term, term_pool, rng)
            )
            if q is None:
                continue
            if per_sentence.get(q.quote, 0) >= 2:
                continue
            per_sentence[q.quote] = per_sentence.get(q.quote, 0) + 1
            out.append(q)
            made += 1
            made_mcq += q.kind == "mcq"
        # Spec §7 1: at least one MCQ from every substantive paragraph.
        if made_mcq == 0:
            fb = make_mcq_fallback(p, cid, term_pool, rng)
            if fb is not None:
                out.append(fb)
    return out


# --- knowledge-based questions (motions & characteristics) --------------------


def _motion_domain(m: kb.Motion) -> int:
    return _CLASS_DOMAIN.get(m.klass, 4)


def _trait_keywords(which: str, m: kb.Motion) -> list[str]:
    if which == "vote":
        return {
            kb.VOTE_MAJORITY: ["majority vote", "majority"],
            kb.VOTE_TWO_THIRDS: ["two-thirds", "two thirds"],
            kb.VOTE_NONE: ["chair", "ruling", "without a vote", "no vote"],
        }[m.vote]
    if which == "debatable":
        return ["debatable", "debate"] if m.debatable else ["not debatable", "debate"]
    if which == "second":
        return ["second"]
    return ["amend"] if m.amendable else ["not amendable", "amend"]


def make_characteristic(
    m: kb.Motion,
    which: str,
    cid: str,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
) -> Question:
    cite, quote = supporting_quote(
        m.section, _trait_keywords(which, m), sents, secq, m.name
    )
    phrase = kb.motion_phrase(m.name)
    rng = random.Random(f"{m.name}:{which}")  # deterministic per motion+trait
    if which == "vote":
        stem = f"What vote does {phrase} require to be adopted?"
        opts = [
            "Majority vote",
            "Two-thirds vote",
            "No vote (chair rules / demand)",
            "Unanimous consent",
        ]
        ans = opts.index(kb.VOTE_LABELS[m.vote])
    elif which == "debatable":
        stem = f"Is {phrase} debatable?"
        correct = "Debatable" if m.debatable else "Not debatable"
        opts, ans = _pad_to_four(
            ["Debatable", "Not debatable"],
            correct,
            rng,
            ["Debatable only with a two-thirds vote", "Debatable for two minutes only"],
        )
    elif which == "second":
        stem = f"Does {phrase} require a second?"
        correct = "Requires a second" if m.second else "No second required"
        opts, ans = _pad_to_four(
            ["Requires a second", "No second required"],
            correct,
            rng,
            ["Requires two seconds", "May be seconded only by the chair"],
        )
    else:  # amendable
        stem = f"Can {phrase} be amended?"
        correct = "Amendable" if m.amendable else "Not amendable"
        opts, ans = _pad_to_four(
            ["Amendable", "Not amendable"],
            correct,
            rng,
            ["Amendable only by the maker", "Amendable only as to time"],
        )
    payload = {
        "kind": "mcq",
        "stem": stem,
        "options": opts,
        "answer": ans,
        "cite": cite,
        "quote": quote,
    }
    label = {
        "vote": "Vote required",
        "debatable": "Debatability",
        "second": "Second required",
        "amendable": "Amendability",
    }[which]
    return Question(
        _motion_domain(m), "mcq", cid, label, payload, stem, opts[ans], cite, quote
    )


def make_classification(
    m: kb.Motion,
    cid: str,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
) -> Question:
    """Applied MCQ: which class a motion belongs to (main / subsidiary /
    privileged / incidental). A core RPCE skill and always four options — the
    fifth item type (spec §7 5)."""
    phrase = kb.motion_phrase(m.name)
    stem = f"To which class of motions does {phrase} belong?"
    opts = [
        kb.CLASS_LABELS[c]
        for c in (
            kb.CLASS_PRIVILEGED,
            kb.CLASS_SUBSIDIARY,
            kb.CLASS_INCIDENTAL,
            kb.CLASS_MAIN,
        )
    ]
    ans = opts.index(kb.CLASS_LABELS[m.klass])
    cite, quote = supporting_quote(
        m.section, kb.CLASS_KEYWORDS[m.klass], sents, secq, m.name
    )
    payload = {
        "kind": "mcq",
        "stem": stem,
        "options": opts,
        "answer": ans,
        "cite": cite,
        "quote": quote,
    }
    return Question(
        _motion_domain(m),
        "mcq",
        cid,
        "Motion classification",
        payload,
        stem,
        opts[ans],
        cite,
        quote,
    )


def _precedence_ref(
    m: kb.Motion,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
) -> tuple[str, str]:
    return supporting_quote(
        m.section, ["precedence", "yield", "takes precedence"], sents, secq, m.name
    )


def make_ranking(
    motions: list[kb.Motion],
    cid: str,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
    rng: random.Random,
    which: str = "highest",
) -> Question:
    # rank 1 = highest precedence, so highest = min rank, lowest = max rank.
    pick = min if which == "highest" else max
    target = pick(motions, key=lambda m: m.rank)
    names = [m.name for m in motions]
    rng.shuffle(names)
    stem = f"Which of these motions has the {which} precedence?"
    ans = names.index(target.name)
    cite, quote = _precedence_ref(target, sents, secq)
    payload = {
        "kind": "mcq",
        "stem": stem,
        "options": names,
        "answer": ans,
        "cite": cite,
        "quote": quote,
    }
    return Question(
        2, "mcq", cid, "Precedence (ranking)", payload, stem, target.name, cite, quote
    )


def make_multi(
    pivot: kb.Motion,
    others: list[kb.Motion],
    cid: str,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
    rng: random.Random,
    direction: str = "higher",
) -> Question:
    # "higher" precedence = smaller rank number.
    names = [m.name for m in others]
    rng.shuffle(names)
    by_name = {m.name: m for m in others}
    if direction == "higher":
        correct = [i for i, nm in enumerate(names) if by_name[nm].rank < pivot.rank]
        verb = "rank higher than (take precedence over)"
    else:
        correct = [i for i, nm in enumerate(names) if by_name[nm].rank > pivot.rank]
        verb = "rank lower than (yield to)"
    stem = f"Select ALL of these motions that {verb} {kb.motion_phrase(pivot.name)}."
    cite, quote = _precedence_ref(pivot, sents, secq)
    # One citation per relevant motion (spec §7 4): the pivot's own precedence
    # rule, then each correctly-selected motion's, de-duped by section.
    cites: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref_cite, ref_quote in [
        _precedence_ref(pivot, sents, secq),
        *(_precedence_ref(by_name[names[i]], sents, secq) for i in correct),
    ]:
        if ref_cite not in seen:
            seen.add(ref_cite)
            cites.append({"cite": ref_cite, "quote": ref_quote})
    payload = {
        "kind": "multi",
        "stem": stem,
        "options": names,
        "correct": correct,
        "cite": cite,
        "quote": quote,
        "cites": cites,
    }
    plain_a = ", ".join(names[i] for i in correct) or "(none)"
    return Question(
        2, "multi", cid, "Precedence (select all)", payload, stem, plain_a, cite, quote
    )


def make_order(
    motions: list[kb.Motion],
    cid: str,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
) -> Question:
    ordered = sorted(motions, key=lambda m: m.rank)  # highest precedence first
    labels = [m.name for m in ordered]
    prompt = "Put these motions in order of precedence (top = higher, bottom = lower)."
    cite, quote = _precedence_ref(ordered[0], sents, secq)
    payload = {
        "kind": "order",
        "prompt": prompt,
        "order": labels,
        "cite": cite,
        "quote": quote,
    }
    return Question(
        2,
        "order",
        cid,
        "Precedence (ordering)",
        payload,
        prompt,
        " \u2192 ".join(labels),
        cite,
        quote,
    )


def build_knowledge(
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
    rng: random.Random,
) -> list[Question]:
    qs: list[Question] = []
    n = 0

    def cid() -> str:
        nonlocal n
        n += 1
        return f"K{n:04d}"

    # Characteristic questions: every motion × four traits, plus its class.
    for m in kb.MOTIONS:
        for which in ("vote", "debatable", "second", "amendable"):
            qs.append(make_characteristic(m, which, cid(), sents, secq))
        qs.append(make_classification(m, cid(), sents, secq))
    ranked = kb.ranked_motions()
    # Ranking (highest + lowest) and ordering over sliding windows + random subsets.
    subsets: list[list[kb.Motion]] = []
    for size in (3, 4, 5):
        for start in range(0, len(ranked) - size + 1):
            subsets.append(ranked[start : start + size])
    for _ in range(50):
        subsets.append(rng.sample(ranked, rng.choice((3, 4, 5))))
    for subset in subsets:
        # Ranking MCQs need ≥4 options (spec §7 4b); ordering has no such limit.
        if len(subset) >= 4:
            qs.append(make_ranking(subset, cid(), sents, secq, rng, "highest"))
            qs.append(make_ranking(subset, cid(), sents, secq, rng, "lowest"))
        qs.append(make_order(subset, cid(), sents, secq))
    # Select-all-that-rank-higher / lower than a pivot.
    for _ in range(120):
        pivot = rng.choice(ranked)
        pool = [m for m in ranked if m is not pivot]
        others = rng.sample(pool, rng.choice((4, 5)))
        direction = rng.choice(("higher", "lower"))
        has_c = any(
            (m.rank < pivot.rank) if direction == "higher" else (m.rank > pivot.rank)
            for m in others
        )
        has_i = any(
            (m.rank >= pivot.rank) if direction == "higher" else (m.rank <= pivot.rank)
            for m in others
        )
        if has_c and has_i:
            qs.append(make_multi(pivot, others, cid(), sents, secq, rng, direction))
    return qs


def build(count: int = 0, per_para: int = PER_PARA) -> list[Question]:
    """Knowledge-based questions + 2–``per_para`` varied questions from every
    substantive corpus paragraph. ``count`` optionally caps the total (0 = no
    cap)."""
    rng = random.Random(SEED)
    paras = parse_corpus()
    secq = section_quotes(paras)
    sents = section_sentences(paras)
    term_pool = sorted({t for p in paras for t in (*p.emphases, *p.bold)})
    questions: list[Question] = list(build_knowledge(sents, secq, rng))
    questions.extend(build_corpus(paras, term_pool, rng, per_para))
    return questions[:count] if count else questions


def render(questions: list[Question]) -> str:
    concepts = {q.concept_id for q in questions}
    kinds: dict[str, int] = {}
    for q in questions:
        kinds[q.label] = kinds.get(q.label, 0) + 1
    out: list[str] = [
        "# RPCE Practice Questions (generated, RONR 12th-ed.-grounded)",
        "",
        f"{len(questions)} questions across {len(concepts)} concepts. Types are "
        "varied so the same fact resurfaces in different shapes (cloze with hints, "
        "applied multiple choice, select-all, order-of-precedence ranking and "
        "ordering, and motion-characteristic questions). Every question is "
        "answerable from what it shows; the RONR (12th ed.) section is cited only "
        "in the answer.",
        "",
        "Counts by type: " + ", ".join(f"{k} ({v})" for k, v in sorted(kinds.items())),
        "",
        "> Reproduce with `python pylib/tools/rpce_generate_questions.py`.",
        "",
    ]
    by_domain: dict[int, list[Question]] = {d: [] for d in DOMAIN_NAMES}
    for q in questions:
        by_domain[q.domain].append(q)
    for d in sorted(DOMAIN_NAMES):
        qs = by_domain[d]
        if not qs:
            continue
        out.append(f"## Domain {d}: {DOMAIN_NAMES[d]}")
        out.append("")
        for i, q in enumerate(qs, 1):
            out.append(f"**{i}.** `[{q.concept_id} \u00b7 {q.label}]` {q.plain_q}")
            if q.payload.get("options"):
                for letter, opt in zip("ABCDEFGH", q.payload["options"]):
                    out.append(f"   {letter}. {opt}")
            out.append("")
            out.append(
                f"   *Answer:* {q.plain_a}. See RONR (12th ed.) \u00a7{q.cite}"
                + (f" \u2014 \u201c{q.quote}\u201d" if q.quote else "")
            )
            out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = full coverage
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path("docs/rpce/rpce_practice_questions.md")
    )
    questions = build(count)
    out_path.write_text(render(questions), encoding="utf-8")
    kinds: dict[str, int] = {}
    for q in questions:
        kinds[q.label] = kinds.get(q.label, 0) + 1
    print(f"wrote {len(questions)} questions to {out_path}")
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
