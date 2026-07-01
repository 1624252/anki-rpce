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

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# Qt stylesheet for RPCE dialogs, matching the Deep Blue web theme (no gray).
_DIALOG_QSS = (
    "QDialog{background:#0a1a3a}"
    "QLabel{color:#cfe2fb;font-size:17px}"
    "QTextBrowser,QTextEdit{background:#0a1c3d;color:#f5f9ff;border:1px solid #1e3f77;"
    "border-radius:12px;font-size:17px;padding:12px}"
    "QPushButton{background:#1d4ed8;color:#fff;border:none;border-radius:12px;"
    "padding:12px 20px;font-size:16px;font-weight:700}"
    "QPushButton:hover{background:#3b82f6}"
)

# App-wide Qt stylesheet appended to Anki's own dark theme so *every* dialog
# (including the AnkiWeb Sync login prompt, which we don't own) fits the Deep
# Blue theme: navy surfaces, white/light-blue readable text, large blue buttons.
_APP_QSS = (
    "QMainWindow,QDialog,QMessageBox,QInputDialog{background:#0a1a3a}"
    "QLabel,QCheckBox,QRadioButton,QGroupBox{color:#eaf2ff;font-size:15px}"
    "QLineEdit,QTextEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QComboBox{"
    "background:#0a1c3d;color:#f5f9ff;border:1px solid #1e3f77;border-radius:10px;"
    "padding:8px 11px;font-size:15px;selection-background-color:#1d4ed8}"
    "QPushButton{background:#1d4ed8;color:#ffffff;border:none;border-radius:10px;"
    "padding:10px 20px;font-size:15px;font-weight:700;min-height:20px;min-width:84px}"
    "QPushButton:hover{background:#3b82f6}"
    "QPushButton:disabled{background:#23407a;color:#9ec3f0}"
)

# Injected into the reviewer (study) webview so flashcards share the Deep Blue
# theme of the practice screen: navy background, white text, sky-blue links/cloze.
_REVIEWER_CSS = (
    "<style>"
    # Solid navy (no gradient) — a subtle gradient bands visibly across the tall
    # reviewer area.
    "html,body{background:#0a1a3a !important;color:#f5f9ff !important}"
    ".card{background:transparent !important;background-color:transparent !important;"
    "color:#f5f9ff !important}"
    "hr{border:none;border-top:1px solid #1e3f77 !important}"
    "a{color:#7dd3fc !important}"
    ".cloze,.cloze b{color:#60a5fa !important;font-weight:700}"
    "</style>"
)

# Navy background for the reviewer's answer-button bar so the whole study screen
# is one theme.
_REVIEWER_BOTTOM_CSS = "<style>body,#innertable{background:#0a1a3a !important}</style>"

# One cohesive "Deep Blue" theme (dark navy + white, blue->sky accents),
# driven by CSS design tokens so the home banner and dashboard stay consistent.
# See docs/rpce/UI_DESIGN.md.
_THEME_CSS = (
    ":root{"
    "--ink:#f5f9ff;--ink2:#9ec3f0;--muted:#7dd3fc;"
    "--ready:#4ade80;--mid:#60a5fa;--warn:#fbbf24;"
    "--surface:#0e2144;--surface2:#12294f;--track:#0a1c3d;"
    "--border:#1e3f77;--accent1:#1d4ed8;--accent2:#3b82f6;"
    "--fs-display:42px;--fs-h1:30px;--fs-h2:22px;--fs-lead:18px;"
    "--fs-body:17px;--fs-small:15px;--fs-label:13px}"
    # Full-page darker-navy background (solid blues, no gray).
    "html,body{background:"
    "radial-gradient(1200px 760px at 12% -12%,rgba(29,78,216,.30),rgba(5,12,28,0) 60%),"
    "linear-gradient(160deg,#050c1c 0%,#0a1a3a 55%,#050c1c 100%) !important;"
    "color:var(--ink) !important}"
    ".rpce-root{font-family:" + _FONT + ";color:var(--ink);font-size:var(--fs-body)}"
    ".rpce-hero{max-width:1060px;margin:44px auto 18px;padding:42px 46px;border-radius:26px;"
    "border:1px solid var(--border);box-shadow:0 24px 64px rgba(2,8,24,.75);"
    "background:radial-gradient(120% 140% at 0% 0%,rgba(29,78,216,.34),rgba(59,130,246,.10) 52%,rgba(8,18,40,0) 100%),"
    "var(--surface)}"
    ".rpce-head{display:flex;flex-direction:column;align-items:center;text-align:center;gap:14px}"
    ".rpce-logo{width:62px;height:62px;border-radius:18px;display:flex;align-items:center;"
    "justify-content:center;font-weight:800;font-size:24px;color:#fff;"
    "background:linear-gradient(135deg,var(--accent1),var(--accent2));box-shadow:0 10px 26px rgba(29,78,216,.7)}"
    ".rpce-h1{font-size:var(--fs-h1);font-weight:800;letter-spacing:-.4px;color:var(--ink)}"
    ".rpce-h1 small{color:var(--ink2);font-weight:600;font-size:var(--fs-lead)}"
    ".rpce-sub{color:var(--ink2);font-size:var(--fs-lead);max-width:60ch;margin-left:auto;margin-right:auto}"
    ".rpce-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px;margin-top:34px}"
    ".rpce-card{background:var(--surface2);border:1px solid var(--border);border-radius:20px;"
    "padding:26px 22px;box-shadow:0 6px 22px rgba(2,8,24,.5);text-align:center;"
    "display:flex;flex-direction:column;align-items:center}"
    ".rpce-label{font-size:var(--fs-label);font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--ink2)}"
    ".rpce-val{font-size:var(--fs-display);font-weight:800;margin:14px 0 16px;line-height:1.02;letter-spacing:-.6px;color:var(--ink)}"
    ".rpce-pill{display:inline-block;font-size:var(--fs-label);font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:5px 13px;border-radius:999px}"
    ".rpce-bar{height:9px;width:100%;border-radius:999px;background:var(--track);margin-top:18px;overflow:hidden}"
    ".rpce-bar>i{display:block;height:100%;border-radius:999px;background:currentColor}"
    ".rpce-cf-abstain{color:var(--muted)}.rpce-pill.rpce-cf-abstain{background:rgba(125,211,252,.18)}"
    ".rpce-cf-low{color:var(--warn)}.rpce-pill.rpce-cf-low{background:rgba(251,191,36,.20)}"
    ".rpce-cf-medium{color:var(--mid)}.rpce-pill.rpce-cf-medium{background:rgba(96,165,250,.22)}"
    ".rpce-cf-high{color:var(--ready)}.rpce-pill.rpce-cf-high{background:rgba(74,222,128,.20)}"
    ".rpce-covhead{display:flex;justify-content:space-between;font-size:var(--fs-small);margin:28px 0 10px;color:var(--ink2)}"
    ".rpce-covhead b{font-weight:700;letter-spacing:.4px;text-transform:uppercase}"
    ".rpce-cov{height:14px;border-radius:999px;background:var(--track);overflow:hidden}"
    ".rpce-cov>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent1),var(--accent2))}"
    ".rpce-chips{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-top:24px}"
    ".rpce-chip{display:inline-flex;align-items:center;gap:7px;font-size:var(--fs-body);color:var(--ink);"
    "background:rgba(37,99,235,.20);border:1px solid var(--border);padding:10px 16px;border-radius:999px}"
    ".rpce-note{margin-top:22px;font-size:var(--fs-body);color:#fcd34d;background:rgba(29,78,216,.16);"
    "border:1px solid var(--border);border-left:4px solid var(--warn);border-radius:12px;padding:15px 18px}"
    ".rpce-foot{margin-top:26px;text-align:center;font-size:var(--fs-small);color:var(--ink2)}.rpce-foot b{color:var(--ink)}"
    ".rpce-tbl{border-collapse:collapse;width:100%;font-size:var(--fs-body)}"
    ".rpce-tbl th{color:var(--ink2);font-size:var(--fs-label);text-transform:uppercase;letter-spacing:.5px;"
    "text-align:left;padding:12px 14px;border-bottom:2px solid var(--border)}"
    ".rpce-tbl td{padding:13px 14px;border-bottom:1px solid rgba(30,63,119,.7)}"
    ".rpce-colbar{height:9px;width:150px;border-radius:999px;background:var(--track);overflow:hidden}"
    ".rpce-colbar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent1),var(--accent2))}"
)


def _theme_style() -> str:
    return f"<style>{_THEME_CSS}</style>"


def _fmt_range(point: float | None, low: float | None, high: float | None) -> str:
    if point is None:
        return "—"
    if low is None or high is None:
        return f"{point:.0%}"
    return f"{point:.0%} (range {low:.0%}–{high:.0%})"


def _score_card(
    label: str, value: str, confidence: str, fill: float | None = None
) -> str:
    """A themed score card: label, big value, confidence pill, optional bar."""
    cf = f"rpce-cf-{confidence}"
    bar = ""
    if fill is not None:
        pct = max(0.0, min(100.0, fill * 100))
        bar = (
            f"<div class='rpce-bar'><i class='{cf}' style='width:{pct:.0f}%'></i></div>"
        )
    # Centered, stacked card: label, big value, confidence pill, optional bar.
    return (
        "<div class='rpce-card'>"
        f"<div class='rpce-label'>{label}</div>"
        f"<div class='rpce-val'>{value}</div>"
        f"<span class='rpce-pill {cf}'>{confidence}</span>"
        f"{bar}</div>"
    )


def _chip(text: str) -> str:
    return f"<span class='rpce-chip'>{text}</span>"


def _timer_chip(col) -> str:
    from anki.rpce import timed

    status = timed.active_session(col)
    if status is None:
        return ""
    if status.expired:
        return _chip(f"⏱ Section {status.section} time is up")
    return _chip(
        f"⏱ Section {status.section}: <b>{timed.format_hms(status.remaining_secs)}</b> left"
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
            "<div class='rpce-note'>"
            f"⚠ Readiness stays hidden until there's enough data — {sec1.evidence}</div>"
        )
    from anki.rpce import progression

    phase = progression.current_phase(col)
    chips = _chip(f"📈 Phase: <b>{phase.title}</b> — {phase.focus}")
    if sec1.best_next_topic:
        chips += _chip(f"🎯 Next: <b>{sec1.best_next_topic}</b>")
    chips += _timer_chip(col)
    chips_row = f"<div class='rpce-chips'>{chips}</div>" if chips else ""
    return f"""{_theme_style()}
<div class="rpce-root"><div class="rpce-hero">
  <div class="rpce-head">
    <div class="rpce-logo">RP</div>
    <div>
      <div class="rpce-h1">Speedrun <small>for the RPCE</small></div>
      <div class="rpce-sub">Registered Parliamentarian Credentialing Exam · pass each section ≥ 80%</div>
    </div>
  </div>
  <div class="rpce-grid">{cards}</div>
  <div class="rpce-covhead"><b>Domain coverage</b><span>{pct:.0%} of {total} domains</span></div>
  <div class="rpce-cov"><i style="width:{pct * 100:.0f}%"></i></div>
  {chips_row}
  {note}
  <div class="rpce-foot">Use the tabs above — <b>Study</b> flashcards, practice
    <b>Section II</b>, open the <b>Dashboard</b>, or start a <b>Timed</b> session.</div>
</div></div>
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

    def cov_bar(weight: float) -> str:
        return f"<div class='rpce-colbar'><i style='width:{min(100, weight * 200):.0f}%'></i></div>"

    cov_rows = "".join(
        "<tr>"
        f"<td>{c.code}. {c.name}</td>"
        f"<td style='text-align:center'>{c.cards}</td>"
        f"<td>{cov_bar(c.weight)}</td></tr>"
        for c in s["coverage"]
    )
    next_topic = (
        f"<p class='rpce-sub'>🎯 <b style='color:var(--ink)'>Best next topic:</b> {sec1.best_next_topic}</p>"
        if sec1.best_next_topic
        else ""
    )
    return f"""{_theme_style()}
<div class="rpce-root" style="max-width:900px;margin:0 auto;padding:20px 12px">
  <div style="text-align:center">
    <div class="rpce-h1">RPCE readiness</div>
    <div class="rpce-sub" style="margin-top:8px">Three scores, each with a range — and an honest abstain when the data is thin.</div>
  </div>
  <div class="rpce-grid">{cards}</div>
  <div style="text-align:center;margin-top:26px">
    <p class="rpce-sub"><b style="color:var(--ink)">Why:</b> {sec1.evidence}</p>
    {next_topic}
  </div>
  <div class="rpce-h1" style="font-size:var(--fs-h2);margin:34px 0 12px">Coverage map
    <small>· 7 Performance-Expectation domains</small></div>
  <table class="rpce-tbl">
    <tr><th>Domain</th><th style="text-align:center">Cards</th><th>Exam weight</th></tr>
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
    dialog.setStyleSheet(_DIALOG_QSS)
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
        self.resize(720, 660)
        self.setStyleSheet(_DIALOG_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)
        heading = QLabel("Section II — performance scenario")
        heading.setStyleSheet("font-size:24px;font-weight:800;color:#f5f9ff")
        layout.addWidget(heading)
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


def _apply_dark_theme() -> None:
    """Lock the app to a single dark theme (no light/follow-system mode) so the
    whole UI — menus, dialogs, and the Sync prompt — stays dark blue + white."""
    mw = aqt.mw
    if mw is None:
        return
    try:
        from aqt.theme import Theme, theme_manager

        if mw.pm.theme() != Theme.DARK:
            mw.pm.set_theme(Theme.DARK)
        theme_manager.apply_style()
    except Exception as exc:  # never block startup over theming
        print(f"RPCE theme error: {exc}")


def _on_style_init(style: str) -> str:
    """Append the Deep Blue app stylesheet after Anki's own theme so it wins."""
    return style + _APP_QSS


def _on_webview_content(web_content, context) -> None:
    """Theme the study/reviewer webviews to match the navy practice screen."""
    try:
        from aqt.reviewer import Reviewer, ReviewerBottomBar

        if isinstance(context, Reviewer):
            web_content.head += _REVIEWER_CSS
        elif isinstance(context, ReviewerBottomBar):
            web_content.head += _REVIEWER_BOTTOM_CSS
    except Exception as exc:  # never break reviewing over theming
        print(f"RPCE reviewer-theme error: {exc}")


def _on_profile_open() -> None:
    """Brand the window and make sure the RPCE deck exists and is selected."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    mw.setWindowTitle(APP_TITLE)
    _apply_dark_theme()
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
    """Replace the deck-browser home with the RPCE landing page (no deck
    management UI — the deck is generated for the candidate)."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    try:
        content.tree = _banner_html(mw.col)
        content.stats = ""
        # Hide Anki's gray deck-browser bottom bar (Get Shared / Create Deck /
        # Import File) — not part of the RPCE flow.
        mw.bottomWeb.hide()
    except Exception as exc:  # never break the deck browser over the banner
        print(f"RPCE home error: {exc}")


def _on_deck_browser_did_render(deck_browser) -> None:
    """The deck browser re-shows its bottom bar (Get Shared / Create Deck /
    Import File) as the last render step — hide it again here so it stays gone."""
    mw = aqt.mw
    if mw is None:
        return
    try:
        mw.bottomWeb.hide()
    except Exception as exc:
        print(f"RPCE bottom-bar error: {exc}")


def _on_state_change(new_state, old_state) -> None:
    """Hide Anki's bottom bar on the home and deck-overview screens (Options /
    Custom Study / Description aren't part of the RPCE flow); keep it for the
    reviewer, which needs the answer buttons."""
    mw = aqt.mw
    if mw is None:
        return
    try:
        if new_state in ("deckBrowser", "overview"):
            mw.bottomWeb.hide()
        else:
            mw.bottomWeb.show()
    except Exception as exc:
        print(f"RPCE bottom-bar error: {exc}")


# Toolbar tabs
######################################################################


def _select_rpce_deck() -> bool:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return False
    deck = mw.col.decks.by_name("RPCE")
    if deck is None:
        from anki.rpce import build_starter_deck

        build_starter_deck(mw.col)
        deck = mw.col.decks.by_name("RPCE")
    if deck is None:
        return False
    mw.col.decks.select(deck["id"])
    return True


def _tab_study() -> None:
    mw = aqt.mw
    if mw is None or not _select_rpce_deck():
        return
    mw.moveToState("overview")


def _tab_timed() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    from anki.rpce import timed

    if timed.active_session(mw.col):
        timed.clear_session(mw.col)
        tooltip("Timed session stopped.")
    else:
        timed.start_session(mw.col, "I")
        tooltip("Started timed Section I (3-hour limit).")
    mw.reset()


_TOOLBAR_CSS = (
    "<style>"
    "body{background:#050c1c !important}"
    ".header{background:linear-gradient(90deg,#081633,#0c2149) !important;"
    "border-bottom:1px solid #1e3f77 !important;padding:10px 8px !important}"
    ".hitem{font-size:16px !important;font-weight:800 !important;color:#ffffff !important;"
    "padding:10px 20px !important;margin:0 5px !important;border-radius:12px !important;text-decoration:none !important;"
    "background:linear-gradient(135deg,#1d4ed8,#3b82f6) !important;border:1px solid #3b82f6 !important;"
    "box-shadow:0 4px 14px rgba(29,78,216,.45) !important}"
    ".hitem:hover{background:linear-gradient(135deg,#2563eb,#60a5fa) !important;"
    "color:#fff !important;border-color:#7dd3fc !important}"
    "</style>"
)


def _on_toolbar_links(links, toolbar) -> None:
    """Replace Anki's deck-management toolbar with themed RPCE tabs (keep Sync)."""
    sync_link = links[-1] if links else None
    links.clear()
    links.append(_TOOLBAR_CSS)
    links.append(
        toolbar.create_link(
            "rpce_study",
            "Study",
            _tab_study,
            tip="Study RPCE flashcards",
            id="rpce_study",
        )
    )
    links.append(
        toolbar.create_link(
            "rpce_scenarios",
            "Section II",
            _show_scenarios,
            tip="Performance scenario practice",
            id="rpce_scenarios",
        )
    )
    links.append(
        toolbar.create_link(
            "rpce_dashboard",
            "Dashboard",
            _show_dashboard,
            tip="Readiness dashboard",
            id="rpce_dashboard",
        )
    )
    links.append(
        toolbar.create_link(
            "rpce_timed",
            "Timed",
            _tab_timed,
            tip="Start/stop a 3-hour timed session",
            id="rpce_timed",
        )
    )
    if sync_link is not None:
        links.append(sync_link)


def setup() -> None:
    """Register all RPCE desktop integration hooks."""
    gui_hooks.style_did_init.append(_on_style_init)
    gui_hooks.webview_will_set_content.append(_on_webview_content)
    gui_hooks.main_window_did_init.append(_add_menu)
    gui_hooks.profile_did_open.append(_on_profile_open)
    gui_hooks.deck_browser_will_render_content.append(_on_deck_browser_content)
    gui_hooks.deck_browser_did_render.append(_on_deck_browser_did_render)
    gui_hooks.reviewer_did_answer_card.append(_on_answer_card)
    gui_hooks.top_toolbar_did_init_links.append(_on_toolbar_links)
    gui_hooks.state_did_change.append(_on_state_change)
