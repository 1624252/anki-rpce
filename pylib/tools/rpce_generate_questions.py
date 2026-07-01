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
``data/RPCE-Sample-Questions-v4-100625.md``):

- **cloze**    — recall a key (emphasised) term blanked out of a real sentence.
- **quote_id** — multiple choice: which section does this verbatim quote come from?
- **stated_in**— multiple choice: which statement appears in a given section?

Usage (from the repo root):

    python pylib/tools/rpce_generate_questions.py [count] [out.md]
    # defaults: 1000  data/rpce_generated_questions.md
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


def first_sentence(text: str, limit: int = 320) -> str:
    """A focused, substantive quote: the first sentence of reasonable length,
    skipping short run-in headings like "The Board."."""
    parts = [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(\u201c])", text)]
    chosen = next((s for s in parts if len(s) >= 60), None)
    if chosen is None:
        chosen = max(parts, key=len) if parts else text.strip()
    if len(chosen) > limit:
        chosen = chosen[:limit].rsplit(" ", 1)[0] + "\u2026"
    return chosen.strip()


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


@dataclass
class Question:
    domain: int
    kind: str
    stem: str
    options: list[str]  # empty for non-MCQ
    answer: str  # letter for MCQ, or the term/quote
    citation: str
    quote: str


def make_cloze(p: Para, rng: random.Random) -> Question | None:
    if not p.emphases:
        return None
    term = rng.choice(p.emphases)
    sentence = next((s for s in re.split(r"(?<=[.;])\s+", p.text) if term in s), None)
    if not sentence:
        return None
    blanked = sentence.replace(term, "_____", 1)
    return Question(
        p.domain,
        "Cloze recall",
        f"Fill in the blank: {blanked}",
        [],
        term,
        p.citation,
        sentence.strip(),
    )


def make_quote_id(p: Para, pool: list[Para], rng: random.Random) -> Question:
    quote = first_sentence(p.text)
    others = rng.sample([q for q in pool if q.citation != p.citation], 3)
    options = [p.citation] + [o.citation for o in others]
    rng.shuffle(options)
    letter = "ABCD"[options.index(p.citation)]
    return Question(
        p.domain,
        "Quote → section (MCQ)",
        f'From which section of RONR (12th ed.) is the following?\n\n   "{quote}"',
        options,
        letter,
        p.citation,
        quote,
    )


def make_stated_in(p: Para, pool: list[Para], rng: random.Random) -> Question:
    correct = first_sentence(p.text)
    others = rng.sample([q for q in pool if q.citation != p.citation], 3)
    options = [correct] + [first_sentence(o.text) for o in others]
    rng.shuffle(options)
    letter = "ABCD"[options.index(correct)]
    return Question(
        p.domain,
        "Stated in section (MCQ)",
        f"Which of the following statements appears in RONR (12th ed.) {p.citation}?",
        options,
        letter,
        p.citation,
        correct,
    )


def build(count: int) -> list[Question]:
    rng = random.Random(SEED)
    paras = parse_corpus()
    rng.shuffle(paras)
    questions: list[Question] = []
    i = 0
    # Rotate through the three types for variety.
    makers = ("cloze", "quote_id", "stated_in")
    while len(questions) < count and i < len(paras) * 3:
        p = paras[i % len(paras)]
        kind = makers[i % 3]
        q: Question | None
        if kind == "cloze":
            q = make_cloze(p, rng)
        elif kind == "quote_id":
            q = make_quote_id(p, paras, rng)
        else:
            q = make_stated_in(p, paras, rng)
        if q is not None:
            questions.append(q)
        i += 1
    return questions[:count]


def render(questions: list[Question]) -> str:
    out: list[str] = [
        "# RPCE Practice Questions (generated, RONR 12th-ed.-grounded)",
        "",
        f"{len(questions)} questions generated from the transcribed *Robert's Rules "
        "of Order Newly Revised, 12th ed.* corpus. Every answer cites the exact "
        "section and quotes it verbatim. Question types are varied (cloze recall, "
        "quote→section, and stated-in-section), following the style of "
        "[`RPCE-Sample-Questions-v4-100625.md`](./RPCE-Sample-Questions-v4-100625.md).",
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
            out.append(f"**{n}.** _{q.kind}_ — {q.stem}")
            out.append("")
            if q.options:
                for letter, opt in zip("ABCD", q.options):
                    out.append(f"   {letter}. {opt}")
                out.append("")
            anchor = "p-" + q.citation.split("(")[0].replace(":", "-")
            link = f"[{q.citation}](roberts_rules_of_order_12th_edition.md#{anchor})"
            if q.options:
                answers.append(
                    f"{n}. Correct answer: **{q.answer}**. See RONR (12th ed.) "
                    f'{link} — "{q.quote}"'
                )
            else:
                answers.append(
                    f"{n}. Answer: **{q.answer}**. See RONR (12th ed.) {link} — "
                    f'"{q.quote}"'
                )
        out.append("**Answer Key**")
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
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path("data/rpce_generated_questions.md")
    )
    questions = build(count)
    out_path.write_text(render(questions), encoding="utf-8")
    kinds = {}
    for q in questions:
        kinds[q.kind] = kinds.get(q.kind, 0) + 1
    print(f"wrote {len(questions)} questions to {out_path}")
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
