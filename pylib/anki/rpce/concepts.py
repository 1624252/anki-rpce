# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The RPCE concept registry: one concept per numbered RP performance expectation.

Every practice item (Review card, Section II scenario, Simulate decision) is
labelled with a concept id (its PE number, e.g. "1.13"), tagged on cards as
``rpce::concept::<id>``. Concepts drive the dashboard's concept coverage and the
Memory/Performance/Readiness scores (see docs/rpce/SCORING.md).

Loaded from ``data/rpce_concepts.json``, which is extracted faithfully from the
NAP Criteria for Credentialing (see docs/rpce/CRITERIA_IMPLEMENTATION_PLAN.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ._paths import data_path


@dataclass(frozen=True)
class Concept:
    id: str  # the PE number, e.g. "1.13" — also the rpce::concept::<id> tag
    domain: int  # 1..7
    group: str  # readable sub-topic heading, e.g. "Amend", "Quorum"
    name: str  # short label of what the PE tests
    ronr_refs: tuple[str, ...] = ()  # RONR (12th ed.) citations in the PE


_CONCEPTS: tuple[Concept, ...] | None = None


def _load() -> tuple[Concept, ...]:
    global _CONCEPTS
    if _CONCEPTS is not None:
        return _CONCEPTS
    path = data_path("rpce_concepts.json")
    out: list[Concept] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path else {}
        for c in data.get("concepts", []):
            out.append(
                Concept(
                    id=str(c["id"]),
                    domain=int(c["domain"]),
                    group=str(c.get("group", "")),
                    name=str(c.get("name", "")),
                    ronr_refs=tuple(c.get("ronr_refs", []) or ()),
                )
            )
    except Exception as exc:  # never break the app over the registry
        print(f"RPCE concept-registry load error: {exc}")
    _CONCEPTS = tuple(out)
    return _CONCEPTS


def all_concepts() -> tuple[Concept, ...]:
    return _load()


def concept_by_id(cid: str) -> Concept | None:
    return next((c for c in _load() if c.id == cid), None)


def concepts_for_domain(domain: int) -> list[Concept]:
    return [c for c in _load() if c.domain == domain]


def groups() -> dict[str, list[Concept]]:
    """Concepts rolled up by their sub-topic heading (for readable UI grouping)."""
    out: dict[str, list[Concept]] = {}
    for c in _load():
        out.setdefault(c.group, []).append(c)
    return out


def concept_tag(cid: str) -> str:
    return f"rpce::concept::{cid}"
