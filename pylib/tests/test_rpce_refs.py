# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Every built-in RONR (12th ed.) citation quote must be **verbatim** from the
corpus. This guards the project accuracy rule: each mode answers with an exact
section citation and a relevant quote actually found in that section.

The test locates ``data/roberts_rules_of_order_12th_edition.md`` relative to the
repo; if it is unavailable (e.g. CI without the copyrighted corpus), it skips.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from anki.rpce import refs

_ALL_REFS = [
    refs.MAJORITY,
    refs.PREVIOUS_QUESTION,
    refs.PRECEDENCE,
    refs.POINT_OF_ORDER,
    refs.QUORUM,
    refs.PLURALITY,
    refs.PARLIAMENTARIAN,
    refs.BYLAWS_AMENDMENT,
]


def _find_corpus() -> Path | None:
    name = "roberts_rules_of_order_12th_edition.md"
    for base in Path(__file__).resolve().parents:
        cand = base / "data" / name
        if cand.exists():
            return cand
    return None


def _normalize(text: str) -> str:
    """Fold markdown/typographic noise so verbatim substrings match reliably."""
    text = re.sub(r"<a id=[^>]*></a>", " ", text)  # anchors
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", "", text)  # inline links (cross-refs)
    text = text.replace("*", "")  # italics/bold markers
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # curly single
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # curly double
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def test_every_ref_section_is_well_formed():
    for ref in _ALL_REFS:
        assert re.fullmatch(r"\d+:\d+", ref.section), ref.section
        assert ref.quote.strip()


def test_every_quote_is_verbatim_in_the_cited_corpus():
    corpus = _find_corpus()
    if corpus is None:
        pytest.skip("RONR corpus not available")
    haystack = _normalize(corpus.read_text(encoding="utf-8"))
    for ref in _ALL_REFS:
        # A quote may elide an inline cross-reference with "…"; each contiguous
        # segment must appear verbatim in the corpus.
        for segment in ref.quote.split("\u2026"):
            needle = _normalize(segment).strip(" .;,")
            assert needle and needle in haystack, (
                f"{ref.section}: not verbatim -> {needle!r}"
            )
