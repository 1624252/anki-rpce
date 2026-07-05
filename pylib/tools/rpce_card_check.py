#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The AI card check (spec §7f).

Two jobs, both offline + deterministic:

1. **Gold set** — confirm the grading gold set is >=50 known-correct Q&A
   (parsed official sample questions, augmented from the authored bank when
   short, with the augmentation source printed), and that it does not leak into
   study content.

2. **Card check** — take 50 cards from ONE real source (the RONR-grounded
   generated bank, ``docs/rpce/rpce_practice_questions.md``) and bin them into
   three counts against a PRE-SET, blocking cutoff:
   correct+useful / wrong / correct-but-bad-teaching.

Exits non-zero if the pre-set cutoff blocks the batch (or the gold set is short).

    PYTHONPATH=out/pylib python pylib/tools/rpce_card_check.py [--n 50]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anki.rpce import card_check, examiner, gold
from anki.rpce.card_check import Bucket

_ROOT = Path(__file__).resolve().parents[2]
_SAMPLE = _ROOT / "data" / "RPCE-Sample-Questions-v4-100625.md"
_CORPUS = _ROOT / "data" / "roberts_rules_of_order_12th_edition.md"
_BANK = _ROOT / "docs" / "rpce" / "rpce_practice_questions.md"


def _gold_section() -> tuple[bool, list[gold.GoldQ]]:
    """Print the gold-set size + source + leakage, return (ok, gold set)."""
    text = _SAMPLE.read_text(encoding="utf-8") if _SAMPLE.exists() else ""
    parsed = gold.parse_gold(text) if text else []
    gset = gold.augmented_gold(text, target=50) if text else []
    augmented = len(gset) - len(parsed)
    leaks = examiner.find_leaks(
        gold.training_texts(), [g.prompt for g in gset], threshold=0.8
    )
    print("== Gold set (grading references, spec §7f) ==")
    print(f"  parsed from official sample questions : {len(parsed)}")
    print(f"  augmented from authored bank (labelled): {augmented}")
    print(f"  total gold Q&A                         : {len(gset)}  (need >= 50)")
    print(
        f"  leakage into study content             : {'CLEAN' if not leaks else f'{len(leaks)} LEAK(S)'}"
    )
    ok = len(gset) >= 50 and not leaks
    return ok, gset


def _card_section(n: int) -> tuple[bool, card_check.CardCheckReport | None]:
    if not _BANK.exists():
        print(f"\ngenerated bank not found at {_BANK}", file=sys.stderr)
        return False, None
    corpus = _CORPUS.read_text(encoding="utf-8") if _CORPUS.exists() else ""
    cards = card_check.parse_generated_bank(_BANK.read_text(encoding="utf-8"), limit=n)
    report = card_check.classify(cards, corpus)

    print(f"\n== Card check: {report.total} cards from one real source ==")
    print(f"  source: {_BANK.relative_to(_ROOT)}")
    if not corpus:
        print("  NOTE: corpus absent — verbatim-citation check skipped.")
    print(
        "  Pre-set cutoff (stated before results): "
        f"wrong <= {report.wrong_cutoff}, "
        f"bad-teaching ratio <= {report.bad_teaching_ratio_cutoff:.0%}"
    )
    print(f"  1. correct AND useful          : {report.correct_useful}")
    print(f"  2. wrong (a wrong fact — worst): {report.wrong}")
    print(f"  3. correct but bad teaching    : {report.bad_teaching}")
    print(f"  bad-teaching ratio             : {report.bad_teaching_ratio:.0%}")
    _print_examples(report)
    print(f"  VERDICT: {'PASS' if report.ok else 'FAIL (batch blocked)'}")
    return report.ok, report


def _print_examples(report: card_check.CardCheckReport) -> None:
    """A few example reasons per non-correct bucket, for transparency."""
    for bucket, label in (
        (Bucket.WRONG, "wrong"),
        (Bucket.BAD_TEACHING, "bad-teaching"),
    ):
        examples = [v for v in report.verdicts if v.bucket is bucket][:3]
        for v in examples:
            q = (
                (v.card.question[:70] + "…")
                if len(v.card.question) > 70
                else v.card.question
            )
            print(f"    [{label}] {v.reason}: {q}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=50, help="cards to classify (default 50)")
    args = ap.parse_args()

    gold_ok, _ = _gold_section()
    card_ok, _ = _card_section(args.n)
    return 0 if (gold_ok and card_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
