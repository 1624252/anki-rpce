# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Gold-set evaluation of the AI examiner from the official sample questions.

Parses the RPCE sample-question markdown (multiple-choice items + answer keys)
into a gold set, then measures the examiner (spec §7e, §7f, §9):

- **accuracy** — passes the known-correct answers,
- **false-pass rate** — how often it wrongly passes a distractor (discrimination),
- **leakage** — no gold prompt is a near-copy of our study content.

Pure + deterministic (offline examiner), so the numbers re-run identically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import examiner, flashcards, gold_rubrics, scenarios, simulations

_Q_SPLIT = re.compile(r"\*\*(\d+)\.\*\*")
_OPTION = re.compile(r"^\s*([A-D])\.\s+(.*\S)\s*$", re.M)
_ANSWER = re.compile(r"(\d+)\.\s*The correct answer is ([A-D])")
_DOMAIN = re.compile(r"^### (Domain \d[^\n]*)$", re.M)


@dataclass
class GoldQ:
    domain: str
    prompt: str
    correct: str
    distractors: list[str] = field(default_factory=list)


def parse_gold(text: str) -> list[GoldQ]:
    """Extract multiple-choice gold questions (+ the keyed correct answer)."""
    gold: list[GoldQ] = []
    chunks = _DOMAIN.split(text)  # [pre, name1, body1, name2, body2, ...]
    for name, body in zip(chunks[1::2], chunks[2::2]):
        # The answer-key header is sometimes glued to the previous option text,
        # so split on the phrase rather than a leading "**".
        pieces = re.split(r"Answer Key for Practice Questions", body, maxsplit=1)
        q_part = pieces[0]
        a_part = pieces[1] if len(pieces) > 1 else ""
        answers = {int(m.group(1)): m.group(2) for m in _ANSWER.finditer(a_part)}
        blocks = _Q_SPLIT.split(q_part)
        for num_s, block in zip(blocks[1::2], blocks[2::2]):
            num = int(num_s)
            opts = {m.group(1): m.group(2).strip() for m in _OPTION.finditer(block)}
            letter = answers.get(num)
            if not letter or letter not in opts:
                continue
            first_opt = opts[next(iter(opts))]
            prompt = block[: block.find(first_opt)].strip()
            gold.append(
                GoldQ(
                    domain=name.strip(),
                    prompt=prompt or f"{name} Q{num}",
                    correct=opts[letter],
                    distractors=[v for k, v in opts.items() if k != letter],
                )
            )
    return gold


def training_texts() -> list[str]:
    """Our study content — the 'train' side of the leakage scan."""
    texts: list[str] = []
    for f in flashcards.all_flashcards():
        texts += [f.cloze, f.mcq_question, *f.mcq_options]
    for s in scenarios.all_scenarios():
        texts += [s.prompt, s.gold_answer]
    for sim in simulations.all_simulations():
        for t in sim.turns:
            texts.append(t.line)
            if t.gold:
                texts.append(t.gold)
    return texts


@dataclass
class GoldEval:
    total: int
    domains: int
    accuracy: float
    false_pass_rate: float
    leaks: int
    accuracy_cutoff: float
    false_pass_cutoff: float

    @property
    def ok(self) -> bool:
        return (
            self.accuracy >= self.accuracy_cutoff
            and self.false_pass_rate <= self.false_pass_cutoff
            and self.leaks == 0
        )


def evaluate_gold(
    text: str,
    grader: examiner.Examiner | None = None,
    *,
    accuracy_cutoff: float = 0.80,
    false_pass_cutoff: float = 0.20,
    use_authored_rubrics: bool = False,
) -> GoldEval:
    """Run the full gold-set evaluation on parsed sample-question markdown.

    ``use_authored_rubrics`` attaches the hand-authored per-question rubrics
    (:mod:`gold_rubrics`) so the grader is fed the discriminating key points.
    These rubrics are *fitted to the gold set*, so a run with this on measures a
    tuned grader, not a held-out one (see :mod:`gold_rubrics`). Off by default,
    so the AI and overlap baselines stay held-out.
    """
    gold = parse_gold(text)
    if not gold:
        raise ValueError("no gold questions parsed")
    grader = grader or examiner.make_examiner()
    corpus = "\n\n".join(g.correct for g in gold)  # grounding so it won't abstain

    def rubric_for(g: GoldQ) -> examiner.Rubric | None:
        return gold_rubrics.authored_rubric(g.correct) if use_authored_rubrics else None

    items = [
        examiner.GoldItem(
            prompt=g.prompt,
            gold_answer=g.correct,
            correct_answer=g.correct,
            rubric=rubric_for(g),
        )
        for g in gold
    ]
    result = examiner.evaluate(grader, items, corpus, accuracy_cutoff=accuracy_cutoff)

    false_pass = distractors = 0
    for g in gold:
        rubric = rubric_for(g)
        for d in g.distractors:
            distractors += 1
            r = grader.grade(d, g.correct, corpus, rubric)
            if r.passed and not r.abstained:
                false_pass += 1
    false_pass_rate = false_pass / distractors if distractors else 0.0

    leaks = examiner.find_leaks(
        training_texts(), [g.prompt for g in gold], threshold=0.8
    )

    return GoldEval(
        total=len(gold),
        domains=len({g.domain for g in gold}),
        accuracy=result.accuracy,
        false_pass_rate=false_pass_rate,
        leaks=len(leaks),
        accuracy_cutoff=accuracy_cutoff,
        false_pass_cutoff=false_pass_cutoff,
    )
