# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Timed practice that mirrors the RPCE's hard section limit (3 hours each).

The RPCE gives three hours per section, so pacing is a tested skill (spec/PRD
§12). This tracks an optional timed session in the (syncing) collection config:
which section, when it started, and how much time remains. Pure functions take
an injectable ``now`` so the logic is fully testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.collection import Collection

CONFIG_KEY = "rpce:timed_session"

#: Seconds allowed per section (3 hours each).
SECTION_LIMIT_SECS: dict[str, int] = {"I": 3 * 3600, "II": 3 * 3600}


@dataclass
class TimedStatus:
    section: str
    elapsed_secs: int
    remaining_secs: int
    limit_secs: int
    expired: bool


def start_session(col: Collection, section: str, now: float | None = None) -> None:
    if section not in SECTION_LIMIT_SECS:
        raise ValueError(f"unknown section: {section}")
    now = time.time() if now is None else now
    col.set_config(CONFIG_KEY, {"section": section, "start_ts": int(now)})


def clear_session(col: Collection) -> None:
    col.set_config(CONFIG_KEY, None)


def active_session(col: Collection, now: float | None = None) -> TimedStatus | None:
    """Return the current timed session's status, or None if none is active."""
    raw = col.get_config(CONFIG_KEY, None)
    if not isinstance(raw, dict) or "section" not in raw or "start_ts" not in raw:
        return None
    section = raw["section"]
    limit = SECTION_LIMIT_SECS.get(section)
    if limit is None:
        return None
    now = time.time() if now is None else now
    elapsed = max(0, int(now) - int(raw["start_ts"]))
    remaining = max(0, limit - elapsed)
    return TimedStatus(
        section=section,
        elapsed_secs=elapsed,
        remaining_secs=remaining,
        limit_secs=limit,
        expired=elapsed >= limit,
    )


def format_hms(secs: int) -> str:
    """Format seconds as H:MM:SS."""
    h, rem = divmod(max(0, secs), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"
