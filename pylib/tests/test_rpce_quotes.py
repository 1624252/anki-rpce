# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the RONR quote bank the meeting simulator draws on.

Guards the invariants the feature relies on: every concept has >= 4 quotes and
>= 1 per referenced section, every quote is verbatim with an exact citation, and
the committed ``data/rpce_quotes.json`` still matches a fresh build (no drift).
"""

from __future__ import annotations

import importlib.util
import random
import re
from pathlib import Path

import pytest

from anki.rpce import concepts, quotes

_ROOT = Path(__file__).resolve().parents[2]
_BUILDER = _ROOT / "pylib" / "tools" / "rpce_build_quotes.py"
_CITATION = re.compile(r"^\d+:\d+$")


def _load_builder():
    spec = importlib.util.spec_from_file_location("rpce_build_quotes", _BUILDER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


def test_every_concept_has_at_least_four_quotes():
    for c in concepts.all_concepts():
        qs = quotes.quotes_for_concept(c.id)
        assert len(qs) >= 4, (c.id, len(qs))


def test_quotes_are_well_formed_and_distinct():
    for c in concepts.all_concepts():
        seen = set()
        for q in quotes.quotes_for_concept(c.id):
            assert _CITATION.match(q.section), (c.id, q.section)
            assert len(q.quote.strip()) >= 20, (c.id, q.quote)
            key = q.quote.lower()
            assert key not in seen, (c.id, q.quote)  # no dup within a concept
            seen.add(key)


def test_every_quote_is_verbatim_from_the_corpus(builder):
    corpus = builder._clean(builder.BOOK.read_text(encoding="utf-8"))
    for q in quotes.all_quotes():
        assert q.quote in corpus, (q.concept, q.section, q.quote[:60])


def test_at_least_one_quote_per_referenced_section_with_prose(builder):
    """Each referenced section that yields quotable prose is cited by >= 1 quote."""
    para, _chapter = builder._load_book()
    corpus = builder._clean(builder.BOOK.read_text(encoding="utf-8"))
    for c in concepts.all_concepts():
        cited = {q.section for q in quotes.quotes_for_concept(c.id)}
        for ref in c.ronr_refs:
            for sec in builder._expand_ref(ref):
                if builder._sentences(para, sec, corpus):  # has prose
                    assert sec in cited, (c.id, sec)


def test_committed_bank_matches_a_fresh_build(builder):
    """The committed data/rpce_quotes.json is exactly what the builder produces."""
    import json

    fresh = builder.build_quotes()["quotes"]
    committed = json.loads(
        (_ROOT / "data" / "rpce_quotes.json").read_text(encoding="utf-8")
    )["quotes"]
    assert committed == fresh


def test_random_quotes_are_distinct_and_bounded():
    qs = quotes.random_quotes(8, rng=random.Random(0))
    assert len(qs) == 8
    assert len({(q.section, q.quote) for q in qs}) == 8  # no repeats
    # Never returns more than the bank holds.
    big = quotes.random_quotes(10**9, rng=random.Random(0))
    assert len(big) == len(quotes.all_quotes())


def test_random_quotes_seeded_is_deterministic():
    a = quotes.random_quotes(5, rng=random.Random(42))
    b = quotes.random_quotes(5, rng=random.Random(42))
    assert [q.quote for q in a] == [q.quote for q in b]
