# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Section II scenario prompts for performance practice.

A small, deliberately conservative built-in set covering each of the seven
Performance-Expectation domains, using well-established RONR fundamentals so the
performance/debrief workflow can be exercised offline. These are clearly
*samples*; the production set is drawn from the official RPCE sample questions
(`data/RPCE-Sample-Questions-v4-100625.md`) and SME-authored items, and any
AI-generated additions must pass the gold-set checker first.

Gold answers state the correct *ruling/reasoning* (what the examiner grades on)
and every model answer carries an exact RONR (12th ed.) section citation plus a
verbatim quote from that section (`ref`); the candidate is not required to cite.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import refs
from .examiner import Rubric, RubricElement


@dataclass(frozen=True)
class Scenario:
    domain_code: int
    prompt: str
    #: The model ruling/reasoning the answer is graded against (accuracy).
    gold_answer: str
    #: RONR (12th ed.) citation + verbatim quote shown with the model answer.
    ref: refs.Ref
    #: Per-element grading rubric for the offline examiner. Optional: when
    #: absent the examiner derives one from ``gold_answer``.
    rubric: Rubric | None = None


# --- Curated rubrics (shared with the matching simulation turns) -------------
#
# Core elements (correct motion + vote threshold + required chair action) are
# essential and weighted heaviest; each carries its wrong-answer twin as a
# forbidden term so a confidently wrong ruling is penalised, not rewarded.

RUBRIC_MAIN_MOTION = Rubric(
    (
        RubricElement(
            "the second",
            ("second",),
            weight=2.0,
            essential=True,
            forbidden=("nosecond",),
            expects="a second",
        ),
        RubricElement(
            "the vote threshold",
            ("majority",),
            weight=2.0,
            essential=True,
            forbidden=("twothirds",),
            expects="a majority vote",
        ),
        RubricElement(
            "stating the question / opening debate",
            ("state", "open debate", "debate"),
            weight=1.0,
        ),
    )
)

RUBRIC_PREVIOUS_QUESTION = Rubric(
    (
        RubricElement(
            "the motion",
            ("previousquestion",),
            weight=2.0,
            essential=True,
            expects="the Previous Question",
        ),
        RubricElement(
            "the vote threshold",
            ("twothirds",),
            weight=2.0,
            essential=True,
            forbidden=("majority",),
            expects="two-thirds",
        ),
        RubricElement(
            "the second", ("second",), forbidden=("nosecond",), expects="a second"
        ),
        RubricElement(
            "debatability",
            ("nodebate",),
            forbidden=("debatable",),
            expects="not debatable",
        ),
    )
)

RUBRIC_POINT_OF_ORDER = Rubric(
    (
        RubricElement(
            "the motion",
            ("pointoforder",),
            weight=2.0,
            essential=True,
            expects="a Point of Order",
        ),
        RubricElement(
            "the second", ("nosecond",), forbidden=("second",), expects="no second"
        ),
        RubricElement(
            "debatability",
            ("nodebate",),
            forbidden=("debatable",),
            expects="not debatable",
        ),
        RubricElement(
            "the chair rules (may be appealed)", ("rule", "chair", "appeal"), weight=1.0
        ),
    )
)

RUBRIC_QUORUM = Rubric(
    (
        RubricElement(
            "the quorum requirement",
            ("quorum",),
            weight=3.0,
            essential=True,
            expects="a quorum must be present",
        ),
        RubricElement("defined by the bylaws", ("bylaw",), weight=1.0),
    )
)

RUBRIC_PLURALITY = Rubric(
    (
        RubricElement(
            "the majority requirement",
            ("majority",),
            weight=2.0,
            essential=True,
            forbidden=("twothirds",),
            expects="a majority — more than half",
        ),
        RubricElement(
            "that a plurality does not elect",
            (
                "plurality does not elect",
                "balloting continues",
                "continue balloting",
                "majority required",
                "not elected",
            ),
            weight=2.0,
            essential=True,
            forbidden=("plurality elects", "plurality is enough", "plurality wins"),
            expects="a plurality does not elect",
        ),
    )
)

RUBRIC_PARLIAMENTARIAN = Rubric(
    (
        RubricElement(
            "that the parliamentarian only advises, impartially",
            (
                "advise",
                "advises",
                "impartial",
                "impartially",
                "neutral",
                "does not rule",
                "not take sides",
            ),
            weight=2.0,
            essential=True,
            forbidden=("take sides", "rule which", "which side is right"),
            expects="impartial, private advice — not a ruling",
        ),
        RubricElement(
            "that the chair makes the rulings",
            ("chair rules", "chair makes", "chair, not"),
            weight=1.0,
        ),
    )
)

RUBRIC_BYLAWS_AMENDMENT = Rubric(
    (
        RubricElement(
            "the vote threshold",
            ("twothirds",),
            weight=2.0,
            essential=True,
            forbidden=("majority",),
            expects="two-thirds",
        ),
        RubricElement(
            "previous notice",
            ("notice",),
            weight=2.0,
            essential=True,
            expects="previous notice",
        ),
    )
)


# The old curated stubs (incl. the narrow "as chair, what do you do before
# debate?" pattern) were scrapped and fully replaced by the authored
# performance-exam bank in data/rpce_section2_scenarios.json (219 scenarios,
# one+ per RONR topic, sample-style). The RUBRIC_* constants above are kept
# because the simulation turns share them.
SCENARIOS: tuple[Scenario, ...] = ()


#: Authored sample-style scenarios (one+ per RONR section), generated by
#: rpce_section2_workflow.js. They have no explicit rubric — the offline
#: KeywordExaminer derives one from the model ruling (which names the decisive
#: facts). Loaded lazily and cached.
_AUTHORED: tuple[Scenario, ...] | None = None


def _load_authored() -> tuple[Scenario, ...]:
    global _AUTHORED
    if _AUTHORED is not None:
        return _AUTHORED
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "data" / "rpce_section2_scenarios.json"
    out: list[Scenario] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data.get("scenarios", []):
            out.append(
                Scenario(
                    int(s["domain"]),
                    s["prompt"],
                    s["gold_answer"],
                    refs.Ref(str(s["section"]), s.get("quote", "")),
                    rubric=None,  # derived from the model ruling by the grader
                )
            )
    except Exception as exc:  # never break Section II over the authored file
        print(f"RPCE authored-scenario load error: {exc}")
    _AUTHORED = tuple(out)
    return _AUTHORED


def scenarios_for(domain_code: int) -> list[Scenario]:
    return [s for s in all_scenarios() if s.domain_code == domain_code]


def all_scenarios() -> tuple[Scenario, ...]:
    # Curated scenarios first, then the authored sample-style bank.
    return SCENARIOS + _load_authored()
