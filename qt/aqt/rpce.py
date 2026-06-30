# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Desktop integration that makes RPCE the focus of the app.

- Rebrands the window to **Speedrun for the RPCE**.
- Puts an **RPCE readiness banner** at the top of the main screen (deck browser):
  the three honest scores, coverage, best-next-topic, and the abstain state.
- Auto-creates and selects the RPCE deck on first open.
- Adds an **RPCE** menu (*Build starter deck*, *Readiness dashboard…*).

Wired from ``aqt.__init__._run`` via hooks so it adds nothing to the hot path
and is easy to remove for an upstream merge.
"""

from __future__ import annotations

import os

import aqt
from aqt import gui_hooks
from aqt.qt import (
    QDialog,
    QLabel,
    QMenu,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import showInfo, tooltip


def _load_corpus() -> str:
    """Load the transcribed RONR 12th-ed. corpus if present (for citations)."""
    for path in (
        "data/roberts_rules_of_order_12th_edition.md",
        os.path.join(
            os.path.dirname(__file__), "data", "roberts_rules_of_order_12th_edition.md"
        ),
    ):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                pass
    return ""


APP_TITLE = "Speedrun for the RPCE"

# Confidence -> accent colour for the badges.
_CONF_COLOR = {
    "abstain": "#8b949e",
    "low": "#d29922",
    "medium": "#3fb950",
    "high": "#2f81f7",
}


def _fmt_range(point: float | None, low: float | None, high: float | None) -> str:
    if point is None:
        return "—"
    if low is None or high is None:
        return f"{point:.0%}"
    return f"{point:.0%} (range {low:.0%}–{high:.0%})"


def _badge(label: str, value: str, confidence: str) -> str:
    color = _CONF_COLOR.get(confidence, "#8b949e")
    return (
        f"<div style='flex:1;min-width:120px;padding:10px 12px;border-radius:10px;"
        f"background:rgba(127,127,127,.08);border:1px solid {color}55'>"
        f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:.5px;opacity:.7'>{label}</div>"
        f"<div style='font-size:18px;font-weight:700;margin-top:2px'>{value}</div>"
        f"<div style='font-size:11px;color:{color};margin-top:2px'>{confidence}</div>"
        f"</div>"
    )


def _banner_html(col) -> str:
    from anki.rpce import scores

    s = scores.readiness_summary(col)
    mem, perf = s["memory"], s["performance"]
    sec1, sec2 = s["section_I"], s["section_II"]
    covered = sum(1 for c in s["coverage"] if c.cards > 0)
    total = len(s["coverage"])
    pct = covered / total if total else 0.0

    def section_value(snap) -> str:
        return (
            "Abstaining"
            if snap.abstained
            else _fmt_range(snap.p_pass, snap.range_low, snap.range_high)
        )

    badges = "".join(
        [
            _badge("Memory", _fmt_range(mem.point, None, None), mem.confidence),
            _badge("Performance", _fmt_range(perf.point, None, None), perf.confidence),
            _badge("Pass Section I", section_value(sec1), sec1.confidence),
            _badge("Pass Section II", section_value(sec2), sec2.confidence),
        ]
    )
    note = ""
    if sec1.abstained or sec2.abstained:
        note = (
            f"<div style='margin-top:10px;font-size:13px;color:#d29922'>"
            f"⚠ Readiness hidden until there's enough data — {sec1.evidence}</div>"
        )
    next_topic = (
        f"<div style='margin-top:8px;font-size:13px'><b>Best next topic:</b> "
        f"{sec1.best_next_topic}</div>"
        if sec1.best_next_topic
        else ""
    )
    return f"""
<div style="max-width:720px;margin:18px auto 8px;padding:18px 20px;border-radius:14px;
            background:linear-gradient(135deg,rgba(47,129,247,.14),rgba(47,129,247,.03));
            border:1px solid rgba(47,129,247,.35)">
  <div style="font-size:22px;font-weight:800">{APP_TITLE}</div>
  <div style="opacity:.7;margin-bottom:14px">NAP Registered Parliamentarian Credentialing Exam · pass each section ≥ 80%</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">{badges}</div>
  <div style="margin-top:10px;font-size:13px"><b>Coverage:</b> {pct:.0%} of {total} Performance-Expectation domains</div>
  {next_topic}
  {note}
  <div style="margin-top:10px;font-size:12px;opacity:.6">Use the <b>RPCE</b> menu for the full dashboard and to build the deck.</div>
</div>
"""


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


class ScenarioDialog(QDialog):
    """Section II performance practice: read a scenario, write a ruling, and get
    examiner-style feedback graded for accuracy (no citation required)."""

    def __init__(self, mw) -> None:
        super().__init__(mw)
        from anki.rpce import scenarios

        self._mw = mw
        self._corpus = _load_corpus()
        self._scenarios = list(scenarios.all_scenarios())
        self._idx = 0

        self.setWindowTitle("RPCE — Section II scenario practice")
        self.resize(660, 580)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Section II — performance scenario</b>"))
        self._domain = QLabel()
        layout.addWidget(self._domain)
        self._prompt = QTextBrowser()
        self._prompt.setMinimumHeight(90)
        layout.addWidget(self._prompt)
        layout.addWidget(QLabel("Your ruling & reasoning (no RONR citation required):"))
        self._answer = QTextEdit()
        layout.addWidget(self._answer)
        self._grade_btn = QPushButton("Grade my answer")
        qconnect(self._grade_btn.clicked, self._grade)
        layout.addWidget(self._grade_btn)
        self._result = QTextBrowser()
        self._result.setMinimumHeight(140)
        layout.addWidget(self._result)
        self._next_btn = QPushButton("Next scenario →")
        qconnect(self._next_btn.clicked, self._next)
        layout.addWidget(self._next_btn)
        self._load()

    def _load(self) -> None:
        from anki.rpce import domain_by_code

        s = self._scenarios[self._idx]
        d = domain_by_code(s.domain_code)
        self._domain.setText(f"<i>Domain {d.code}: {d.name}</i>")
        self._prompt.setText(s.prompt)
        self._answer.clear()
        self._result.clear()

    def _grade(self) -> None:
        from anki.rpce import examiner, scores

        answer = self._answer.toPlainText().strip()
        if not answer:
            return
        s = self._scenarios[self._idx]
        # Uses the LLM examiner when an API key is configured, else the offline
        # baseline (the app always grades, AI on or off).
        result = examiner.make_examiner().grade(
            answer, s.gold_answer, self._corpus or s.gold_answer
        )
        scores.record_scenario(self._mw.col)
        verdict = "pass" if result.passed else "keep practicing"
        citation = (
            f"<br><b>RONR reference:</b> {result.citation}" if result.citation else ""
        )
        self._result.setHtml(
            f"<div><b>Score:</b> {result.score:.1f}/5 ({verdict})<br>"
            f"<b>Feedback:</b> {result.feedback}{citation}<br><br>"
            f"<b>Model ruling:</b> {s.gold_answer}</div>"
        )

    def _next(self) -> None:
        self._idx = (self._idx + 1) % len(self._scenarios)
        self._load()


def _show_scenarios() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    ScenarioDialog(mw).exec()


def _add_menu() -> None:
    mw = aqt.mw
    if mw is None:
        return
    mw.setWindowTitle(APP_TITLE)
    menu = QMenu("&RPCE", mw)
    mw.form.menubar.insertMenu(mw.form.menuHelp.menuAction(), menu)
    build_action = menu.addAction("Build starter deck")
    qconnect(build_action.triggered, _build_deck)
    scenario_action = menu.addAction("Section II scenario practice…")
    qconnect(scenario_action.triggered, _show_scenarios)
    dash_action = menu.addAction("Readiness dashboard…")
    qconnect(dash_action.triggered, _show_dashboard)


def _on_profile_open() -> None:
    """Brand the window and make sure the RPCE deck exists and is selected."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    mw.setWindowTitle(APP_TITLE)
    if mw.col.decks.by_name("RPCE") is None:
        from anki.rpce import build_starter_deck

        deck_id = build_starter_deck(mw.col)
        mw.col.decks.set_current(deck_id)


def _on_deck_browser_content(deck_browser, content) -> None:
    """Put the RPCE readiness banner at the top of the main screen."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    try:
        content.tree = _banner_html(mw.col) + content.tree
    except Exception as exc:  # never break the deck browser over the banner
        print(f"RPCE banner error: {exc}")


def setup() -> None:
    """Register all RPCE desktop integration hooks."""
    gui_hooks.main_window_did_init.append(_add_menu)
    gui_hooks.profile_did_open.append(_on_profile_open)
    gui_hooks.deck_browser_will_render_content.append(_on_deck_browser_content)
