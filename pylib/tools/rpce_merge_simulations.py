# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Merge the per-domain simulation batches (authored by subagents, one JSON each
in the scratchpad) into ``data/rpce_simulations.json``.

Each simulation is a scripted meeting (<=10 turns); its decision turns carry a
concept id + a verbatim RONR quote so Simulation mode is labelled/counted by
concept and every model ruling cites RONR (docs/rpce Phase 4).

Usage: python rpce_merge_simulations.py <scratch_dir>
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rpce_simulations.json"
BATCHES = [f"sim_d{d}.json" for d in range(1, 8)]


def main(scratch: str) -> None:
    sp = Path(scratch)
    out: list[dict] = []
    for name in BATCHES:
        p = sp / name
        if not p.exists():
            print(f"  (missing {name})")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        sims = data["simulations"] if isinstance(data, dict) else data
        for s in sims:
            turns = s.get("turns") or []
            if not turns or len(turns) > 10:  # enforce the <=10-turn rule
                print(f"  (skipped a {len(turns)}-turn sim in {name})")
                continue
            out.append(s)
    OUT.write_text(
        json.dumps({"simulations": out}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    decisions = [t for s in out for t in s["turns"] if t.get("prompt")]
    concepts = {t["concept"] for t in decisions if t.get("concept")}
    print(f"wrote {len(out)} simulations to {OUT}")
    print(f"decision turns: {len(decisions)} | distinct concepts: {len(concepts)}")
    print("by domain:", dict(sorted(Counter(s["domain"] for s in out).items())))
    print("max turns in any sim:", max((len(s["turns"]) for s in out), default=0))


if __name__ == "__main__":
    main(sys.argv[1])
