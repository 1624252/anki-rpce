#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Build the RONR (12th ed.) quote bank the meeting simulator draws on.

For every RPCE concept in ``data/rpce_concepts.json`` this extracts a list of
**verbatim** quotes from ``data/roberts_rules_of_order_12th_edition.md``, each
tagged with its exact ``section:paragraph`` citation. The simulator feeds a
random set of these quotes to the AI (which authors a meeting where each decision
turns on one quote) and shows the governing quote when the answer is graded, so
the citation is always OUR retrieval — never the model's invention (the
"traceable source" rule in docs/rpce/AI_NOTES.md).

Guarantees per concept (see docs/rpce/AI_NOTES.md § "Simulation from quotes"):

- **>= 4 quotes** per concept, and
- **>= 1 quote per referenced section** that contains quotable prose.

The extraction is deliberately a *script*, not model-authored: it copies whole
sentences straight from the corpus, so every quote is exact and every citation
is correct. Selection is by simple heuristics (real sentences from the cited
paragraphs; list/heading fragments and cross-reference-only lines are dropped).
When a concept's own sections don't yield four prose sentences, the builder
draws additional quotes from adjacent paragraphs in the same chapter, then from
sibling concepts in the same group/domain — always with the source paragraph's
own citation.

Run from the repo root (no build needed — reads the data files directly):

    python pylib/tools/rpce_build_quotes.py

writes ``data/rpce_quotes.json``. Pass an output path to override.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "data" / "roberts_rules_of_order_12th_edition.md"
CONCEPTS = ROOT / "data" / "rpce_concepts.json"
DEFAULT_OUT = ROOT / "data" / "rpce_quotes.json"

#: Minimum quotes to produce for every concept.
TARGET = 4

# A book paragraph: <a id="p-<ch>-<par>"></a>*<ch>:<par>* <text…> (up to next anchor).
_PARA_RE = re.compile(
    r'<a id="p-(\d+)-(\d+)"></a>\s*\*(\d+):(\d+)\*\s*(.*?)(?=<a id=)', re.DOTALL
)
# A leading list enumerator to strip from a sentence: "2. ", "(3) ", "(a) ".
_ENUM_RE = re.compile(r"^\(?[0-9]{1,3}\)?[).]\s+|^\([a-z]\)\s+")


def _load_book() -> tuple[dict[str, list[str]], dict[int, list[int]]]:
    """Parse the corpus into ``{"ch:par": [raw md, …]}`` and a chapter ->
    ordered-paragraph-number index (for adjacent-paragraph fallback)."""
    text = BOOK.read_text(encoding="utf-8")
    para: dict[str, list[str]] = {}
    chapter: dict[int, list[int]] = defaultdict(list)
    for m in _PARA_RE.finditer(text):
        ch, pn = int(m.group(1)), int(m.group(2))
        sec = f"{ch}:{pn}"
        if sec not in para:
            chapter[ch].append(pn)
        para.setdefault(sec, []).append(m.group(5))
    return para, chapter


def _clean(md: str) -> str:
    """Strip markdown so a quote reads as plain prose: drop anchors, turn
    ``[label](#link)`` into ``label``, remove emphasis marks, collapse space."""
    md = re.sub(r'<a id="[^"]*"></a>', " ", md)
    md = re.sub(r"\[([^\]]*)\]\(#[^)]*\)", r"\1", md)
    md = md.replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", md).strip()


def _sentences(para: dict[str, list[str]], sec: str, corpus: str) -> list[str]:
    """The quotable sentences of section ``sec`` — real sentences only (>= 8
    words, ending in terminal punctuation); headings, list-title fragments,
    dangling list numbers, and cross-reference-only lines are dropped. Every
    returned sentence is checked to be a **verbatim** substring of ``corpus``
    (the cleaned book), so no quote is ever silently altered."""
    text = _clean(" ".join(para.get(sec, [])))
    out: list[str] = []
    for raw in re.split(r'(?<=[.!?])\s+(?=[A-Z“"(0-9])', text):
        s = _ENUM_RE.sub("", raw).strip()  # drop a leading list enumerator
        if not s.endswith((".", "!", "?", "”", '"')):
            continue  # heading / fragment with no sentence end
        if len(s.split()) < 8 or len(s) > 340 or not re.search(r"[a-z]", s):
            continue
        if re.search(r"[:;]\s*\d{1,3}\.$", s) or re.search(r"\s\d{1,3}\.$", s):
            continue  # a list intro with a glued-on item number ("…: 1.")
        if s.lower().count("see ") >= 2:
            continue  # mostly a cross-reference
        if s not in corpus:
            continue  # never emit a non-verbatim quote
        out.append(s)
    return out


def _expand_ref(ref: str) -> list[str]:
    """The concrete ``ch:par`` sections a concept ref denotes. Ranges like
    ``6:1–3`` expand; table/page refs (``t3-t5``, ``pg-…``) yield nothing."""
    ref = ref.strip()
    m = re.match(r"^(\d+):(\d+)(?:[–-](\d+))?", ref)
    if not m:
        return []
    ch, a, b = int(m.group(1)), int(m.group(2)), m.group(3)
    if b is None:
        return [f"{ch}:{a}"]
    end = int(b)
    if end < a or end - a > 40:  # malformed/typo range -> just the start paragraph
        return [f"{ch}:{a}"]
    return [f"{ch}:{a + i}" for i in range(end - a + 1)]


def _concept_sections(para: dict[str, list[str]], concept: dict) -> list[str]:
    """The concept's referenced sections that actually exist in the corpus."""
    secs: list[str] = []
    for ref in concept.get("ronr_refs", []) or []:
        for s in _expand_ref(ref):
            if s in para and s not in secs:
                secs.append(s)
    return secs


def _adjacent(chapter: dict[int, list[int]], secs: list[str]) -> list[str]:
    """Paragraphs surrounding ``secs`` in the same chapter (nearest first) —
    the topical fallback when a concept's own sections are too thin."""
    out: list[str] = []
    for s in secs:
        ch, pn = (int(x) for x in s.split(":"))
        paras = chapter.get(ch, [])
        if pn in paras:
            i = paras.index(pn)
            forward = range(i + 1, len(paras))
            backward = range(i - 1, -1, -1)
            out += [f"{ch}:{paras[j]}" for j in list(forward) + list(backward)]
    return out


def _norm(quote: str) -> str:
    return re.sub(r"\W+", " ", quote.lower()).strip()


def build_quotes() -> dict:
    """Assemble ``{"quotes": {concept_id: [{"section","quote"}, …]}}``."""
    para, chapter = _load_book()
    corpus = _clean(BOOK.read_text(encoding="utf-8"))  # for the verbatim check
    concepts = json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]

    # Section pools for the group/domain fallback (concepts with no prose refs).
    group_pool: dict[tuple, list[str]] = defaultdict(list)
    domain_pool: dict[int, list[str]] = defaultdict(list)
    for c in concepts:
        for s in _concept_sections(para, c):
            group_pool[(c["domain"], c.get("group", ""))].append(s)
            domain_pool[c["domain"]].append(s)

    result: dict[str, list[dict]] = {}
    for c in concepts:
        secs = _concept_sections(para, c)
        quotes: list[dict] = []
        seen: set[str] = set()

        def add(sec: str, sent: str) -> None:
            key = _norm(sent)
            if key and key not in seen:
                seen.add(key)
                quotes.append({"section": sec, "quote": sent})

        # 1) >= 1 quote for each referenced section that has prose.
        for s in secs:
            ss = _sentences(para, s, corpus)
            if ss:
                add(s, ss[0])
        # 2) top up toward TARGET with more sentences from those sections.
        for s in secs:
            for sent in _sentences(para, s, corpus)[1:]:
                if len(quotes) >= TARGET:
                    break
                add(s, sent)
        # 3) still short -> adjacent paragraphs in the same chapter.
        if len(quotes) < TARGET:
            for s in _adjacent(chapter, secs):
                if len(quotes) >= TARGET:
                    break
                ss = _sentences(para, s, corpus)
                if ss:
                    add(s, ss[0])
        # 4) still short (e.g. table-only refs) -> group, then domain siblings.
        if len(quotes) < TARGET:
            pool = group_pool.get((c["domain"], c.get("group", "")), [])
            pool = pool + domain_pool.get(c["domain"], [])
            for s in pool:
                if len(quotes) >= TARGET:
                    break
                ss = _sentences(para, s, corpus)
                if ss:
                    add(s, ss[0])
        result[str(c["id"])] = quotes

    total = sum(len(v) for v in result.values())
    return {
        "meta": {
            "source": "Robert's Rules of Order Newly Revised, 12th ed.",
            "concepts": len(result),
            "quotes": total,
            "min_per_concept": TARGET,
            "note": "Verbatim excerpts with exact citations; built by "
            "pylib/tools/rpce_build_quotes.py. Do not hand-edit.",
        },
        "quotes": result,
    }


def main(out_path: str | None = None) -> None:
    data = build_quotes()
    # Fail loudly if the invariant broke — never ship a thin bank.
    thin = {cid: len(q) for cid, q in data["quotes"].items() if len(q) < TARGET}
    if thin:
        print(
            f"ERROR: {len(thin)} concept(s) below {TARGET} quotes: {thin}",
            file=sys.stderr,
        )
        sys.exit(1)
    out = Path(out_path) if out_path else DEFAULT_OUT
    out.write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {out} — {data['meta']['concepts']} concepts, "
        f"{data['meta']['quotes']} quotes"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
