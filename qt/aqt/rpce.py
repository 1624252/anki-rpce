# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Desktop integration for the RPCE study app.

Adds an **RPCE** menu to the main window with:

- *Build starter deck* — seeds the seven-domain RPCE deck, and
- *Readiness dashboard…* — shows the three honest scores (memory, performance,
  readiness per section) each with a range, the coverage map, the best next
  topic, and the **abstain** state when there isn't enough data yet.

Wired from ``aqt.__init__._run`` via ``main_window_did_init`` so it adds nothing
to the hot path and is easy to remove for an upstream merge.
"""

from __future__ import annotations

import aqt
from aqt import gui_hooks
from aqt.qt import QMenu, qconnect
from aqt.utils import showInfo, tooltip


def _fmt_range(point: float | None, low: float | None, high: float | None) -> str:
    if point is None:
        return "—"
    if low is None or high is None:
        return f"{point:.0%}"
    return f"{point:.0%} (range {low:.0%}–{high:.0%})"


def _readiness_html(col) -> str:
    from anki.rpce import scores

    summary = scores.readiness_summary(col)
    mem = summary["memory"]
    perf = summary["performance"]
    rows = [
        "<h2>RPCE readiness</h2>",
        "<table cellpadding=6 style='border-collapse:collapse'>",
        "<tr><th align=left>Score</th><th align=left>Value</th><th align=left>Confidence</th></tr>",
        f"<tr><td>Memory</td><td>{_fmt_range(mem.point, mem.low, mem.high)}</td><td>{mem.confidence}</td></tr>",
        f"<tr><td>Performance</td><td>{_fmt_range(perf.point, perf.low, perf.high)}</td><td>{perf.confidence}</td></tr>",
    ]
    for key, label in (
        ("section_I", "Readiness — Section I"),
        ("section_II", "Readiness — Section II"),
    ):
        snap = summary[key]
        value = (
            "Abstaining"
            if snap.abstained
            else _fmt_range(snap.p_pass, snap.range_low, snap.range_high)
        )
        rows.append(
            f"<tr><td>{label}</td><td>{value}</td><td>{snap.confidence}</td></tr>"
        )
    rows.append("</table>")

    # Honesty payload: evidence + what's missing + best next topic.
    sec1 = summary["section_I"]
    rows.append(f"<p><b>Why:</b> {sec1.evidence}</p>")
    if sec1.best_next_topic:
        rows.append(f"<p><b>Best next topic:</b> {sec1.best_next_topic}</p>")

    # Coverage map.
    rows.append("<h3>Coverage map (7 domains)</h3>")
    rows.append("<table cellpadding=4 style='border-collapse:collapse'>")
    rows.append("<tr><th align=left>Domain</th><th>Cards</th><th>Weight</th></tr>")
    for c in summary["coverage"]:
        rows.append(
            f"<tr><td>{c.code}. {c.name}</td><td align=center>{c.cards}</td><td align=center>{c.weight:.2f}</td></tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def _build_deck() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    from anki.rpce import build_starter_deck

    build_starter_deck(mw.col)
    mw.reset()
    tooltip("Built the RPCE starter deck (7 domains).")


def _show_dashboard() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    showInfo(_readiness_html(mw.col), title="RPCE", textFormat="rich")


def _add_menu() -> None:
    mw = aqt.mw
    if mw is None:
        return
    menu = QMenu("&RPCE", mw)
    mw.form.menubar.insertMenu(mw.form.menuHelp.menuAction(), menu)
    build_action = menu.addAction("Build starter deck")
    qconnect(build_action.triggered, _build_deck)
    dash_action = menu.addAction("Readiness dashboard…")
    qconnect(dash_action.triggered, _show_dashboard)


def setup() -> None:
    """Register the RPCE menu to be added once the main window is initialized."""
    gui_hooks.main_window_did_init.append(_add_menu)
