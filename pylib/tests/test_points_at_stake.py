# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Python-calling test for the RPCE points-at-stake queue (the Rust change).

Exercises the new `get_points_at_stake_queue` backend RPC end to end: it adds
tagged, due cards and confirms the Rust engine orders them by
`topic exam-weight x student weakness`, highest value first.
"""

from tests.shared import getEmptyCol


def _add_due_card(col, front: str, tag: str):
    note = col.newNote()
    note["Front"] = front
    note["Back"] = "back"
    note.tags = [tag]
    col.addNote(note)
    cid = col.find_cards(f"nid:{note.id}")[0]
    # Turn it into a review card due today so `is:due` gathers it.
    col._backend.set_due_date(card_ids=[cid], days="0", config_key=None)
    return cid


def test_points_at_stake_orders_by_weight_times_weakness():
    col = getEmptyCol()

    low = _add_due_card(col, "low-weight", "domain::1")
    high = _add_due_card(col, "high-weight", "domain::2")

    entries = col._backend.get_points_at_stake_queue(
        topic_weights={"domain::1": 0.1, "domain::2": 0.9},
        default_weight=0.0,
        limit=0,
    )

    ids = [e.card_id for e in entries]
    assert ids == [high, low], "higher exam-weight domain must come first"
    assert entries[0].matched_tag == "domain::2"
    assert entries[0].points_at_stake > entries[1].points_at_stake


def test_points_at_stake_limit_and_default_weight():
    col = getEmptyCol()

    tagged = _add_due_card(col, "tagged", "domain::1")
    _add_due_card(col, "untagged", "unrelated")

    # Only the tagged card matches; default_weight keeps the other in the queue.
    entries = col._backend.get_points_at_stake_queue(
        topic_weights={"domain::1": 0.8},
        default_weight=0.2,
        limit=1,
    )

    assert len(entries) == 1, "limit caps the queue length"
    assert entries[0].card_id == tagged
