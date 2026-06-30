# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for timed practice (3-hour section limit)."""

import pytest

from anki.rpce import timed
from tests.shared import getEmptyCol


def test_no_session_by_default():
    col = getEmptyCol()
    assert timed.active_session(col) is None


def test_session_tracks_remaining_time():
    col = getEmptyCol()
    timed.start_session(col, "I", now=1000)
    status = timed.active_session(col, now=1000 + 600)  # 10 minutes in
    assert status is not None
    assert status.section == "I"
    assert status.elapsed_secs == 600
    assert status.remaining_secs == 3 * 3600 - 600
    assert status.expired is False


def test_session_expires_after_three_hours():
    col = getEmptyCol()
    timed.start_session(col, "II", now=0)
    status = timed.active_session(col, now=3 * 3600 + 1)
    assert status.expired is True
    assert status.remaining_secs == 0


def test_clear_session():
    col = getEmptyCol()
    timed.start_session(col, "I", now=0)
    timed.clear_session(col)
    assert timed.active_session(col) is None


def test_start_session_rejects_unknown_section():
    col = getEmptyCol()
    with pytest.raises(ValueError):
        timed.start_session(col, "III")


def test_format_hms():
    assert timed.format_hms(3 * 3600) == "3:00:00"
    assert timed.format_hms(125) == "0:02:05"
    assert timed.format_hms(-5) == "0:00:00"
