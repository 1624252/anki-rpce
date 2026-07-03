#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Export the phone's bundled Section II + Simulation JSON from the Python data.

Keeps ``mobile/.../assets/scenarios.json`` and ``simulations.json`` in lock-step
with ``anki.rpce.scenarios`` / ``anki.rpce.simulations`` — including the RONR
(12th ed.) citation + verbatim quote (`ref`) every model answer must carry.

Run from the repo root (needs the built pylib on the path):

    PYTHONPATH=out/pylib python pylib/tools/rpce_export_assets.py \
        mobile/app/app/src/main/assets
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from anki.rpce import concepts, scenarios, simulations


def _ref(ref) -> dict | None:
    if ref is None:
        return None
    return {"section": ref.section, "quote": ref.quote}


def _concept_name(cid: str) -> str:
    if not cid:
        return ""
    c = concepts.concept_by_id(cid)
    return c.name if c else ""


def _scenarios_json() -> list[dict]:
    return [
        {
            "domain": s.domain_code,
            "concept": s.concept,
            "conceptName": _concept_name(s.concept),
            "prompt": s.prompt,
            "gold": s.gold_answer,
            "keywords": list(s.keywords),
            "ref": _ref(s.ref),
        }
        for s in scenarios.all_scenarios()
    ]


def _simulations_json() -> list[dict]:
    out = []
    for sim in simulations.all_simulations():
        turns = []
        for t in sim.turns:
            turn: dict = {"speaker": t.speaker, "line": t.line}
            if t.needs_response:
                turn["prompt"] = t.prompt
                turn["gold"] = t.gold
                turn["ref"] = _ref(t.ref)
                # Step-by-step expected key concepts (groups of synonyms) for the
                # phone's lenient sim grader, mirroring examiner.grade_sim_step.
                turn["expected"] = [list(g) for g in t.expected]
            turns.append(turn)
        out.append(
            {
                "id": sim.id,
                "domain": sim.domain_code,
                "title": sim.title,
                "setting": sim.setting,
                "turns": turns,
            }
        )
    return out


def main(assets_dir: str) -> None:
    out_dir = Path(assets_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("scenarios.json", _scenarios_json()),
        ("simulations.json", _simulations_json()),
    ):
        path = out_dir / name
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: rpce_export_assets.py <assets_dir>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
