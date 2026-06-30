# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""AI Examiner for Section II — grading, grounding, baseline, eval, leakage.

Embodies Spiky POV 3 (the AI is an *examiner*, not a tutor): it grades a
free-text answer **for accuracy** against a rubric and grounds its feedback in
the transcribed RONR 12th-ed. corpus, citing it or abstaining (anti-NAPMobile).
The candidate is never required to cite.

This module is deliberately **LLM-agnostic and offline-capable** (spec: the app
must score with AI off):

- :class:`BaselineExaminer` uses keyword retrieval only — no network — and is
  both the **AI-off fallback** and the **baseline the LLM must beat** (spec §7f).
- :class:`Examiner` is the interface an LLM-backed grader implements; with no
  API key configured the app uses the baseline.
- :func:`find_leaks` and :func:`evaluate` implement the leakage check (§7e) and
  the held-out gold-set eval with a pre-set cutoff (§7f).

Retrieval works over any corpus text, so tests use a small inline corpus; in the
app the corpus is `data/roberts_rules_of_order_12th_edition.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# RONR paragraph citations look like "12:70", "12:70-71", or "16:1-16:5".
_CITATION_RE = re.compile(r"\b\d{1,2}:\d{1,3}(?:-\d{1,2}:\d{1,3}|-\d{1,3})?\b")
_WORD_RE = re.compile(r"[a-z0-9]+")

# Common words that should not drive grounding/grading overlap.
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "not",
    "are",
    "was",
    "its",
    "has",
    "had",
    "about",
    "here",
    "from",
    "this",
    "that",
    "into",
    "out",
    "any",
    "all",
    "you",
    "your",
    "but",
    "can",
    "may",
    "will",
    "shall",
    "must",
    "have",
    "which",
    "when",
    "what",
    "who",
    "how",
    "why",
    "where",
    "a",
    "an",
    "in",
    "of",
    "to",
    "is",
    "it",
    "on",
    "or",
    "no",
    "be",
    "by",
    "as",
    "at",
}


def _tokens(text: str) -> set[str]:
    """Content tokens: lowercased words of length ≥ 3 that aren't stopwords."""
    return {
        w for w in _WORD_RE.findall(text.lower()) if len(w) >= 3 and w not in _STOPWORDS
    }


@dataclass
class Passage:
    text: str
    citation: str | None
    score: float


def retrieve(corpus: str, query: str, k: int = 1) -> list[Passage]:
    """Return the top-k corpus paragraphs by keyword overlap with `query`.

    Each passage carries an RONR citation parsed from its text when present.
    This is the grounding step; an empty result means the examiner must abstain.
    """
    q = _tokens(query)
    if not q:
        return []
    passages: list[Passage] = []
    for para in (p.strip() for p in corpus.split("\n\n")):
        if not para:
            continue
        overlap = len(q & _tokens(para))
        if overlap == 0:
            continue
        match = _CITATION_RE.search(para)
        passages.append(
            Passage(
                text=para, citation=match.group(0) if match else None, score=overlap
            )
        )
    passages.sort(key=lambda p: p.score, reverse=True)
    return passages[:k]


@dataclass
class GradeResult:
    """An examiner verdict on a Section II answer."""

    score: float  # 0..5 rubric score
    passed: bool  # score >= pass threshold
    feedback: str
    citation: str | None  # RONR citation supplied by the examiner (not the candidate)
    abstained: bool


class Examiner:
    """Interface for a Section II grader (baseline or LLM-backed)."""

    def grade(self, answer: str, gold_answer: str, corpus: str) -> GradeResult:
        raise NotImplementedError


class BaselineExaminer(Examiner):
    """Offline keyword-overlap grader. No network: the AI-off fallback and the
    baseline the LLM must beat. Grades accuracy as overlap with the rubric."""

    def __init__(self, pass_score: float = 3.0) -> None:
        self.pass_score = pass_score

    def grade(self, answer: str, gold_answer: str, corpus: str) -> GradeResult:
        gold = _tokens(gold_answer)
        if not gold:
            return GradeResult(
                0.0, False, "No rubric to grade against.", None, abstained=True
            )
        overlap = len(_tokens(answer) & gold) / len(gold)
        score = round(5.0 * overlap, 2)
        passages = retrieve(corpus, gold_answer, k=1)
        if not passages:
            # No supporting passage found -> abstain rather than invent.
            return GradeResult(
                score, False, "No supporting RONR passage found.", None, abstained=True
            )
        citation = passages[0].citation
        passed = score >= self.pass_score
        verdict = "matches" if passed else "misses key points from"
        feedback = f"Your answer {verdict} the model ruling."
        return GradeResult(score, passed, feedback, citation, abstained=False)


@dataclass
class GoldItem:
    prompt: str
    gold_answer: str
    # A representative *correct* candidate answer, used to measure that a good
    # answer is graded as passing.
    correct_answer: str


@dataclass
class EvalResult:
    total: int
    correct: int
    wrong: int
    accuracy: float
    wrong_rate: float
    passed_cutoff: bool


def evaluate(
    examiner: Examiner,
    gold_set: list[GoldItem],
    corpus: str,
    *,
    accuracy_cutoff: float,
) -> EvalResult:
    """Grade known-correct answers and report accuracy vs a pre-set cutoff.

    A "correct" eval outcome means the examiner *passed* a known-good answer.
    The cutoff must be chosen before looking at results (spec §7f).
    """
    total = len(gold_set)
    correct = 0
    for item in gold_set:
        result = examiner.grade(item.correct_answer, item.gold_answer, corpus)
        if result.passed and not result.abstained:
            correct += 1
    wrong = total - correct
    accuracy = correct / total if total else 0.0
    return EvalResult(
        total=total,
        correct=correct,
        wrong=wrong,
        accuracy=accuracy,
        wrong_rate=(wrong / total if total else 0.0),
        passed_cutoff=accuracy >= accuracy_cutoff,
    )


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_leaks(
    train_texts: list[str], test_texts: list[str], *, threshold: float = 0.8
) -> list[tuple[int, int, float]]:
    """Flag train/test pairs that are near-duplicates (token Jaccard ≥ threshold).

    A clean run returns an empty list; any hit means a held-out/gold item (or a
    near-copy) leaked into training and that score is void (spec §7e).
    """
    leaks: list[tuple[int, int, float]] = []
    for i, train in enumerate(train_texts):
        for j, test in enumerate(test_texts):
            sim = jaccard(train, test)
            if sim >= threshold:
                leaks.append((i, j, sim))
    return leaks
