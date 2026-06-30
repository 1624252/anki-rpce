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
from aqt.utils import tooltip
from aqt.webview import AnkiWebView


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

# Confidence -> accent colour (modern palette).
_CONF_COLOR = {
    "abstain": "#94a3b8",  # slate
    "low": "#f59e0b",  # amber
    "medium": "#10b981",  # emerald
    "high": "#3b82f6",  # blue
}

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _fmt_range(point: float | None, low: float | None, high: float | None) -> str:
    if point is None:
        return "—"
    if low is None or high is None:
        return f"{point:.0%}"
    return f"{point:.0%} (range {low:.0%}–{high:.0%})"


def _score_card(
    label: str, value: str, confidence: str, fill: float | None = None
) -> str:
    """A modern score card: label, big value, confidence pill, optional bar."""
    color = _CONF_COLOR.get(confidence, "#94a3b8")
    bar = ""
    if fill is not None:
        pct = max(0.0, min(100.0, fill * 100))
        bar = (
            "<div style='height:6px;border-radius:999px;background:rgba(148,163,184,.18);"
            "margin-top:16px;overflow:hidden'>"
            f"<div style='height:100%;width:{pct:.0f}%;background:{color};border-radius:999px'></div></div>"
        )
    return (
        "<div style='background:rgba(148,163,184,.06);border:1px solid rgba(148,163,184,.16);"
        "border-radius:18px;padding:20px 22px;box-shadow:0 1px 2px rgba(0,0,0,.25)'>"
        "<div style='display:flex;justify-content:space-between;align-items:center;gap:8px'>"
        f"<span style='font-size:12px;font-weight:600;letter-spacing:.7px;text-transform:uppercase;color:#94a3b8'>{label}</span>"
        f"<span style='font-size:10.5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;"
        f"color:{color};background:{color}26;padding:3px 9px;border-radius:999px'>{confidence}</span></div>"
        f"<div style='font-size:38px;font-weight:800;margin-top:10px;line-height:1.05;letter-spacing:-.5px'>{value}</div>"
        f"{bar}</div>"
    )


def _chip(text: str, color: str = "#cbd5e1") -> str:
    return (
        f"<span style='display:inline-flex;align-items:center;gap:6px;font-size:13.5px;"
        f"background:rgba(148,163,184,.10);border:1px solid rgba(148,163,184,.18);"
        f"color:{color};padding:6px 12px;border-radius:999px'>{text}</span>"
    )


def _timer_chip(col) -> str:
    from anki.rpce import timed

    status = timed.active_session(col)
    if status is None:
        return ""
    if status.expired:
        return _chip(f"⏱ Section {status.section} time is up", "#f87171")
    return _chip(
        f"⏱ Section {status.section}: <b>{timed.format_hms(status.remaining_secs)}</b> left",
        "#60a5fa",
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

    cards = "".join(
        [
            _score_card(
                "Memory", _fmt_range(mem.point, None, None), mem.confidence, mem.point
            ),
            _score_card(
                "Performance",
                _fmt_range(perf.point, None, None),
                perf.confidence,
                perf.point,
            ),
            _score_card(
                "Pass Section I",
                section_value(sec1),
                sec1.confidence,
                None if sec1.abstained else sec1.p_pass,
            ),
            _score_card(
                "Pass Section II",
                section_value(sec2),
                sec2.confidence,
                None if sec2.abstained else sec2.p_pass,
            ),
        ]
    )
    note = ""
    if sec1.abstained or sec2.abstained:
        note = (
            "<div style='margin-top:16px;font-size:14px;color:#fbbf24;"
            "background:rgba(245,158,11,.10);border:1px solid rgba(245,158,11,.28);"
            "border-radius:12px;padding:12px 16px'>"
            f"⚠ Readiness stays hidden until there's enough data — {sec1.evidence}</div>"
        )
    from anki.rpce import progression

    phase = progression.current_phase(col)
    _phase_color = {
        "foundations": "#60a5fa",
        "application": "#34d399",
        "mastery": "#a78bfa",
    }
    chips = _chip(
        f"📈 Phase: <b>{phase.title}</b> — {phase.focus}",
        _phase_color.get(phase.key, "#cbd5e1"),
    )
    if sec1.best_next_topic:
        chips += _chip(f"🎯 Next: <b>{sec1.best_next_topic}</b>")
    chips += _timer_chip(col)
    chips_row = (
        f"<div style='display:flex;flex-wrap:wrap;gap:10px;margin-top:18px'>{chips}</div>"
        if chips
        else ""
    )
    coverage_bar = f"""
  <div style="margin-top:22px">
    <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:8px;color:#94a3b8">
      <span style="font-weight:600;letter-spacing:.4px;text-transform:uppercase">Domain coverage</span>
      <span>{pct:.0%} of {total} domains</span>
    </div>
    <div style="height:10px;border-radius:999px;background:rgba(148,163,184,.18);overflow:hidden">
      <div style="height:100%;width:{pct * 100:.0f}%;border-radius:999px;
                  background:linear-gradient(90deg,#3b82f6,#10b981)"></div>
    </div>
  </div>"""
    return f"""
<div style="font-family:{_FONT};max-width:980px;margin:28px auto 12px;padding:30px 32px;
            border-radius:24px;border:1px solid rgba(148,163,184,.16);
            box-shadow:0 10px 34px rgba(0,0,0,.28);
            background:radial-gradient(130% 150% at 0% 0%, rgba(59,130,246,.18),
                       rgba(16,185,129,.05) 55%, rgba(2,6,23,0) 100%), rgba(148,163,184,.05)">
  <div style="display:flex;align-items:center;gap:14px">
    <div style="width:46px;height:46px;border-radius:14px;display:flex;align-items:center;
                justify-content:center;font-weight:800;font-size:17px;color:#fff;
                background:linear-gradient(135deg,#3b82f6,#10b981);
                box-shadow:0 6px 16px rgba(59,130,246,.45)">RP</div>
    <div>
      <div style="font-size:25px;font-weight:800;letter-spacing:-.3px">Speedrun
        <span style="opacity:.5;font-weight:600">for the RPCE</span></div>
      <div style="opacity:.6;font-size:13.5px">Registered Parliamentarian Credentialing Exam · pass each section ≥ 80%</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:22px">{cards}</div>
  {coverage_bar}
  {chips_row}
  {note}
  <div style="margin-top:18px;font-size:13px;color:#94a3b8">Use the
    <b style="color:#cbd5e1">RPCE</b> menu for the dashboard, Section II practice, and timed sessions.</div>
</div>
"""


def _readiness_html(col) -> str:
    from anki.rpce import scores

    s = scores.readiness_summary(col)
    mem, perf = s["memory"], s["performance"]
    sec1, sec2 = s["section_I"], s["section_II"]

    def secval(snap) -> str:
        return (
            "Abstaining"
            if snap.abstained
            else _fmt_range(snap.p_pass, snap.range_low, snap.range_high)
        )

    cards = "".join(
        [
            _score_card(
                "Memory",
                _fmt_range(mem.point, mem.low, mem.high),
                mem.confidence,
                mem.point,
            ),
            _score_card(
                "Performance",
                _fmt_range(perf.point, perf.low, perf.high),
                perf.confidence,
                perf.point,
            ),
            _score_card(
                "Pass Section I",
                secval(sec1),
                sec1.confidence,
                None if sec1.abstained else sec1.p_pass,
            ),
            _score_card(
                "Pass Section II",
                secval(sec2),
                sec2.confidence,
                None if sec2.abstained else sec2.p_pass,
            ),
        ]
    )

    def cov_bar(weight: float, has_cards: bool) -> str:
        color = "#10b981" if has_cards else "#475569"
        return (
            "<div style='height:6px;width:120px;border-radius:999px;background:rgba(148,163,184,.18);overflow:hidden'>"
            f"<div style='height:100%;width:{min(100, weight * 200):.0f}%;background:{color};border-radius:999px'></div></div>"
        )

    cov_rows = "".join(
        "<tr style='border-bottom:1px solid rgba(148,163,184,.12)'>"
        f"<td style='padding:11px 12px'>{c.code}. {c.name}</td>"
        f"<td style='padding:11px 12px;text-align:center;color:{'#e2e8f0' if c.cards else '#64748b'}'>{c.cards}</td>"
        f"<td style='padding:11px 12px'>{cov_bar(c.weight, c.cards > 0)}</td></tr>"
        for c in s["coverage"]
    )
    next_topic = (
        f"<p style='font-size:15px;color:#cbd5e1'>🎯 <b>Best next topic:</b> {sec1.best_next_topic}</p>"
        if sec1.best_next_topic
        else ""
    )
    return f"""
<div style="font-family:{_FONT};max-width:900px;margin:0 auto;padding:14px 10px;color:#e2e8f0">
  <div style="font-size:28px;font-weight:800;letter-spacing:-.3px">RPCE readiness</div>
  <div style="opacity:.6;margin-bottom:22px;font-size:15px">Three scores, each with a range — and an honest abstain when the data is thin.</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px">{cards}</div>
  <p style="font-size:15px;margin-top:22px;color:#94a3b8"><b style="color:#cbd5e1">Why:</b> {sec1.evidence}</p>
  {next_topic}
  <div style="font-size:18px;font-weight:700;margin:26px 0 12px">Coverage map
    <span style="font-weight:500;color:#94a3b8;font-size:14px">· 7 Performance-Expectation domains</span></div>
  <table style="border-collapse:collapse;width:100%;font-size:14.5px">
    <tr style="border-bottom:2px solid rgba(148,163,184,.25);color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.5px">
      <th style="text-align:left;padding:10px 12px">Domain</th>
      <th style="padding:10px 12px;text-align:center">Cards</th>
      <th style="text-align:left;padding:10px 12px">Exam weight</th>
    </tr>
    {cov_rows}
  </table>
</div>
"""


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
    dialog = QDialog(mw)
    dialog.setWindowTitle("RPCE readiness")
    dialog.resize(900, 760)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(0, 0, 0, 0)
    web = AnkiWebView(title="rpce-dashboard")
    web.stdHtml(_readiness_html(mw.col))
    layout.addWidget(web)
    close = QPushButton("Close")
    qconnect(close.clicked, dialog.accept)
    layout.addWidget(close)
    dialog.exec()
    web.cleanup()


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
        # Placeholder grader for now — no AI API calls yet (swap in the LLM
        # examiner later without changing this screen).
        result = examiner.PlaceholderExaminer().grade(
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


def _start_timer(section: str) -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    from anki.rpce import timed

    timed.start_session(mw.col, section)
    mw.reset()
    tooltip(f"Started timed Section {section} (3-hour limit).")


def _stop_timer() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    from anki.rpce import timed

    timed.clear_session(mw.col)
    mw.reset()
    tooltip("Stopped the practice timer.")


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
    menu.addSeparator()
    timer_menu = menu.addMenu("Timed practice")
    t1 = timer_menu.addAction("Start Section I (3h)")
    qconnect(t1.triggered, lambda: _start_timer("I"))
    t2 = timer_menu.addAction("Start Section II (3h)")
    qconnect(t2.triggered, lambda: _start_timer("II"))
    t3 = timer_menu.addAction("Stop timer")
    qconnect(t3.triggered, _stop_timer)


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


def _on_answer_card(reviewer, card, ease) -> None:
    """Tally each review by its Transfer-Ladder format rung."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    try:
        from anki.rpce import transfer_ladder

        transfer_ladder.record_review(mw.col, card.note().tags)
    except Exception as exc:  # never break reviewing over the tally
        print(f"RPCE format-tally error: {exc}")


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
    gui_hooks.reviewer_did_answer_card.append(_on_answer_card)
