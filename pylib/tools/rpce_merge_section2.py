# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Merge the per-domain Section II scenario batches (authored by subagents, one
JSON array each in the scratchpad) into ``data/rpce_section2_scenarios.json``.

Each scenario is tagged with its performance-expectation concept id so Section
II is labelled + scored by concept, and carries explicit grading ``keywords``
(fed to the offline grader and the online AI examiner) plus a verbatim RONR
(12th ed.) quote for the model answer.

Usage: python rpce_merge_section2.py <scratch_dir> [--check-quotes]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rpce_section2_scenarios.json"
CORPUS = ROOT / "data" / "roberts_rules_of_order_12th_edition.md"
BATCHES = [f"q_s2_d{d}.json" for d in range(1, 8)]


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


def _map(s: dict) -> dict | None:
    """Validate + normalise a subagent scenario record."""
    try:
        domain = int(s["domain"])
        concept = str(s["concept"]).strip()
        prompt = str(s["prompt"]).strip()
        gold = str(s["gold_answer"]).strip()
        section = str(s.get("section", "") or "").strip()
        quote = str(s.get("quote", "") or "").strip()
        keywords = [str(k).strip() for k in (s.get("keywords") or []) if str(k).strip()]
    except (KeyError, ValueError, TypeError):
        return None
    if not (domain and concept and prompt and gold):
        return None
    return {
        "domain": domain,
        "concept": concept,
        "section": section,
        "quote": quote,
        "prompt": prompt,
        "gold_answer": gold,
        "keywords": keywords,
    }


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
        recs = recs["scenarios"] if isinstance(recs, dict) else recs
        for s in recs:
            m = _map(s)
            if not m:
                dropped += 1
                continue
            key = f"{m['concept']}|{m['prompt']}"
            if key in seen:
                dropped += 1
                continue
            if check_quotes and m["quote"] and _norm(m["quote"]) not in corpus:
                dropped += 1
                continue
            seen.add(key)
            out.append(m)
    OUT.write_text(
        json.dumps({"scenarios": out}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    concepts = {s["concept"] for s in out}
    print(f"wrote {len(out)} scenarios to {OUT} (dropped {dropped})")
    print("by domain:", dict(sorted(Counter(s["domain"] for s in out).items())))
    print(f"distinct concepts: {len(concepts)}")
    per = Counter(s["concept"] for s in out)
    print("concepts with <3 scenarios:", [c for c, n in per.items() if n < 3][:20])


if __name__ == "__main__":
    main(sys.argv[1], "--check-quotes" in sys.argv)
