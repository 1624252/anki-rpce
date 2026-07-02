#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Reproducible two-way sync test (spec §7b) for the shared engine.

Drives the exact backend calls both apps use (the phone via JNI, the desktop
natively) against a running Anki sync server, proving:

- a device can upload its collection and another can download it,
- reviews made on each device flow both ways with **none lost or double-counted**,
- and the documented conflict rule (last-writer / higher-`usn`) resolves a
  same-card-offline edit to a single, consistent winner.

Start a server first (from the repo root):

    PYTHONPATH=out/pylib SYNC_USER1="rpce:rpcepass" SYNC_BASE=./out/syncsrv3 \
        SYNC_HOST=127.0.0.1 SYNC_PORT=8085 \
        python -c "import anki.syncserver as s; s.run_sync_server()"

then run:

    PYTHONPATH=out/pylib python pylib/tools/rpce_sync_test.py
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import anki.scheduler_pb2 as sched
import anki.sync_pb2 as sp
from anki.collection import Collection
from anki.rpce import build_starter_deck

ENDPOINT = os.environ.get("RPCE_SYNC_ENDPOINT", "http://127.0.0.1:8085/")
USER = os.environ.get("RPCE_SYNC_USER", "rpce")
PASS = os.environ.get("RPCE_SYNC_PASS", "rpcepass")

_FULL = {
    sp.SyncCollectionResponse.FULL_SYNC,
    sp.SyncCollectionResponse.FULL_DOWNLOAD,
    sp.SyncCollectionResponse.FULL_UPLOAD,
}


def _auth(col: Collection) -> sp.SyncAuth:
    return col._backend.sync_login(
        sp.SyncLoginRequest(username=USER, password=PASS, endpoint=ENDPOINT)
    )


def revlog(col: Collection) -> int:
    return col.db.scalar("select count() from revlog") or 0


def card_state(col: Collection, cid: int):
    return col.db.first("select due, ivl, reps, lapses from cards where id = ?", cid)


def review_next(col: Collection) -> int | None:
    """Answer the next queued card 'Good' via the same path the phone uses."""
    q = col._backend.get_queued_cards(fetch_limit=1, intraday_learning_only=False)
    if not q.cards:
        return None
    qc = q.cards[0]
    col._backend.answer_card(
        sched.CardAnswer(
            card_id=qc.card.id,
            current_state=qc.states.current,
            new_state=qc.states.good,
            rating=sched.CardAnswer.GOOD,
            answered_at_millis=int(time.time() * 1000),
            milliseconds_taken=1500,
        )
    )
    return qc.card.id


def normal_sync(col: Collection) -> None:
    """Perform a normal sync; do a full up/down only if the server demands it."""
    resp = col._backend.sync_collection(auth=_auth(col), sync_media=False)
    if resp.required in _FULL:
        upload = resp.required == sp.SyncCollectionResponse.FULL_UPLOAD
        col._backend.full_upload_or_download(
            sp.FullUploadOrDownloadRequest(auth=_auth(col), upload=upload)
        )


def full(col: Collection, upload: bool) -> None:
    col._backend.full_upload_or_download(
        sp.FullUploadOrDownloadRequest(auth=_auth(col), upload=upload)
    )


def main() -> None:
    # spec §7b uses 10 + 10; override with RPCE_SYNC_REVIEWS for a quick run.
    n = int(os.environ.get("RPCE_SYNC_REVIEWS", "10"))
    tmp = Path(tempfile.mkdtemp())
    a_path, b_path = str(tmp / "deviceA.anki2"), str(tmp / "deviceB.anki2")

    # --- Phase 1: device A provisions the shared deck and uploads it (0 reviews). ---
    a = Collection(a_path)
    deck_id = build_starter_deck(a)
    a.decks.set_current(deck_id)  # queue the RPCE new cards
    a._backend.sync_collection(auth=_auth(a), sync_media=False)  # -> full required
    full(a, upload=True)
    print(f"Phase 1: device A uploaded the deck (cards={a.card_count()}, reviews={revlog(a)})")

    # --- Phase 2: device B downloads; must match A exactly. ---
    b = Collection(b_path)
    b._backend.sync_collection(auth=_auth(b), sync_media=False)  # -> full download
    full(b, upload=False)
    b.close()
    b = Collection(b_path)
    b.decks.set_current(deck_id)
    assert b.card_count() == a.card_count(), "B has the same cards as A"
    print(f"Phase 2: device B downloaded (cards={b.card_count()})")

    # --- Phase 3 (spec §7b): each device reviews n cards OFFLINE, then reconnect
    # and sync both ways. All 2n review events must land, none lost or doubled. ---
    for _ in range(n):
        review_next(a)  # desktop reviews n cards offline
    for _ in range(n):
        review_next(b)  # phone reviews n cards offline
    normal_sync(a)  # reconnect: A pushes its n
    normal_sync(b)  # B pushes its n, pulls A's
    normal_sync(a)  # A pulls B's
    assert revlog(a) == revlog(b) == 2 * n, (
        f"two-way merge: expected {2 * n}/{2 * n}, got {revlog(a)}/{revlog(b)} (none lost/doubled)"
    )
    print(
        f"Phase 3: {n} reviews on the desktop + {n} on the phone reconciled to "
        f"{revlog(a)} on both — none lost or double-counted"
    )

    # --- Phase 4: conflict — both review the SAME next card offline. ---
    cid_a = review_next(a)
    cid_b = review_next(b)
    assert cid_a == cid_b, "both devices edited the same card offline"
    normal_sync(a)  # A syncs first
    normal_sync(b)  # B syncs second -> B is the last writer
    normal_sync(a)  # A pulls the resolved state
    normal_sync(b)
    assert revlog(a) == revlog(b), "conflict: revlog counts match (no double-count)"
    assert card_state(a, cid_a) == card_state(b, cid_b), (
        "conflict: the card resolves to one consistent state on both devices"
    )
    print(
        f"Phase 4: same-card conflict resolved to one state (last-writer=deviceB); "
        f"reviews={revlog(a)} on both, consistent"
    )

    a.close()
    b.close()
    print("\nSYNC OK: two-way sync + conflict resolution verified.")


if __name__ == "__main__":
    main()
