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
    min_scenarios: int = 10


@dataclass
class ScoreRange:
    """A point estimate with a likely range, a confidence label, and the main
    reasons behind the number (spec §4: every score explains itself)."""

    point: float | None
    low: float | None
    high: float | None
    confidence: str  # abstain | low | medium | high
    explanation: str = ""


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
        return ScoreRange(None, None, None, CONFIDENCE_ABSTAIN)
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
        return ScoreRange(
            None,
            None,
            None,
            CONFIDENCE_ABSTAIN,
            "No domain has review history yet — this bridges memory to new "
            "exam-style questions once you have practised.",
        )
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
    return ScoreRange(
        point,
        max(0.0, point - margin),
        min(1.0, point + margin),
        "high" if cov >= 0.8 else "medium" if cov >= 0.5 else "low",
        explanation,
    )


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


def readiness_summary(col: Collection, rule: GiveUpRule | None = None) -> dict:
    """All dashboard data in one call: the three scores plus both sections'
    readiness and per-domain coverage. Used by the desktop dashboard."""
    from . import coverage as _coverage

    return {
        "memory": memory_score(col),
        "performance": performance_score(col),
        "section_I": readiness(col, "I", rule),
        "section_II": readiness(col, "II", rule),
        "coverage": _coverage(col),
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
        missing.append(f"{reviews}/{rule.min_graded_reviews} graded reviews")
    if cov < rule.min_coverage:
        missing.append(f"{cov:.0%}/{rule.min_coverage:.0%} domain coverage")
    if needs_scenarios and scenarios < rule.min_scenarios:
        missing.append(f"{scenarios}/{rule.min_scenarios} graded scenarios")

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
        )

    perf = performance_score(col)
    assert perf.point is not None
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
