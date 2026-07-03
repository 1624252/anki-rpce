#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Gold-set evaluation of the examiner (spec §7e, §7f, §9, Friday "Desktop (AI)").

Loads the **official RPCE sample questions**
(``data/RPCE-Sample-Questions-v4-100625.md``) and, BEFORE any student sees a
grade, measures each grader against a pre-set cutoff:

- accuracy on known-correct answers,
- false-pass rate on distractors (a wrong "pass" is the dangerous error),
- a clean leakage scan (test items must not appear in our study content).

It runs a **side-by-side**: the online AI examiner (when a key is configured)
vs. two simpler methods — a rubric grader and plain keyword overlap — to show
the AI beats the simpler baseline (Friday deliverable). The baselines are
deterministic and offline, so they re-run identically; the AI row needs a key.

    PYTHONPATH=out/pylib python pylib/tools/rpce_gold_eval.py [--ai-sample N]
"""

from __future__ import annotations

import sys
from pathlib import Path

from anki.rpce import ai, examiner, gold

DATA = Path("data/RPCE-Sample-Questions-v4-100625.md")


def _row(name: str, ev: gold.GoldEval) -> str:
    acc = f"{ev.accuracy:5.0%}"
    fp = f"{ev.false_pass_rate:5.0%}"
    ok = ev.accuracy >= ev.accuracy_cutoff and ev.false_pass_rate <= ev.false_pass_cutoff
    return f"  {name:22s} accuracy {acc}   false-pass {fp}   {'PASS' if ok else 'FAIL'}"


def main() -> int:
    if not DATA.exists():
        print(f"gold data not found at {DATA}", file=sys.stderr)
        return 2
    text = DATA.read_text(encoding="utf-8")

    # Deterministic, offline baselines (always run; the 'simpler method').
    graders = [
        ("Rubric (offline)", examiner.KeywordExaminer()),
        ("Keyword overlap", examiner.BaselineExaminer()),
    ]
    ai_on = ai.ai_configured() and ai.ai_enabled()
    if ai_on:
        # AutoExaminer uses the LLM (with offline fallback on any error).
        graders.insert(0, ("AI examiner (online)", examiner.make_examiner()))

    evs = [(name, gold.evaluate_gold(text, grader)) for name, grader in graders]
    best = evs[0][1]  # AI when configured, else the rubric baseline

    print(f"Gold set: {best.total} questions across {best.domains} domains")
    print(f"Pre-set cutoffs: accuracy >= {best.accuracy_cutoff:.0%}, "
          f"false-pass <= {best.false_pass_cutoff:.0%}")
    print("Side-by-side (AI vs simpler methods):")
    for name, ev in evs:
        print(_row(name, ev))
    print(f"Leakage scan (test items in study content): "
          f"{'CLEAN' if best.leaks == 0 else f'{best.leaks} LEAK(S)'}")
    if not ai_on:
        print("Note: no AI proxy configured — showing the offline baselines "
              "only. Set RPCE_AI_PROXY_URL (or ~/.rpce/ai_proxy_url) for the "
              "AI row.")
    # Gate: leakage clean AND the best grader clears the accuracy cutoff.
    ok = best.leaks == 0 and best.accuracy >= best.accuracy_cutoff
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
