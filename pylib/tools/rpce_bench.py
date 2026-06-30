# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""One-command RPCE benchmark (spec §7h / §10).

Builds a synthetic deck and reports p50 / p95 / worst-case latency for the
operations the spec sets targets on:

- **answer (button-press ack)** — target p95 < 50 ms
- **next card** — target p95 < 100 ms
- **points-at-stake queue** — the RPCE Rust change

Run via ``just bench`` (or directly). Defaults to a small deck for a quick
check; pass ``--cards 50000`` for the spec's reference size.

    python pylib/tools/rpce_bench.py --cards 50000
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from statistics import median


def _bootstrap_paths() -> None:
    """Make the built `anki` package importable when run from the repo root."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    built = os.path.join(repo, "out", "pylib")
    if os.path.isdir(built):
        sys.path.insert(0, built)
    os.environ.setdefault("ANKI_TEST_MODE", "1")


def _percentiles(samples_ms: list[float]) -> tuple[float, float, float]:
    ordered = sorted(samples_ms)
    p50 = median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    return p50, p95, ordered[-1]


def _report(name: str, samples_ms: list[float], target_ms: float | None) -> None:
    p50, p95, worst = _percentiles(samples_ms)
    target = f"   target p95 < {target_ms:.0f} ms" if target_ms else ""
    flag = ""
    if target_ms and p95 >= target_ms:
        flag = "  [OVER TARGET]"
    print(
        f"{name:24} p50={p50:7.2f}ms  p95={p95:7.2f}ms  worst={worst:7.2f}ms{target}{flag}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="RPCE latency benchmark")
    parser.add_argument(
        "--cards", type=int, default=2000, help="deck size (default 2000)"
    )
    parser.add_argument(
        "--iterations", type=int, default=300, help="timed samples per op"
    )
    args = parser.parse_args()

    _bootstrap_paths()
    from anki import rpce
    from anki.collection import Collection

    tmp = tempfile.mkdtemp(prefix="rpce_bench_")
    col = Collection(os.path.join(tmp, "collection.anki2"))
    try:
        print(f"Building synthetic deck of {args.cards} cards...")
        did = col.decks.id("RPCE-bench")
        basic = col.models.by_name("Basic")
        for i in range(args.cards):
            note = col.new_note(basic)
            note["Front"] = f"q{i}"
            note["Back"] = f"a{i}"
            note.tags = [rpce.domain_tag((i % 7) + 1)]
            col.add_note(note, did)
        col.decks.set_current(did)

        weights = rpce.topic_weights(col)

        # next card + answer (button ack)
        next_samples: list[float] = []
        answer_samples: list[float] = []
        for _ in range(args.iterations):
            t0 = time.perf_counter()
            card = col.sched.getCard()
            next_samples.append((time.perf_counter() - t0) * 1000)
            if card is None:
                break
            t0 = time.perf_counter()
            col.sched.answerCard(card, 3)
            answer_samples.append((time.perf_counter() - t0) * 1000)

        # points-at-stake queue
        queue_samples: list[float] = []
        for _ in range(max(20, args.iterations // 10)):
            t0 = time.perf_counter()
            col._backend.get_points_at_stake_queue(
                topic_weights=weights, default_weight=0.0, limit=50
            )
            queue_samples.append((time.perf_counter() - t0) * 1000)

        print()
        _report("next card", next_samples, 100)
        _report("answer (button ack)", answer_samples, 50)
        _report("points-at-stake queue", queue_samples, None)
    finally:
        col.close()


if __name__ == "__main__":
    main()
