# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The three RPCE scores and the honest-readiness payload.

Implements the spec's separation of **memory**, **performance**, and
**readiness** (spec §4), each with a range, plus the **give-up rule**: no
readiness is shown until enough data exists (spec §1, §4 honesty rule).

Modeling notes (transparent bridges, not black boxes):

- **Memory** = mean per-card recall estimate from review history, a
  Laplace-smoothed ``(reps - lapses + 1) / (reps + 2)``. This is a transparent
  proxy; the upgrade path is FSRS-calibrated retrievability with a Brier/log-loss
  check on held-out reviews (spec §9 Step 1).
- **Performance** = exam-weighted mean of per-domain recall (spec §9 Step 2);
  it incorporates coverage by weighting unseen domains as 0.
- **Readiness** = P(pass a section ≥ 80%), a logistic mapping of performance
  around the 0.8 bar — never an invented scaled score (RPCE is pass/section).

Every number carries a range and a confidence; below the give-up line the app
**abstains** and explains what is missing.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import TYPE_CHECKING

from . import DOMAINS, coverage_pct, domain_tag, topic_weights

if TYPE_CHECKING:
    from anki.collection import Collection

#: Config counter incremented when a Section II scenario is graded.
SCENARIO_COUNT_KEY = "rpce:graded_scenarios"
#: Audit trail of readiness computations (spec §7.4) + when it was last updated.
SNAPSHOTS_KEY = "rpce:readiness_snapshots"
LAST_UPDATED_KEY = "rpce:readiness_updated_at"
#: Ring-buffer cap so the (syncing) config stays small.
MAX_SNAPSHOTS = 200

CONFIDENCE_ABSTAIN = "abstain"


@dataclass
class GiveUpRule:
    """Thresholds below which readiness abstains (spec §4 give-up rule)."""

    min_graded_reviews: int = 200
    min_coverage: float = 0.5
    min_scenarios: int = 100


CONFIDENCE_LABELS = {
    "high": "High confidence",
    "medium": "Moderate confidence",
    "low": "Low confidence",
    CONFIDENCE_ABSTAIN: "Not enough data yet — low confidence",
}


def confidence_label(confidence: str) -> str:
    """A human confidence label; always contains the word "confidence" (spec §10)."""
    return CONFIDENCE_LABELS.get(confidence, f"{confidence} confidence")


@dataclass
class ScoreRange:
    """A point estimate with a likely range, a confidence label, and the main
    reasons behind the number (spec §4: every score explains itself).

    ``confidence_label`` (contains "confidence") and ``elaboration`` (prose about
    how prepared/strong the user's memory is, not how the number is computed) are
    the fields the desktop and phone dashboards surface in a dropdown (spec §10).
    """

    point: float | None
    low: float | None
    high: float | None
    confidence: str  # abstain | low | medium | high
    explanation: str = ""
    confidence_label: str = ""
    elaboration: str = ""


@dataclass
class ReadinessSnapshot:
    """The full honest payload behind a readiness number (spec §4)."""

    section: str
    p_pass: float | None
    range_low: float | None
    range_high: float | None
    confidence: str
    pct_covered: float
    graded_reviews: int
    graded_scenarios: int
    evidence: str
    best_next_topic: str | None
    abstained: bool
    confidence_label: str = ""
    elaboration: str = ""


def _recall_estimate(reps: int, lapses: int) -> float:
    """Laplace-smoothed recall in (0, 1): fewer lapses per rep => better."""
    return (reps - lapses + 1) / (reps + 2)


def _fsrs_retrievability(col: Collection, cid: int) -> float | None:
    """The card's true FSRS retrievability (probability of recall now), or None
    when FSRS is disabled / the card has no memory state yet."""
    try:
        stats = col._backend.card_stats(cid)
        if stats.HasField("fsrs_retrievability"):
            r = float(stats.fsrs_retrievability)
            if 0.0 < r <= 1.0:
                return r
    except Exception:
        pass
    return None


def _card_recall(col: Collection, cid: int, card) -> float:
    """Per-card recall probability: real FSRS retrievability when available,
    otherwise the transparent reps/lapses heuristic (spec §8 upgrade path)."""
    r = _fsrs_retrievability(col, cid)
    return r if r is not None else _recall_estimate(card.reps, card.lapses)


def _reviewed_recalls(col: Collection) -> list[float]:
    recalls: list[float] = []
    for cid in col.find_cards("is:review OR is:due"):
        card = col.get_card(cid)
        if card.reps > 0:
            recalls.append(_card_recall(col, cid, card))
    return recalls


def _range_from(values: list[float]) -> ScoreRange:
    """Mean with a 95% normal interval; confidence scales with sample size."""
    if not values:
        # No data yet: abstain from a point estimate but still show the honest
        # full-uncertainty range (0-100%) so memory/performance always carry a
        # range, not a blank.
        return ScoreRange(None, 0.0, 1.0, CONFIDENCE_ABSTAIN)
    point = mean(values)
    n = len(values)
    se = (pstdev(values) / math.sqrt(n)) if n > 1 else 0.5
    margin = 1.96 * se
    low = max(0.0, point - margin)
    high = min(1.0, point + margin)
    confidence = "high" if n >= 200 else "medium" if n >= 50 else "low"
    return ScoreRange(point, low, high, confidence)


def graded_reviews(col: Collection) -> int:
    """Number of logged reviews (the raw material for the memory model)."""
    return col.db.scalar("select count() from revlog") or 0


def graded_scenarios(col: Collection) -> int:
    return int(col.get_config(SCENARIO_COUNT_KEY, 0) or 0)


def record_scenario(col: Collection) -> None:
    """Increment the graded-scenario counter (called by the AI examiner)."""
    col.set_config(SCENARIO_COUNT_KEY, graded_scenarios(col) + 1)


def _memory_prose(point: float | None) -> str:
    """How strong the user's memory is right now (preparedness, not maths)."""
    if point is None:
        return (
            "There isn't enough review history yet to say how well the material is "
            "sticking. Study a few flashcard sessions and this will show how strong "
            "your recall is."
        )
    if point >= 0.85:
        return (
            "Your recall is strong — the facts you've studied are well retained and "
            "should hold up under exam pressure. Keep light reviews going so they stay fresh."
        )
    if point >= 0.7:
        return (
            "Your recall is solid on what you've studied, with a few facts still "
            "settling in. A bit more spaced review will lock them in."
        )
    if point >= 0.5:
        return (
            "Your memory of the material is still forming — you remember much of it, "
            "but enough is slipping that more spaced review would pay off before the exam."
        )
    return (
        "The material hasn't stuck yet. Short, frequent review sessions will build "
        "durable recall faster than cramming."
    )


def _performance_prose(point: float | None, cov: float, weakest: str | None) -> str:
    """How prepared the user is across the exam blueprint (not how it's computed)."""
    focus = f" Your weakest area is {weakest}." if weakest else ""
    if point is None:
        return (
            "You haven't practised enough exam-style questions yet to gauge how "
            "prepared you are across the blueprint." + focus
        )
    if point >= 0.8:
        return (
            "You're performing at or above the exam bar across the domains you've "
            f"covered ({cov:.0%} of the blueprint)." + focus
        )
    if point >= 0.6:
        return (
            "You're getting close to exam-ready on the material you've covered "
            f"({cov:.0%} of the blueprint), with clear room to firm up weak spots."
            + focus
        )
    return (
        "You're still building toward exam-ready; broaden your coverage and "
        f"strengthen recall (currently {cov:.0%} of the blueprint covered)." + focus
    )


def _readiness_prose(snap_abstained: bool, p_pass: float | None, section: str) -> str:
    """How prepared the user is to pass this section (preparedness, not maths)."""
    if snap_abstained or p_pass is None:
        return (
            f"There isn't enough evidence yet to judge your chances on Section {section}. "
            "Keep studying and practising until the dashboard has enough to go on."
        )
    if p_pass >= 0.8:
        return (
            f"You look well prepared for Section {section} — on current evidence you'd "
            "most likely clear the 80% bar. Keep your reviews ticking over."
        )
    if p_pass >= 0.5:
        return (
            f"You're on the cusp for Section {section}. A focused push on your weak "
            "areas should tip you over the 80% pass bar."
        )
    return (
        f"You're not yet prepared to pass Section {section} with confidence. Steady "
        "study across the weak domains is what will move this."
    )


def memory_score(col: Collection) -> ScoreRange:
    """P(recall a taught fact now), averaged over reviewed cards."""
    recalls = _reviewed_recalls(col)
    sr = _range_from(recalls)
    n = len(recalls)
    if n == 0:
        sr.explanation = (
            "No reviewed cards yet — study some flashcards to build a memory estimate."
        )
    else:
        method = (
            "FSRS retrievability"
            if col.get_config("fsrs", False)
            else "a reps/lapses recall estimate (enable FSRS for calibrated recall)"
        )
        sr.explanation = (
            f"Mean recall over {n} reviewed card(s) using {method}. The range is a "
            "95% interval; confidence rises as you accumulate reviews."
        )
    sr.confidence_label = confidence_label(sr.confidence)
    sr.elaboration = _memory_prose(sr.point)
    return sr


def _domain_recall(col: Collection, code: int) -> float | None:
    recalls = [
        _card_recall(col, cid, c)
        for cid in col.find_cards(f"tag:{domain_tag(code)}")
        if (c := col.get_card(cid)).reps > 0
    ]
    return mean(recalls) if recalls else None


def performance_score(col: Collection) -> ScoreRange:
    """Exam-weighted recall across domains; unseen domains count as 0."""
    weights = topic_weights(col)
    total_weight = sum(weights.values()) or 1.0
    point = 0.0
    seen = 0
    for d in DOMAINS:
        recall = _domain_recall(col, d.code)
        w = weights[domain_tag(d.code)] / total_weight
        if recall is not None:
            seen += 1
            point += w * recall
        # unseen domain contributes 0, penalising incomplete coverage
    if seen == 0:
        sr = ScoreRange(
            None,
            None,
            None,
            CONFIDENCE_ABSTAIN,
            "No domain has review history yet — this bridges memory to new "
            "exam-style questions once you have practised.",
        )
        sr.confidence_label = confidence_label(sr.confidence)
        sr.elaboration = _performance_prose(
            None, coverage_pct(col), best_next_topic(col)
        )
        return sr
    cov = coverage_pct(col)
    # Wider band when coverage is low (less certain about unseen material).
    margin = 0.1 + 0.4 * (1.0 - cov)
    weakest = best_next_topic(col)
    explanation = (
        f"Exam-weighted recall across the 7 domains; {seen}/{len(DOMAINS)} have "
        f"review history and unseen domains count as 0 (so incomplete coverage "
        f"lowers the score). Weakest area: {weakest}. The range widens when "
        f"coverage is low ({cov:.0%} covered)."
    )
    sr = ScoreRange(
        point,
        max(0.0, point - margin),
        min(1.0, point + margin),
        "high" if cov >= 0.8 else "medium" if cov >= 0.5 else "low",
        explanation,
    )
    sr.confidence_label = confidence_label(sr.confidence)
    sr.elaboration = _performance_prose(point, cov, weakest)
    return sr


def best_next_topic(col: Collection) -> str | None:
    """The single highest-value thing to study: max ``weight × gap``,
    where gap favours uncovered or weakly-recalled domains."""
    weights = topic_weights(col)
    best: tuple[float, str] | None = None
    for d in DOMAINS:
        recall = _domain_recall(col, d.code)
        gap = 1.0 if recall is None else (1.0 - recall)
        value = weights[domain_tag(d.code)] * gap
        if best is None or value > best[0]:
            best = (value, d.name)
    return best[1] if best else None


def _logistic_pass_probability(performance: float) -> float:
    """Map a performance estimate to P(section ≥ 80%). Centred on the 0.8 bar;
    the slope (k) is a documented assumption, not a fitted value yet."""
    k = 12.0
    return 1.0 / (1.0 + math.exp(-k * (performance - 0.8)))


def _overall_elaboration(
    mem: ScoreRange, perf: ScoreRange, sec1: ReadinessSnapshot
) -> str:
    """One preparedness-focused paragraph for the dashboard dropdown (spec §10):
    how prepared the user is and how strong their memory is — not the formulae."""
    if not sec1.abstained and sec1.p_pass is not None:
        return f"{_readiness_prose(False, sec1.p_pass, 'I')} {perf.elaboration}"
    if perf.point is not None:
        return f"{perf.elaboration} {mem.elaboration}"
    return mem.elaboration


def readiness_summary(col: Collection, rule: GiveUpRule | None = None) -> dict:
    """All dashboard data in one call: the three scores plus both sections'
    readiness and per-domain coverage. Used by the desktop dashboard.

    ``confidence_label`` (a string containing "confidence") and ``elaboration``
    (preparedness-focused prose) are surfaced for the UI dropdown (spec §10);
    the original per-score keys are kept for backward compatibility."""
    from . import coverage as _coverage

    mem = memory_score(col)
    perf = performance_score(col)
    sec1 = readiness(col, "I", rule)
    sec2 = readiness(col, "II", rule)
    overall = perf.confidence if perf.point is not None else mem.confidence
    return {
        "memory": mem,
        "performance": perf,
        "section_I": sec1,
        "section_II": sec2,
        "coverage": _coverage(col),
        "confidence_label": confidence_label(overall),
        "elaboration": _overall_elaboration(mem, perf, sec1),
    }


def readiness(
    col: Collection, section: str, rule: GiveUpRule | None = None
) -> ReadinessSnapshot:
    """P(pass `section` ≥ 80%) with full evidence, or abstain below the line."""
    rule = rule or GiveUpRule()
    cov = coverage_pct(col)
    reviews = graded_reviews(col)
    scenarios = graded_scenarios(col)
    next_topic = best_next_topic(col)

    # Section II is the scenario half; Section I does not require scenarios.
    needs_scenarios = section == "II"
    missing: list[str] = []
    if reviews < rule.min_graded_reviews:
        missing.append(
            f"{rule.min_graded_reviews - reviews} more graded reviews needed "
            f"({reviews}/{rule.min_graded_reviews})"
        )
    if cov < rule.min_coverage:
        missing.append(f"domain coverage {cov:.0%} of {rule.min_coverage:.0%} needed")
    if needs_scenarios and scenarios < rule.min_scenarios:
        missing.append(
            f"{rule.min_scenarios - scenarios} more graded scenarios needed "
            f"({scenarios}/{rule.min_scenarios})"
        )

    if missing:
        return ReadinessSnapshot(
            section=section,
            p_pass=None,
            range_low=None,
            range_high=None,
            confidence=CONFIDENCE_ABSTAIN,
            pct_covered=cov,
            graded_reviews=reviews,
            graded_scenarios=scenarios,
            evidence="Not enough data: " + "; ".join(missing),
            best_next_topic=next_topic,
            abstained=True,
            confidence_label=confidence_label(CONFIDENCE_ABSTAIN),
            elaboration=_readiness_prose(True, None, section),
        )

    perf = performance_score(col)
    # The review/coverage gates above can pass while performance still has no
    # recall history to score from (they measure different things) — abstain
    # rather than crash the whole dashboard.
    if perf.point is None:
        return ReadinessSnapshot(
            section=section,
            p_pass=None,
            range_low=None,
            range_high=None,
            confidence=CONFIDENCE_ABSTAIN,
            pct_covered=cov,
            graded_reviews=reviews,
            graded_scenarios=scenarios,
            evidence="Not enough performance data yet — practise more to score.",
            best_next_topic=next_topic,
            abstained=True,
            confidence_label=confidence_label(CONFIDENCE_ABSTAIN),
            elaboration=_readiness_prose(True, None, section),
        )
    p_pass = _logistic_pass_probability(perf.point)
    low = _logistic_pass_probability(perf.low or perf.point)
    high = _logistic_pass_probability(perf.high or perf.point)
    scen_note = f", {scenarios} graded scenarios" if section == "II" else ""
    evidence = (
        f"Maps a {perf.point:.0%} performance estimate through the 80% section "
        f"bar to a pass probability. Evidence: {reviews} reviews across "
        f"{cov:.0%} of domains{scen_note}. Focus next on {next_topic}."
    )
    return ReadinessSnapshot(
        section=section,
        p_pass=p_pass,
        range_low=low,
        range_high=high,
        confidence=perf.confidence,
        pct_covered=cov,
        graded_reviews=reviews,
        graded_scenarios=scenarios,
        evidence=evidence,
        best_next_topic=next_topic,
        abstained=False,
        confidence_label=confidence_label(perf.confidence),
        elaboration=_readiness_prose(False, p_pass, section),
    )


def record_readiness_snapshots(col: Collection, rule: GiveUpRule | None = None) -> int:
    """Append the current readiness for both sections to the audit trail and
    stamp the last-updated time (spec §7.4). Stored in the syncing collection
    config (capped ring buffer) so past predictions can be scored later, and so
    the panel can show *when* a number was produced. Returns the epoch seconds.

    Called at meaningful moments (dashboard open, after answering), not on every
    passive render, so the trail stays a record of real computations.
    """
    now = int(time.time())
    existing = col.get_config(SNAPSHOTS_KEY, None)
    snaps: list[dict] = list(existing) if isinstance(existing, list) else []
    for section in ("I", "II"):
        snap = readiness(col, section, rule)
        snaps.append(
            {
                "section": snap.section,
                "p_pass": snap.p_pass,
                "low": snap.range_low,
                "high": snap.range_high,
                "confidence": snap.confidence,
                "pct_covered": snap.pct_covered,
                "abstained": snap.abstained,
                "ts": now,
            }
        )
    col.set_config(SNAPSHOTS_KEY, snaps[-MAX_SNAPSHOTS:])
    col.set_config(LAST_UPDATED_KEY, now)
    return now


def readiness_snapshots(col: Collection) -> list[dict]:
    """The stored audit trail of past readiness computations (oldest first)."""
    snaps = col.get_config(SNAPSHOTS_KEY, None)
    return list(snaps) if isinstance(snaps, list) else []


def last_updated(col: Collection) -> int | None:
    """Epoch seconds of the most recent readiness computation, or None."""
    ts = col.get_config(LAST_UPDATED_KEY, None)
    return int(ts) if ts else None


def _last_review_passed(col: Collection, cid: int) -> int | None:
    """1 if the card's most recent review was a pass (ease ≥ 2), 0 if a lapse
    (ease == 1), or None if it has never been reviewed."""
    row = col.db.first(
        "select ease from revlog where cid = ? order by id desc limit 1", cid
    )
    if not row or row[0] is None:
        return None
    return 1 if int(row[0]) != 1 else 0


def memory_calibration(col: Collection) -> dict | None:
    """Calibrate the FSRS memory model on this collection (spec §9 Step 1):
    compare each card's predicted retrievability against whether its most recent
    review was actually a pass, and report Brier score, log loss, and Expected
    Calibration Error. Returns None when FSRS predictions aren't available (so
    the caller can fall back to reporting the heuristic memory score only).
    """
    from . import metrics

    predictions: list[float] = []
    outcomes: list[int] = []
    for cid in col.find_cards("is:review OR is:due"):
        r = _fsrs_retrievability(col, cid)
        outcome = _last_review_passed(col, cid)
        if r is not None and outcome is not None:
            predictions.append(r)
            outcomes.append(outcome)
    if not predictions:
        return None
    return {
        "n": len(predictions),
        "brier": metrics.brier_score(predictions, outcomes),
        "log_loss": metrics.log_loss(predictions, outcomes),
        "ece": metrics.expected_calibration_error(predictions, outcomes),
    }
