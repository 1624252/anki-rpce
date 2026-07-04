# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The RONR (12th ed.) quote bank the meeting simulator draws on.

Loaded from ``data/rpce_quotes.json`` (built by ``pylib/tools/rpce_build_quotes.py``
from the corpus + the concept registry). Every quote is a **verbatim** excerpt
tagged with its exact ``section:paragraph`` citation, so when the simulator shows
the governing quote at grading the citation is OUR retrieval — never the model's
invention (the "traceable source" rule; see docs/rpce/AI_NOTES.md).

The simulator feeds :func:`random_quotes` to the AI, which authors a meeting where
each decision point turns on one of the supplied quotes; the exact quote is then
shown when that answer is graded. See :mod:`anki.rpce.ai` and ``qt/aqt/rpce.py``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from ._paths import data_path


@dataclass(frozen=True)
class Quote:
    section: str  # RONR citation, e.g. "6:1"
    quote: str  # verbatim excerpt from that section
    concept: str  # the concept id this quote was gathered for, e.g. "1.3"

    def as_dict(self) -> dict[str, str]:
        return {"section": self.section, "quote": self.quote}


_BY_CONCEPT: dict[str, tuple[Quote, ...]] | None = None
_ALL: tuple[Quote, ...] | None = None


def _load() -> dict[str, tuple[Quote, ...]]:
    global _BY_CONCEPT, _ALL
    if _BY_CONCEPT is not None:
        return _BY_CONCEPT
    path = data_path("rpce_quotes.json")
    by_concept: dict[str, tuple[Quote, ...]] = {}
    flat: list[Quote] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path else {}
        for cid, items in (data.get("quotes") or {}).items():
            qs = tuple(
                Quote(str(it.get("section", "")), str(it.get("quote", "")), str(cid))
                for it in items
                if it.get("quote")
            )
            by_concept[str(cid)] = qs
            flat.extend(qs)
    except Exception as exc:  # never break the app over the quote bank
        print(f"RPCE quote-bank load error: {exc}")
    _BY_CONCEPT = by_concept
    _ALL = tuple(flat)
    return _BY_CONCEPT


def all_quotes() -> tuple[Quote, ...]:
    """Every quote in the bank (flattened across concepts)."""
    _load()
    assert _ALL is not None
    return _ALL


def quotes_for_concept(concept_id: str) -> tuple[Quote, ...]:
    """The quotes gathered for one concept id (empty if unknown)."""
    return _load().get(str(concept_id), ())


def random_quotes(n: int = 8, *, rng: random.Random | None = None) -> list[Quote]:
    """A random set of ``n`` DISTINCT quotes to seed a simulated meeting.

    Sampled without replacement across the whole bank so a meeting draws on a
    varied mix of rules. Returns fewer than ``n`` only if the bank is smaller
    than ``n`` (or empty). ``rng`` is injectable for deterministic tests."""
    pool = list(all_quotes())
    if not pool:
        return []
    r = rng or random
    k = min(max(n, 0), len(pool))
    return r.sample(pool, k)
