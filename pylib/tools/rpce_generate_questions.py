#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Generate RPCE practice questions grounded in the real RONR 12th-ed. corpus.

Every question is built from actual paragraph text in
``data/roberts_rules_of_order_12th_edition.md`` so that each answer can cite the
**exact section** (e.g. ``RONR (12th ed.) 10:11``) and give a **verbatim quote**
from that section — nothing is fabricated (spec §7: AI output must trace to a
named source). The generator is deterministic (fixed seed) so it is reproducible.

Question types (varied, per the sample set in
``data/RPCE-Sample-Questions-v4-100625.md``). Both test the rule's content;
neither names a RONR section in the stem or options — the section appears only
in the answer, alongside the relevant verbatim quote:

- **cloze**    — recall a key (emphasised) term blanked out of a real sentence.
- **term_mcq** — applied multiple choice: pick the term that fills the blank,
  among plausible distractor terms drawn from other concepts.

Each item is tagged with a **Concept ID** and a **format**. Every format of one
concept shares its Concept ID, so the spaced-repetition scheduler treats them as
a single problem on one FSRS schedule and rotates the format each repetition
(spec §7.1 / SPOV 1 — the Transfer Ladder). The format tag is how answers of the
same type are tracked.

Usage (from the repo root):

    python pylib/tools/rpce_generate_questions.py [count] [out.md]
    # defaults: 1000  docs/rpce/rpce_practice_questions.md
"""

from __future__ import annotations

import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path("data/roberts_rules_of_order_12th_edition.md")
SEED = 20260701

# A paragraph line looks like:
#   [<a id="pg-573"></a>]<a id="p-44-1"></a>*44:1* <text...>
_PARA_RE = re.compile(
    r'(?:<a id="pg-\d+"></a>)*<a id="p-(\d+)-(\d+)"></a>\*([\d]+:[\d]+[^*]*)\*\s*(.*)'
)
_TAG_RE = re.compile(r'<a id="[^"]*"></a>')
_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:#|https?)[^)]*\)")  # keep link text
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")  # run-in headings
_EMPH_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")  # italic key terms only
_MULTISPACE_RE = re.compile(r"\s+")
# Footnote markers like "> **13.**" and leading blockquotes.
_FOOTNOTE_RE = re.compile(r"^>\s*")

# The seven Performance-Expectation domains, by primary RONR section ranges.
# (Approximate blueprint mapping; the citation/quote is the authoritative part.)
DOMAIN_NAMES = {
    1: "Motions in General and Main Motions",
    2: "Subsidiary and Privileged Motions",
    3: "Incidental Motions and Motions that Bring a Question Again Before the Assembly",
    4: "Organization and Conduct of Meetings",
    5: "Voting, Nominations, and Elections",
    6: "Being and Serving as a Professional Parliamentarian and Teaching Parliamentary Procedure",
    7: "Boards and Committees, and Writing and Interpreting Bylaws",
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
    # Everything else (basic provisions, meetings, minutes, officers, notice…).
    return 4


def clean(text: str) -> str:
    """Turn raw corpus markup into clean prose, restoring conversion mojibake."""
    text = text.replace("\ufffd?T", "\u2019").replace("\ufffd?o", "\u201c")
    text = text.replace("\ufffd", "")
    text = _FOOTNOTE_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    # Strip markdown emphasis markers so display text is plain prose.
    text = text.replace("**", "").replace("*", "").replace("_", "")
    text = _MULTISPACE_RE.sub(" ", text).strip()
    return text


@dataclass
class Para:
    citation: str  # e.g. "10:11"
    section: int
    domain: int
    text: str  # cleaned full paragraph
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
        # Italic key terms only (drop **bold run-in headings** first).
        italic_src = _BOLD_RE.sub(" ", body)
        emphases = [clean(e) for e in _EMPH_RE.findall(italic_src)]
        text = clean(body)
        # Keep substantive prose only.
        if len(text) < 90 or ":" not in citation:
            continue
        # Usable emphasised terms: multi-char, not pure punctuation/numbers.
        emph = [
            e
            for e in emphases
            if 3 <= len(e) <= 40 and re.search(r"[A-Za-z]", e) and e in text
        ]
        paras.append(Para(citation, sec, domain_for_section(sec), text, emph))
    return paras


# A RONR section reference (e.g. "10:5", "§23", "Section 4"). Questions and their
# options must NOT mention sections — that belongs only in the answer citation.
_SECTION_RE = re.compile(r"\b\d+:\d+\b|§|\bRONR\b|\bsections?\s+\d+", re.I)


def mentions_section(*texts: str) -> bool:
    """True if any text names a RONR section (disallowed in stems/options)."""
    return any(_SECTION_RE.search(t) for t in texts if t)


@dataclass
class Question:
    domain: int
    kind: str  # human-readable format label
    fmt: str  # machine format key: cloze | term_mcq
    concept_id: str  # e.g. "C0007" — shared by every format of one concept
    stem: str
    options: list[str]  # empty for non-MCQ
    answer: str  # letter for MCQ, or the term/quote
    citation: str
    quote: str


def make_cloze(p: Para, concept_id: str, rng: random.Random) -> Question | None:
    if not p.emphases:
        return None
    term = rng.choice(p.emphases)
    sentence = next((s for s in re.split(r"(?<=[.;])\s+", p.text) if term in s), None)
    if not sentence:
        return None
    blanked = sentence.replace(term, "_____", 1)
    # Never quiz on a sentence that itself names a section.
    if mentions_section(blanked):
        return None
    return Question(
        p.domain,
        "Cloze recall",
        "cloze",
        concept_id,
        f"Fill in the blank: {blanked}",
        [],
        term,
        p.citation,
        sentence.strip(),
    )


def make_term_mcq(
    p: Para, concept_id: str, term_pool: list[str], rng: random.Random
) -> Question | None:
    """Applied multiple-choice on the concept's key term.

    The stem is the concept sentence with its key term blanked; the options are
    that term plus three plausible distractor terms drawn from other concepts.
    This tests understanding of the *rule itself* — never which section a
    passage came from (that kind of section-recall question is intentionally
    excluded; the citation is shown only in the answer debrief).
    """
    if not p.emphases:
        return None
    term = rng.choice(p.emphases)
    sentence = next((s for s in re.split(r"(?<=[.;])\s+", p.text) if term in s), None)
    if not sentence:
        return None
    blanked = sentence.replace(term, "_____", 1)
    # Skip sentences/terms that name a section (must stay out of stems & options).
    if mentions_section(blanked, term):
        return None
    pool = [
        t for t in term_pool if t.lower() != term.lower() and not mentions_section(t)
    ]
    if len(pool) < 3:
        return None
    options = [term, *rng.sample(pool, 3)]
    rng.shuffle(options)
    letter = "ABCD"[options.index(term)]
    return Question(
        p.domain,
        "Applied multiple-choice",
        "term_mcq",
        concept_id,
        f"Fill in the blank: {blanked}",
        options,
        letter,
        p.citation,
        sentence.strip(),
    )


# The formats each concept is taught in (Transfer Ladder / SPOV 1: same concept,
# different shapes). Every format of one concept shares its Concept ID so the
# spaced-repetition scheduler treats them as ONE problem on ONE FSRS schedule.
# Both formats test the rule's content; the RONR section is never named in a
# stem or option — it appears only in the answer's citation/quote.
FORMATS = ("cloze", "term_mcq")


def build(count: int) -> list[Question]:
    """Generate ``count`` questions **grouped by concept**.

    A *concept* is one source paragraph. For each concept we emit up to two
    format variants (cloze recall + applied multiple-choice), both tagged with
    the same ``concept_id``. Downstream, items sharing a Concept ID are scheduled
    as a single problem whose *format rotates* each repetition — never the same
    shape twice in a row (spec §7.1 / SPOV 1). Deterministic (fixed seed).
    """
    rng = random.Random(SEED)
    paras = parse_corpus()
    # Distractor pool for the applied MCQ: every emphasised term in the corpus.
    term_pool = sorted({t for p in paras for t in p.emphases})
    rng.shuffle(paras)
    questions: list[Question] = []
    concept_n = 0
    for p in paras:
        if len(questions) >= count:
            break
        concept_n += 1
        concept_id = f"C{concept_n:04d}"
        for fmt in FORMATS:
            if len(questions) >= count:
                break
            if fmt == "cloze":
                q = make_cloze(p, concept_id, rng)
            else:  # term_mcq
                q = make_term_mcq(p, concept_id, term_pool, rng)
            if q is not None:
                questions.append(q)
    return questions[:count]


def render(questions: list[Question]) -> str:
    concepts = {q.concept_id for q in questions}
    out: list[str] = [
        "# RPCE Practice Questions (generated, RONR 12th-ed.-grounded)",
        "",
        f"{len(questions)} questions across {len(concepts)} concepts, generated from "
        "the transcribed *Robert's Rules of Order Newly Revised, 12th ed.* corpus. "
        "Every answer cites the exact section and quotes it verbatim (spec §7). "
        "Question types are varied (cloze recall, quote→section, stated-in-section), "
        "following [`RPCE-Sample-Questions-v4-100625.md`](./RPCE-Sample-Questions-v4-100625.md).",
        "",
        "**Spaced-repetition grouping.** Each item is tagged `[Concept Cxxxx · "
        "format]`. Items that share a **Concept ID** are the *same concept in "
        "different formats*: the app schedules them as **one problem on a single "
        "FSRS schedule** and *rotates* the format each repetition — never the same "
        "shape twice in a row (spec §7.1 / SPOV 1, the Transfer Ladder). The format "
        "tag is how the scheduler tracks answers of the same type.",
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
        answers: list[str] = []
        for n, q in enumerate(qs, 1):
            out.append(f"**{n}.** `[{q.concept_id} · {q.fmt}]` _{q.kind}_ — {q.stem}")
            out.append("")
            if q.options:
                for letter, opt in zip("ABCD", q.options):
                    out.append(f"   {letter}. {opt}")
                out.append("")
            anchor = "p-" + q.citation.split("(")[0].replace(":", "-")
            link = f"[{q.citation}](roberts_rules_of_order_12th_edition.md#{anchor})"
            label = "Correct answer" if q.options else "Answer"
            answers.append(
                f"{n}. `[{q.concept_id} · {q.fmt}]` {label}: **{q.answer}**. "
                f'See RONR (12th ed.) {link} — "{q.quote}"'
            )
        out.append("**Answer Key** (with Concept ID · format for SRS tracking)")
        out.append("")
        out.extend(answers)
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def main() -> None:
    # The summary contains non-cp1252 characters (e.g. "→"); force UTF-8 output.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    # Default to the repo-tracked docs path (data/ is a gitignored nested repo).
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path("docs/rpce/rpce_practice_questions.md")
    )
    questions = build(count)
    out_path.write_text(render(questions), encoding="utf-8")
    kinds: dict[str, int] = {}
    for q in questions:
        kinds[q.kind] = kinds.get(q.kind, 0) + 1
    concepts = len({q.concept_id for q in questions})
    print(f"wrote {len(questions)} questions across {concepts} concepts to {out_path}")
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
