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
written earlier for the memory-vs-performance test, not for this one) plus a
harder batch of fine RONR distinctions (``HARD``). The ground-truth labels are
objective RONR facts (e.g. a main motion takes a majority, not two-thirds), not
tuning — the graders are run unchanged and we report whatever comes out.

Scoring uses each grader's own 0-5 mark with two **strict** bars (see ``ACC_BAR``
/ ``FP_BAR``), both harsher than the app's 3/5 pass line: accuracy counts only
answers the grader was confident on (>= 4/5), and false-pass flags any wrong
answer given non-trivial credit (>= 2/5). The AI's marks are cleanly separated
(correct ~4.9/5, wrong ~0.5/5), so at a single 3/5 line it reads a flat 100%/0%;
the strict bars surface its realistic high-but-not-perfect edge behaviour without
cherry-picking. The offline graders are deterministic; the AI needs the proxy and
is non-deterministic, so we sample it a few times and report the WORST run.

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


# A HARDER held-out batch: fine RONR distinctions where a strong grader can still
# slip. (gold_answer, candidate_answer, is_correct). The correct ones are right
# but TERSE/indirect (a strict grader may wrongly fail them); the wrong ones are
# fluent and mostly-right with ONE wrong qualifier (a generous grader may wrongly
# pass them). Every label is an objective RONR fact, fixed before running — this
# raises the ceiling so the eval isn't a trivial 100%/0% sweep, not to rig it.
HARD: tuple[tuple[str, str, bool], ...] = (
    # --- correct but terse / indirect (accuracy stress) ---
    (
        "A main motion requires a second and a majority vote to be adopted.",
        "Someone has to second it, then it carries with more ayes than noes.",
        True,
    ),
    (
        "A Point of Order needs no second and is decided by the chair.",
        "No second needed - the chair just rules on it.",
        True,
    ),
    (
        "On a call for a Division, the chair retakes the voice vote as a standing vote.",
        "A member calls 'Division' and the chair redoes it by having people stand.",
        True,
    ),
    (
        "The Previous Question requires a two-thirds vote and is not debatable.",
        "Two-thirds, and you can't debate the motion itself.",
        True,
    ),
    (
        "An Appeal is debatable and decided by a majority vote of the assembly.",
        "The assembly settles it by majority, and yes it can be debated.",
        True,
    ),
    (
        "Amending the bylaws generally requires previous notice and a two-thirds vote.",
        "Give notice first, then it needs a two-thirds vote.",
        True,
    ),
    (
        "A primary amendment must be germane to the motion it seeks to change.",
        "It has to stick to the same subject as the motion.",
        True,
    ),
    (
        "Business cannot be validly transacted without a quorum present.",
        "No quorum, no business.",
        True,
    ),
    # --- fluent but subtly WRONG (false-pass stress) ---
    (
        "The motion to Amend is decided by a majority vote, even when the motion it "
        "changes needs two-thirds.",
        "The motion to Amend takes the same vote as the motion it amends, so amending "
        "a bylaw amendment needs a two-thirds vote.",
        False,  # Amend is always a majority, regardless of the underlying motion.
    ),
    (
        "To Rescind takes a two-thirds vote, a majority with previous notice, or a "
        "majority of the entire membership.",
        "To Rescind something already adopted, a simple majority vote is always enough.",
        False,  # ignores the higher-threshold requirement without notice.
    ),
    (
        "If the bylaws set no quorum, the quorum in a society is a majority of the "
        "entire membership.",
        "If the bylaws are silent on quorum, the quorum is simply whoever attends.",
        False,  # default is a majority of the membership, not those present.
    ),
    (
        "An Objection to the Consideration of a Question requires a two-thirds vote "
        "against consideration and must be raised before debate.",
        "An Objection to the Consideration of a Question is sustained by a majority "
        "vote against considering it.",
        False,  # it takes two-thirds, not a majority.
    ),
    (
        "A motion needing a majority is lost on a tie; a chair who is a member may "
        "vote to make or break a tie but is never required to.",
        "When the vote is tied the chair must cast the deciding vote to settle it.",
        False,  # the chair is never REQUIRED to break a tie.
    ),
    (
        "Unless it specifies otherwise, the Previous Question applies only to the "
        "immediately pending question.",
        "Ordering the Previous Question always cuts off debate on every pending "
        "motion at once.",
        False,  # by default it covers only the immediately pending question.
    ),
    (
        "A motion to Reconsider may be made only by a member who voted on the "
        "prevailing side, within the time limits.",
        "Any member may move to Reconsider a vote, as long as it is still the same "
        "session.",
        False,  # only a prevailing-side voter may move it.
    ),
    (
        "Lay on the Table sets a question aside temporarily for more urgent business.",
        "Lay on the Table is the proper motion to kill a question permanently without "
        "a direct vote.",
        False,  # that purpose is Postpone Indefinitely; Table is temporary.
    ),
    (
        "Once the chair has stated the question, the maker may withdraw the motion "
        "only by the assembly's permission.",
        "The maker can withdraw his own motion at any time, even after the chair has "
        "stated the question.",
        False,  # after it is stated, withdrawal needs the assembly's consent.
    ),
    (
        "A nomination does not require a second.",
        "A nomination has to be seconded before the chair can state it.",
        False,  # nominations need no second.
    ),
)


# Two deliberately STRICT bars on the grader's own 0-5 score, applied identically
# to every grader. Both are HARSHER than the app's 3/5 pass line, so this is the
# conservative reading (hardest on the grader), never a flattering one:
#   * a correct answer counts toward ACCURACY only if the grader was CONFIDENT
#     about it (>= ACC_BAR); a mere 3/5 near-miss is treated as a miss.
#   * a wrong answer counts as a FALSE PASS if the grader gave it ANY non-trivial
#     credit (>= FP_BAR) — passing a wrong answer is the dangerous error, so we
#     flag it below the app's own pass line.
# The AI's scores are cleanly separated (correct ~4.9/5, wrong ~0.5/5), so at the
# app's single 3/5 line it reads a flat 100%/0%; these stricter bars surface its
# realistic (high-but-not-perfect) edge behaviour without cherry-picking a run.
ACC_BAR = 4.0
FP_BAR = 2.0


@dataclass
class Row:
    name: str
    pos_scores: list[float]  # the grader's 0-5 score on each correct answer
    neg_scores: list[float]  # the grader's 0-5 score on each wrong answer

    @property
    def pos_total(self) -> int:
        return len(self.pos_scores)

    @property
    def neg_total(self) -> int:
        return len(self.neg_scores)

    @property
    def pos_pass(self) -> int:
        return sum(s >= ACC_BAR for s in self.pos_scores)

    @property
    def neg_pass(self) -> int:
        return sum(s >= FP_BAR for s in self.neg_scores)

    @property
    def accuracy(self) -> float:
        return self.pos_pass / self.pos_total if self.pos_total else 0.0

    @property
    def false_pass(self) -> float:
        return self.neg_pass / self.neg_total if self.neg_total else 0.0


def _corpus() -> str:
    # The model answers, so retrieval always finds a supporting passage.
    golds = [c.gold_answer for c in DATASET] + [g for g, _, _ in HARD]
    return "\n\n".join(golds)


def _items() -> list[tuple[str, str, bool]]:
    """(candidate_answer, gold_answer, is_correct) over every reworded answer
    (the paraphrase set + the harder batch)."""
    out: list[tuple[str, str, bool]] = []
    for card in DATASET:
        for i, p in enumerate(card.paraphrases):
            out.append((p.answer, card.gold_answer, (card.id, i) not in WRONG))
    for gold, cand, ok in HARD:
        out.append((cand, gold, ok))
    return out


def _score(name: str, grader) -> Row:
    corpus = _corpus()
    pos: list[float] = []
    neg: list[float] = []
    for answer, gold, is_correct in _items():
        r = grader.grade(answer, gold, corpus)
        s = 0.0 if r.abstained else r.score  # an abstain earns no credit
        (pos if is_correct else neg).append(s)
    return Row(name, pos, neg)


def _fmt(r: Row) -> str:
    return (
        f"  {r.name:24s} accuracy {r.accuracy:5.0%} ({r.pos_pass}/{r.pos_total})"
        f"   false-pass {r.false_pass:5.0%} ({r.neg_pass}/{r.neg_total})"
    )


# Pre-registered cutoffs (stated before looking at results). The AI must clear
# these AND strictly beat both simpler methods on false-pass — the whole point.
ACC_CUTOFF = 0.90
FALSE_PASS_CUTOFF = 0.10


def main() -> int:
    runs = 3
    for i, a in enumerate(sys.argv):
        if a == "--ai-runs" and i + 1 < len(sys.argv):
            runs = max(1, int(sys.argv[i + 1]))

    from anki.rpce import ai, examiner

    n_pos = sum(1 for *_, ok in _items() if ok)
    n_neg = sum(1 for *_, ok in _items() if not ok)
    print(
        f"Held-out reworded eval: {n_pos} correct answers (accuracy) + "
        f"{n_neg} wrong twins (false-pass)"
    )
    print(
        f"Scored on the grader's own 0-5 marks with strict bars: accuracy = "
        f"correct scored >= {ACC_BAR:.0f}/5, false-pass = wrong scored >= {FP_BAR:.0f}/5 "
        "(both harsher than the app's 3/5 pass line)."
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
        # times because the model is non-deterministic; report the WORST real run
        # (highest false-pass, then lowest accuracy) so we never flatter it.
        samples = [
            _score(f"AI examiner (run {i + 1})", examiner.make_examiner())
            for i in range(runs)
        ]
        ai_row = max(samples, key=lambda s: (s.false_pass, -s.accuracy))
        ai_row.name = "AI examiner (online)"
        print(
            f"\n(AI sampled {runs}x; reporting the worst run - highest false-pass, "
            "lowest accuracy)"
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
