#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Gold-set evaluation of the AI examiner (spec §7e, §7f, §9).

Loads the **official RPCE sample questions** (``data/RPCE-Sample-Questions-v4-100625.md``)
and reports accuracy on known-correct answers, false-pass rate on distractors,
and a clean leakage scan — with a cutoff chosen before looking. Logic lives in
``anki.rpce.gold`` (so it is unit-tested); this is a thin CLI wrapper.

    PYTHONPATH=out/pylib python pylib/tools/rpce_gold_eval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from anki.rpce import gold

DATA = Path("data/RPCE-Sample-Questions-v4-100625.md")


def main() -> int:
    if not DATA.exists():
        print(f"gold data not found at {DATA}", file=sys.stderr)
        return 2
    ev = gold.evaluate_gold(DATA.read_text(encoding="utf-8"))
    print(f"Gold set: {ev.total} questions across {ev.domains} domains")
    print(f"  cutoff (pre-set): accuracy >= {ev.accuracy_cutoff:.0%}")
    print(
        f"  accuracy on known-correct: {ev.accuracy:.0%} -> "
        f"{'PASS' if ev.accuracy >= ev.accuracy_cutoff else 'FAIL'}"
    )
    print(
        f"  false-pass on distractors: {ev.false_pass_rate:.0%} -> "
        f"{'PASS' if ev.false_pass_rate <= ev.false_pass_cutoff else 'FAIL'}"
    )
    print(f"  leakage scan: {'CLEAN' if ev.leaks == 0 else f'{ev.leaks} LEAK(S)'}")
    print("GOLD EVAL OK" if ev.ok else "GOLD EVAL: review needed")
    return 0 if ev.ok else 1


if __name__ == "__main__":
    sys.exit(main())
