# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Logout wipe: reset_local_progress must leave no local study results behind,
while keeping the deck itself and forcing a full sync so re-login re-downloads."""

from anki import rpce
from tests.shared import getEmptyCol


def _give_cards_history(col):
    """Put every card into a reviewed state with real revlog rows, so there is
    genuine local progress for the reset to wipe."""
    # Reviewed cards: type/queue = review (2), non-zero reps/lapses/interval.
    col.db.execute(
        "update cards set reps = 3, lapses = 1, queue = 2, type = 2, ivl = 10"
    )
    for i, cid in enumerate(col.find_cards("")):
        col.db.execute(
            "insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, "
            "time, type) values (?,?,?,?,?,?,?,?,?)",
            1_000 + i,
            cid,
            -1,
            3,
            10,
            1,
            2500,
            1000,
            0,
        )


def test_reset_wipes_results_but_keeps_deck():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    n_cards = len(col.find_cards(""))
    assert n_cards > 0
    _give_cards_history(col)
    # Sanity: we actually produced results to wipe.
    assert col.db.scalar("select count() from revlog") > 0
    assert col.db.scalar("select count() from cards where reps > 0") > 0

    rpce.reset_local_progress(col)

    # Deck + cards survive, but every card is back to new with no history.
    assert len(col.find_cards("")) == n_cards
    assert col.db.scalar("select count() from revlog") == 0
    assert col.db.scalar("select count() from cards where reps > 0") == 0
    assert col.db.scalar("select count() from cards where queue != 0") == 0


def test_reset_clears_practice_tallies():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    for key in rpce.RESULT_CONFIG_KEYS:
        col.set_config(key, 42)

    rpce.reset_local_progress(col)

    for key in rpce.RESULT_CONFIG_KEYS:
        assert col.get_config(key, None) is None


def test_reset_forces_full_sync():
    col = getEmptyCol()
    rpce.build_starter_deck(col)
    # Pretend a prior sync happened so schema is "clean" (scm <= ls).
    col.db.execute("update col set ls = scm")
    assert not col.schema_changed()

    rpce.reset_local_progress(col)

    # Bumped schema => next sync is a forced full sync (which the caller steers to
    # a safe download), so the wiped collection never uploads over the account.
    assert col.schema_changed()


def test_reset_on_empty_collection_is_safe():
    col = getEmptyCol()  # no deck built
    rpce.reset_local_progress(col)  # must not raise
    assert col.db.scalar("select count() from revlog") == 0
