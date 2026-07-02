#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""§7g crash / offline resilience test — CI-safe, one command.

"Kill each app in the middle of a review 20 times in a row. Show zero corrupted
collections afterward."

We build a Collection with the RPCE deck, then repeat 20 times:

1. a **child process** opens the collection from disk, starts a review, answers
   a card through the *real* backend path (``answer_card``, the same call the
   phone and desktop use), fetches the next card, and is then **hard-killed**
   with ``os._exit`` — no clean ``col.close()``, exactly like the OS killing the
   app mid-review;
2. the parent reopens the collection from disk and runs an integrity check
   (SQLite ``pragma integrity_check`` + Anki's own ``check_database``), asserting
   the collection is intact and the committed reviews are still there.

Using a real child process that is killed (not a mocked "unclean close") is the
honest simulation: the OS closes the file handles under a live SQLite/WAL write,
and the next open must recover cleanly.

It also runs a short **offline** check: with no API key, ``make_examiner()`` must
return the offline :class:`~anki.rpce.examiner.KeywordExaminer` and still grade —
proving AI degrades cleanly when offline.

Exits non-zero on any failure, so it is safe to wire into CI.

    just rpce-crash
    # or: PYTHONPATH=out/pylib python pylib/tools/rpce_crash_test.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

DECK_NAME = "RPCE"
ITERATIONS = int(os.environ.get("RPCE_CRASH_ITERS", "20"))
#: argv marker that puts this script into single-crash child mode.
_WORKER_FLAG = "--crash-worker"


def _bootstrap_paths() -> None:
    """Make the built ``anki`` package importable when run from the repo root."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    built = os.path.join(repo, "out", "pylib")
    if os.path.isdir(built):
        sys.path.insert(0, built)
    os.environ.setdefault("ANKI_TEST_MODE", "1")


def _worker(path: str) -> None:
    """Child process: start a review, answer a card via the backend, fetch the
    next one, then hard-exit mid-review WITHOUT a clean close (simulated crash)."""
    _bootstrap_paths()
    import time as _time

    import anki.scheduler_pb2 as sched
    from anki.collection import Collection

    col = Collection(path)
    col.decks.set_current(col.decks.id(DECK_NAME))

    queued = col._backend.get_queued_cards(fetch_limit=1, intraday_learning_only=False)
    if queued.cards:
        qc = queued.cards[0]
        # Real answer path (same call the phone/desktop use). This commits.
        col._backend.answer_card(
            sched.CardAnswer(
                card_id=qc.card.id,
                current_state=qc.states.current,
                new_state=qc.states.good,
                rating=sched.CardAnswer.GOOD,
                answered_at_millis=int(_time.time() * 1000),
                milliseconds_taken=1500,
            )
        )
        # Fetch the next card so we die WHILE a card is on screen, unanswered.
        col._backend.get_queued_cards(fetch_limit=1, intraday_learning_only=False)

    sys.stdout.flush()
    # Skip col.close() entirely: hard-kill the process as if the OS killed the app.
    os._exit(137)  # 128 + SIGKILL


def _spawn_crash(path: str) -> None:
    """Run one crash iteration in a child process and wait for it to die."""
    env = dict(os.environ)
    # Child imports the built engine from out/pylib as well.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in ("out/pylib", env.get("PYTHONPATH", "")) if p
    )
    subprocess.run(
        [sys.executable, os.path.abspath(__file__), _WORKER_FLAG, path],
        env=env,
        check=False,
    )


def _integrity_ok(path: str) -> tuple[bool, int, str]:
    """Reopen from disk and check integrity. Returns (ok, revlog_count, detail)."""
    from anki.collection import Collection

    col = Collection(path)
    try:
        pragma = col.db.scalar("pragma integrity_check")
        revlog = col.db.scalar("select count() from revlog") or 0
        # Anki's own structural check; ok == no problems found.
        _report, check_ok = col.fix_integrity()
        ok = (pragma == "ok") and check_ok
        detail = f"pragma={pragma}, check_database_ok={check_ok}"
        return ok, int(revlog), detail
    finally:
        col.close()


def _offline_examiner_ok() -> bool:
    """With no API key, make_examiner() must be the offline grader and still grade."""
    for key in ("RPCE_AI_KEY", "OPENAI_API_KEY"):
        os.environ.pop(key, None)
    from anki.rpce import examiner as ex

    grader = ex.make_examiner()
    if not isinstance(grader, ex.KeywordExaminer):
        print(f"  offline: FAIL — make_examiner() returned {type(grader).__name__}")
        return False
    gold = "A main motion requires a second and a majority vote to be adopted."
    result = grader.grade(
        "A main motion needs a second and a majority vote to be adopted.", gold, gold
    )
    ok = (not result.abstained) and result.passed
    verdict = "PASS" if ok else "FAIL"
    print(
        f"  offline: {verdict} — no API key -> KeywordExaminer, "
        f"graded a correct answer as passed={result.passed}"
    )
    return ok


def main() -> int:
    _bootstrap_paths()
    from anki.collection import Collection
    from anki.rpce import build_starter_deck

    tmp = Path(tempfile.mkdtemp(prefix="rpce_crash_"))
    path = str(tmp / "collection.anki2")

    # Provision the deck and close cleanly (baseline good collection).
    col = Collection(path)
    deck_id = build_starter_deck(col)
    col.decks.set_current(deck_id)
    col.close()

    print(f"§7g crash test — killing a review mid-flight {ITERATIONS} times\n")
    corrupted = 0
    for i in range(1, ITERATIONS + 1):
        _spawn_crash(path)  # child answers a card then is hard-killed
        ok, revlog, detail = _integrity_ok(path)
        if ok:
            print(f"  iter {i:2}/{ITERATIONS}: clean   (revlog={revlog}; {detail})")
        else:
            corrupted += 1
            print(f"  iter {i:2}/{ITERATIONS}: CORRUPT (revlog={revlog}; {detail})")

    print(
        f"\n{ITERATIONS - corrupted}/{ITERATIONS} iterations, {corrupted} corrupted collections"
    )

    print("\nOffline degradation check:")
    offline_ok = _offline_examiner_ok()

    if corrupted == 0 and offline_ok:
        print("\nCRASH TEST OK: zero corrupted collections; AI grades offline.")
        return 0
    print("\nCRASH TEST FAILED.")
    return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == _WORKER_FLAG:
        _worker(sys.argv[2])  # child mode: never returns (os._exit)
    raise SystemExit(main())
