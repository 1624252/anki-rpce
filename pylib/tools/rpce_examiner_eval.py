#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Held-out examiner eval: does the AI grader beat the simpler methods on
answers that are *reworded*, not verbatim?

The gold-MCQ eval (``rpce_gold_eval.py``) grades the exact keyed answer text, so
every grader trivially passes and accuracy pins at 100% — it can't separate a
grader that understands from one that string-matches. This eval fixes that by
grading **paraphrased** answers, where surface overlap no longer gives the
answer away:

- **Positives** — a correct answer stated in NEW words. A keyword grader loses
  the lexical overlap and starts failing good answers, so accuracy drops below
  100% and spreads the graders apart.
- **Hard negatives** — a plausible, fluent, but factually WRONG answer (a wrong
  vote threshold, a reversed rule). Passing one is a *false pass* — the dangerous
  error — and it's where understanding beats matching.

The items come from the authored §7d paraphrase set (``rpce_paraphrase.DATASET``,
written earlier for the memory-vs-performance test, not for this one). The
ground-truth WRONG labels below are objective RONR facts (e.g. a main motion
takes a majority, not two-thirds), not tuning — the graders are run unchanged and
we report whatever comes out. The offline graders are deterministic; the AI row
needs the proxy and is non-deterministic (temperature 0, but the model may still
vary), so we sample it a few times and report the range.

    PYTHONPATH=out/pylib python pylib/tools/rpce_examiner_eval.py [--ai-runs N]
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# Same-dir import: the authored paraphrase dataset lives in the sibling tool.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpce_paraphrase import DATASET  # noqa: E402

# Ground-truth WRONG reworded answers, as (card_id, paraphrase_index). Each is
# wrong by an objective RONR rule; everything else in DATASET is a correct
# paraphrase. Kept here as an explicit answer key so it is auditable in one place
# and never derived from a grader's own verdict (which would be circular).
WRONG: dict[tuple[str, int], str] = {
    ("d1-main-adopt", 1): "main motion is a majority, not two-thirds",
    ("d1-ratify", 1): "improper action does need Ratify, not nothing",
    ("d1-postpone-carries", 1): "pending subsidiary motions DO go with a postponement",
    ("d2-previous-question", 1): "Previous Question is two-thirds and not debatable",
    ("d2-amend-germane", 1): "an amendment must be germane",
    ("d2-suspend-rules", 1): "Suspend the Rules is two-thirds, not majority",
    ("d3-point-of-order", 1): "a Point of Order is not debatable and needs no second",
    ("d3-appeal", 1): "an Appeal is debatable and decided by the assembly",
    ("d3-reconsider-timing", 1): "only the prevailing side, within time limits",
    ("d3-point-of-order-minutes", 1): "the ruling IS entered in the minutes",
    ("d4-quorum-in-bylaws", 1): "members set the quorum; RONR does not fix it",
    ("d4-unanimous-consent", 1): "no objection is not proof every member agrees",
    (
        "d4-previous-question-recognized",
        1,
    ): "the chair cannot order the Previous Question",
    ("d5-majority-elect", 1): "election needs a majority, not a plurality",
    ("d5-division", 1): "a Division forces a standing vote, not a re-listen",
    ("d5-majority-of-votes-cast", 1): "abstentions are not counted as votes",
    ("d5-change-ballot", 1): "a deposited secret ballot cannot be changed",
    ("d6-regular-meeting-notice", 1): "bylaws-fixed dates need no separate notice",
    ("d6-scope-of-notice", 1): "an amendment may not exceed the scope of notice",
    ("d7-board-small-rules", 1): "small-board motions need no second",
    (
        "d7-ex-officio-quorum",
        1,
    ): "an outside ex-officio member is not counted in quorum",
    ("d7-bylaws-amendment", 1): "amending bylaws needs notice and two-thirds",
}


@dataclass
class Row:
    name: str
    pos_total: int
    pos_pass: int  # correct paraphrases passed (accuracy numerator)
    neg_total: int
    neg_pass: int  # wrong paraphrases wrongly passed (false-pass numerator)

    @property
    def accuracy(self) -> float:
        return self.pos_pass / self.pos_total if self.pos_total else 0.0

    @property
    def false_pass(self) -> float:
        return self.neg_pass / self.neg_total if self.neg_total else 0.0


def _corpus() -> str:
    # The model answers, so retrieval always finds a supporting passage.
    return "\n\n".join(c.gold_answer for c in DATASET)


def _items() -> list[tuple[str, str, bool]]:
    """(candidate_answer, gold_answer, is_correct) over every reworded answer."""
    out: list[tuple[str, str, bool]] = []
    for card in DATASET:
        for i, p in enumerate(card.paraphrases):
            out.append((p.answer, card.gold_answer, (card.id, i) not in WRONG))
    return out


def _score(name: str, grader) -> Row:
    corpus = _corpus()
    pos_t = pos_p = neg_t = neg_p = 0
    for answer, gold, is_correct in _items():
        r = grader.grade(answer, gold, corpus)
        passed = bool(r.passed and not r.abstained)
        if is_correct:
            pos_t += 1
            pos_p += passed
        else:
            neg_t += 1
            neg_p += passed
    return Row(name, pos_t, pos_p, neg_t, neg_p)


def _fmt(r: Row) -> str:
    return (
        f"  {r.name:24s} accuracy {r.accuracy:5.0%} ({r.pos_pass}/{r.pos_total})"
        f"   false-pass {r.false_pass:5.0%} ({r.neg_pass}/{r.neg_total})"
    )


# Pre-registered cutoffs (stated before looking at results). The AI must clear
# these AND strictly beat both simpler methods on false-pass — the whole point.
ACC_CUTOFF = 0.80
FALSE_PASS_CUTOFF = 0.20


def main() -> int:
    runs = 3
    for i, a in enumerate(sys.argv):
        if a == "--ai-runs" and i + 1 < len(sys.argv):
            runs = max(1, int(sys.argv[i + 1]))

    from anki.rpce import ai, examiner

    n_pos = sum(1 for *_, ok in _items() if ok)
    n_neg = sum(1 for *_, ok in _items() if not ok)
    print(
        f"Held-out reworded eval: {n_pos} correct paraphrases (accuracy) + "
        f"{n_neg} wrong twins (false-pass)"
    )
    print(
        f"Pre-set cutoffs: accuracy >= {ACC_CUTOFF:.0%}, "
        f"false-pass <= {FALSE_PASS_CUTOFF:.0%}; AI must also beat both baselines "
        "on false-pass."
    )

    # Deterministic offline baselines (the 'simpler methods').
    rubric = _score("Rubric (offline)", examiner.KeywordExaminer())
    keyword = _score("Keyword overlap", examiner.BaselineExaminer())

    ai_row: Row | None = None
    if ai.ai_configured() and ai.ai_enabled():
        # AutoExaminer uses the LLM (offline fallback on any error). Sample a few
        # times because the model is non-deterministic; report the worst (highest
        # false-pass, lowest accuracy) so we never flatter it.
        samples = [
            _score(f"AI examiner (run {i + 1})", examiner.make_examiner())
            for i in range(runs)
        ]
        worst_acc = min(s.accuracy for s in samples)
        worst_fp = max(s.false_pass for s in samples)
        ai_row = Row(
            "AI examiner (online)",
            samples[0].pos_total,
            round(worst_acc * samples[0].pos_total),
            samples[0].neg_total,
            round(worst_fp * samples[0].neg_total),
        )
        print(
            f"\n(AI sampled {runs}x; reporting the worst run - lowest acc, highest false-pass)"
        )

    print("\nSide-by-side (AI vs simpler methods):")
    if ai_row:
        print(_fmt(ai_row))
    print(_fmt(rubric))
    print(_fmt(keyword))

    if not ai_row:
        print(
            "\nNote: no AI proxy configured — offline baselines only. Set "
            "RPCE_AI_PROXY_URL (or ~/.rpce/ai_proxy_url) for the AI row."
        )
        return 0

    beats = (
        ai_row.false_pass < rubric.false_pass and ai_row.false_pass < keyword.false_pass
    )
    clears = ai_row.accuracy >= ACC_CUTOFF and ai_row.false_pass <= FALSE_PASS_CUTOFF
    print()
    if beats and clears:
        print(
            f"PASS: the AI examiner clears the cutoffs AND has a lower false-pass "
            f"than both the rubric ({rubric.false_pass:.0%}) and keyword overlap "
            f"({keyword.false_pass:.0%}) - understanding beats string-matching."
        )
        return 0
    print(
        "FAIL: the AI examiner did not clear the cutoffs and beat both baselines "
        "on false-pass."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
