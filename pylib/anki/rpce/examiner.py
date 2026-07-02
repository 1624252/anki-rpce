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

import json
import os
import re
from collections.abc import Callable
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


# Discriminative RONR phrases collapsed to single keyword tokens *before*
# tokenizing. This keeps the offline grader robust: negation and threshold
# phrases survive (they'd otherwise lose "no"/"not" to the stopword list and
# split on the hyphen), so "no second" no longer matches a positive "second",
# and "two-thirds" / "no debate" score as one positive keyword each (§12).
_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\btwo[\s-]thirds\b"), " twothirds "),
    (re.compile(r"\bno second\b|\bwithout a second\b|\bno seconder\b"), " nosecond "),
    (
        re.compile(r"\bnot debatable\b|\bno debate\b|\bundebatable\b|\bcannot be debated\b"),
        " nodebate ",
    ),
    (re.compile(r"\bno vote\b|\bwithout a vote\b"), " novote "),
)


def _normalize(text: str) -> str:
    """Collapse discriminative phrases so polarity/thresholds survive tokenizing."""
    t = text.lower()
    for pat, repl in _PHRASES:
        t = pat.sub(repl, t)
    return t


def _tokens(text: str) -> set[str]:
    """Content keywords: length ≥ 3, not stopwords, with RONR phrases collapsed
    to positive keyword tokens (``twothirds``/``nodebate``/``nosecond``)."""
    return {
        w for w in _WORD_RE.findall(_normalize(text)) if len(w) >= 3 and w not in _STOPWORDS
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


class PlaceholderExaminer(Examiner):
    """The active grader until real AI is enabled — **no network calls**.

    Grades accuracy deterministically (via the baseline) and adds a simulation
    debrief, clearly labelled as a placeholder. Swap in `LLMExaminer` later
    without changing callers.
    """

    def __init__(self, pass_score: float = 3.0) -> None:
        self.pass_score = pass_score

    def grade(self, answer: str, gold_answer: str, corpus: str) -> GradeResult:
        base = BaselineExaminer(self.pass_score).grade(answer, gold_answer, corpus)
        if base.abstained:
            return base
        debrief = (
            f"{base.feedback} Debrief: compare your ruling to the model below. "
            "(Placeholder examiner — AI grading is not enabled yet.)"
        )
        return GradeResult(
            base.score, base.passed, debrief, base.citation, abstained=False
        )


def build_grading_prompt(answer: str, gold_answer: str, context: str) -> str:
    """Construct the examiner prompt: grade for accuracy against the rubric,
    grounded in the supplied RONR context; the candidate need not cite."""
    return (
        "You are a strict RPCE Section II examiner. Grade the candidate's answer "
        "for ACCURACY and reasoning against the model ruling, using only the RONR "
        "context provided. The candidate is NOT required to cite sources. Do not "
        "introduce facts absent from the context. Respond as JSON: "
        '{"score": <0-5 number>, "feedback": "<one or two sentences>"}.\n\n'
        f"RONR context:\n{context}\n\n"
        f"Model ruling:\n{gold_answer}\n\n"
        f"Candidate answer:\n{answer}\n"
    )


def _parse_llm_json(raw: str) -> dict:
    """Extract the first JSON object from an LLM response, leniently."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in model output")
    return json.loads(match.group(0))


class LLMExaminer(Examiner):
    """LLM-backed grader. Network access is injected as `call_fn(prompt)->str`
    so it is testable offline; grading is grounded in retrieved RONR passages
    and abstains when none are found (never invents)."""

    def __init__(self, call_fn: Callable[[str], str], pass_score: float = 3.0) -> None:
        self.call_fn = call_fn
        self.pass_score = pass_score

    def grade(self, answer: str, gold_answer: str, corpus: str) -> GradeResult:
        passages = retrieve(corpus, gold_answer, k=3)
        if not passages:
            return GradeResult(
                0.0, False, "No supporting RONR passage found.", None, abstained=True
            )
        context = "\n\n".join(p.text for p in passages)
        try:
            data = _parse_llm_json(
                self.call_fn(build_grading_prompt(answer, gold_answer, context))
            )
            score = max(0.0, min(5.0, float(data["score"])))
            feedback = str(data.get("feedback", "")).strip() or "(no feedback)"
        except (ValueError, KeyError, TypeError) as exc:
            # Malformed/unavailable model output -> abstain rather than guess.
            return GradeResult(
                0.0, False, f"Examiner unavailable: {exc}", None, abstained=True
            )
        return GradeResult(
            score,
            score >= self.pass_score,
            feedback,
            passages[0].citation,
            abstained=False,
        )


def make_examiner(call_fn: Callable[[str], str] | None = None) -> Examiner:
    """Return an LLM examiner when a grader is available, else the offline
    baseline. `call_fn` (or an env API key) opts into the LLM; with neither, the
    app still grades via :class:`BaselineExaminer` (AI-off)."""
    if call_fn is not None:
        return LLMExaminer(call_fn)
    if os.environ.get("RPCE_AI_KEY") or os.environ.get("OPENAI_API_KEY"):
        return LLMExaminer(_default_llm_call)
    return BaselineExaminer()


def _default_llm_call(prompt: str) -> str:  # pragma: no cover - requires network + key
    """Minimal OpenAI-compatible chat call using only the stdlib. Reads
    RPCE_AI_KEY/OPENAI_API_KEY, optional RPCE_AI_BASE_URL and RPCE_AI_MODEL.
    Only invoked when a key is configured; never exercised in tests."""
    import urllib.request

    key = os.environ.get("RPCE_AI_KEY") or os.environ["OPENAI_API_KEY"]
    base = os.environ.get("RPCE_AI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("RPCE_AI_MODEL", "gpt-4o-mini")
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


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
