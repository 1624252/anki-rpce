# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the per-PE concept registry (docs/rpce/SCORING.md)."""

import re

from anki.rpce import concepts


def test_registry_loads_all_domains():
    cs = concepts.all_concepts()
    assert len(cs) >= 180  # one per numbered RP performance expectation
    assert {c.domain for c in cs} == {1, 2, 3, 4, 5, 6, 7}


def test_ids_are_unique_pe_numbers():
    cs = concepts.all_concepts()
    ids = [c.id for c in cs]
    assert len(set(ids)) == len(ids)
    # every id is a PE number like "1.1" / "7.43"
    assert all(re.fullmatch(r"\d+\.\d+", c.id) for c in cs)


def test_every_concept_has_label_and_group():
    for c in concepts.all_concepts():
        assert c.name.strip()
        assert c.group.strip()


def test_lookup_and_tag():
    c = concepts.concept_by_id("3.29")
    assert c is not None and c.domain == 3
    assert concepts.concept_tag("7.10") == "rpce::concept::7.10"
