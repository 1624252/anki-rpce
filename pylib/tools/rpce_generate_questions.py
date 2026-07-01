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
- **mcq**    — applied multiple choice grounded in the corpus (exactly one right).
- **multi**  — select ALL that apply (e.g. all motions ranking higher than X).
- **order**  — put a random set of motions in order of precedence (top = higher).
- motion **characteristics** (vote / debatable / second / amendable) and
  **precedence** ranking / which-is-higher, from :mod:`anki.rpce.knowledge`.

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
        made = 0
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
        opts = ["Debatable", "Not debatable"]
        ans = 0 if m.debatable else 1
    elif which == "second":
        stem = f"Does {phrase} require a second?"
        opts = ["Requires a second", "No second required"]
        ans = 0 if m.second else 1
    else:  # amendable
        stem = f"Can {phrase} be amended?"
        opts = ["Amendable", "Not amendable"]
        ans = 0 if m.amendable else 1
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


def make_pair(
    a: kb.Motion,
    b: kb.Motion,
    cid: str,
    sents: dict[int, list[tuple[str, str]]],
    secq: dict[int, tuple[str, str]],
) -> Question:
    higher = a if a.rank < b.rank else b
    opts = [a.name, b.name]
    stem = f"Which motion takes precedence \u2014 {a.name} or {b.name}?"
    ans = opts.index(higher.name)
    cite, quote = _precedence_ref(higher, sents, secq)
    payload = {
        "kind": "mcq",
        "stem": stem,
        "options": opts,
        "answer": ans,
        "cite": cite,
        "quote": quote,
    }
    return Question(
        2,
        "mcq",
        cid,
        "Precedence (which is higher)",
        payload,
        stem,
        higher.name,
        cite,
        quote,
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
    payload = {
        "kind": "multi",
        "stem": stem,
        "options": names,
        "correct": correct,
        "cite": cite,
        "quote": quote,
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

    # Characteristic questions: every motion × four traits.
    for m in kb.MOTIONS:
        for which in ("vote", "debatable", "second", "amendable"):
            qs.append(make_characteristic(m, which, cid(), sents, secq))
    ranked = kb.ranked_motions()
    # Ranking (highest + lowest) and ordering over sliding windows + random subsets.
    subsets: list[list[kb.Motion]] = []
    for size in (3, 4, 5):
        for start in range(0, len(ranked) - size + 1):
            subsets.append(ranked[start : start + size])
    for _ in range(50):
        subsets.append(rng.sample(ranked, rng.choice((3, 4, 5))))
    for subset in subsets:
        qs.append(make_ranking(subset, cid(), sents, secq, rng, "highest"))
        qs.append(make_ranking(subset, cid(), sents, secq, rng, "lowest"))
        qs.append(make_order(subset, cid(), sents, secq))
    # Pairwise "which is higher".
    for _ in range(60):
        a, b = rng.sample(ranked, 2)
        qs.append(make_pair(a, b, cid(), sents, secq))
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
