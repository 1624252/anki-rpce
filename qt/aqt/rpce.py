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
    QPushButton,
    QTextBrowser,
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
    # Larger question + multiple-choice text on the bigger desktop screen,
    # with tighter spacing between the answer choices.
    ".rpce-q{font-size:23px !important;line-height:1.55 !important}"
    ".rpce-opts{gap:2px !important;margin-top:8px !important}"
    ".rpce-opt{font-size:20px !important;padding:6px 16px !important;margin:0 !important}"
    ".rpce-opt .k{font-size:20px !important}"
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
        # Abstaining: no point number, but still show the uncertainty range when
        # we have one (memory/performance carry a full 0-100% abstain range).
        if low is not None and high is not None:
            return (
                "—<span style='display:block;font-size:13px;font-weight:600;"
                f"color:var(--ink2);margin-top:4px'>range {low:.0%}–{high:.0%}</span>"
            )
        return "—"
    if low is None or high is None:
        return f"{point:.0%}"
    # Big point value, with the range on its own small muted line beneath.
    return (
        f"{point:.0%}"
        "<span style='display:block;font-size:13px;font-weight:600;color:var(--ink2);"
        f"margin-top:4px'>range {low:.0%}–{high:.0%}</span>"
    )


def _confidence_label(c: str) -> str:
    """'high' → 'high confidence'; abstain stays 'abstaining'."""
    return f"{c} confidence" if c in ("low", "medium", "high") else "abstaining"


def _score_card(
    label: str,
    value: str,
    confidence: str,
    fill: float | None = None,
    reason: str = "",
    abstaining: bool = False,
) -> str:
    """A themed score card: label, big value, confidence pill, the main reasons
    behind the number (spec §4), and an optional bar. When ``abstaining`` we show
    the reason (the data still required) openly in a callout instead of hiding it
    behind a dropdown, so the candidate can see what to do to unlock the score."""
    cf = f"rpce-cf-{confidence}"
    bar = ""
    if fill is not None:
        pct = max(0.0, min(100.0, fill * 100))
        bar = (
            f"<div class='rpce-bar'><i class='{cf}' style='width:{pct:.0f}%'></i></div>"
        )
    if reason and abstaining:
        # Visible "data needed" callout (amber), not tucked away in a dropdown.
        reason_html = (
            "<div style='margin-top:12px;background:#fff7ed;border:1px solid #fed7aa;"
            "border-radius:12px;padding:10px 14px;color:#9a3412;font-size:13px;"
            "line-height:1.5;text-align:left'><b>📋 Data needed to show this "
            f"score:</b>{reason}</div>"
        )
    elif reason:
        reason_html = (
            "<details style='margin-top:10px'>"
            "<summary style='cursor:pointer;font-size:13px;font-weight:700;"
            "color:var(--accent1);list-style:none'>ℹ️ Why this score</summary>"
            f"<div class='rpce-reason' style='margin-top:6px'>{reason}</div></details>"
        )
    else:
        reason_html = ""
    return (
        "<div class='rpce-card'>"
        f"<div class='rpce-label'>{label}</div>"
        f"<div class='rpce-val'>{value}</div>"
        f"<span class='rpce-pill {cf}'>{_confidence_label(confidence)}</span>"
        f"{reason_html}{bar}</div>"
    )


def _chip(text: str) -> str:
    return f"<span class='rpce-chip'>{text}</span>"


def _examiner_badge(used: str = "offline") -> str:
    """Show which examiner actually graded this answer: the online AI examiner
    (when a key is set and the call succeeded) or the offline examiner. Mirrors
    the phone."""
    if used == "ai":
        return (
            "<div style='margin-top:8px;color:#15803d;font-weight:700'>"
            "🤖 AI examiner</div>"
        )
    return (
        "<div style='margin-top:8px;color:#b45309;font-weight:700'>"
        "🔌 Offline examiner. Set an AI examiner key (Tools menu) for "
        "richer feedback when online.</div>"
    )


def _ai_toggle_html() -> str:
    """A small in-page AI on/off control for the Section II / Simulate pages, so
    the switch is visible where grading happens (also on Tools ▸ AI examiner)."""
    from anki.rpce import ai

    if not ai.ai_configured():
        return (
            "<span style='color:var(--ink2);font-size:13px'>Offline examiner "
            "(no AI key)</span>"
        )
    on = ai.ai_enabled()
    color = "#15803d" if on else "#b45309"
    return (
        f"<a href='#' onclick=\"pycmd('rpce:aitoggle');return false;\" "
        f"style='color:{color};font-weight:700;font-size:13px;text-decoration:none'>"
        f"🤖 AI grading: {'ON' if on else 'OFF'} · turn {'off' if on else 'on'}</a>"
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
        # Always render the range — abstaining shows "— range 0%–100%", matching
        # Memory/Performance, so every score carries a range.
        return _fmt_range(snap.p_pass, snap.range_low, snap.range_high)

    def section_needs(snap) -> str:
        """The concrete requirement text for an abstaining section: the give-up
        checklist ('N more graded reviews (x/y)' …) as a bulleted list."""
        ev = (snap.evidence or "").strip()
        prefix = "Not enough data: "
        if ev.startswith(prefix):
            items = [x.strip() for x in ev[len(prefix) :].split(";") if x.strip()]
            return (
                "<ul style='margin:6px 0 0;padding-left:18px'>"
                + "".join(f"<li>{i}</li>" for i in items)
                + "</ul>"
            )
        return f"<div style='margin-top:6px'>{ev}</div>"

    # Memory/Performance abstain when there's no review history yet. Wrap their
    # prose as a requirement and append the concrete graded-review target (the
    # same one the sections use) so every "Data needed" note has a number.
    from anki.rpce.scores import GiveUpRule, graded_reviews

    _rule = GiveUpRule()
    _reviews = graded_reviews(col)
    _more = max(0, _rule.min_graded_reviews - _reviews)
    _review_need = (
        "<ul style='margin:6px 0 0;padding-left:18px'>"
        f"<li>{_more} more graded reviews needed "
        f"({_reviews}/{_rule.min_graded_reviews})</li></ul>"
        if _more > 0
        else ""
    )

    def prose_needs(text: str) -> str:
        prose = f"<div style='margin-top:6px'>{text}</div>" if text else ""
        return prose + _review_need

    mem_abstain = mem.point is None
    perf_abstain = perf.point is None
    cards = "".join(
        [
            _score_card(
                "Memory",
                _fmt_range(mem.point, mem.low, mem.high),
                mem.confidence,
                mem.point,
                prose_needs(mem.elaboration or mem.explanation)
                if mem_abstain
                else (mem.elaboration or mem.explanation),
                abstaining=mem_abstain,
            ),
            _score_card(
                "Performance",
                _fmt_range(perf.point, perf.low, perf.high),
                perf.confidence,
                perf.point,
                prose_needs(perf.elaboration or perf.explanation)
                if perf_abstain
                else (perf.elaboration or perf.explanation),
                abstaining=perf_abstain,
            ),
            _score_card(
                "Pass Section I",
                section_value(sec1),
                sec1.confidence,
                None if sec1.abstained else sec1.p_pass,
                section_needs(sec1) if sec1.abstained else sec1.elaboration,
                abstaining=sec1.abstained,
            ),
            _score_card(
                "Pass Section II",
                section_value(sec2),
                sec2.confidence,
                None if sec2.abstained else sec2.p_pass,
                section_needs(sec2) if sec2.abstained else sec2.elaboration,
                abstaining=sec2.abstained,
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
    # Your activity totals (reviews combine across devices via sync; the two
    # practice counters are stored in config, so they persist + sync too). Count
    # reviews of cards that still exist — same basis as the readiness gate — so
    # "reviews done" matches the "x/200 graded reviews" figure (old deck versions
    # can leave orphaned revlog rows that would otherwise inflate this).
    from anki.rpce.scores import graded_reviews

    reviews_done = graded_reviews(col)
    sec2_graded = int(col.get_config("rpce:section2_graded", 0))
    sim_responses = int(col.get_config("rpce:sim_responses", 0))
    activity_html = (
        "<div class='rpce-foot' style='margin-top:22px'><b>Your activity</b><br>"
        f"Reviews done: <b>{reviews_done}</b> · "
        f"Section II answers graded: <b>{sec2_graded}</b> · "
        f"Simulation responses: <b>{sim_responses}</b></div>"
    )
    # Prominent settings control (spec: make the review-session length obvious).
    # A big gear pill-button near the top of the dashboard, not tiny muted text.
    session_html = (
        "<div style='text-align:center;margin-top:26px'>"
        "<a href='#' onclick=\"pycmd('rpce:session_length');return false;\" "
        "style='display:inline-flex;align-items:center;gap:10px;"
        "background:linear-gradient(135deg,#1d4ed8,#3b82f6);color:#fff;"
        "font-weight:800;font-size:var(--fs-body);text-decoration:none;"
        "padding:13px 24px;border-radius:999px;"
        "box-shadow:0 6px 18px rgba(29,78,216,.28)'>"
        f"⚙️ Review session length: <b>{_session_limit()}</b> questions "
        "<span style='opacity:.85;font-weight:700'>(change)</span></a></div>"
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
  {session_html}
  <div class="rpce-grid">{cards}</div>
  <div class="rpce-covhead"><b>Domain coverage</b><span>{pct:.0%} of {total} domains</span></div>
  <div class="rpce-cov"><i style="width:{pct * 100:.0f}%"></i></div>
  <div class="rpce-foot" style="margin-top:22px">{cal_line}</div>
  <div class="rpce-foot" style="margin-top:6px">Use the tabs above — start a <b>Review session</b>,
    practice <b>Section II</b>, or run a <b>Simulation</b>.</div>
  {activity_html}
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


#: Which page the deck-browser webview shows. Section II and Simulate are
#: rendered IN-WINDOW (like the Dashboard) by branching on this flag in
#: ``_on_deck_browser_content`` — not as separate popup dialogs.
_RPCE_VIEW = "dashboard"  # "dashboard" | "section2" | "simulate"
#: Which Section II scenario is on screen (index into ``all_scenarios()``).
_S2_IDX = 0
#: In-window simulation state (see ``_sim_reset``): sim_idx, turn, pending, log,
#: done. ``None`` until first entered.
_SIM: dict | None = None


def _show_dashboard() -> None:
    """The readiness dashboard IS the home screen (the deck-browser banner) — no
    popup. Record a snapshot to refresh 'last updated', then return home."""
    global _RPCE_VIEW
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    from anki.rpce import scores

    _RPCE_VIEW = "dashboard"
    try:
        scores.record_readiness_snapshots(mw.col)
    except Exception as exc:
        print(f"RPCE dashboard error: {exc}")
    mw.moveToState("deckBrowser")


# Injected once with the Section II page: shows a spinner immediately (so the UI
# never looks frozen while grading, which may go online) then hands the base64
# answer to Python. Encoded UTF-8-safe so accented text survives ``btoa``.
_S2_SUBMIT_JS = """<script>
function rpceGradeS2(){
  var v = document.getElementById('s2ans').value;
  document.getElementById('s2fb').innerHTML =
    '<div style="color:#1d4ed8;font-weight:700;margin-top:14px">🤖 Grading your answer…</div>';
  pycmd('rpce:s2grade:' + btoa(unescape(encodeURIComponent(v))));
}
</script>"""


def _s2_scenario():
    """The Section II scenario currently on screen (wraps ``_S2_IDX``)."""
    from anki.rpce import scenarios

    scen = scenarios.all_scenarios()
    return scen[_S2_IDX % len(scen)], _S2_IDX % len(scen), len(scen)


def _section2_html(col) -> str:
    """Section II performance practice as an IN-WINDOW page (mirrors the
    dashboard): domain label, prompt, answer box, Submit (async graded), a
    feedback slot, Next scenario, and a Home link."""
    from anki.rpce import domain_by_code

    s, i, total = _s2_scenario()
    d = domain_by_code(s.domain_code)
    return f"""{_theme_style()}{_S2_SUBMIT_JS}
<div class="rpce-root"><div class="rpce-hero">
  <div style="text-align:left;margin-bottom:8px">
    <a href="#" onclick="pycmd('rpce:home');return false;"
       style="color:var(--accent1);font-weight:700;text-decoration:none">‹ Home</a>
  </div>
  <div class="rpce-h1">Section II <small>performance scenario</small></div>
  <div class="rpce-sub">Domain {d.code}: {d.name} · scenario {i + 1} of {total}</div>
  <div style="margin-top:22px;padding:18px 20px;background:var(--surface2);
    border:1px solid var(--border);border-radius:16px;font-size:var(--fs-lead);
    line-height:1.5;text-align:left">{s.prompt}</div>
  <div style="margin-top:18px;font-weight:700;color:var(--ink2);text-align:left">
    Your ruling &amp; reasoning:</div>
  <textarea id="s2ans" rows="7" style="width:100%;margin-top:8px;padding:14px;
    border:1px solid var(--border);border-radius:14px;background:var(--surface);
    color:var(--ink);font-size:var(--fs-body);font-family:{_FONT};
    box-sizing:border-box;resize:vertical"></textarea>
  <div style="margin-top:14px">
    <button onclick="rpceGradeS2();return false;"
      style="background:var(--accent1);color:#fff;border:none;border-radius:14px;
      padding:13px 26px;font-size:var(--fs-body);font-weight:800;cursor:pointer">
      Submit for grading</button>
  </div>
  <div id="s2fb"></div>
  <div style="margin-top:18px;border-top:1px solid var(--border);padding-top:16px">
    <button onclick="pycmd('rpce:s2next');return false;"
      style="background:var(--surface);color:var(--accent1);border:1px solid var(--border);
      border-radius:14px;padding:11px 22px;font-size:var(--fs-body);font-weight:800;
      cursor:pointer">Next scenario →</button>
  </div>
</div></div>
"""


def _s2_inject(html: str) -> None:
    """Inject feedback HTML into the Section II page's ``#s2fb`` slot without a
    full re-render (keeps the answer + spinner context)."""
    import json

    mw = aqt.mw
    if mw is None:
        return
    try:
        mw.web.eval(
            f"var e=document.getElementById('s2fb');if(e)e.innerHTML={json.dumps(html)};"
        )
    except Exception as exc:
        print(f"RPCE section2 inject error: {exc}")


def _s2_grade(answer_b64: str) -> None:
    """Grade a Section II answer OFF the main thread (spinner shown in JS), then
    inject the score/feedback/badge/model-ruling/citation via ``mw.web.eval``."""
    from anki.rpce import examiner, scores

    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    try:
        answer = base64.b64decode(answer_b64).decode("utf-8").strip()
    except Exception:
        answer = ""
    if not answer:
        _s2_inject(
            "<div style='color:#b45309;font-weight:700;margin-top:14px'>"
            "Write your ruling first.</div>"
        )
        return
    s, _i, _total = _s2_scenario()
    corpus = _load_corpus() or s.gold_answer
    rubric = getattr(s, "rubric", None)
    gold = s.gold_answer

    def op():
        # Section II is graded by the deterministic offline keyword/rubric grader
        # ONLY — no AI grading here (per product decision).
        result = examiner.KeywordExaminer().grade(answer, gold, corpus, rubric)
        return result, "offline"

    def on_done(future) -> None:
        # Runs back on the main thread.
        try:
            result, _used = future.result()
        except Exception as exc:
            _s2_inject(
                "<div style='color:#b45309;font-weight:700;margin-top:14px'>"
                f"Grading failed: {exc}</div>"
            )
            return
        col = mw.col
        if col is not None:
            scores.record_scenario(col)
            col.set_config(
                "rpce:section2_graded",
                int(col.get_config("rpce:section2_graded", 0)) + 1,
            )
        # Which key points the answer hit vs missed (the "words you have / are
        # missing" display), regardless of which grader scored it.
        matched, missing = examiner.keyword_report(answer, gold, rubric)
        kw_html = ""
        if matched:
            kw_html += (
                "<div style='margin-top:10px;color:#15803d;font-weight:700'>"
                "✓ You covered: " + ", ".join(matched) + "</div>"
            )
        if missing:
            kw_html += (
                "<div style='margin-top:4px;color:#be123c;font-weight:700'>"
                "Still missing: " + ", ".join(missing) + "</div>"
            )
        verdict = "pass" if result.passed else "keep practicing"
        html = (
            "<div style='margin-top:16px;padding:16px 18px;background:var(--surface2);"
            "border:1px solid var(--border);border-radius:16px;text-align:left'>"
            "<div style='font-size:20px;font-weight:800;color:var(--ink)'>"
            f"Score: {result.score:.1f}/5.0 "
            f"<span style='color:var(--ink2);font-weight:600'>({verdict})</span></div>"
            f"<div style='margin-top:8px;color:var(--ink)'>{result.feedback}</div>"
            + kw_html
            + f"<div style='margin-top:10px;color:var(--ink)'><b>Model ruling:</b> {gold}</div>"
            + _ref_block(s.ref.section, s.ref.quote)
            + "</div>"
        )
        _s2_inject(html)

    mw.taskman.run_in_background(op, on_done)


def _s2_next() -> None:
    """Advance to the next Section II scenario and re-render the page."""
    global _S2_IDX
    from anki.rpce import scenarios

    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    _S2_IDX = (_S2_IDX + 1) % len(scenarios.all_scenarios())
    mw.moveToState("deckBrowser")


def _show_scenarios() -> None:
    """Section II is an in-window page (like the Dashboard), rendered through the
    deck-browser content hook — not a popup dialog."""
    global _RPCE_VIEW
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    _RPCE_VIEW = "section2"
    mw.moveToState("deckBrowser")


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
    """Route dashboard/Section II/Simulate webview commands. The two practice
    pages render in-window (no popups), so their Submit/Next/Home actions arrive
    here as ``pycmd`` messages. Returns a filter result tuple."""
    if message == "rpce:reference":
        _show_reference()
        return (True, None)
    if message == "rpce:logout":
        _logout_ankiweb()
        return (True, None)
    if message == "rpce:session_length":
        _set_session_length()
        return (True, None)
    if message == "rpce:home":
        _show_dashboard()  # resets _RPCE_VIEW to "dashboard"
        return (True, None)
    if message == "rpce:newsession":
        _start_new_session()
        return (True, None)
    if message == "rpce:aitoggle":
        from anki.rpce import ai

        ai.set_ai_enabled(not ai.ai_enabled())
        aqt.mw.moveToState("deckBrowser")  # re-render the current page with new state
        return (True, None)
    # Section II performance practice.
    if message.startswith("rpce:s2grade:"):
        _s2_grade(message[len("rpce:s2grade:") :])
        return (True, None)
    if message == "rpce:s2next":
        _s2_next()
        return (True, None)
    # Simulation mode.
    if message.startswith("rpce:simrespond:"):
        _sim_respond(message[len("rpce:simrespond:") :])
        return (True, None)
    if message == "rpce:simnext":
        _sim_next()
        return (True, None)
    if message == "rpce:simai":
        _sim_ai()
        return (True, None)
    return handled


# Injected once with the Simulate page: shows a spinner immediately then hands
# the base64 response to Python (UTF-8-safe, like the Section II submitter).
_SIM_SUBMIT_JS = """<script>
function rpceRespondSim(){
  var v = document.getElementById('simans').value;
  document.getElementById('simfb').innerHTML =
    '<div style="color:#1d4ed8;font-weight:700;margin-top:14px">🤖 Grading your response…</div>';
  // Pass the current scroll position so the re-rendered page can restore it
  // (don't jump back to the top on Respond).
  var y = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
  pycmd('rpce:simrespond:' + y + ':' + btoa(unescape(encodeURIComponent(v))));
}
</script>"""


def _sim_current():
    """The Simulation currently on screen. For an AI-generated scenario this is
    the ``Simulation`` built in ``_sim_ai`` and stashed in ``_SIM['sim']``;
    otherwise it wraps the scripted ``_SIM['sim_idx']``."""
    from anki.rpce import simulations

    if _SIM and _SIM.get("ai") and _SIM.get("sim") is not None:
        return _SIM["sim"]
    sims = simulations.all_simulations()
    return sims[_SIM["sim_idx"] % len(sims)]


def _sim_play() -> None:
    """Advance the current meeting, appending spoken lines to the transcript log
    until the next decision point (sets ``pending``) or adjournment (``done``).
    Mirrors ``SimulationDialog._play`` but drives module state instead of Qt
    widgets, so the meeting survives across the re-renders that pycmd triggers."""
    sim = _sim_current()
    while _SIM["turn"] < len(sim.turns):
        turn = sim.turns[_SIM["turn"]]
        # AI-generated decision turns carry no spoken line; only echo real lines.
        if turn.line:
            _SIM["log"].append(
                "<p style='margin:10px 0'>"
                f"<b style='color:#1d4ed8'>{turn.speaker}:</b> {turn.line}</p>"
            )
        if turn.needs_response:
            _SIM["pending"] = turn
            _SIM["turn"] += 1
            return
        _SIM["turn"] += 1
    _SIM["pending"] = None
    _SIM["done"] = True


def _sim_reset() -> None:
    """Start a RANDOM meeting fresh and play to the first decision point (so you
    don't always get the same simulation on entering Simulate)."""
    global _SIM
    import random

    from anki.rpce import simulations

    n = len(simulations.all_simulations())
    idx = random.randrange(n) if n else 0
    _SIM = {"sim_idx": idx, "turn": 0, "pending": None, "log": [], "done": False}
    _sim_play()


def _simulate_html(col) -> str:
    """Simulation mode as an IN-WINDOW page (mirrors the dashboard): a scripted
    meeting plays out turn by turn; at each decision point the candidate responds
    as the parliamentarian and the response is graded for accuracy (async, with a
    spinner). No RONR citation is required of the candidate."""
    from anki.rpce import ai

    if _SIM is None:
        _sim_reset()
    sim = _sim_current()
    transcript = "".join(_SIM["log"])
    # AI scenario controls: a Generate button, a "generating…" state, and any
    # last-generation error. Only shown when a key is set and AI is enabled;
    # scripted simulations are always available regardless.
    ai_html = ""
    if ai.ai_configured() and ai.ai_enabled():
        if _SIM.get("generating"):
            ai_html = (
                "<div style='margin-top:18px;color:var(--accent1);font-weight:800'>"
                "🤖 Generating a scenario…</div>"
            )
        else:
            err = _SIM.get("ai_error")
            err_html = (
                "<div style='margin-top:10px;color:#b45309;font-weight:700'>"
                f"{err}</div>"
                if err
                else ""
            )
            ai_html = (
                "<div style='margin-top:18px;border-top:1px solid var(--border);"
                "padding-top:16px'>"
                "<button onclick=\"pycmd('rpce:simai');return false;\" "
                "style='background:var(--surface);color:var(--accent1);"
                "border:1px solid var(--border);border-radius:14px;padding:11px 22px;"
                "font-size:var(--fs-body);font-weight:800;cursor:pointer'>"
                "🤖 Generate AI scenario</button>"
                f"{err_html}</div>"
            )
    ai_tag = (
        "<span class='rpce-pill' style='background:rgba(21,128,61,.14);"
        "color:#15803d;margin-left:8px'>🤖 AI-generated</span>"
        if _SIM.get("ai")
        else ""
    )
    if _SIM.get("continuing"):
        # AI meeting is mid-turn: the model is generating the next situation.
        controls = (
            "<div style='margin-top:18px;color:var(--accent1);font-weight:800'>"
            "🤖 The meeting continues…</div>"
        )
    elif _SIM["done"]:
        controls = (
            "<div style='margin-top:18px;font-size:20px;font-weight:800;"
            "color:var(--ready)'>✅ Meeting adjourned. Well done.</div>"
            "<div style='margin-top:14px'>"
            "<button onclick=\"pycmd('rpce:simnext');return false;\" "
            "style='background:var(--accent1);color:#fff;border:none;border-radius:14px;"
            "padding:13px 26px;font-size:var(--fs-body);font-weight:800;cursor:pointer'>"
            "Next meeting →</button></div>"
        )
    else:
        pending = _SIM["pending"]
        controls = (
            "<div style='margin-top:18px;font-weight:800;color:var(--ink);"
            f"text-align:left'>🎤 {pending.prompt}</div>"
            "<textarea id='simans' rows='5' placeholder='Respond as the parliamentarian…' "
            "style='width:100%;margin-top:8px;padding:14px;border:1px solid var(--border);"
            "border-radius:14px;background:var(--surface);color:var(--ink);"
            f"font-size:var(--fs-body);font-family:{_FONT};box-sizing:border-box;"
            "resize:vertical'></textarea>"
            "<div style='margin-top:14px'>"
            '<button onclick="rpceRespondSim();return false;" '
            "style='background:var(--accent1);color:#fff;border:none;border-radius:14px;"
            "padding:13px 26px;font-size:var(--fs-body);font-weight:800;cursor:pointer'>"
            "Respond</button></div>"
            "<div id='simfb'></div>"
        )
    return f"""{_theme_style()}{_SIM_SUBMIT_JS}
<div class="rpce-root"><div class="rpce-hero">
  <div style="text-align:left;margin-bottom:8px">
    <a href="#" onclick="pycmd('rpce:home');return false;"
       style="color:var(--accent1);font-weight:700;text-decoration:none">‹ Home</a>
  </div>
  <div class="rpce-h1">{sim.title}{ai_tag}</div>
  <div class="rpce-sub"><i>{sim.setting}</i></div>
  <div style="margin-top:20px;padding:16px 20px;background:var(--surface2);
    border:1px solid var(--border);border-radius:16px;text-align:left;
    font-size:var(--fs-body);line-height:1.5">{transcript}</div>
  {controls}
  {ai_html}
</div></div>
<script>
  // Restore the scroll position captured on Respond, so the page doesn't jump
  // back to the top when the meeting re-renders. Fresh loads have scroll_y=0.
  (function(){{ var y={int(_SIM.get("scroll_y", 0)) if _SIM else 0};
    if(y>0) window.scrollTo(0, y); }})();
</script>
"""


def _sim_respond(payload: str) -> None:
    """Grade the parliamentarian's response OFF the main thread (spinner shown in
    JS), append the debrief to the transcript, advance the meeting, and re-render
    the page. Faithful to ``SimulationDialog._respond``'s auto-advance flow.

    ``payload`` is ``"<scrollY>:<base64 answer>"`` — the scroll offset is stashed
    so the re-rendered page can restore it (don't jump to the top on Respond)."""
    from anki.rpce import examiner, scores

    mw = aqt.mw
    if mw is None or mw.col is None or _SIM is None:
        return
    pending = _SIM.get("pending")
    if pending is None:
        return
    scroll_str, _, answer_b64 = payload.partition(":")
    try:
        _SIM["scroll_y"] = int(scroll_str)
    except (ValueError, TypeError):
        _SIM["scroll_y"] = 0
    try:
        answer = base64.b64decode(answer_b64).decode("utf-8").strip()
    except Exception:
        answer = ""
    if not answer:
        return
    corpus = _load_corpus() or pending.gold
    rubric = getattr(pending, "rubric", None)
    gold = pending.gold
    # AI examiner ONLY for AI-generated scenarios; scripted sims stay OFFLINE.
    is_ai = bool(_SIM.get("ai"))
    # Echo the response into the transcript before grading.
    _SIM["log"].append(
        f"<p style='margin:10px 0'><b>You (parliamentarian):</b> {answer}</p>"
    )

    expected = getattr(pending, "expected", ()) or ()
    ref = getattr(pending, "ref", None)
    step_cite = ref.section if ref else None

    def op():
        # Runs OFF the UI thread.
        if is_ai:
            ex = examiner.make_examiner()
            result = ex.grade(answer, gold, corpus, rubric)
            return result, getattr(ex, "used", "offline")
        # Scripted simulation: short, step-by-step. Grade leniently against this
        # step's key concept(s) so a brief correct reply ("wait for a second")
        # is full credit — NOT the stricter Section II performance grader.
        result = examiner.grade_sim_step(answer, expected, step_cite)
        return result, None

    def on_done(future) -> None:
        # Runs back on the main thread.
        try:
            result, used = future.result()
        except Exception as exc:
            _SIM["log"].append(f"<p style='color:#b45309'>Grading failed: {exc}</p>")
            mw.moveToState("deckBrowser")
            return
        col = mw.col
        if col is not None:
            scores.record_scenario(col)
            col.set_config(
                "rpce:sim_responses",
                int(col.get_config("rpce:sim_responses", 0)) + 1,
            )
        verdict = "pass" if result.passed else "keep practicing"
        ref = pending.ref
        ref_html = _ref_block(ref.section, ref.quote) if ref else ""
        _SIM["log"].append(
            "<div style='margin:12px 0;padding:14px 16px;background:var(--surface);"
            "border:1px solid var(--border);border-radius:14px'>"
            "<div style='font-weight:800;color:var(--ink)'>"
            f"Examiner: {result.score:.1f}/5.0 ({verdict})</div>"
            f"<div style='margin-top:6px;color:var(--ink)'>{result.feedback}</div>"
            + (_examiner_badge(used) if used else "")
            + f"<div style='margin-top:8px;color:var(--ink)'><b>Model ruling:</b> {gold}</div>"
            + ref_html
            + "</div>"
        )
        # Advance through any remaining pre-generated turns to the next decision
        # point (or the end of the fixed script) and re-render.
        _SIM["pending"] = None
        _sim_play()
        # AI sims: don't stop at the end of the fixed script — continue the
        # meeting dynamically, reacting to the ruling just graded. Scripted sims
        # keep their existing fixed-script behavior (they simply adjourn here).
        if is_ai and _SIM.get("done") and not _SIM.get("pending"):
            _SIM["done"] = False  # not truly finished — ask the AI to continue
            _sim_continue_ai(answer)
            return
        mw.moveToState("deckBrowser")

    mw.taskman.run_in_background(op, on_done)


#: Safety cap: an AI meeting continues for at most this many extra decision
#: rounds (each one an ``ai.continue_simulation`` call) so the conversation can
#: never run forever. Tracked in ``_SIM['ai_rounds']``.
_SIM_AI_MAX_ROUNDS = 5


def _sim_transcript_text() -> str:
    """A compact PLAIN-TEXT transcript of the meeting so far, for the AI
    continuation prompt (strips the accumulated HTML from ``_SIM['log']``)."""
    import html
    import re

    parts = []
    for chunk in _SIM["log"] if _SIM else []:
        text = re.sub(r"<[^>]+>", " ", str(chunk))
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _sim_continue_ai(last_ruling: str) -> None:
    """AI sims ONLY: after a decision is graded and the pre-generated turns are
    exhausted, ask the model to CONTINUE the meeting — reacting to the ruling and
    presenting the next situation/decision — instead of ending on the fixed
    script. Runs OFF the UI thread with a "the meeting continues…" spinner state,
    is bounded by ``_SIM_AI_MAX_ROUNDS``, and ends the meeting gracefully with a
    note if the continuation is unavailable (offline/error)."""
    from anki.rpce import ai, simulations

    mw = aqt.mw
    if mw is None or mw.col is None or _SIM is None:
        return

    def adjourn(note: str) -> None:
        _SIM["log"].append(
            "<p style='margin:10px 0;color:var(--ink2)'><i>" + note + "</i></p>"
        )
        _SIM["pending"] = None
        _SIM["continuing"] = False
        _SIM["done"] = True
        mw.moveToState("deckBrowser")

    # Safety cap: never let the conversation run forever.
    rounds = int(_SIM.get("ai_rounds", 0))
    if rounds >= _SIM_AI_MAX_ROUNDS:
        adjourn("The chair moves to adjourn; the practice meeting ends here.")
        return
    # Show the "meeting continues…" spinner state while the model responds.
    _SIM["continuing"] = True
    history = _sim_transcript_text()
    mw.moveToState("deckBrowser")

    def op():
        # Runs OFF the UI thread. Bound the prompt to a corpus slice (DATA).
        context = _corpus_slice(_load_corpus(), 12000)
        return ai.continue_simulation(history, last_ruling, context)

    def on_done(future) -> None:
        if _SIM is None:
            return
        try:
            data = future.result()
        except Exception:
            data = None
        if not data:
            # Offline / error / malformed → end the meeting gracefully.
            adjourn(
                "The meeting cannot continue right now (offline or "
                "unavailable). Adjourned."
            )
            return
        _SIM["continuing"] = False
        _SIM["ai_rounds"] = rounds + 1
        new_turns, has_decision = _ai_turns_from_json(data.get("turns"))
        sim = _SIM.get("sim")
        if sim is not None and new_turns:
            # Extend the frozen Simulation's turns so _sim_play drives the new
            # lines exactly like the pre-generated ones.
            _SIM["sim"] = simulations.Simulation(
                id=sim.id,
                domain_code=sim.domain_code,
                title=sim.title,
                setting=sim.setting,
                turns=sim.turns + tuple(new_turns),
            )
        # Play the new spoken lines; stop at the next decision if one was given.
        _sim_play()
        if data.get("adjourned") or not has_decision:
            # The model closed the meeting (or offered no next decision).
            _SIM["pending"] = None
            _SIM["done"] = True
        mw.moveToState("deckBrowser")

    mw.taskman.run_in_background(op, on_done)


def _sim_next() -> None:
    """Move on to a RANDOM different meeting and re-render."""
    global _SIM
    import random

    from anki.rpce import simulations

    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    sims = simulations.all_simulations()
    cur = _SIM["sim_idx"] if _SIM else 0
    others = [i for i in range(len(sims)) if i != cur]
    idx = random.choice(others) if others else 0
    _SIM = {"sim_idx": idx, "turn": 0, "pending": None, "log": [], "done": False}
    _sim_play()
    mw.moveToState("deckBrowser")


def _corpus_slice(corpus: str, size: int) -> str:
    """A bounded chunk of the RONR corpus to keep the generation prompt small.
    Picks a random window so repeated generations draw on different sections."""
    corpus = corpus or ""
    if len(corpus) <= size:
        return corpus
    import random

    start = random.randint(0, len(corpus) - size)
    return corpus[start : start + size]


def _ai_turns_from_json(turns):
    """Convert a list of AI turn dicts into ``SimTurn``s (shared by the initial
    ``generate_simulation`` and the dynamic ``continue_simulation`` flows). All
    text is HTML-escaped so a stray tag can't break the page. Decision turns carry
    ``gold``/``cite``/``quote`` (as a ``refs.Ref``) so grading + the citation
    block work exactly like scripted ones. Returns ``(built, has_decision)``."""
    import html

    from anki.rpce import refs, simulations

    def esc(v) -> str:
        return html.escape(str(v or "").strip())

    built = []
    has_decision = False
    for t in turns if isinstance(turns, list) else []:
        if not isinstance(t, dict):
            continue
        if t.get("decision") and t.get("gold"):
            cite = esc(t.get("cite"))
            quote = esc(t.get("quote"))
            ref = refs.Ref(cite, quote) if cite else None
            built.append(
                simulations.SimTurn(
                    speaker="",
                    line="",
                    prompt=esc(t.get("decision")),
                    gold=esc(t.get("gold")),
                    ref=ref,
                )
            )
            has_decision = True
        elif t.get("line"):
            built.append(
                simulations.SimTurn(
                    speaker=esc(t.get("speaker")) or "Member",
                    line=esc(t.get("line")),
                )
            )
    return built, has_decision


def _build_ai_simulation(data):
    """Turn the AI JSON into a ``Simulation`` in the SAME shape the scripted flow
    expects. AI text is HTML-escaped. Returns ``None`` if the JSON has no usable
    decision point (so the UI falls back)."""
    import html

    from anki.rpce import simulations

    if not isinstance(data, dict):
        return None

    def esc(v) -> str:
        return html.escape(str(v or "").strip())

    built, has_decision = _ai_turns_from_json(data.get("turns"))
    if not built or not has_decision:
        return None
    return simulations.Simulation(
        id=0,
        domain_code=0,
        title=esc(data.get("title")) or "AI-generated meeting",
        setting=esc(data.get("setting")),
        turns=tuple(built),
    )


def _sim_ai() -> None:
    """Generate an AI meeting scenario grounded in the RONR corpus, OFF the UI
    thread, and load it into ``_SIM`` in the scripted shape. Shows a
    "generating…" state first; on any failure it shows a small message and stays
    on the current scenario, so the page never breaks."""
    global _SIM
    from anki.rpce import ai

    mw = aqt.mw
    if mw is None or mw.col is None or _SIM is None:
        return
    # Render the "🤖 Generating a scenario…" state immediately.
    _SIM["generating"] = True
    _SIM["ai_error"] = None
    mw.moveToState("deckBrowser")

    def op():
        # Runs OFF the UI thread. Bound the prompt to a corpus slice.
        context = _corpus_slice(_load_corpus(), 12000)
        return ai.generate_simulation(context)

    def on_done(future) -> None:
        global _SIM
        try:
            data = future.result()
        except Exception:
            data = None
        if _SIM is None:
            return
        _SIM["generating"] = False
        sim = _build_ai_simulation(data) if data else None
        if sim is None:
            _SIM["ai_error"] = (
                "Couldn't generate a scenario (offline or unavailable) — "
                "try a scripted one."
            )
            mw.moveToState("deckBrowser")
            return
        # Load into the scripted shape, flag it AI-generated, and play to the
        # first decision point.
        _SIM = {
            "sim_idx": 0,
            "sim": sim,
            "ai": True,
            "turn": 0,
            "pending": None,
            "log": [],
            "done": False,
        }
        _sim_play()
        mw.moveToState("deckBrowser")

    mw.taskman.run_in_background(op, on_done)


def _show_simulation() -> None:
    """Simulate is an in-window page (like the Dashboard), rendered through the
    deck-browser content hook — not a popup dialog. Starts a fresh meeting."""
    global _RPCE_VIEW
    mw = aqt.mw
    if mw is None or mw.col is None:
        return
    _RPCE_VIEW = "simulate"
    _sim_reset()
    mw.moveToState("deckBrowser")


# Object names of Anki menu actions that manage decks/collections or edit
# content — all irrelevant to the RPCE study flow, so hide them (hiding an action
# also disables its keyboard shortcut). Matched by objectName, which is stable
# across languages. Found by inspecting qt/aqt/forms/main.ui.
_HIDE_ACTION_NAMES = {
    "actionSwitchProfile",  # File: switch profile
    "actionImport",  # File: import (also enforced separately below)
    "actionExport",  # File: export collection
    "action_create_backup",  # File: create backup
    "action_open_backup",  # File: restore backup (could replace the deck)
    "actionStudyDeck",  # Tools: study deck
    "actionCreateFiltered",  # Tools: create filtered deck
    "actionFullDatabaseCheck",  # Tools: check database
    "actionCheckMediaDatabase",  # Tools: check media
    "actionEmptyCards",  # Tools: empty cards
    "actionAdd_ons",  # Tools: add-ons
    "actionNoteTypes",  # Tools: manage note types
    "action_check_for_updates",  # Tools: check for add-on updates
    "actionDocumentation",  # Help: Anki manual (confusing for RPCE users)
    "actionDonate",  # Help: donate to Anki
}

# Fallback English text substrings (lowercase) for any equivalent item added
# under a different objectName. The kept items (Exit/Quit, Preferences,
# Undo/Redo, About, zoom, full screen, and the RPCE-added Tools actions) match
# none of these.
_HIDE_ACTION_TEXT = (
    "import",
    "export",
    "switch profile",
    "note type",
    "manage note",
    "add-on",
    "addon",
    "check media",
    "check database",
    "study deck",
    "filtered deck",
    "empty cards",
    "backup",
    "browse",
    "check for updates",
    "get shared",
    "preferences",
)


def _declutter_menus(mw) -> None:
    """Hide Anki menu items that manage decks/collections or edit content, so the
    menu bar only offers what's useful for RPCE study: sync (top-right button),
    Exit, Undo/Redo, and the RPCE Tools actions. Matches each action by
    objectName first, then a small English text fallback. Fully guarded so a
    menu-shape change upstream never blocks startup."""
    # Actual menu attribute names, from qt/aqt/forms/main.ui (File is "menuCol";
    # the View menu is "menuqt_accel_view", not "menuView").
    for menu_name in (
        "menuCol",
        "menuEdit",
        "menuqt_accel_view",
        "menuTools",
        "menuHelp",
    ):
        try:
            menu = getattr(mw.form, menu_name, None)
            if menu is None:
                continue
            for act in menu.actions():
                try:
                    if act.isSeparator():
                        continue
                    name = act.objectName()
                    text = act.text().replace("&", "").lower()
                    if name in _HIDE_ACTION_NAMES or any(
                        s in text for s in _HIDE_ACTION_TEXT
                    ):
                        act.setVisible(False)
                        act.setEnabled(False)
                except Exception:
                    continue
        except Exception as exc:  # never block startup over decluttering
            print(f"RPCE menu-declutter error ({menu_name}): {exc}")


def _disable_editing(mw) -> None:
    """Enforce read-only study: neutralize the card/note editor and the browser
    entry points (reviewer 'e' key + Edit button, the 'b' browse shortcut, and
    Add Card) so no editing UI can open. The RPCE deck is generated for the
    candidate; editing it would desync from the phone. Shows a tooltip instead."""
    from aqt.utils import tooltip

    def _blocked(*_args, **_kwargs) -> None:
        tooltip("Editing is disabled in Speedrun for the RPCE.")

    # These bound methods funnel every edit/browse entry point through
    # aqt.dialogs.open(...); shadowing them on the instance blocks all of them.
    for attr in ("onEditCurrent", "onBrowse", "onAddCard"):
        try:
            setattr(mw, attr, _blocked)
        except Exception as exc:
            print(f"RPCE edit-disable error ({attr}): {exc}")


def _brand_main_window() -> None:
    """Brand the window (title + logo icon). All RPCE actions live on the top
    toolbar tabs (Review session / Section II / Simulate / Dashboard), so there is no
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
        from anki.rpce import ai

        act = QAction("Review session length…", mw)
        qconnect(act.triggered, _set_session_length)
        mw.form.menuTools.addAction(act)
        aikey = QAction("Set AI examiner key…", mw)
        qconnect(aikey.triggered, _set_ai_key)
        mw.form.menuTools.addAction(aikey)
        # Checkable AI on/off — only meaningful once a key is configured. Toggling
        # flips online grading (offline examiner is the fallback either way).
        ai_toggle = QAction("AI examiner (online grading)", mw)
        ai_toggle.setCheckable(True)
        ai_toggle.setChecked(ai.ai_enabled())
        ai_toggle.setEnabled(ai.ai_configured())
        qconnect(ai_toggle.toggled, _toggle_ai_examiner)
        mw.form.menuTools.addAction(ai_toggle)
        logout = QAction("Log out of AnkiWeb", mw)
        qconnect(logout.triggered, _logout_ankiweb)
        mw.form.menuTools.addAction(logout)
    except Exception as exc:
        print(f"RPCE menu error: {exc}")
    # Block deck import: the RPCE deck is generated; importing an arbitrary
    # collection would break its notetypes/tags. Hide the menu action (also kills
    # its Ctrl+Shift+I shortcut) and refuse drag-and-drop file imports.
    try:
        mw.form.actionImport.setVisible(False)
        mw.form.actionImport.setEnabled(False)
        mw.setAcceptDrops(False)
    except Exception as exc:
        print(f"RPCE import-disable error: {exc}")
    # Declutter the menu bar (hide deck/collection-management + editing items) and
    # enforce read-only study (no editor/browser can open). Both are guarded.
    _declutter_menus(mw)
    _disable_editing(mw)


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
    """Seed (or update in place) the RPCE deck from the shared starter deck.

    Notes carry stable GUIDs, so the importer matches existing notes by GUID and
    updates their content in place — critically with ``with_scheduling=false`` so
    each card KEEPS its review progress across deck-version bumps. Genuinely new
    questions arrive as fresh new cards. Previously we wiped + re-imported, which
    reset every card to "new" (in fixed insertion order), so the candidate saw
    the exact same first questions again after every content update."""
    from anki.rpce import build_starter_deck

    apkg = _rpce_starter_apkg()
    if apkg:
        try:
            import anki.import_export_pb2 as ie

            opts = ie.ImportAnkiPackageOptions(
                merge_notetypes=True,  # keep one notetype; apply template/CSS updates
                update_notes=ie.IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS,
                update_notetypes=ie.IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS,
                with_scheduling=False,  # preserve the candidate's existing progress
            )
            mw.col.import_anki_package(
                ie.ImportAnkiPackageRequest(package_path=apkg, options=opts)
            )
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
    # This is a rebranded fork pointed at its own sync host, so Anki's background
    # update check just hits AnkiWeb and logs "update check failed". We already
    # hide the manual "check for updates" UI; disable the automatic one too.
    # Idempotent + persisted in the profile meta, so it also covers next launch.
    try:
        if mw.pm.check_for_updates():
            mw.pm.set_update_check(False)
    except Exception:
        pass
    from anki.rpce import RPCE_DECK_VERSION

    if mw.col.decks.by_name("RPCE") is None:
        _build_or_import_rpce_deck(mw)
        deck = mw.col.decks.by_name("RPCE")
        if deck is not None:
            mw.col.decks.set_current(deck["id"])
        return
    # Keep the desktop deck in step with the shared starter deck. On a content
    # version bump we RE-IMPORT IN PLACE (match by GUID, with_scheduling=false) so
    # question text/hints/templates update while every card KEEPS its review
    # progress — we no longer wipe the deck first, which used to reset all cards
    # to "new" and re-show the same questions in fixed order every session.
    try:
        # Only genuinely non-RPCE notes are stale. Match RPCE notetypes by PREFIX
        # (note:RPCE*): repeated imports can leave name-collision variants ("RPCE
        # Q 1++", "RPCE Concept 1+++"), and the exact-name filter treated ALL of
        # those as stale — deleting every note each launch, which forced a reseed
        # that reset all cards to new (the "same questions every session" bug).
        stale = mw.col.find_notes("deck:RPCE -note:RPCE*")
        if stale:
            mw.col.remove_notes(stale)
        current = bool(mw.col.find_cards(f"tag:rpce::ver::{RPCE_DECK_VERSION}"))
        did_reseed = False
        if _rpce_starter_apkg() and not current:
            # In-place update: no remove_notes() here — that wiped scheduling.
            _build_or_import_rpce_deck(mw)
            did_reseed = True
        elif not mw.col.find_cards("note:RPCE*"):
            _build_or_import_rpce_deck(mw)
            did_reseed = True
        deck = mw.col.decks.by_name("RPCE")
        if deck is not None:
            mw.col.decks.set_current(deck["id"])
            # Lift the daily cap on the existing deck too (build sets it for new
            # ones); idempotent so it's cheap on every open. NO_SORT keeps the
            # deck's built-in add-order, which the exporter lays out round-robin
            # by question type (a uniform RANDOM_CARD order over-showed MCQs).
            try:
                conf = mw.col.decks.config_dict_for_deck_id(deck["id"])
                if (
                    conf.get("new", {}).get("perDay", 0) < 9999
                    or conf.get("newSortOrder", 0) != 1
                ):
                    conf["new"]["perDay"] = 9999
                    conf["rev"]["perDay"] = 9999
                    conf["newSortOrder"] = 1  # NEW_CARD_SORT_ORDER_NO_SORT
                    mw.col.decks.update_config(conf)
            except Exception:
                pass
        # A re-seed bulk-imports/removes notes and bumps the schema, which can
        # leave Anki's counts inconsistent so the pre-sync sanity check aborts
        # with "please use Check Database, then sync". Run that check (same as
        # Tools > Check Database) ONCE per deck version — covers both a fresh
        # re-seed and a collection reseeded by an older build that never ran it.
        # After it, the next sync is a clean one-time full alignment (desktop is
        # the content source of truth); every later sync is incremental, so
        # reviews/scores from both devices combine two-way.
        try:
            checked = mw.col.get_config("rpce:integrity_version", default="")
            if did_reseed or checked != RPCE_DECK_VERSION:
                mw.col.fix_integrity()
                mw.col.set_config("rpce:integrity_version", RPCE_DECK_VERSION)
            # A re-seed (bulk remove + apkg import) diverges the collection from
            # AnkiWeb, so the next NORMAL incremental sync fails its sanity check
            # ("Please use the Check Database function, then sync again"). fix_integrity
            # alone doesn't clear it. Mark the schema modified so the next sync is a
            # FULL (one-way) sync, which _auto_full_sync auto-resolves by uploading
            # the authoritative desktop deck. Only on an actual re-seed.
            if did_reseed:
                try:
                    mw.col.mod_schema(check=False)
                except Exception as exc:
                    print(f"RPCE schema-mark error: {exc}")
        except Exception as exc:
            print(f"RPCE integrity check failed: {exc}")
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
    # Tally this answer for the completion-page breakdown (rating + format).
    global _session_done, _session_stats
    if _session_stats is None:
        _session_stats = _new_session_stats()
    _session_stats["total"] += 1
    bucket = _RATING_BUCKET.get(ease)
    if bucket:
        _session_stats["ratings"][bucket] += 1
    kind = _rpce_card_kind(card)
    _session_stats["by_type"][kind] = _session_stats["by_type"].get(kind, 0) + 1
    concept, domain = _rpce_card_concept_domain(card)
    if concept:
        _session_stats["concepts"].add(concept)
    if domain:
        _session_stats["by_domain"][domain] = (
            _session_stats["by_domain"].get(domain, 0) + 1
        )
    # Cap the session at the configured length, then return home for a new one.
    _session_done += 1
    if _session_done >= _session_limit():
        from aqt.qt import QTimer

        global _last_session_stats
        _last_session_stats = _session_stats  # freeze for the completion page
        # No artificial delay — the user has already seen + rated this card, so
        # jump straight to the completion page on the next event-loop tick.
        QTimer.singleShot(0, _end_session)


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
        "<style>"
        + render_js.RENDER_CSS
        + "</style>"
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
#: Live tally for the current session; frozen into ``_last_session_stats`` at the
#: cap so the completion page can show a breakdown after the counter resets.
_session_stats: dict | None = None
_last_session_stats: dict | None = None

#: Rating (ease) → bucket for the completion-page breakdown.
_RATING_BUCKET = {1: "again", 2: "hard", 3: "good", 4: "easy"}
#: Payload ``kind`` → human label for the per-type breakdown.
_KIND_LABEL = {
    "cloze": "Cloze",
    "mcq": "Multiple choice",
    "multi": "Select-all",
    "order": "Ordering",
}


def _new_session_stats() -> dict:
    return {
        "total": 0,
        "ratings": {"again": 0, "hard": 0, "good": 0, "easy": 0},
        "by_type": {},
        "concepts": set(),  # distinct concept ids practised this session
        "by_domain": {},  # readable domain name -> answers
    }


def _rpce_card_concept_domain(card) -> tuple[str | None, str | None]:
    """The card's concept id and readable domain name from its rpce tags, for the
    session breakdown ('rpce::concept::<id>' and 'rpce::domain::<code>')."""
    from anki.rpce import domain_by_code

    concept = domain = None
    try:
        for t in card.note().tags:
            if t.startswith("rpce::concept::"):
                concept = t.rsplit("::", 1)[-1]
            elif t.startswith("rpce::domain::"):
                try:
                    domain = domain_by_code(int(t.rsplit("::", 1)[-1])).name
                except Exception:
                    pass
    except Exception:
        pass
    return concept, domain


def _rpce_card_kind(card) -> str:
    """The question format of an RPCE card ('Cloze'/'Multiple choice'/…), read
    from its payload JSON; 'Question' if it can't be determined."""
    import json

    try:
        note = card.note()
        for f in (
            "Payload",
            "ClozePayload",
            "McqPayload",
            "SecondPayload",
            "DebatablePayload",
        ):
            try:
                raw = note[f]
            except Exception:
                continue
            if raw:
                kind = json.loads(raw).get("kind", "")
                return _KIND_LABEL.get(kind, "Question")
    except Exception:
        pass
    return "Question"


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
        mw,
        "Review session length",
        "Questions per review session:",
        _session_limit(),
        1,
        500,
        1,
    )
    if ok:
        mw.col.set_config("rpce:session_limit", int(n))
        tooltip(f"Review sessions are now {n} questions.")
        # Re-render the dashboard so the ⚙️ pill shows the new length immediately.
        if mw.state == "deckBrowser":
            mw.moveToState("deckBrowser")


def _set_ai_key() -> None:
    """Set/clear the OpenAI examiner key. Stored in a local git-ignored file
    (~/.rpce/openai_key) — NEVER in the collection (which syncs) or the repo, so
    the secret can't leak. Blank clears it; the app then uses the offline
    examiner. Enables the online AI examiner for Section II + simulations."""
    from aqt.qt import QInputDialog, QLineEdit
    from aqt.utils import tooltip
    from anki.rpce import ai

    mw = aqt.mw
    if mw is None:
        return
    current = "•••• (set)" if ai.ai_configured() else ""
    key, ok = QInputDialog.getText(
        mw,
        "AI examiner key",
        "OpenAI API key (leave blank to clear and use the offline examiner):",
        QLineEdit.EchoMode.Password,
        current,
    )
    if not ok or key.strip() == "••••  (set)".strip():
        return  # unchanged
    if key.strip().startswith("••"):
        return  # user left the masked placeholder untouched
    ai.set_openai_key(key.strip())
    tooltip(
        "AI examiner enabled — online grading with offline fallback."
        if key.strip()
        else "AI key cleared — using the offline examiner."
    )


def _toggle_ai_examiner(checked: bool) -> None:
    """Turn online AI grading on/off (works even when online). The offline
    examiner is the fallback either way; only meaningful when a key is set."""
    from aqt.utils import tooltip
    from anki.rpce import ai

    ai.set_ai_enabled(checked)
    tooltip(
        "AI grading on — online with offline fallback."
        if checked
        else "AI grading off — using the offline examiner."
    )


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


def _stat_pill(value: str, label: str, color: str) -> str:
    """One big-number stat tile for the completion page."""
    return (
        "<div style='flex:1;min-width:96px;background:var(--surface2);"
        "border:1px solid var(--border);border-radius:16px;padding:14px 10px;text-align:center'>"
        f"<div style='font-size:30px;font-weight:900;color:{color};line-height:1'>{value}</div>"
        f"<div style='margin-top:6px;font-size:13px;font-weight:700;color:var(--ink2)'>{label}</div>"
        "</div>"
    )


def _session_done_html(col) -> str:
    """The end-of-session completion page, rendered in-window through the
    deck-browser content hook (switched by ``_RPCE_VIEW``): a heading, a
    statistics panel for the session just finished (how many recalled well vs.
    missed, and a breakdown by question type), a prominent 'Start new session'
    button, and a link back to the dashboard."""
    st = _last_session_stats or _new_session_stats()
    total = st["total"] or _session_limit()
    r = st["ratings"]
    recalled = r["good"] + r["easy"]  # rated Good/Easy = confident recall
    struggled = r["hard"]
    missed = r["again"]
    acc = round(100 * recalled / total) if total else 0

    concepts = len(st.get("concepts") or ())
    # Big stat tiles: total, recalled, needed effort, missed, distinct concepts.
    tiles = "".join(
        [
            _stat_pill(str(total), "questions", "var(--ink)"),
            _stat_pill(str(recalled), "recalled", "#15803d"),
            _stat_pill(str(struggled), "needed effort", "#b45309"),
            _stat_pill(str(missed), "missed", "#be123c"),
            _stat_pill(str(concepts), "concepts", "var(--accent1)"),
        ]
    )

    def _breakdown(title: str, data: dict) -> str:
        rows = "".join(
            f"<div style='display:flex;justify-content:space-between;gap:12px;"
            f"padding:6px 0;border-bottom:1px solid var(--border)'>"
            f"<span>{name}</span><b>{cnt}</b></div>"
            for name, cnt in sorted(data.items(), key=lambda kv: -kv[1])
        )
        return (
            "<div style='margin-top:24px'><div style='font-weight:800;"
            f"color:var(--ink);margin-bottom:6px'>{title}</div>{rows}</div>"
            if rows
            else ""
        )

    # Breakdowns by question type and by domain (the named concept groupings).
    type_html = _breakdown("By question type", st.get("by_type") or {})
    domain_html = _breakdown("Concepts by domain", st.get("by_domain") or {})

    return f"""{_theme_style()}
<div class="rpce-root"><div class="rpce-hero">
  <div class="rpce-head" style="gap:18px">
    <div class="rpce-h1" style="font-size:var(--fs-display)">✅ Session complete</div>
    <div class="rpce-sub">You recalled <b>{acc}%</b> of this session confidently.</div>
  </div>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:22px">{tiles}</div>
  {type_html}
  {domain_html}
  <div style="text-align:center;margin-top:30px">
    <button onclick="pycmd('rpce:newsession');return false;"
      style="background:linear-gradient(135deg,#1d4ed8,#3b82f6);color:#fff;border:none;
      border-radius:14px;padding:15px 30px;font-size:var(--fs-lead);font-weight:800;
      cursor:pointer;box-shadow:0 6px 18px rgba(29,78,216,.28)">
      Start new session</button>
  </div>
  <div style="text-align:center;margin-top:18px">
    <a href="#" onclick="pycmd('rpce:home');return false;"
       style="color:var(--accent1);font-weight:700;text-decoration:none">‹ Dashboard</a>
  </div>
</div></div>
"""


def _start_new_session() -> None:
    """Start a fresh review session from the completion page (reset the counter,
    then begin reviewing the RPCE deck)."""
    global _session_done
    _session_done = 0
    _tab_study()  # sets _RPCE_VIEW="dashboard" and moves to the reviewer


def _end_session() -> None:
    """End the review session at the cap and show an in-window 'Session complete'
    page (via the deck-browser content hook, like Section II / Simulate) so the
    user can start a fresh session or return to the dashboard."""
    global _session_done, _RPCE_VIEW
    _session_done = 0
    mw = aqt.mw
    if mw is None:
        return
    try:
        _RPCE_VIEW = "session_done"
        mw.moveToState("deckBrowser")  # the content hook renders the done page
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
        # The deck-browser webview is the single in-window canvas: the Dashboard,
        # Section II, and Simulate are all rendered here, switched by _RPCE_VIEW.
        if _RPCE_VIEW == "section2":
            content.tree = _section2_html(mw.col)
        elif _RPCE_VIEW == "simulate":
            content.tree = _simulate_html(mw.col)
        elif _RPCE_VIEW == "session_done":
            content.tree = _session_done_html(mw.col)
        else:
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
            global _session_done, _session_stats
            _session_done = 0
            _session_stats = _new_session_stats()
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
    """Start a review session straight away (like the phone) — skip Anki's
    intermediate overview/"Study Now" screen so 'Review session' always begins a session."""
    global _RPCE_VIEW
    mw = aqt.mw
    if mw is None or not _select_rpce_deck():
        return
    # Leaving to Review: the home screen returns to the Dashboard afterward.
    _RPCE_VIEW = "dashboard"
    mw.moveToState("review")


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
    # Sync-status indicator: amber not-signed-in, green signed-in, orange
    # syncing, gray offline.
    "#rpce_sync_out{background:#fef3c7 !important;color:#b45309 !important;"
    "border-color:#f0c674 !important;box-shadow:none !important}"
    "#rpce_sync_in{background:#e7f6ec !important;color:#15803d !important;"
    "border-color:#9fd8b3 !important;box-shadow:none !important}"
    "#rpce_sync_offline{background:#e5e7eb !important;color:#6b7280 !important;"
    "border-color:#d1d5db !important;box-shadow:none !important}"
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
            "Review session",
            _tab_study,
            tip="Start an RPCE review session",
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


def _is_offline() -> bool:
    """Best-effort connectivity check for the sync indicator — no new deps.

    A quick TCP probe (short timeout) to a public DNS resolver: connects fast
    when online, fails fast (or times out) when the network is down. Returns
    False (assume online) on anything unexpected so we never falsely hide the
    live 'Synced' state."""
    import socket

    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=0.4):
            return False
    except OSError:  # no route / DNS down / refused → treat as offline
        return True
    except Exception:
        return False


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
    status. Orange while syncing, green signed-in, amber not-signed-in — and,
    when offline, an offline badge that still shows the last-synced time."""
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
            if _is_offline():
                # Offline but signed in: keep the last-synced time visible so the
                # user still knows how fresh their data is (can't sync until back
                # online). Gray styling — a neutral, non-alarming state.
                label = f"📴 Offline · last synced {when}" if when else "📴 Offline"
                ident = "rpce_sync_offline"
            else:
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
