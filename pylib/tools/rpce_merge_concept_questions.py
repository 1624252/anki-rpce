# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Merge the per-domain concept-tagged question batches (authored by subagents,
one JSON array each in the scratchpad) into ``data/rpce_authored_questions.json``
in the schema the starter-deck exporter (rpce_export_starter.add_authored_
questions) consumes. Each question is tagged with its performance-expectation
concept id (e.g. "1.13") so cards carry ``rpce::concept::1.13`` for concept
coverage and scoring (docs/rpce/SCORING.md).

Usage: python rpce_merge_concept_questions.py <scratch_dir> [--check-quotes]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rpce_authored_questions.json"
CORPUS = ROOT / "data" / "roberts_rules_of_order_12th_edition.md"
BATCHES = [
    "q_d1_d2.json",
    "q_d3_d4.json",
    "q_d5_d6.json",
    "q_d7.json",
    "q_backfill.json",
    "q_fill.json",
]


def _norm(t: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        t.replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-"),
    ).strip()


def _cloze_plain(text: str) -> str:
    return re.sub(r"\[\[\d+\]\]", "___", text)


def _map(q: dict) -> dict | None:
    """Map a subagent question record to the authored-bank schema."""
    kind = q.get("kind")
    concept = str(q.get("concept", "")).strip()
    domain = int(q.get("domain", 0))
    cite = str(q.get("section", "") or "")
    quote = str(q.get("quote", "") or "")
    if not concept or not domain:
        return None
    base = {
        "kind": kind,
        "domain": domain,
        "concept": concept,
        "cite": cite,
        "quote": quote,
    }
    if kind == "mcq":
        opts = list(q.get("options") or [])
        ans = int(q.get("answer", 0))
        if len(opts) < 3 or not (0 <= ans < len(opts)):
            return None
        base.update(
            stem=q["prompt"],
            options=opts,
            answer=ans,
            plainQ=q["prompt"],
            plainA=opts[ans],
        )
    elif kind == "multi":
        opts = list(q.get("options") or [])
        correct = [int(i) for i in (q.get("correct") or [])]
        if len(opts) < 3 or not correct:
            return None
        base.update(
            stem=q["prompt"],
            options=opts,
            correct=correct,
            plainQ=q["prompt"],
            plainA=", ".join(opts[i] for i in correct if 0 <= i < len(opts)),
        )
    elif kind == "order":
        order = list(q.get("order") or [])
        if len(order) < 3:
            return None
        base.update(
            prompt=q["prompt"],
            order=order,
            plainQ=q["prompt"],
            plainA=" > ".join(order),
        )
    elif kind == "cloze":
        text = q.get("prompt", "")
        blanks = [{"a": b.get("a", ""), "h": ""} for b in (q.get("blanks") or [])]
        if not blanks or "[[0]]" not in text:
            return None
        base.update(
            text=text,
            blanks=blanks,
            plainQ=_cloze_plain(text),
            plainA=q.get("answer_text") or ", ".join(b["a"] for b in blanks),
        )
    else:
        return None
    return base


def main(scratch: str, check_quotes: bool = False) -> None:
    sp = Path(scratch)
    corpus = _norm(CORPUS.read_text(encoding="utf-8")) if check_quotes else ""
    out: list[dict] = []
    seen: set[str] = set()
    dropped = 0
    for name in BATCHES:
        p = sp / name
        if not p.exists():
            print(f"  (missing {name})")
            continue
        recs = json.loads(p.read_text(encoding="utf-8"))
        recs = recs["questions"] if isinstance(recs, dict) else recs
        for q in recs:
            m = _map(q)
            if not m:
                dropped += 1
                continue
            key = (
                m["kind"],
                m.get("stem") or m.get("text") or m.get("prompt", ""),
            ).__str__()
            if key in seen:
                dropped += 1
                continue
            if check_quotes and m["quote"] and _norm(m["quote"]) not in corpus:
                dropped += 1
                continue
            seen.add(key)
            out.append(m)
    OUT.write_text(
        json.dumps({"questions": out}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    from collections import Counter

    print(f"wrote {len(out)} questions to {OUT} (dropped {dropped})")
    print("by kind:", dict(Counter(q["kind"] for q in out)))
    print("distinct concepts:", len({q["concept"] for q in out}))


if __name__ == "__main__":
    main(sys.argv[1], "--check-quotes" in sys.argv)
