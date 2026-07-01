#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Generate varied, answerable RPCE practice questions (spec §7).

Each question shows enough to answer it and cites its RONR (12th ed.) section
only in the answer (never in a stem or option). For broad coverage the generator
emits up to a few questions from **every** corpus paragraph, plus a bank of
precedence/characteristic questions. Types:

- **cloze**  — fill a key term blanked from a real RONR sentence. A hint appears
  only when the answer isn't obvious from the sentence (e.g. debatable-vs-not);
  hints never reveal spelling.
- **mcq**    — applied multiple choice grounded in the corpus (pick the term).
- **multi**  — select ALL that apply (e.g. all motions ranking higher than X).
- **order**  — put a random set of motions in order of precedence (top = higher).
- motion characteristics (vote / debatable / second / amendable) and precedence
  ranking / which-is-higher, from :mod:`anki.rpce.knowledge`.

Precedence and characteristic questions come from structured knowledge (a motion
bank + the saved order of precedence) because prose cloze can't test them — too
many combinations to fill one blank. The corpus is read from
``data/roberts_rules_of_order_12th_edition.md``. Deterministic (fixed seed).

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
from anki.rpce import hint_for  # noqa: E402
from anki.rpce import knowledge as kb  # noqa: E402

CORPUS = Path("data/roberts_rules_of_order_12th_edition.md")
SEED = 20260701

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
    text = text.replace("�?T", "’").replace("�?o", "“")
    text = text.replace("�", "")
    text = _FOOTNOTE_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = text.replace("**", "").replace("*", "").replace("_", "")
    text = _MULTISPACE_RE.sub(" ", text).strip()
    return text


def first_sentence(text: str, limit: int = 300) -> str:
    parts = [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(“])", text)]
    chosen = next((s for s in parts if len(s) >= 60), None)
    if chosen is None:
        chosen = max(parts, key=len) if parts else text.strip()
    if len(chosen) > limit:
        chosen = chosen[:limit].rsplit(" ", 1)[0] + "…"
    return chosen.strip()


def mentions_section(*texts: str) -> bool:
    return any(_SECTION_RE.search(t) for t in texts if t)


@dataclass
class Para:
    citation: str
    section: int
    domain: int
    text: str
    emphases: list[str] = field(default_factory=list)


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
            e
            for e in emphases
            if 3 <= len(e) <= 40 and re.search(r"[A-Za-z]", e) and e in text
        ]
        paras.append(Para(citation, sec, domain_for_section(sec), text, emph))
    return paras


def section_quotes(paras: list[Para]) -> dict[int, tuple[str, str]]:
    """First substantive (citation, quote) found for each RONR section."""
    out: dict[int, tuple[str, str]] = {}
    for p in paras:
        if p.section not in out:
            out[p.section] = (p.citation, first_sentence(p.text))
    return out


@dataclass
class Question:
    domain: int
    kind: str  # cloze | mcq | order
    concept_id: str
    label: str  # human category label (for the doc)
    payload: dict  # full render payload, incl. cite + quote
    plain_q: str  # no-JS / doc question text
    plain_a: str  # no-JS / doc answer text
    cite: str
    quote: str


# Sentences describing order of precedence can't be a fair fill-in-the-blank
# (too many possible motions) — those belong in ranking/ordering/select-all
# questions, never cloze/term MCQ.
_PRECEDENCE_RE = re.compile(r"\bprecedence\b|\byield(s|ed)?\b|\boutrank", re.I)

# --- corpus-grounded questions ------------------------------------------------


def _sentence_with(p: Para, term: str) -> str | None:
    return next((s for s in re.split(r"(?<=[.;])\s+", p.text) if term in s), None)


def make_cloze(
    p: Para, cid: str, rng: random.Random, only_term: str | None = None
) -> Question | None:
    if not p.emphases:
        return None
    term = only_term or rng.choice(p.emphases)
    if term not in p.emphases:
        return None
    sentence = _sentence_with(p, term)
    if not sentence or mentions_section(sentence) or _PRECEDENCE_RE.search(sentence):
        return None
    text = sentence.replace(term, "[[0]]", 1)
    blanks = [{"a": term, "h": hint_for(term)}]
    plain_q = "Fill the blank: " + re.sub(r"\[\[\d+\]\]", "_____", text)
    payload = {
        "kind": "cloze",
        "text": text,
        "blanks": blanks,
        "cite": p.citation,
        "quote": sentence.strip(),
    }
    return Question(
        p.domain,
        "cloze",
        cid,
        "Cloze recall",
        payload,
        plain_q,
        f"{term} — “{sentence.strip()}”",
        p.citation,
        sentence.strip(),
    )


def make_term_mcq(
    p: Para, cid: str, pool: list[str], rng: random.Random, only_term: str | None = None
) -> Question | None:
    if not p.emphases:
        return None
    term = only_term or rng.choice(p.emphases)
    if term not in p.emphases:
        return None
    sentence = _sentence_with(p, term)
    if (
        not sentence
        or mentions_section(sentence, term)
        or _PRECEDENCE_RE.search(sentence)
    ):
        return None
    distractors = [
        t for t in pool if t.lower() != term.lower() and not mentions_section(t)
    ]
    if len(distractors) < 3:
        return None
    options = [term, *rng.sample(distractors, 3)]
    rng.shuffle(options)
    answer = options.index(term)
    stem = f"Fill in the blank: {sentence.replace(term, '_____', 1)}"
    payload = {
        "kind": "mcq",
        "stem": stem,
        "options": options,
        "answer": answer,
        "cite": p.citation,
        "quote": sentence.strip(),
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
        sentence.strip(),
    )


# --- knowledge-based questions (motions & characteristics) --------------------


def _motion_domain(m: kb.Motion) -> int:
    return _CLASS_DOMAIN.get(m.klass, 4)


def _kb_ref(m: kb.Motion, secq: dict[int, tuple[str, str]]) -> tuple[str, str]:
    cite, quote = secq.get(m.section, (str(m.section), ""))
    return cite, quote


def make_characteristic(
    m: kb.Motion, which: str, cid: str, secq: dict[int, tuple[str, str]]
) -> Question:
    cite, quote = _kb_ref(m, secq)
    if which == "vote":
        stem = f"What vote does the motion to {m.name} require to be adopted?"
        opts = [
            "Majority vote",
            "Two-thirds vote",
            "No vote (chair rules / demand)",
            "Unanimous consent",
        ]
        ans = opts.index(kb.VOTE_LABELS[m.vote])
    elif which == "debatable":
        stem = f"Is the motion to {m.name} debatable?"
        opts = ["Debatable", "Not debatable"]
        ans = 0 if m.debatable else 1
    elif which == "second":
        stem = f"Does the motion to {m.name} require a second?"
        opts = ["Requires a second", "No second required"]
        ans = 0 if m.second else 1
    else:  # amendable
        stem = f"Can the motion to {m.name} be amended?"
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
        _motion_domain(m), "mcq", cid, label, payload, stem, f"{opts[ans]}", cite, quote
    )


def make_ranking(
    motions: list[kb.Motion],
    cid: str,
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
    cite, quote = _kb_ref(target, secq)
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
    a: kb.Motion, b: kb.Motion, cid: str, secq: dict[int, tuple[str, str]]
) -> Question:
    higher = a if a.rank < b.rank else b
    opts = [a.name, b.name]
    stem = f"Which motion takes precedence — {a.name} or {b.name}?"
    ans = opts.index(higher.name)
    cite, quote = _kb_ref(higher, secq)
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
    stem = f"Select ALL of these motions that {verb} the motion to {pivot.name}."
    cite, quote = _kb_ref(pivot, secq)
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
    motions: list[kb.Motion], cid: str, secq: dict[int, tuple[str, str]]
) -> Question:
    ordered = sorted(motions, key=lambda m: m.rank)  # highest precedence first
    labels = [m.name for m in ordered]
    prompt = "Put these motions in order of precedence."
    cite, quote = _kb_ref(ordered[0], secq)
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
        " → ".join(labels),
        cite,
        quote,
    )


def build_knowledge(
    secq: dict[int, tuple[str, str]], rng: random.Random
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
            qs.append(make_characteristic(m, which, cid(), secq))
    ranked = kb.ranked_motions()
    # Ranking (highest + lowest) and ordering over sliding windows + random subsets.
    subsets: list[list[kb.Motion]] = []
    for size in (3, 4, 5):
        for start in range(0, len(ranked) - size + 1):
            subsets.append(ranked[start : start + size])
    for _ in range(50):
        subsets.append(rng.sample(ranked, rng.choice((3, 4, 5))))
    for subset in subsets:
        qs.append(make_ranking(subset, cid(), secq, rng, "highest"))
        qs.append(make_ranking(subset, cid(), secq, rng, "lowest"))
        qs.append(make_order(subset, cid(), secq))
    # Pairwise "which is higher".
    for _ in range(60):
        a, b = rng.sample(ranked, 2)
        qs.append(make_pair(a, b, cid(), secq))
    # Select-all-that-rank-higher / lower than a pivot.
    for _ in range(120):
        pivot = rng.choice(ranked)
        pool = [m for m in ranked if m is not pivot]
        others = rng.sample(pool, rng.choice((4, 5)))
        direction = rng.choice(("higher", "lower"))
        # ensure a well-formed set (at least one correct and one incorrect).
        has_c = any(
            (m.rank < pivot.rank) if direction == "higher" else (m.rank > pivot.rank)
            for m in others
        )
        has_i = any(
            (m.rank >= pivot.rank) if direction == "higher" else (m.rank <= pivot.rank)
            for m in others
        )
        if has_c and has_i:
            qs.append(make_multi(pivot, others, cid(), secq, rng, direction))
    return qs


def build(count: int = 0, per_para: int = 5) -> list[Question]:
    """Knowledge-based questions + up to ``per_para`` varied questions from every
    corpus paragraph (spec: broad coverage). ``count`` optionally caps the total
    (0 = no cap)."""
    rng = random.Random(SEED)
    paras = parse_corpus()
    secq = section_quotes(paras)
    term_pool = sorted({t for p in paras for t in p.emphases})
    questions: list[Question] = list(build_knowledge(secq, rng))
    # Coverage: walk every paragraph and emit up to `per_para` varied questions
    # from its key terms (distinct cloze + applied-MCQ items).
    cn = 0
    for p in paras:
        cn += 1
        cid = f"C{cn:04d}"
        made = 0
        terms = rng.sample(p.emphases, len(p.emphases)) if p.emphases else []
        for term in terms:
            if made >= per_para:
                break
            for maker in (
                lambda t=term: make_cloze(p, cid, rng, only_term=t),
                lambda t=term: make_term_mcq(p, cid, term_pool, rng, only_term=t),
            ):
                if made >= per_para:
                    break
                q = maker()
                if q is not None:
                    questions.append(q)
                    made += 1
        if count and len(questions) >= count:
            break
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
        "applied multiple choice, order-of-precedence ranking and ordering, and "
        "motion-characteristic questions). Every question is answerable from what "
        "it shows; the RONR (12th ed.) section is cited only in the answer.",
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
            out.append(f"**{i}.** `[{q.concept_id} · {q.label}]` {q.plain_q}")
            if q.payload.get("options"):
                for letter, opt in zip("ABCD", q.payload["options"]):
                    out.append(f"   {letter}. {opt}")
            out.append("")
            out.append(
                f"   *Answer:* {q.plain_a}. See RONR (12th ed.) §{q.cite}"
                + (f" — “{q.quote}”" if q.quote else "")
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
