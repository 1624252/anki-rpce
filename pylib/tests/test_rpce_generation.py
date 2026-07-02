# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The question generator must produce varied, answerable, well-formed items that
never leak a section into a stem/option and always cite an exact section with a
verbatim RONR (12th ed.) quote (project accuracy rule; spec §7).

Coverage/quote checks need the (git-ignored, copyrighted) corpus; they skip when
it is unavailable. The phrasing/well-formedness unit checks run without it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from anki.rpce import knowledge as kb

_REPO: Path | None = None
for _base in Path(__file__).resolve().parents:
    if (_base / "pylib" / "tools" / "rpce_generate_questions.py").exists():
        _REPO = _base
        sys.path.insert(0, str(_base / "pylib" / "tools"))
        break

if _REPO is None:  # pragma: no cover - layout guard
    pytest.skip("generator tool not found", allow_module_level=True)

import rpce_generate_questions as gen  # noqa: E402

_CORPUS = _REPO / "data" / "roberts_rules_of_order_12th_edition.md"
_HAS_CORPUS = _CORPUS.exists()
if _HAS_CORPUS:
    gen.CORPUS = _CORPUS

corpus_only = pytest.mark.skipif(not _HAS_CORPUS, reason="RONR corpus not available")

# Build the full bank once for the whole module (deterministic, fixed seed).
_QUESTIONS = gen.build(count=0) if _HAS_CORPUS else []
_PARAS = gen.parse_corpus() if _HAS_CORPUS else []


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


# --- phrasing (no corpus needed) ---------------------------------------------


def test_motion_phrase_reads_naturally():
    assert kb.motion_phrase("Adjourn") == "the motion to Adjourn"
    assert kb.motion_phrase("Main Motion") == "a main motion"
    assert (
        kb.motion_phrase("Previous Question") == "the motion for the Previous Question"
    )
    assert kb.motion_phrase("Point of Order") == "a Point of Order"


# --- generated bank (corpus-backed) ------------------------------------------


@corpus_only
def test_bank_is_large_and_varied():
    labels = {q.label for q in _QUESTIONS}
    # every question type is present
    kinds = {q.payload["kind"] for q in _QUESTIONS}
    assert kinds == {"cloze", "mcq", "multi", "order"}
    assert "Precedence (select all)" in labels
    assert "Precedence (ordering)" in labels
    assert len(_QUESTIONS) > 3000


@corpus_only
def test_no_section_reference_leaks_into_stems_or_options():
    for q in _QUESTIONS:
        pl = q.payload
        surfaces = [pl.get("stem", ""), pl.get("text", ""), pl.get("prompt", "")]
        surfaces += list(pl.get("options", []))
        for s in surfaces:
            assert not gen.mentions_section(s), f"leak in {q.concept_id}: {s!r}"


@corpus_only
def test_mcq_has_exactly_one_correct_answer():
    for q in _QUESTIONS:
        if q.payload["kind"] != "mcq":
            continue
        opts = q.payload["options"]
        assert len(opts) >= 2
        assert len(set(opts)) == len(opts), f"dup option in {q.concept_id}"
        assert 0 <= q.payload["answer"] < len(opts)


@corpus_only
def test_multi_select_has_some_but_not_all_correct():
    seen = False
    for q in _QUESTIONS:
        if q.payload["kind"] != "multi":
            continue
        seen = True
        correct = set(q.payload["correct"])
        n = len(q.payload["options"])
        assert 1 <= len(correct) < n, f"bad select-all set in {q.concept_id}"
    assert seen, "expected select-all questions"


@corpus_only
def test_order_questions_follow_the_saved_precedence():
    seen = False
    for q in _QUESTIONS:
        if q.payload["kind"] != "order":
            continue
        seen = True
        names = q.payload["order"]
        assert len(names) >= 3
        ranks = [kb.by_name(n).rank for n in names]
        assert ranks == sorted(ranks), f"{q.concept_id} not highest→lowest"
    assert seen, "expected ordering questions"


@corpus_only
def test_every_question_cites_a_section_and_verbatim_quote():
    haystack = _norm(" ".join(gen.clean(p.text) for p in _PARAS))
    for q in _QUESTIONS:
        assert re.fullmatch(r"\d+:\d+", q.cite), f"{q.concept_id}: bad cite {q.cite!r}"
        assert q.quote, f"{q.concept_id}: empty quote"
        # Generated quotes are whole substrings of a cleaned corpus paragraph
        # (any "…" they contain is the corpus's own, not an elision marker).
        needle = _norm(q.quote).strip(" .;,")
        assert needle and needle in haystack, f"{q.cite}: not verbatim {needle!r}"


@corpus_only
def test_cloze_blanks_follow_the_hint_rule():
    # Rule R1 (docs/rpce/QUESTION_RULES.md): a blank may have NO hint (renders as
    # a plain "?"), but any hint it does carry must reveal only a semantic
    # category — never the answer's length, first letter, or word count.
    banned = re.compile(r"\bletters?\b|\bstarts?\b|begins?\b|first letter|\bwords?\b|characters?", re.I)
    for q in _QUESTIONS:
        if q.payload["kind"] != "cloze":
            continue
        assert q.payload["blanks"], q.concept_id
        for b in q.payload["blanks"]:
            assert b["a"].strip(), f"{q.concept_id}: empty answer"
            assert not banned.search(b["h"]), f"{q.concept_id}: hint reveals spelling: {b['h']!r}"


@corpus_only
def test_covers_at_least_ninety_percent_of_substantive_paragraphs():
    from collections import Counter

    per_para = Counter(q.concept_id for q in _QUESTIONS if q.concept_id.startswith("C"))
    covered = sum(1 for v in per_para.values() if v >= 2)
    ratio = covered / len(_PARAS)
    assert ratio >= 0.9, f"only {covered}/{len(_PARAS)} paragraphs have ≥2 questions"
