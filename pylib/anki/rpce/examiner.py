# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""AI Examiner for Section II — grading, grounding, baseline, eval, leakage.

Embodies Spiky POV 3 (the AI is an *examiner*, not a tutor): it grades a
free-text answer **for accuracy** against a rubric and grounds its feedback in
the transcribed RONR 12th-ed. corpus, citing it or abstaining (anti-NAPMobile).
The candidate is never required to cite.

This module is deliberately **LLM-agnostic and offline-capable** (spec: the app
must score with AI off):

- :class:`KeywordExaminer` is the **AI-off fallback**: a deterministic rubric
  grader (alias table + light stemmer + forbidden-term penalty) that scores an
  answer against per-element rubrics — explicit where authored, else derived
  from the gold ruling — so a confidently *wrong* threshold fails even when the
  other words overlap.
- :class:`BaselineExaminer` is the older keyword-overlap grader, kept as the
  **baseline the LLM/rubric grader must beat** (spec §7f).
- :class:`Examiner` is the interface an LLM-backed grader implements; with no
  API key configured the app uses :class:`KeywordExaminer`.
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


# --- Rubric grading: alias table + stemmer + forbidden-term penalty ----------
#
# The offline grader turns recall-only overlap into precision+recall by scoring
# a free-text answer against a small per-element rubric. Paraphrases are folded
# to canonical single tokens (aliases + phrase map) and morphology is collapsed
# by a dependency-free suffix stemmer, so "more than half" == "majority" and
# "adjournment" == "adjourned" == "adjourn".

# Paraphrase -> canonical single token. Applied AFTER `_PHRASES`, so the
# discriminative negation/threshold phrases (twothirds/nodebate/nosecond) are
# already collapsed and are never touched here (no word boundary inside them).
_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    # vote thresholds
    (re.compile(r"\b2\s*/\s*3\b|⅔"), " twothirds "),  # 2/3, ⅔
    (re.compile(r"\bmore than half\b|\bover half\b|\bgreater than half\b"), " majority "),
    (re.compile(r"\bsimple majority\b|\bmajority\b"), " majority "),
    # motions / incidental questions
    (re.compile(r"\bprevious question\b|\bclose debate\b|\bmotion to close debate\b"),
     " previousquestion "),
    (re.compile(r"\bpoint of order\b|\braise a point\b|\bquestion of order\b"),
     " pointoforder "),
    (re.compile(r"\bmain motion\b"), " mainmotion "),
    # actions: adopt / pass / carry / approve all mean "adopt"
    (re.compile(r"\badopt(?:ed|s)?\b|\bpass(?:ed|es)?\b|\bcarr(?:y|ied|ies)\b|"
                r"\bapprov(?:e|ed|es)\b"), " adopt "),
    # a second (positive); "no second" already collapsed to nosecond by _PHRASES
    (re.compile(r"\bseconded\b|\bsecond(?:er|s)?\b"), " second "),
    # positive debatability; "not debatable"/"no debate" already -> nodebate
    (re.compile(r"\bdebatable\b|\bdebated\b|\bdebate\b"), " debatable "),
    # previous notice for bylaws amendments
    (re.compile(r"\bprevious notice\b|\bprior notice\b|\bnotice\b"), " notice "),
)

# Suffixes stripped by the light stemmer, longest first. Only strip when the
# stem stays >= 3 chars, so short words are left alone.
_SUFFIXES: tuple[str, ...] = (
    "ization", "izations", "ational", "ations", "ation", "ments", "ment",
    "ings", "ing", "edly", "able", "ible", "ally", "ness", "ies", "ied",
    "ed", "es", "ly", "s",
)


# Canonical tokens the aliases/phrase map produce: never stem these, so the
# discriminative forms survive intact (e.g. "twothirds" must not lose its "s"
# and "debatable" must not collapse to "debat" — those literals anchor rubrics).
_PROTECTED: frozenset[str] = frozenset(
    {
        "twothirds", "nosecond", "nodebate", "novote", "majority", "second",
        "debatable", "previousquestion", "pointoforder", "mainmotion", "adopt",
        "quorum", "plurality", "appeal", "adjourn", "amend", "notice",
    }
)


def _stem(word: str) -> str:
    """Dependency-free suffix stemmer (adjourn/adjournment/adjourned -> adjourn).

    Canonical rubric tokens are protected so their discriminative form survives."""
    if word in _PROTECTED:
        return word
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _canonicalize(text: str) -> str:
    """Lower-case, collapse discriminative phrases, then fold paraphrases to
    canonical tokens (so synonyms/thresholds match through the rubric)."""
    t = text.lower()
    for pat, repl in _PHRASES:
        t = pat.sub(repl, t)
    for pat, repl in _ALIASES:
        t = pat.sub(repl, t)
    return t


def _canon_seq(text: str) -> list[str]:
    """Canonicalized, stemmed content-token sequence (order + duplicates kept so
    multi-word rubric phrases can be matched as a contiguous run)."""
    return [
        _stem(w)
        for w in _WORD_RE.findall(_canonicalize(text))
        if len(w) >= 2 and w not in _STOPWORDS
    ]


def _phrase_matches(phrase: str, seq: list[str]) -> bool:
    """True if `phrase` (canonicalized) appears in the answer token sequence —
    single tokens by membership, multi-word phrases as a contiguous run."""
    p = _canon_seq(phrase)
    if not p:
        return False
    if len(p) == 1:
        return p[0] in seq
    n = len(p)
    return any(seq[i : i + n] == p for i in range(len(seq) - n + 1))


@dataclass(frozen=True)
class RubricElement:
    """One gradeable point in a ruling.

    ``accepted`` are synonym phrases that satisfy the point (matched through the
    alias table + stemmer); ``forbidden`` are the wrong-answer twins whose
    assertion subtracts points (e.g. "majority" for a two-thirds motion).
    ``essential`` elements (correct motion + threshold + chair action) are
    required for a pass; the rest are graded bonus. ``expects`` is the
    human-readable correct value shown in feedback."""

    name: str
    accepted: tuple[str, ...]
    weight: float = 1.0
    forbidden: tuple[str, ...] = ()
    essential: bool = False
    expects: str = ""


@dataclass(frozen=True)
class Rubric:
    elements: tuple[RubricElement, ...]


# Motion/concept tokens that anchor a derived rubric's essential element. Kept
# deliberately narrow: "plurality" is intentionally absent so a wrong "a
# plurality elects" answer earns nothing from the derived rubric.
_MOTION_TOKENS: tuple[tuple[str, str, str], ...] = (
    ("previousquestion", "the motion", "the Previous Question"),
    ("pointoforder", "the motion", "a Point of Order"),
    ("mainmotion", "the motion", "a main motion"),
    ("quorum", "the requirement", "a quorum"),
    ("appeal", "the motion", "an Appeal"),
    ("adjourn", "the motion", "to adjourn"),
    ("amend", "the motion", "to amend"),
)


def derive_rubric(gold_answer: str) -> Rubric | None:
    """Best-effort rubric extracted from a gold ruling when no explicit one is
    authored: pulls the motion name, vote threshold, and second/debate polarity
    (with their forbidden twins) via the phrase map. Returns ``None`` when the
    ruling has no structured element to grade (caller falls back to overlap)."""
    seq = _canon_seq(gold_answer)
    els: list[RubricElement] = []

    for token, name, display in _MOTION_TOKENS:
        if token in seq:
            els.append(
                RubricElement(name, (token,), weight=2.0, essential=True, expects=display)
            )
            break

    if "twothirds" in seq:
        els.append(
            RubricElement("the vote threshold", ("twothirds",), weight=2.0,
                          essential=True, forbidden=("majority",), expects="two-thirds")
        )
    elif "majority" in seq:
        els.append(
            RubricElement("the vote threshold", ("majority",), weight=2.0,
                          essential=True, forbidden=("twothirds",), expects="a majority")
        )

    if "nosecond" in seq:
        els.append(
            RubricElement("the second", ("nosecond",), forbidden=("second",),
                          expects="no second")
        )
    elif "second" in seq:
        els.append(
            RubricElement("the second", ("second",), forbidden=("nosecond",),
                          expects="a second")
        )

    if "nodebate" in seq:
        els.append(
            RubricElement("debatability", ("nodebate",), forbidden=("debatable",),
                          expects="not debatable")
        )
    elif "debatable" in seq:
        els.append(
            RubricElement("debatability", ("debatable",), forbidden=("nodebate",),
                          expects="debatable")
        )

    return Rubric(tuple(els)) if els else None


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
    """Interface for a Section II grader (baseline or LLM-backed).

    ``rubric`` is optional and honoured by :class:`KeywordExaminer`; other
    graders ignore it, so the signature stays uniform for all callers."""

    def grade(
        self,
        answer: str,
        gold_answer: str,
        corpus: str,
        rubric: Rubric | None = None,
    ) -> GradeResult:
        raise NotImplementedError


class BaselineExaminer(Examiner):
    """Offline keyword-overlap grader. No network: the AI-off fallback and the
    baseline the LLM must beat. Grades accuracy as overlap with the rubric."""

    def __init__(self, pass_score: float = 3.0) -> None:
        self.pass_score = pass_score

    def grade(
        self,
        answer: str,
        gold_answer: str,
        corpus: str,
        rubric: Rubric | None = None,
    ) -> GradeResult:
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


class KeywordExaminer(Examiner):
    """Deterministic, offline rubric grader — the AI-off fallback.

    Scores an answer against a per-element rubric (explicit where authored, else
    :func:`derive_rubric` from the gold ruling) using the alias table + stemmer
    for recall and a forbidden-term penalty for precision, so a confidently
    *wrong* threshold ("majority" for a two-thirds motion) fails even though the
    other words overlap. Grounds feedback in a retrieved RONR passage and
    abstains when none is found (never invents)."""

    #: Asserting a forbidden twin subtracts this multiple of the element weight.
    _PENALTY = 1.0

    def __init__(self, pass_score: float = 3.0) -> None:
        self.pass_score = pass_score

    def grade(
        self,
        answer: str,
        gold_answer: str,
        corpus: str,
        rubric: Rubric | None = None,
    ) -> GradeResult:
        passages = retrieve(corpus, gold_answer, k=1)
        if not passages:
            # No supporting passage -> abstain rather than invent (anti-NAPMobile).
            return GradeResult(
                0.0, False, "No supporting RONR passage found.", None, abstained=True
            )
        citation = passages[0].citation

        if not answer.strip():
            return GradeResult(
                0.0, False, "No answer provided.", citation, abstained=False
            )

        rub = rubric or derive_rubric(gold_answer)
        if rub is None or not rub.elements:
            return self._grade_overlap(answer, gold_answer, citation)

        return self._grade_rubric(answer, rub, citation)

    def _grade_rubric(
        self, answer: str, rubric: Rubric, citation: str | None
    ) -> GradeResult:
        seq = _canon_seq(answer)
        earned = penalty = total = 0.0
        got: list[str] = []
        missing: list[str] = []
        wrong: list[RubricElement] = []
        essentials_ok = True

        for el in rubric.elements:
            total += el.weight
            positive = any(_phrase_matches(a, seq) for a in el.accepted)
            contradicted = any(_phrase_matches(f, seq) for f in el.forbidden)
            if contradicted:
                # Wrong twin asserted: subtract, and any essential point fails.
                penalty += el.weight * self._PENALTY
                wrong.append(el)
                if el.essential:
                    essentials_ok = False
            elif positive:
                earned += el.weight
                got.append(el.name)
            else:
                missing.append(el.name)
                if el.essential:
                    essentials_ok = False

        raw = (earned - penalty) / total if total else 0.0
        score = round(5.0 * max(0.0, min(1.0, raw)), 2)
        passed = essentials_ok and score >= self.pass_score
        feedback = self._feedback(got, missing, wrong)
        return GradeResult(score, passed, feedback, citation, abstained=False)

    def _grade_overlap(
        self, answer: str, gold_answer: str, citation: str | None
    ) -> GradeResult:
        # No structured element to grade -> fall back to keyword overlap.
        gold = _tokens(gold_answer)
        overlap = len(_tokens(answer) & gold) / len(gold) if gold else 0.0
        score = round(5.0 * overlap, 2)
        passed = score >= self.pass_score
        verdict = "matches" if passed else "misses key points from"
        return GradeResult(
            score, passed, f"Your answer {verdict} the model ruling.", citation,
            abstained=False,
        )

    @staticmethod
    def _feedback(
        got: list[str], missing: list[str], wrong: list[RubricElement]
    ) -> str:
        parts: list[str] = []
        if got:
            parts.append("Identified " + ", ".join(got) + ".")
        for el in wrong:
            if el.expects:
                parts.append(f"Wrong {el.name} — needs {el.expects}.")
            else:
                parts.append(f"Wrong on {el.name}.")
        if missing:
            parts.append("Missing: " + ", ".join(missing) + ".")
        if not parts:
            parts.append("No relevant points identified.")
        return " ".join(parts)


class PlaceholderExaminer(Examiner):
    """The active grader until real AI is enabled — **no network calls**.

    Grades accuracy deterministically (via the baseline) and adds a simulation
    debrief, clearly labelled as a placeholder. Swap in `LLMExaminer` later
    without changing callers.
    """

    def __init__(self, pass_score: float = 3.0) -> None:
        self.pass_score = pass_score

    def grade(
        self,
        answer: str,
        gold_answer: str,
        corpus: str,
        rubric: Rubric | None = None,
    ) -> GradeResult:
        base = KeywordExaminer(self.pass_score).grade(
            answer, gold_answer, corpus, rubric
        )
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

    def grade(
        self,
        answer: str,
        gold_answer: str,
        corpus: str,
        rubric: Rubric | None = None,
    ) -> GradeResult:
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
    return KeywordExaminer()


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
