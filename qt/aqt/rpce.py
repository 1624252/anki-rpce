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

# One cohesive "Aurora" theme (indigo -> cyan accents on deep indigo), shared by
# the home banner and the dashboard as CSS classes so everything matches.
_THEME_CSS = (
    # Full-page themed background so the whole screen is designed, not a card in a void.
    "html,body{background:"
    "radial-gradient(1200px 720px at 12% -12%,rgba(99,102,241,.24),rgba(2,6,23,0) 60%),"
    "linear-gradient(160deg,#0b1020 0%,#0e1233 55%,#0b1020 100%) !important;"
    "color:#e8eaf6 !important}"
    ".rpce-root{font-family:" + _FONT + ";color:#e8eaf6;font-size:16px}"
    ".rpce-hero{max-width:1060px;margin:44px auto 18px;padding:42px 46px;border-radius:28px;"
    "border:1px solid rgba(129,140,248,.38);box-shadow:0 26px 70px rgba(79,70,229,.32);"
    "background:radial-gradient(120% 140% at 0% 0%,rgba(99,102,241,.34),rgba(34,211,238,.10) 52%,rgba(2,6,23,0) 100%),"
    "linear-gradient(135deg,rgba(99,102,241,.15),rgba(139,92,246,.07))}"
    ".rpce-head{display:flex;align-items:center;gap:18px}"
    ".rpce-logo{width:58px;height:58px;border-radius:17px;display:flex;align-items:center;"
    "justify-content:center;font-weight:800;font-size:23px;color:#fff;"
    "background:linear-gradient(135deg,#6366f1,#22d3ee);box-shadow:0 10px 26px rgba(99,102,241,.55)}"
    ".rpce-h1{font-size:33px;font-weight:800;letter-spacing:-.4px;color:#fff}"
    ".rpce-h1 small{opacity:.55;font-weight:600;font-size:19px}"
    ".rpce-sub{color:#a6b0d6;font-size:16px}"
    ".rpce-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px;margin-top:28px}"
    ".rpce-card{background:rgba(129,140,248,.08);border:1px solid rgba(129,140,248,.24);border-radius:20px;"
    "padding:24px 26px;box-shadow:0 3px 16px rgba(2,6,23,.40)}"
    ".rpce-row{display:flex;justify-content:space-between;align-items:center;gap:8px}"
    ".rpce-label{font-size:13.5px;font-weight:600;letter-spacing:.8px;text-transform:uppercase;color:#a6b0d6}"
    ".rpce-val{font-size:46px;font-weight:800;margin-top:12px;line-height:1.02;letter-spacing:-.6px;color:#fff}"
    ".rpce-pill{font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:4px 11px;border-radius:999px}"
    ".rpce-bar{height:8px;border-radius:999px;background:rgba(148,163,184,.22);margin-top:18px;overflow:hidden}"
    ".rpce-bar>i{display:block;height:100%;border-radius:999px;background:currentColor}"
    ".rpce-cf-abstain{color:#94a3b8}.rpce-pill.rpce-cf-abstain{background:rgba(148,163,184,.22)}"
    ".rpce-cf-low{color:#fbbf24}.rpce-pill.rpce-cf-low{background:rgba(251,191,36,.20)}"
    ".rpce-cf-medium{color:#34d399}.rpce-pill.rpce-cf-medium{background:rgba(52,211,153,.20)}"
    ".rpce-cf-high{color:#818cf8}.rpce-pill.rpce-cf-high{background:rgba(129,140,248,.24)}"
    ".rpce-covhead{display:flex;justify-content:space-between;font-size:15px;margin:28px 0 10px;color:#a6b0d6}"
    ".rpce-covhead b{font-weight:600;letter-spacing:.4px;text-transform:uppercase}"
    ".rpce-cov{height:13px;border-radius:999px;background:rgba(148,163,184,.22);overflow:hidden}"
    ".rpce-cov>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#6366f1,#22d3ee)}"
    ".rpce-chips{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}"
    ".rpce-chip{display:inline-flex;align-items:center;gap:7px;font-size:15px;color:#cdd3f5;"
    "background:rgba(129,140,248,.14);border:1px solid rgba(129,140,248,.30);padding:9px 15px;border-radius:999px}"
    ".rpce-note{margin-top:22px;font-size:16px;color:#fcd34d;background:rgba(251,191,36,.11);"
    "border:1px solid rgba(251,191,36,.30);border-radius:14px;padding:15px 18px}"
    ".rpce-foot{margin-top:24px;font-size:15px;color:#a6b0d6}.rpce-foot b{color:#cdd3f5}"
    ".rpce-tbl{border-collapse:collapse;width:100%;font-size:16px}"
    ".rpce-tbl th{color:#a6b0d6;font-size:13px;text-transform:uppercase;letter-spacing:.5px;"
    "text-align:left;padding:12px 14px;border-bottom:2px solid rgba(129,140,248,.32)}"
    ".rpce-tbl td{padding:13px 14px;border-bottom:1px solid rgba(129,140,248,.16)}"
    ".rpce-colbar{height:8px;width:150px;border-radius:999px;background:rgba(148,163,184,.22);overflow:hidden}"
    ".rpce-colbar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#6366f1,#22d3ee)}"
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
    return (
        "<div class='rpce-card'><div class='rpce-row'>"
        f"<span class='rpce-label'>{label}</span>"
        f"<span class='rpce-pill {cf}'>{confidence}</span></div>"
        f"<div class='rpce-val'>{value}</div>{bar}</div>"
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
        f"<p class='rpce-sub' style='font-size:15px'>🎯 <b style='color:#c7cdf2'>Best next topic:</b> {sec1.best_next_topic}</p>"
        if sec1.best_next_topic
        else ""
    )
    return f"""{_theme_style()}
<div class="rpce-root" style="max-width:900px;margin:0 auto;padding:14px 10px">
  <div class="rpce-h1" style="font-size:28px">RPCE readiness</div>
  <div class="rpce-sub" style="margin-bottom:22px;font-size:15px">Three scores, each with a range — and an honest abstain when the data is thin.</div>
  <div class="rpce-grid">{cards}</div>
  <p class="rpce-sub" style="font-size:15px;margin-top:22px"><b style="color:#c7cdf2">Why:</b> {sec1.evidence}</p>
  {next_topic}
  <div class="rpce-h1" style="font-size:18px;margin:26px 0 12px">Coverage map
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
        self.setStyleSheet(
            "QDialog{background:#0e1233}"
            "QLabel{color:#cdd3f5;font-size:16px}"
            "QTextBrowser,QTextEdit{background:#0b1020;color:#e8eaf6;border:1px solid #343a63;"
            "border-radius:12px;font-size:16px;padding:10px}"
            "QPushButton{background:#6366f1;color:#fff;border:none;border-radius:12px;"
            "padding:11px 18px;font-size:15px;font-weight:600}"
            "QPushButton:hover{background:#7c7ff5}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        heading = QLabel("Section II — performance scenario")
        heading.setStyleSheet("font-size:22px;font-weight:800;color:#fff")
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
    """Replace the deck-browser home with the RPCE landing page (no deck
    management UI — the deck is generated for the candidate)."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    try:
        content.tree = _banner_html(mw.col)
        content.stats = ""
    except Exception as exc:  # never break the deck browser over the banner
        print(f"RPCE home error: {exc}")


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
    "body{background:#0b1020 !important}"
    ".header{background:linear-gradient(90deg,#0e1233,#141a44) !important;"
    "border-bottom:1px solid rgba(129,140,248,.30) !important;padding:7px 6px !important}"
    ".hitem{font-size:15px !important;font-weight:600 !important;color:#c7cdf2 !important;"
    "padding:9px 18px !important;margin:0 4px !important;border-radius:10px !important;text-decoration:none !important}"
    ".hitem:hover{background:rgba(129,140,248,.20) !important;color:#fff !important}"
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
    gui_hooks.main_window_did_init.append(_add_menu)
    gui_hooks.profile_did_open.append(_on_profile_open)
    gui_hooks.deck_browser_will_render_content.append(_on_deck_browser_content)
    gui_hooks.reviewer_did_answer_card.append(_on_answer_card)
    gui_hooks.top_toolbar_did_init_links.append(_on_toolbar_links)
