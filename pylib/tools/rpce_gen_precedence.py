#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Generate order + multiselect questions from the canonical motion knowledge.

These are objective (precedence / class / characteristics of the ranked
motions), so they're generated deterministically from ``anki.rpce.knowledge``
and are correct by construction (self-checked). They balance the type counts so
the round-robin deck order shows ordering/multiselect as often as MCQ/cloze.
Writes ``data/rpce_precedence_questions.json`` which the deck loader merges with
the authored MCQ/cloze bank.
"""

from __future__ import annotations

import json
from pathlib import Path

from anki.rpce import knowledge as kb
from anki.rpce import refs

OUT = Path(__file__).resolve().parents[2] / "data" / "rpce_precedence_questions.json"
REF = refs.PRECEDENCE
RANKED = [m.name for m in kb.ranked_motions()]  # highest -> lowest
BY_NAME = {m.name: m for m in kb.MOTIONS}


def order_questions() -> list[dict]:
    """Slide windows of size 3-6 across the ranked motions -> 'put in order'."""
    out, seen = [], set()
    n = 0
    for size in (3, 4, 5, 6):
        for start in range(0, len(RANKED) - size + 1):
            subset = RANKED[start : start + size]
            ordered = kb.canonical_order(subset)
            assert kb.is_ordered_by_precedence(ordered)  # correct by construction
            key = tuple(ordered)
            if key in seen:
                continue
            seen.add(key)
            n += 1
            prompt = "Put these motions in order of precedence (top = higher, bottom = lower)."
            out.append({
                "domain": 2,
                "concept": f"prec-order-{n}",
                "kind": "order",
                "prompt": prompt,
                "order": ordered,
                "cite": REF.section,
                "quote": REF.quote,
                "plainQ": prompt + " Motions: " + ", ".join(subset),
                "plainA": " → ".join(ordered),
            })
    return out


def _multi(concept: str, domain: int, stem: str, pool: list[str], winners: list[str]) -> dict:
    correct = [i for i, name in enumerate(pool) if name in winners]
    return {
        "domain": domain,
        "concept": concept,
        "kind": "multi",
        "stem": stem,
        "options": list(pool),
        "correct": correct,
        "cite": REF.section,
        "quote": REF.quote,
        "plainQ": stem + " Options: " + ", ".join(pool),
        "plainA": ", ".join(pool[i] for i in correct) or "(none)",
    }


def multi_questions() -> list[dict]:
    out: list[dict] = []
    n = 0
    # Precedence higher/lower than a pivot, over varied pools.
    pivots = [
        ("Postpone to a Certain Time", ["Amend", "Recess", "Commit or Refer", "Previous Question", "Postpone Indefinitely"], "higher"),
        ("Recess", ["Adjourn", "Amend", "Lay on the Table", "Fix the Time to Which to Adjourn"], "lower"),
        ("Commit or Refer", ["Amend", "Postpone Indefinitely", "Previous Question", "Lay on the Table"], "higher"),
        ("Previous Question", ["Amend", "Recess", "Limit or Extend Limits of Debate", "Commit or Refer"], "lower"),
        ("Amend", ["Postpone Indefinitely", "Commit or Refer", "Previous Question", "Adjourn"], "higher"),
        ("Lay on the Table", ["Adjourn", "Recess", "Previous Question", "Amend"], "lower"),
    ]
    for pivot, pool, direction in pivots:
        n += 1
        winners = (kb.motions_higher_than(pivot, pool) if direction == "higher"
                   else kb.motions_lower_than(pivot, pool))
        verb = ("rank higher than (take precedence over)" if direction == "higher"
                else "rank lower than (yield to)")
        out.append(_multi(f"prec-{direction}-{n}", 2,
                           f"Select ALL of these motions that {verb} {kb.motion_phrase(pivot)}.",
                           pool, winners))

    # Class membership (privileged / subsidiary) over mixed pools.
    class_pools = [
        ["Adjourn", "Amend", "Recess", "Commit or Refer", "Raise a Question of Privilege"],
        ["Lay on the Table", "Fix the Time to Which to Adjourn", "Postpone Indefinitely", "Call for the Orders of the Day", "Previous Question"],
        ["Limit or Extend Limits of Debate", "Adjourn", "Postpone to a Certain Time", "Recess"],
    ]
    for klass, label in ((kb.CLASS_PRIVILEGED, "privileged motions"), (kb.CLASS_SUBSIDIARY, "subsidiary motions")):
        for pool in class_pools:
            n += 1
            winners = [m for m in pool if BY_NAME[m].klass == klass]
            out.append(_multi(f"prec-class-{n}", 2,
                               f"Select ALL of these that are {label}.", pool, winners))

    # Characteristics: debatable / amendable / needs a second / two-thirds vote.
    char_pools = [
        ["Adjourn", "Amend", "Commit or Refer", "Previous Question", "Postpone to a Certain Time"],
        ["Recess", "Postpone Indefinitely", "Lay on the Table", "Limit or Extend Limits of Debate", "Raise a Question of Privilege"],
    ]
    checks = [
        ("debatable", "are debatable", lambda m: m.debatable),
        ("amendable", "are amendable", lambda m: m.amendable),
        ("second", "require a second", lambda m: m.second),
        ("twothirds", "require a two-thirds vote to adopt", lambda m: m.vote == kb.VOTE_TWO_THIRDS),
    ]
    for pool in char_pools:
        for key, phrase, pred in checks:
            n += 1
            winners = [m for m in pool if pred(BY_NAME[m])]
            out.append(_multi(f"prec-char-{key}-{n}", 2,
                               f"Select ALL of these motions that {phrase}.", pool, winners))
    return out


def main() -> None:
    qs = order_questions() + multi_questions()
    OUT.write_text(json.dumps({"questions": qs}, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds: dict[str, int] = {}
    for q in qs:
        kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
    print(f"wrote {OUT} ({len(qs)} questions): {kinds}")


if __name__ == "__main__":
    main()
