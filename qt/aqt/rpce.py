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

import base64
import functools
import os

import aqt
from aqt import gui_hooks
from aqt.qt import (
    QDialog,
    QIcon,
    QLabel,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import aqt_data_folder


def _icon_path(filename: str) -> str:
    """Absolute path to a bundled icon under aqt's data/qt/icons folder."""
    return os.path.join(aqt_data_folder(), "qt", "icons", filename)


@functools.lru_cache(maxsize=None)
def _logo_data_uri() -> str:
    """The app logo as an inline data URI (cached), for the web home banner."""
    try:
        with open(_icon_path("rpce_logo_small.png"), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except OSError:
        return ""


def app_icon() -> QIcon:
    """The Speedrun-for-the-RPCE window/app icon."""
    return QIcon(_icon_path("rpce_logo.png"))


def _apply_app_icon() -> None:
    """Set the RPCE logo as the window + application (taskbar) icon."""
    try:
        icon = app_icon()
        if icon.isNull():
            return
        from aqt.qt import QApplication

        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(icon)
        if aqt.mw is not None:
            aqt.mw.setWindowIcon(icon)
    except Exception as exc:  # never block startup over branding
        print(f"RPCE icon error: {exc}")


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

# Qt stylesheet for RPCE dialogs, matching the light Blue-on-White theme (no gray).
_DIALOG_QSS = (
    "QDialog{background:#f1f6ff}"
    "QLabel{color:#0a1f44;font-size:17px}"
    "QTextBrowser,QTextEdit{background:#ffffff;color:#0a1f44;border:1px solid #caddf7;"
    "border-radius:12px;font-size:17px;padding:12px}"
    "QPushButton{background:#1d4ed8;color:#fff;border:none;border-radius:12px;"
    "padding:12px 20px;font-size:16px;font-weight:700}"
    "QPushButton:hover{background:#3b82f6}"
)

# App-wide Qt stylesheet appended to Anki's own theme so *every* dialog (including
# the AnkiWeb Sync login prompt, which we don't own) fits the light Blue-on-White
# theme: white surfaces, dark-navy readable text, large blue buttons.
_APP_QSS = (
    "QMainWindow,QDialog,QMessageBox,QInputDialog{background:#f1f6ff}"
    "QLabel,QCheckBox,QRadioButton,QGroupBox{color:#0a1f44;font-size:15px}"
    "QLineEdit,QTextEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QComboBox{"
    "background:#ffffff;color:#0a1f44;border:1px solid #caddf7;border-radius:10px;"
    "padding:8px 11px;font-size:15px;selection-background-color:#1d4ed8;selection-color:#fff}"
    "QPushButton{background:#1d4ed8;color:#ffffff;border:none;border-radius:10px;"
    "padding:10px 20px;font-size:15px;font-weight:700;min-height:20px;min-width:84px}"
    "QPushButton:hover{background:#3b82f6}"
    "QPushButton:disabled{background:#b7ccf2;color:#eef4ff}"
)

# Injected into the reviewer (study) webview so flashcards share the light theme
# of the practice screen: white background, dark-navy text, blue links/cloze.
_REVIEWER_CSS = (
    "<style>"
    # Match the phone: soft-blue page, a white rounded card container.
    "html,body{background:#eef4ff !important;color:#0a1f44 !important}"
    ".card{background:#ffffff !important;border:1px solid #caddf7 !important;"
    "border-radius:20px !important;padding:24px 20px !important;max-width:680px !important;"
    "margin:18px auto !important;box-shadow:0 6px 20px rgba(10,31,68,.06) !important;"
    "color:#0a1f44 !important;text-align:left !important}"
    "hr{border:none;border-top:1px solid #caddf7 !important}"
    "a{color:#1d4ed8 !important}"
    ".cloze,.cloze b{color:#1d4ed8 !important;font-weight:700}"
    # Revealed cloze blank — green, matching the phone.
    ".cloze-reveal{color:#15803d !important;font-weight:700}"
    "</style>"
)

# Theme the reviewer's bottom bar: light background, and rating buttons coloured
# by difficulty (Again/Hard/Good/Easy) instead of Anki's gray defaults — matching
# the phone app. Edit / More / Show-Answer become themed blue.
_REVIEWER_BOTTOM_CSS = (
    "<style>"
    "body,#innertable{background:#eef4ff !important}"
    "body{color:#35548c !important}"
    # Remove the reviewer's Edit and More buttons (not part of the RPCE flow).
    "button[onclick*='edit']{display:none !important}"
    "button[onclick*='more']{display:none !important}"
    # …and keep both side cells equal width so the rating buttons stay centered
    # now that the left (Edit) cell is empty.
    "td.stat{width:120px !important}"
    # Big, bold, colored rating buttons matching the phone's Again/Hard/Good/Easy.
    "button{background:#1d4ed8 !important;color:#fff !important;"
    "border:none !important;border-radius:14px !important;padding:15px 22px !important;"
    "font-size:16px !important;font-weight:800 !important;"
    "box-shadow:0 3px 10px rgba(29,78,216,.25) !important}"
    "button *{color:#fff !important}"
    "button:hover{filter:brightness(1.06)}"
    "button[data-ease='1']{background:#9f1239 !important}"  # Again  (red)
    "button[data-ease='2']{background:#a16207 !important}"  # Hard   (amber)
    "button[data-ease='3']{background:#1d4ed8 !important}"  # Good   (blue)
    "button[data-ease='4']{background:#15803d !important}"  # Easy   (green)
    ".stattxt,.nobold,.new-count,.review-count,.learn-count{color:#35548c !important}"
    "</style>"
)

# One cohesive "Deep Blue" theme (dark navy + white, blue->sky accents),
# driven by CSS design tokens so the home banner and dashboard stay consistent.
# See docs/rpce/UI_DESIGN.md.
_THEME_CSS = (
    ":root{"
    "--ink:#0a1f44;--ink2:#35548c;--muted:#2563eb;"
    "--ready:#15803d;--mid:#2563eb;--warn:#b45309;"
    "--surface:#ffffff;--surface2:#f4f8ff;--track:#dbe8fb;"
    "--border:#caddf7;--accent1:#1d4ed8;--accent2:#3b82f6;"
    "--fs-display:42px;--fs-h1:30px;--fs-h2:22px;--fs-lead:18px;"
    "--fs-body:17px;--fs-small:15px;--fs-label:13px}"
    # Full-page light background (white -> soft blue, no gray). min-height fills
    # the whole viewport so short content doesn't leave the webview's black
    # backing showing below the banner.
    "html,body{min-height:100vh !important;margin:0 !important;background:"
    "radial-gradient(1200px 760px at 12% -12%,rgba(59,130,246,.16),rgba(255,255,255,0) 60%),"
    "linear-gradient(160deg,#ffffff 0%,#eef4ff 55%,#ffffff 100%) !important;"
    "background-attachment:fixed !important;color:var(--ink) !important}"
    ".rpce-root{font-family:" + _FONT + ";color:var(--ink);font-size:var(--fs-body)}"
    ".rpce-hero{max-width:1060px;margin:44px auto 18px;padding:42px 46px;border-radius:26px;"
    "border:1px solid var(--border);box-shadow:0 20px 50px rgba(29,78,216,.14);"
    "background:radial-gradient(120% 140% at 0% 0%,rgba(59,130,246,.12),rgba(59,130,246,.04) 52%,rgba(255,255,255,0) 100%),"
    "var(--surface)}"
    ".rpce-head{display:flex;flex-direction:column;align-items:center;text-align:center;gap:14px}"
    ".rpce-logo{width:76px;height:76px;border-radius:20px;display:block;object-fit:contain;"
    "box-shadow:0 10px 26px rgba(29,78,216,.28)}"
    ".rpce-h1{font-size:var(--fs-h1);font-weight:800;letter-spacing:-.4px;color:var(--ink)}"
    ".rpce-h1 small{color:var(--ink2);font-weight:600;font-size:var(--fs-lead)}"
    ".rpce-sub{color:var(--ink2);font-size:var(--fs-lead);max-width:60ch;margin-left:auto;margin-right:auto}"
    ".rpce-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px;margin-top:34px}"
    ".rpce-card{background:var(--surface2);border:1px solid var(--border);border-radius:20px;"
    "padding:26px 22px;box-shadow:0 6px 20px rgba(29,78,216,.08);text-align:center;"
    "display:flex;flex-direction:column;align-items:center}"
    ".rpce-label{font-size:var(--fs-label);font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--ink2)}"
    ".rpce-val{font-size:var(--fs-display);font-weight:800;margin:14px 0 16px;line-height:1.02;letter-spacing:-.6px;color:var(--ink)}"
    ".rpce-pill{display:inline-block;font-size:var(--fs-label);font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:5px 13px;border-radius:999px}"
    ".rpce-reason{font-size:var(--fs-small);line-height:1.45;color:var(--ink2);margin-top:14px;text-align:left}"
    ".rpce-bar{height:9px;width:100%;border-radius:999px;background:var(--track);margin-top:18px;overflow:hidden}"
    ".rpce-bar>i{display:block;height:100%;border-radius:999px;background:currentColor}"
    ".rpce-cf-abstain{color:var(--muted)}.rpce-pill.rpce-cf-abstain{background:rgba(37,99,235,.12)}"
    ".rpce-cf-low{color:var(--warn)}.rpce-pill.rpce-cf-low{background:rgba(180,83,9,.14)}"
    ".rpce-cf-medium{color:var(--mid)}.rpce-pill.rpce-cf-medium{background:rgba(37,99,235,.14)}"
    ".rpce-cf-high{color:var(--ready)}.rpce-pill.rpce-cf-high{background:rgba(21,128,61,.14)}"
    ".rpce-covhead{display:flex;justify-content:space-between;font-size:var(--fs-small);margin:28px 0 10px;color:var(--ink2)}"
    ".rpce-covhead b{font-weight:700;letter-spacing:.4px;text-transform:uppercase}"
    ".rpce-cov{height:14px;border-radius:999px;background:var(--track);overflow:hidden}"
    ".rpce-cov>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent1),var(--accent2))}"
    ".rpce-chips{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-top:24px}"
    ".rpce-chip{display:inline-flex;align-items:center;gap:7px;font-size:var(--fs-body);color:var(--ink);"
    "background:rgba(37,99,235,.10);border:1px solid var(--border);padding:10px 16px;border-radius:999px}"
    ".rpce-note{margin-top:22px;font-size:var(--fs-body);color:#92400e;background:rgba(180,83,9,.10);"
    "border:1px solid rgba(180,83,9,.30);border-left:4px solid var(--warn);border-radius:12px;padding:15px 18px}"
    ".rpce-foot{margin-top:26px;text-align:center;font-size:var(--fs-small);color:var(--ink2)}.rpce-foot b{color:var(--ink)}"
    ".rpce-tbl{border-collapse:collapse;width:100%;font-size:var(--fs-body)}"
    ".rpce-tbl th{color:var(--ink2);font-size:var(--fs-label);text-transform:uppercase;letter-spacing:.5px;"
    "text-align:left;padding:12px 14px;border-bottom:2px solid var(--border)}"
    ".rpce-tbl td{padding:13px 14px;border-bottom:1px solid var(--border)}"
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
    label: str,
    value: str,
    confidence: str,
    fill: float | None = None,
    reason: str = "",
) -> str:
    """A themed score card: label, big value, confidence pill, the main reasons
    behind the number (spec §4), and an optional bar."""
    cf = f"rpce-cf-{confidence}"
    bar = ""
    if fill is not None:
        pct = max(0.0, min(100.0, fill * 100))
        bar = (
            f"<div class='rpce-bar'><i class='{cf}' style='width:{pct:.0f}%'></i></div>"
        )
    reason_html = (
        "<details style='margin-top:10px'>"
        "<summary style='cursor:pointer;font-size:13px;font-weight:700;"
        "color:var(--accent1);list-style:none'>ℹ️ Why this score</summary>"
        f"<div class='rpce-reason' style='margin-top:6px'>{reason}</div></details>"
        if reason
        else ""
    )
    return (
        "<div class='rpce-card'>"
        f"<div class='rpce-label'>{label}</div>"
        f"<div class='rpce-val'>{value}</div>"
        f"<span class='rpce-pill {cf}'>{confidence}</span>"
        f"{reason_html}{bar}</div>"
    )


def _chip(text: str) -> str:
    return f"<span class='rpce-chip'>{text}</span>"


def _examiner_badge() -> str:
    """Show which examiner graded: the built-in offline keyword matcher (no AI
    key wired) or an online AI examiner. Mirrors the phone."""
    return (
        "<div style='margin-top:8px;color:#b45309;font-weight:700'>"
        "🔌 Offline examiner (keyword match). Connect an online AI examiner for "
        "richer feedback.</div>"
    )


def _sync_status_html() -> str:
    """A visible AnkiWeb sign-in/sync indicator for the desktop banner."""
    signed_in = False
    try:
        signed_in = bool(aqt.mw and aqt.mw.pm.sync_auth())
    except Exception:
        pass
    if signed_in:
        return (
            "<span style='display:inline-block;padding:8px 14px;border-radius:999px;"
            "background:#e7f6ec;color:#15803d;font-weight:700'>🟢 Signed in to AnkiWeb — "
            "use the <b>Sync</b> button (top-right) to sync now</span>"
        )
    return (
        "<span style='display:inline-block;padding:8px 14px;border-radius:999px;"
        "background:#fef3c7;color:#b45309;font-weight:700'>⚠️ Not signed in to AnkiWeb — "
        "click <b>Sync</b> (top-right) to log in and sync with your phone</span>"
    )


def _elaboration_html(s: dict) -> str:
    """Collapsible confidence elaboration for the dashboard (spec §4). Reads the
    engine summary's ``confidence_label`` (a string containing "confidence") and
    ``elaboration`` (preparedness-focused prose) when present, and tucks the prose
    into a ``<details>`` so the dashboard stays uncluttered. Falls back to a
    generic confidence label so the word "confidence" is always shown."""
    body = str(s.get("elaboration") or "").strip()
    if not body:
        return ""
    return (
        "<details class='rpce-elab' style='margin-top:22px;background:var(--surface2);"
        "border:1px solid var(--border);border-radius:16px;padding:2px 18px'>"
        "<summary style='cursor:pointer;font-weight:800;color:var(--ink);"
        "font-size:var(--fs-body);padding:14px 0'>"
        "ℹ️ Why these scores</summary>"
        "<div style='color:var(--ink2);font-size:var(--fs-small);line-height:1.5;"
        f"padding:0 0 16px'>{body}</div></details>"
    )


def _banner_html(col) -> str:
    from anki.rpce import scores

    s = scores.readiness_summary(col)
    mem, perf = s["memory"], s["performance"]
    sec1, sec2 = s["section_I"], s["section_II"]
    covered = sum(1 for c in s["coverage"] if c.cards > 0)
    total = len(s["coverage"])
    pct = covered / total if total else 0.0
    cal = scores.memory_calibration(col)
    cal_line = (
        f"Memory calibration: <b>Brier {cal['brier']:.3f}</b> · log-loss "
        f"{cal['log_loss']:.3f} (FSRS retrievability vs. outcome, n={cal['n']})"
        if cal
        else "Memory calibration: review more with FSRS on to measure accuracy"
    )

    def section_value(snap) -> str:
        return (
            "—"  # dash when abstaining, matching Memory/Performance
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
                mem.explanation,
            ),
            _score_card(
                "Performance",
                _fmt_range(perf.point, perf.low, perf.high),
                perf.confidence,
                perf.point,
                perf.explanation,
            ),
            _score_card(
                "Pass Section I",
                section_value(sec1),
                sec1.confidence,
                None if sec1.abstained else sec1.p_pass,
                sec1.evidence,
            ),
            _score_card(
                "Pass Section II",
                section_value(sec2),
                sec2.confidence,
                None if sec2.abstained else sec2.p_pass,
                sec2.evidence,
            ),
        ]
    )
    # Dashboard kept clean: no phase/next chips or "readiness hidden" note —
    # the score cards + coverage already say enough.
    # Sign-in status lives in the top-right; here we only offer Log out when
    # signed in (the redundant "Signed in to AnkiWeb" banner is gone).
    signed_in = False
    try:
        signed_in = bool(aqt.mw and aqt.mw.pm.sync_auth())
    except Exception:
        pass
    logout_html = (
        "<div style='margin-top:10px'><a href='#' "
        "onclick=\"pycmd('rpce:logout');return false;\" "
        "style='color:#b45309;font-weight:700;text-decoration:underline;cursor:pointer'>"
        "Log out of AnkiWeb</a></div>"
        if signed_in
        else ""
    )
    return f"""{_theme_style()}
<div class="rpce-root"><div class="rpce-hero">
  <div class="rpce-head">
    <img class="rpce-logo" src="{_logo_data_uri()}" alt="Speedrun for the RPCE logo">
    <div>
      <div class="rpce-h1">Speedrun <small>for the RPCE</small></div>
      <div class="rpce-sub">Registered Parliamentarian Credentialing Exam · pass each section ≥ 80%</div>
    </div>
  </div>
  <div class="rpce-grid">{cards}</div>
  <div class="rpce-covhead"><b>Domain coverage</b><span>{pct:.0%} of {total} domains</span></div>
  <div class="rpce-cov"><i style="width:{pct * 100:.0f}%"></i></div>
  <div class="rpce-foot" style="margin-top:22px">{cal_line}</div>
  <div class="rpce-foot" style="margin-top:6px">Use the tabs above — <b>Study</b> flashcards,
    practice <b>Section II</b>, or run a <b>Simulation</b>.</div>
  {logout_html}
  <div class="rpce-foot" style="margin-top:12px">Readiness last updated: <b>{_updated_str(col)}</b></div>
</div></div>
"""


def _updated_str(col) -> str:
    """Human-readable 'last updated' time for the readiness panel (spec §7.4)."""
    import time

    from anki.rpce import scores

    ts = scores.last_updated(col)
    if not ts:
        return "not yet computed"
    return time.strftime("%b %d, %Y %H:%M", time.localtime(ts))


def _show_dashboard() -> None:
    """The readiness dashboard IS the home screen (the deck-browser banner) — no
    popup. Record a snapshot to refresh 'last updated', then return home."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    from anki.rpce import scores

    try:
        scores.record_readiness_snapshots(mw.col)
    except Exception as exc:
        print(f"RPCE dashboard error: {exc}")
    mw.moveToState("deckBrowser")


class ScenarioDialog(QDialog):
    """Section II performance practice: read a scenario, write a ruling, and get
    examiner-style feedback graded for accuracy."""

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
        heading.setStyleSheet("font-size:24px;font-weight:800;color:#0a1f44")
        layout.addWidget(heading)
        self._domain = QLabel()
        layout.addWidget(self._domain)
        self._prompt = QTextBrowser()
        self._prompt.setMinimumHeight(90)
        layout.addWidget(self._prompt)
        layout.addWidget(QLabel("Your ruling & reasoning:"))
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
        # Always give an explicit way back to the Dashboard (don't trap the user).
        self._close_btn = QPushButton("← Back to Dashboard")
        qconnect(self._close_btn.clicked, self.accept)
        layout.addWidget(self._close_btn)
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
        self._result.setHtml(
            f"<div><b>Score:</b> {result.score:.1f}/5 ({verdict})<br>"
            f"<b>Feedback:</b> {result.feedback}</div>"
            + _examiner_badge()
            + f"<div style='margin-top:8px'><b>Model ruling:</b> {s.gold_answer}</div>"
            + _ref_block(s.ref.section, s.ref.quote)
        )

    def _next(self) -> None:
        self._idx = (self._idx + 1) % len(self._scenarios)
        self._load()


def _show_scenarios() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    ScenarioDialog(mw).exec()


# Motion-class colors (fg, bg) for the reference pills — shared look with mobile.
_CLASS_COLOR = {
    "privileged": ("#6d28d9", "#f3e8ff"),
    "subsidiary": ("#1d4ed8", "#e0ecff"),
    "main": ("#0f766e", "#ccfbf1"),
    "incidental": ("#b45309", "#fef3c7"),
}


def _class_pill(cls: str) -> str:
    fg, bg = _CLASS_COLOR.get(cls, ("#35548c", "#eef4ff"))
    return (
        f"<span style='padding:2px 10px;border-radius:999px;font-size:12px;"
        f"font-weight:700;color:{fg};background:{bg}'>{cls}</span>"
    )


def _yn_cell(v: str) -> str:
    return (
        "<span style='color:#15803d;font-weight:700'>Yes</span>"
        if v == "Yes"
        else "<span style='color:#94a3b8'>No</span>"
    )


def _vote_cell(v: str) -> str:
    color = (
        "#1d4ed8" if "Majority" in v else "#b45309" if "Two-thirds" in v else "#64748b"
    )
    return f"<span style='color:{color};font-weight:700'>{v}</span>"


def _reference_html(ref: dict) -> str:
    """Order-of-precedence + motion-characteristics tables, color-coded by class,
    vote, and yes/no."""
    prec = "".join(
        f"<tr><td class='rank'>{r['rank']}</td><td><b>{r['name']}</b></td>"
        f"<td>{_class_pill(r['class'])}</td></tr>"
        for r in ref["precedence"]
    )
    chars = "".join(
        f"<tr><td><b>{r['name']}</b></td><td>{_class_pill(r['class'])}</td>"
        f"<td>{_yn_cell(r['second'])}</td><td>{_yn_cell(r['debatable'])}</td>"
        f"<td>{_yn_cell(r['amendable'])}</td><td>{_vote_cell(r['vote'])}</td></tr>"
        for r in ref["characteristics"]
    )
    return (
        "<style>body{font-family:-apple-system,Segoe UI,sans-serif;color:#0a1f44}"
        "h3{color:#1b3faa;margin:18px 0 8px}"
        "table{border-collapse:separate;border-spacing:0;width:100%;font-size:14px}"
        "th,td{padding:9px 11px;text-align:left;border-bottom:1px solid #e6eefb}"
        "th{color:#35548c;text-transform:uppercase;font-size:11px;letter-spacing:.5px;"
        "background:#f4f8ff;position:sticky;top:0}"
        "tr:nth-child(even) td{background:#fbfdff}"
        ".rank{font-weight:800;color:#1d4ed8;text-align:center;width:34px}</style>"
        "<h3>Order of precedence <span style='font-weight:400;color:#64748b'>"
        "(highest → lowest)</span></h3>"
        "<table><tr><th>#</th><th>Motion</th><th>Class</th></tr>" + prec + "</table>"
        "<h3>Motion characteristics</h3>"
        "<table><tr><th>Motion</th><th>Class</th><th>2nd</th><th>Debate</th>"
        "<th>Amend</th><th>Vote</th></tr>" + chars + "</table>"
    )


class ReferenceDialog(QDialog):
    """Reference tab: RONR order of precedence + motion characteristics tables."""

    def __init__(self, mw) -> None:
        super().__init__(mw)
        from anki.rpce import knowledge

        self.setWindowTitle("RPCE — Reference tables")
        self.resize(760, 720)
        self.setStyleSheet(_DIALOG_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        view = QTextBrowser()
        view.setHtml(_reference_html(knowledge.reference_tables()))
        layout.addWidget(view)
        close = QPushButton("Close")
        qconnect(close.clicked, self.accept)
        layout.addWidget(close)


def _show_reference() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    ReferenceDialog(mw).exec()


def _trigger_sync() -> None:
    """Start AnkiWeb sync (also prompts login the first time), from the toolbar
    status indicator — mirrors the phone's Sync button."""
    try:
        aqt.mw.on_sync_button_clicked()
    except Exception as exc:
        print(f"RPCE sync error: {exc}")


def _auto_full_upload(mw, server_usn, on_done) -> None:
    """Skip Anki's "your AnkiWeb collection has no cards — replace it?" prompt
    after logging in with an empty AnkiWeb account: the local RPCE deck is the
    source of truth, so proceed straight to the upload. Mirrors the "proceed"
    branch of ``aqt.sync.confirm_full_upload``. (Only the empty-UPLOAD case is
    auto-handled; full_download and the 3-way conflict dialog are untouched.)"""
    import aqt.sync

    mw.closeAllWindows(lambda: aqt.sync.full_upload(mw, server_usn, on_done))


def _auto_full_sync(mw, out, on_done) -> None:
    """Resolve Anki's full-sync conflict without the scary Download/Upload dialog.

    A full sync is forced only when the device and AnkiWeb schemas differ (the
    two apps each seed their own deck). It can't merge, so we apply a documented
    conflict rule: the desktop holds the authoritative generated deck, so on a
    conflict it UPLOADS (desktop wins); the phone then downloads once. If the
    server is strictly newer (FULL_DOWNLOAD, local behind), take its copy. After
    this one alignment, every later sync is incremental and reviews combine."""
    import aqt.sync

    server_usn = out.server_media_usn if mw.pm.media_syncing_enabled() else None
    if out.required == out.FULL_DOWNLOAD:
        mw.closeAllWindows(lambda: aqt.sync.full_download(mw, server_usn, on_done))
    else:  # FULL_UPLOAD or FULL_SYNC conflict → desktop is the source of truth
        mw.closeAllWindows(lambda: aqt.sync.full_upload(mw, server_usn, on_done))


def _on_webview_message(handled, message: str, context):
    """Open the Reference dialog from the dashboard banner link (keeps it off the
    top toolbar). Returns a filter result tuple."""
    if message == "rpce:reference":
        _show_reference()
        return (True, None)
    if message == "rpce:logout":
        _logout_ankiweb()
        return (True, None)
    return handled


class SimulationDialog(QDialog):
    """Simulation mode: a scripted meeting plays out turn by turn — members and
    the chair speak, and at decision points the candidate responds *as the
    parliamentarian*. Each response is graded for accuracy with an immediate
    debrief (SPOV 2 + Insight 4). No RONR citation is required of the candidate."""

    def __init__(self, mw) -> None:
        super().__init__(mw)
        from anki.rpce import simulations

        self._mw = mw
        self._corpus = _load_corpus()
        self._sims = list(simulations.all_simulations())
        self._sim_idx = 0
        self._turn = 0
        self._pending = None  # the turn awaiting a response

        self.setWindowTitle("RPCE — Meeting simulation")
        self.resize(760, 720)
        self.setStyleSheet(_DIALOG_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        self._heading = QLabel()
        self._heading.setStyleSheet("font-size:22px;font-weight:800;color:#0a1f44")
        self._heading.setWordWrap(True)
        layout.addWidget(self._heading)

        self._transcript = QTextBrowser()
        self._transcript.setMinimumHeight(320)
        layout.addWidget(self._transcript)

        self._prompt = QLabel()
        self._prompt.setWordWrap(True)
        layout.addWidget(self._prompt)

        self._answer = QTextEdit()
        self._answer.setPlaceholderText("Respond as the parliamentarian…")
        self._answer.setMinimumHeight(90)
        layout.addWidget(self._answer)

        self._respond_btn = QPushButton("Respond")
        qconnect(self._respond_btn.clicked, self._respond)
        layout.addWidget(self._respond_btn)

        self._next_btn = QPushButton("Next meeting →")
        qconnect(self._next_btn.clicked, self._next_sim)
        layout.addWidget(self._next_btn)

        # Always give an explicit way back to the Dashboard (don't trap the user).
        self._close_btn = QPushButton("← Back to Dashboard")
        qconnect(self._close_btn.clicked, self.accept)
        layout.addWidget(self._close_btn)

        self._load_sim()

    def _sim(self):
        return self._sims[self._sim_idx]

    def _load_sim(self) -> None:
        sim = self._sim()
        self._turn = 0
        self._pending = None
        self._transcript.setHtml(f"<p style='color:#35548c'><i>{sim.setting}</i></p>")
        self._heading.setText(f"{sim.title}")
        self._answer.clear()
        self._answer.setEnabled(True)
        self._respond_btn.setEnabled(True)
        self._play()

    def _append(self, html: str) -> None:
        self._transcript.append(html)

    def _play(self) -> None:
        """Play spoken lines until the next response point (or the end)."""
        sim = self._sim()
        while self._turn < len(sim.turns):
            turn = sim.turns[self._turn]
            self._append(
                f"<p><b style='color:#1d4ed8'>{turn.speaker}:</b> {turn.line}</p>"
            )
            if turn.needs_response:
                self._pending = turn
                self._turn += 1
                self._prompt.setText(f"🎤 {turn.prompt}")
                self._answer.setEnabled(True)
                self._answer.setFocus()
                self._respond_btn.setEnabled(True)
                return
            self._turn += 1
        # Reached the end of the meeting.
        self._pending = None
        self._prompt.setText("✅ Meeting adjourned. Well done.")
        self._answer.setEnabled(False)
        self._respond_btn.setEnabled(False)

    def _respond(self) -> None:
        from anki.rpce import examiner, scores

        if self._pending is None:
            return
        answer = self._answer.toPlainText().strip()
        if not answer:
            return
        result = examiner.PlaceholderExaminer().grade(
            answer, self._pending.gold, self._corpus or self._pending.gold
        )
        scores.record_scenario(self._mw.col)
        verdict = "pass" if result.passed else "keep practicing"
        ref = self._pending.ref
        ref_html = _ref_block(ref.section, ref.quote) if ref else ""
        self._append(
            f"<p><b>You (parliamentarian):</b> {answer}</p>"
            f"<p style='color:#35548c'><b>Examiner:</b> {result.score:.1f}/5 "
            f"({verdict}) — {result.feedback}<br>"
            f"<b>Model ruling:</b> {self._pending.gold}</p>" + ref_html
        )
        self._answer.clear()
        self._play()

    def _next_sim(self) -> None:
        self._sim_idx = (self._sim_idx + 1) % len(self._sims)
        self._load_sim()


def _show_simulation() -> None:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    SimulationDialog(mw).exec()


def _brand_main_window() -> None:
    """Brand the window (title + logo icon). All RPCE actions live on the top
    toolbar tabs (Study / Section II / Simulate / Dashboard), so there is no
    separate RPCE dropdown menu."""
    mw = aqt.mw
    if mw is None:
        return
    mw.setWindowTitle(APP_TITLE)
    _apply_app_icon()
    # Keep the top bar (4 tabs + right-tray sync status + Sync) from clipping:
    # enforce a minimum width, and widen the current window if it's narrower.
    try:
        min_w = 1120
        mw.setMinimumWidth(min_w)
        if mw.width() < min_w:
            mw.resize(min_w, mw.height())
    except Exception as exc:  # never block startup over sizing
        print(f"RPCE window-size error: {exc}")
    # Tools ▸ RPCE actions: session length + AnkiWeb logout.
    try:
        from aqt.qt import QAction

        act = QAction("Review session length…", mw)
        qconnect(act.triggered, _set_session_length)
        mw.form.menuTools.addAction(act)
        logout = QAction("Log out of AnkiWeb", mw)
        qconnect(logout.triggered, _logout_ankiweb)
        mw.form.menuTools.addAction(logout)
    except Exception as exc:
        print(f"RPCE menu error: {exc}")


def _apply_light_theme() -> None:
    """Lock the app to a single light theme (no dark/follow-system mode) so the
    whole UI — menus, dialogs, and the Sync prompt — stays blue-on-white."""
    mw = aqt.mw
    if mw is None:
        return
    try:
        from aqt.theme import Theme, theme_manager

        if mw.pm.theme() != Theme.LIGHT:
            mw.pm.set_theme(Theme.LIGHT)
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


def _rpce_starter_apkg() -> str | None:
    """Locate the committed starter deck the phone also bundles, so the desktop
    imports the *same* 1000-question deck (identical note GUIDs → clean sync).
    Returns None (→ curated fallback) if it can't be found (e.g. a packaged
    install that didn't ship it)."""
    import os

    candidates = [
        os.environ.get("RPCE_STARTER_APKG", ""),
        # dev run: CWD is the repo root (run.bat), where the phone asset lives.
        os.path.join(
            "mobile", "app", "app", "src", "main", "assets", "rpce_starter.apkg"
        ),
    ]
    try:
        import anki.rpce as _r

        pkg_dir = os.path.dirname(_r.__file__ or "")
        if pkg_dir:
            candidates.append(os.path.join(pkg_dir, "starter.apkg"))
    except Exception:
        pass
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _build_or_import_rpce_deck(mw) -> None:
    """Seed the RPCE deck: import the shared starter deck (same questions as the
    phone) if available, otherwise build the curated seven-domain deck."""
    from anki.rpce import build_starter_deck

    apkg = _rpce_starter_apkg()
    if apkg:
        try:
            import anki.import_export_pb2 as ie

            mw.col.import_anki_package(ie.ImportAnkiPackageRequest(package_path=apkg))
            return
        except Exception as exc:  # fall back to the curated deck
            print(f"RPCE starter-deck import failed ({exc}); building curated deck")
    build_starter_deck(mw.col)


def _on_profile_open() -> None:
    """Brand the window and make sure the RPCE deck exists and is selected."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    mw.setWindowTitle(APP_TITLE)
    _apply_app_icon()
    _apply_light_theme()
    from anki.rpce import CONCEPT_NOTETYPE, QUESTION_NOTETYPE, RPCE_DECK_VERSION

    if mw.col.decks.by_name("RPCE") is None:
        _build_or_import_rpce_deck(mw)
        deck = mw.col.decks.by_name("RPCE")
        if deck is not None:
            mw.col.decks.set_current(deck["id"])
        return
    # Keep the desktop deck in step with the shared starter deck. Re-seed when the
    # deck content version changes (new question types/hints) or the notetype was
    # bumped, so the desktop always matches the phone. Safe: the RPCE deck is
    # generated for the candidate (no user-authored notes to lose).
    try:
        stale = mw.col.find_notes(
            f'deck:RPCE -note:"{QUESTION_NOTETYPE}" -note:"{CONCEPT_NOTETYPE}"'
        )
        if stale:
            mw.col.remove_notes(stale)
        current = bool(mw.col.find_cards(f"tag:rpce::ver::{RPCE_DECK_VERSION}"))
        if _rpce_starter_apkg() and not current:
            notes = mw.col.find_notes("deck:RPCE")
            if notes:
                mw.col.remove_notes(notes)
            _build_or_import_rpce_deck(mw)
        elif not mw.col.find_cards(
            f'note:"{QUESTION_NOTETYPE}" OR note:"{CONCEPT_NOTETYPE}"'
        ):
            _build_or_import_rpce_deck(mw)
        deck = mw.col.decks.by_name("RPCE")
        if deck is not None:
            mw.col.decks.set_current(deck["id"])
            # Lift the daily cap on the existing deck too (build sets it for new
            # ones); idempotent so it's cheap on every open.
            try:
                conf = mw.col.decks.config_dict_for_deck_id(deck["id"])
                if (
                    conf.get("new", {}).get("perDay", 0) < 9999
                    or conf.get("newSortOrder", 0) != 4
                ):
                    conf["new"]["perDay"] = 9999
                    conf["rev"]["perDay"] = 9999
                    conf["newSortOrder"] = 4  # RANDOM_CARD — interleave types
                    mw.col.decks.update_config(conf)
            except Exception:
                pass
    except Exception as exc:
        print(f"RPCE deck migration error: {exc}")


def _on_answer_card(reviewer, card, ease) -> None:
    """Tally each review by its format tag (drives the M9 study experiment)."""
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    try:
        from anki.rpce import transfer_ladder

        # Legacy question notes carry a rpce::fmt tag; concept sibling cards
        # encode the format in their card-template name instead.
        rung = transfer_ladder.rung_of_tags(card.note().tags)
        if rung is None:
            try:
                rung = card.template()["name"]
            except Exception:
                rung = None
        if rung:
            transfer_ladder.record_rung(mw.col, rung)
    except Exception as exc:  # never break reviewing over the tally
        print(f"RPCE format-tally error: {exc}")
    # Concept grouping (our Rust engine change): bury the other cards of this
    # concept so a concept isn't shown again today across question types — the
    # same idea as sibling burying, keyed on the rpce::concept tag (spec §7/§14).
    try:
        if _is_rpce_card(card):
            mw.col._backend.bury_concept_siblings(card_id=card.id)
    except Exception as exc:  # never break reviewing over concept burying
        print(f"RPCE concept-bury error: {exc}")
    # Cap the session at the configured length, then return home for a new one.
    global _session_done
    _session_done += 1
    if _session_done >= _session_limit():
        from aqt.qt import QTimer

        QTimer.singleShot(500, _end_session)


def _is_rpce_card(card) -> bool:
    from anki.rpce import CONCEPT_NOTETYPE, QUESTION_NOTETYPE

    try:
        # Prefix match: an earlier bug could leave name-collision duplicates
        # (e.g. "RPCE Q 1++"), which must still render.
        name = card.note_type()["name"]
        return name.startswith(QUESTION_NOTETYPE) or name.startswith(CONCEPT_NOTETYPE)
    except Exception:
        return False


def _ref_block(section: str, quote: str) -> str:
    """Render the RONR (12th ed.) citation + verbatim quote shown with an answer.

    Used by every mode (flashcard reviewer, Section II, Simulation) so each mode
    answers with an exact section citation and a relevant quote (accuracy rule).
    """
    if not section:
        return ""
    return (
        "<div style='margin-top:16px;padding:12px 15px;border-left:4px solid #2f6fed;"
        "background:#eef4ff;border-radius:10px;text-align:left'>"
        "<div style='font-weight:700;color:#1b3faa;font-size:15px'>"
        f"RONR (12th ed.) §{section}</div>"
        "<div style='margin-top:6px;font-style:italic;color:#0a1f44;font-size:16px'>"
        f"&ldquo;{quote}&rdquo;</div></div>"
    )


def _rpce_render_html(payload_b64: str, reveal: bool) -> str:
    """Return interactive card HTML driven by the shared renderer. The reviewer
    webview runs the script — the same renderer the phone uses, so both behave
    identically. ``reveal`` renders the answered state (used on the answer side,
    which keeps the question on screen with the answer shown + citation)."""
    from anki.rpce import render_js

    # On the question side, completing the card (MCQ picked / every cloze blank
    # revealed / order placed) triggers Anki's own answer-flip via pycmd('ans').
    # That hides the "Show Answer" button and surfaces the rating buttons —
    # matching the phone, where Show Answer is never shown for interactive cards.
    # Flip immediately on completion — no delay.
    opts = (
        "{reveal:true}"
        if reveal
        else "{reveal:false,onComplete:function(){try{pycmd('ans');}catch(e){}}}"
    )
    return (
        "<style>" + render_js.RENDER_CSS + "</style>"
        + _session_progress_html()
        + "<div id='rpce-host'></div>"
        "<script>"
        + render_js.RENDER_JS
        + "(function(){try{var p=JSON.parse(decodeURIComponent(escape(atob('"
        + payload_b64
        + "'))));window.RPCE.render(p,document.getElementById('rpce-host'),"
        + opts
        + ");}catch(e){document.getElementById('rpce-host').textContent=''+e;}})();"
        "</script>"
    )


#: A review session is capped at this many cards (configurable via the Tools ▸
#: "Review session length…" menu, stored in the syncing collection config); the
#: user starts a new session from the home screen afterward.
_DEFAULT_SESSION_LIMIT = 20
_session_done = 0  # cards answered in the current session


def _session_limit() -> int:
    """The configured questions-per-session (default 20), from the collection
    config so it syncs to the phone."""
    try:
        col = aqt.mw.col if aqt.mw else None
        n = int(col.get_config("rpce:session_limit", _DEFAULT_SESSION_LIMIT))
        return max(1, min(500, n))
    except Exception:
        return _DEFAULT_SESSION_LIMIT


def _set_session_length() -> None:
    """Prompt for the review-session length and save it to the collection."""
    from aqt.qt import QInputDialog
    from aqt.utils import tooltip

    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    n, ok = QInputDialog.getInt(
        mw, "Review session length", "Questions per review session:",
        _session_limit(), 1, 500, 1,
    )
    if ok:
        mw.col.set_config("rpce:session_limit", int(n))
        tooltip(f"Review sessions are now {n} questions.")


def _logout_ankiweb() -> None:
    """Log out of AnkiWeb (clear saved sync auth); local reviews are kept."""
    from aqt.utils import tooltip

    mw = aqt.mw
    if mw is None:
        return
    try:
        mw.pm.clear_sync_auth()
        _redraw_toolbar()
        if mw.state == "deckBrowser":  # refresh so the Log out link disappears
            mw.deckBrowser.refresh()
        tooltip("Logged out of AnkiWeb. Your local reviews are kept.")
    except Exception as exc:
        print(f"RPCE logout error: {exc}")


def _session_progress_html() -> str:
    """A slim 'Question N of M' progress bar shown atop each reviewer card."""
    limit = _session_limit()
    n = min(_session_done + 1, limit)
    pct = int(100 * min(_session_done, limit) / limit)
    return (
        "<div style='max-width:680px;margin:0 auto 14px'>"
        "<div style='display:flex;justify-content:space-between;font-size:13px;"
        "font-weight:700;color:#35548c;margin-bottom:5px'>"
        f"<span>Question {n} of {limit}</span>"
        f"<span>{limit - _session_done} left</span></div>"
        "<div style='height:8px;border-radius:999px;background:#dbe8fb;overflow:hidden'>"
        f"<i style='display:block;height:100%;width:{pct}%;"
        "background:linear-gradient(90deg,#1d4ed8,#3b82f6)'></i></div></div>"
    )


def _end_session() -> None:
    """End the review session at the cap and return home so the user can start a
    fresh one from the Study button."""
    global _session_done
    limit = _session_limit()
    _session_done = 0
    mw = aqt.mw
    if mw is None:
        return
    try:
        mw.moveToState("deckBrowser")
        from aqt.utils import tooltip

        tooltip(f"Session complete — {limit} questions. Tap Study for another.")
    except Exception as exc:
        print(f"RPCE end-session error: {exc}")


def _on_card_will_show(text: str, card, kind: str) -> str:
    """Render an RPCE card interactively (tappable MCQ, per-blank cloze reveal,
    tap-to-order precedence). The answer side re-renders fully revealed so the
    question stays on screen with the answer + citation. Non-RPCE cards are
    untouched."""
    try:
        if not _is_rpce_card(card):
            return text
        note = card.note()
        # Read the payload from the note's per-format field so BOTH sides render
        # the interactive card. On the answer side this reveals in place — the
        # question stays, blanks fill / the choice is marked, and the RONR
        # citation shows — exactly like the phone (not Anki's plain answer). The
        # concept notetype stores payload per format; the question notetype uses
        # "Payload". Pick the field by the card's template name.
        tmpl = ""
        try:
            tmpl = card.template()["name"]
        except Exception:
            pass
        field = {
            "cloze": "ClozePayload",
            "mcq": "McqPayload",
            "second": "SecondPayload",
            "debatable": "DebatablePayload",
        }.get(tmpl, "Payload")
        payload = ""
        for f in (field, "Payload"):
            try:
                if note[f]:
                    payload = note[f]
                    break
            except Exception:
                continue
        if not payload:
            return text
        return _rpce_render_html(payload, reveal="Answer" in kind)
    except Exception as exc:  # never break reviewing over rendering
        print(f"RPCE format-render error: {exc}")
        return text


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


def _on_overview_bottom(link_handler, links):
    """Empty the deck-overview bottom bar (Options / Custom Study / Description) —
    not part of the RPCE flow. Returns the handler unchanged (filter hook)."""
    try:
        links.clear()
    except Exception as exc:
        print(f"RPCE overview-bottom error: {exc}")
    return link_handler


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
        # Starting review (from home/overview) begins a fresh session.
        if new_state == "review" and old_state != "review":
            global _session_done
            _session_done = 0
        # A finished study session is a meaningful moment to record readiness
        # to the audit trail + refresh the last-updated stamp (§7.4).
        if (
            old_state == "review"
            and new_state in ("deckBrowser", "overview")
            and mw.col
        ):
            from anki.rpce import scores

            scores.record_readiness_snapshots(mw.col)
    except Exception as exc:
        print(f"RPCE state-change error: {exc}")


# Toolbar tabs
######################################################################


def _select_rpce_deck() -> bool:
    mw = aqt.mw
    if mw is None or mw.col is None:
        return False
    deck = mw.col.decks.by_name("RPCE")
    if deck is None:
        _build_or_import_rpce_deck(mw)
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


_TOOLBAR_CSS = (
    "<style>"
    "body{background:#ffffff !important}"
    ".header{background:linear-gradient(90deg,#eef4ff,#e0ecff) !important;"
    "border-bottom:1px solid #caddf7 !important;padding:10px 8px !important}"
    ".hitem{font-size:16px !important;font-weight:800 !important;color:#ffffff !important;"
    "padding:10px 20px !important;margin:0 5px !important;border-radius:12px !important;text-decoration:none !important;"
    "background:linear-gradient(135deg,#1d4ed8,#3b82f6) !important;border:1px solid #3b82f6 !important;"
    "box-shadow:0 4px 14px rgba(29,78,216,.30) !important}"
    ".hitem:hover{background:linear-gradient(135deg,#2563eb,#60a5fa) !important;"
    "color:#fff !important;border-color:#1d4ed8 !important}"
    # Sync-status indicator: amber not-signed-in, green signed-in, orange syncing.
    "#rpce_sync_out{background:#fef3c7 !important;color:#b45309 !important;"
    "border-color:#f0c674 !important;box-shadow:none !important}"
    "#rpce_sync_in{background:#e7f6ec !important;color:#15803d !important;"
    "border-color:#9fd8b3 !important;box-shadow:none !important}"
    "#rpce_sync_busy{background:#fff1e0 !important;color:#c2410c !important;"
    "border-color:#fdba74 !important;box-shadow:none !important}"
    # Anki's own Sync button turns orange while a sync is in progress.
    "#sync.rpce-syncing{background:linear-gradient(135deg,#ea580c,#f97316) !important;"
    "color:#fff !important;border-color:#ea580c !important}"
    "</style>"
)


def _on_toolbar_links(links, toolbar) -> None:
    """Replace Anki's deck-management toolbar with themed RPCE tabs. The sync
    status indicator + Anki's Sync button live in the top-right tray instead
    (see ``_on_right_tray``)."""
    links.clear()
    links.append(_TOOLBAR_CSS)
    links.append(
        toolbar.create_link(
            "rpce_dashboard",
            "Dashboard",
            _show_dashboard,
            tip="Readiness dashboard (home)",
            id="rpce_dashboard",
        )
    )
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
            "rpce_simulate",
            "Simulate",
            _show_simulation,
            tip="Run a meeting as the parliamentarian",
            id="rpce_simulate",
        )
    )


def _last_sync_label() -> str:
    """Relative time since the last successful sync (persisted per collection),
    e.g. 'just now' / '5m ago' — mirrors the phone's last-synced indicator."""
    try:
        col = aqt.mw.col if aqt.mw else None
        ts = col.get_config("rpce:last_sync", None) if col else None
        if not ts:
            return ""
        import time

        delta = int(time.time()) - int(ts)
        if delta < 60:
            return "just now"
        if delta < 3600:
            return f"{delta // 60}m ago"
        if delta < 86400:
            return f"{delta // 3600}h ago"
        return f"{delta // 86400}d ago"
    except Exception:
        return ""


_syncing = False  # True while a sync is in progress (drives the orange state)


def _on_left_tray(content, toolbar) -> None:
    """Top-left corner: quick access to the RONR reference tables."""
    content.append(
        toolbar.create_link(
            "rpce_reference",
            "📋 Reference",
            _show_reference,
            tip="RONR reference tables — order of precedence & motion characteristics",
            id="rpce_reference",
        )
    )


def _on_right_tray(content, toolbar) -> None:
    """Top-right corner: a live sync-status indicator (with last-synced time)
    followed by Anki's own Sync button — mirrors the phone's top-right sync
    status. Orange while syncing, green signed-in, amber not-signed-in."""
    if _syncing:
        label, ident = "🔄 Syncing…", "rpce_sync_busy"
    else:
        signed_in = False
        try:
            signed_in = bool(aqt.mw and aqt.mw.pm.sync_auth())
        except Exception:
            pass
        if signed_in:
            when = _last_sync_label()
            label = f"🟢 Synced · {when}" if when else "🟢 Synced"
            ident = "rpce_sync_in"
        else:
            label, ident = "⚠️ Not signed in", "rpce_sync_out"
    content.append(
        toolbar.create_link(
            "rpce_sync_status",
            label,
            _trigger_sync,
            tip="AnkiWeb sync — click to sign in and sync with your phone",
            id=ident,
        )
    )
    content.append(toolbar._create_sync_link())


def _redraw_toolbar() -> None:
    try:
        if aqt.mw is not None:
            aqt.mw.toolbar.draw()
    except Exception as exc:  # never break sync over the indicator
        print(f"RPCE sync-status refresh error: {exc}")


def _on_sync_will_start(*args) -> None:
    """Turn the sync status + Sync button orange while a sync runs."""
    global _syncing
    _syncing = True
    _redraw_toolbar()
    try:  # tint Anki's own Sync button orange after the redraw recreates it
        from aqt.qt import QTimer

        QTimer.singleShot(
            60,
            lambda: aqt.mw.toolbar.web.eval(
                "var b=document.getElementById('sync');"
                "if(b)b.classList.add('rpce-syncing');"
            ),
        )
    except Exception:
        pass


def _on_sync_finished(*args) -> None:
    """Clear the syncing state, stamp the last-synced time, refresh the
    indicator back to 'Synced · just now'."""
    global _syncing
    _syncing = False
    try:
        if aqt.mw and aqt.mw.col:
            import time

            aqt.mw.col.set_config("rpce:last_sync", int(time.time()))
    except Exception as exc:
        print(f"RPCE last-sync stamp error: {exc}")
    _redraw_toolbar()


def _remove_deck_browser_bottom_bar() -> None:
    """Delete the deck-browser bottom bar (Get Shared / Create Deck / Import
    File) at the source. The RPCE deck is generated for the candidate, so there
    is no deck-management UI. Overriding ``_drawButtons`` stops the bar from ever
    being drawn — more reliable than hiding it after render, since ``BottomBar``
    re-shows the widget asynchronously and would win the race."""
    from aqt.deckbrowser import DeckBrowser

    def _no_buttons(self) -> None:
        self.mw.bottomWeb.hide()

    DeckBrowser._drawButtons = _no_buttons


def setup() -> None:
    """Register all RPCE desktop integration hooks."""
    _remove_deck_browser_bottom_bar()
    # Auto-proceed past the post-login "empty AnkiWeb collection — replace it?"
    # prompt (the local RPCE deck is the source of truth). Only the empty-UPLOAD
    # case is monkeypatched; download/conflict dialogs are left untouched.
    import aqt.sync

    aqt.sync.confirm_full_upload = _auto_full_upload
    aqt.sync.full_sync = _auto_full_sync
    gui_hooks.style_did_init.append(_on_style_init)
    gui_hooks.webview_will_set_content.append(_on_webview_content)
    gui_hooks.main_window_did_init.append(_brand_main_window)
    gui_hooks.profile_did_open.append(_on_profile_open)
    gui_hooks.deck_browser_will_render_content.append(_on_deck_browser_content)
    gui_hooks.deck_browser_did_render.append(_on_deck_browser_did_render)
    gui_hooks.overview_will_render_bottom.append(_on_overview_bottom)
    gui_hooks.reviewer_did_answer_card.append(_on_answer_card)
    gui_hooks.card_will_show.append(_on_card_will_show)
    gui_hooks.webview_did_receive_js_message.append(_on_webview_message)
    gui_hooks.top_toolbar_did_init_links.append(_on_toolbar_links)
    gui_hooks.top_toolbar_will_set_left_tray_content.append(_on_left_tray)
    gui_hooks.top_toolbar_will_set_right_tray_content.append(_on_right_tray)
    gui_hooks.state_did_change.append(_on_state_change)
    # Live-update the top-right sync-status indicator after login/sync.
    gui_hooks.sync_did_finish.append(_on_sync_finished)
    gui_hooks.sync_will_start.append(_on_sync_will_start)
