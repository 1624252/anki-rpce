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
- **Performance** = concept-weighted projection of first-attempt correctness
  (getting a NEW question right) across all 210 concepts, un-practised = 0
  (spec §9 Step 2); it generalises Memory to fresh exam questions.
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

from . import DOMAINS, domain_tag, topic_weights

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
    #: A concept counts as "covered" once you've PRACTICED it (this many graded
    #: items). 1 = "you've studied at least one question of this concept," so
    #: coverage reflects the breadth of concepts practised and climbs as you study
    #: (a 20-card session touches ~20 concepts -> ~10%), instead of sitting at 0%
    #: until every concept has 5 graded reviews.
    min_items_per_concept: int = 1


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
    """Per-card recall probability, from the transparent reps/lapses heuristic.

    Deliberately NOT FSRS retrievability: the phone engine has no FSRS, so using
    the same heuristic on both platforms keeps the Memory/Performance/readiness
    SCORES identical across devices (they read the same synced card fields). FSRS
    retrievability is still surfaced separately as the calibration readout
    (``memory_calibration``), where its accuracy is the point."""
    return _recall_estimate(card.reps, card.lapses)


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
    """Number of logged reviews of cards that still exist (the raw material for
    the memory model). Reviews of deleted cards (a deck re-seed can leave orphaned
    revlog rows) are excluded so this count agrees with the performance estimate,
    which is computed from current cards — otherwise the readiness gate could look
    satisfied while performance still has no data to score."""
    return (
        col.db.scalar("select count() from revlog where cid in (select id from cards)")
        or 0
    )


#: Anki review ease for an "Easy" rating, and the minimum "pass" (Good) rating.
_EASE_EASY = 4
_EASE_GOOD = 3
#: How many most-recent reviews of a card define coverage. Cards are reviewed
#: only a couple of times before their concept siblings are buried, so requiring
#: a long all-Easy streak was unreachable (coverage stuck at 0%). Coverage now
#: looks at the last COVERAGE_RECENT_N reviews: the most recent must be Easy and
#: every one of them at least Good — consistent recent mastery, not one fluke.
COVERAGE_RECENT_N = 2


def concept_item_counts(col: Collection) -> dict[str, int]:
    """Graded (reps>0) card count per performance-expectation concept, keyed by
    concept id, read from the ``rpce::concept::<id>`` tags in one pass."""
    counts: dict[str, int] = {}
    for row in col.db.execute(
        "select n.tags from cards c join notes n on c.nid = n.id where c.reps > 0"
    ):
        for tok in (row[0] or "").split():
            if tok.startswith("rpce::concept::"):
                cid = tok.rsplit("::", 1)[-1]
                counts[cid] = counts.get(cid, 0) + 1
    return counts


def concepts_mastered(col: Collection) -> set[str]:
    """Concept ids you've MASTERED: at least one card of the concept whose
    ``COVERAGE_RECENT_N`` most-recent reviews were all a pass (>= Good) with the
    most recent rated Easy. This is the bar for concept coverage — a concept
    counts once you're recently, consistently acing a question of it."""
    # Most-recent eases per card, from the review log (one pass, newest first).
    last: dict[int, list[int]] = {}
    for cid, ease in col.db.execute("select cid, ease from revlog order by id desc"):
        lst = last.setdefault(int(cid), [])
        if len(lst) < COVERAGE_RECENT_N:
            lst.append(int(ease))
    mastered_cards = [
        cid
        for cid, es in last.items()
        if len(es) == COVERAGE_RECENT_N
        and es[0] == _EASE_EASY  # most recent review is Easy
        and all(e >= _EASE_GOOD for e in es)  # and every recent review a pass
    ]
    if not mastered_cards:
        return set()
    out: set[str] = set()
    ph = ",".join("?" * len(mastered_cards))
    for (tags,) in col.db.execute(
        f"select n.tags from cards c join notes n on c.nid = n.id where c.id in ({ph})",
        *mastered_cards,
    ):
        for tok in (tags or "").split():
            if tok.startswith("rpce::concept::"):
                out.add(tok.rsplit("::", 1)[-1])
    return out


def concept_coverage_pct(col: Collection) -> float:
    """Fraction of the RP performance-expectation concepts you've MASTERED — a
    concept counts once one of its cards has its 2 most-recent reviews both a
    pass with the most recent rated Easy (:func:`concepts_mastered`). 0.0 if the
    registry is empty."""
    from . import concepts

    cs = concepts.all_concepts()
    if not cs:
        return 0.0
    mastered = concepts_mastered(col)
    return sum(1 for c in cs if c.id in mastered) / len(cs)


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
    """How well the user gets NEW questions right across the blueprint — the
    meaning of the first-attempt projection, not how it's computed."""
    focus = f" Your weakest area is {weakest}." if weakest else ""
    if point is None:
        return (
            "You haven't answered enough questions yet to project how you'd do on "
            "fresh exam questions." + focus
        )
    if point >= 0.8:
        return (
            "You're getting new questions right at or above the exam bar across the "
            f"concepts you've practised ({cov:.0%} of the blueprint covered)." + focus
        )
    if point >= 0.6:
        return (
            "You get most new questions right, with clear room to firm up weak spots "
            f"and broaden coverage ({cov:.0%} covered)." + focus
        )
    return (
        "You're still building the ability to get fresh questions right; broaden "
        f"coverage and drill your weak areas ({cov:.0%} of the blueprint covered)."
        + focus
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


def _concept_correctness(col: Collection) -> dict[str, float]:
    """Per-concept FIRST-ATTEMPT correctness: the fraction of a concept's cards
    answered correctly (ease >= Good) the FIRST time they were seen — a measure of
    getting a NEW question on that concept right, before any drilling. Read from
    the ``rpce::concept::<id>`` tags + the earliest revlog entry per card."""
    # Earliest review's ease per card (oldest first; keep the first seen).
    first_ease: dict[int, int] = {}
    for cid, ease in col.db.execute("select cid, ease from revlog order by id asc"):
        first_ease.setdefault(int(cid), int(ease))
    buckets: dict[str, list[int]] = {}
    for cid, tags in col.db.execute(
        "select c.id, n.tags from cards c join notes n on c.nid = n.id "
        "where c.reps > 0 and n.tags like '%rpce::concept::%'"
    ):
        fe = first_ease.get(int(cid))
        if fe is None:
            continue
        correct = 1 if fe >= _EASE_GOOD else 0
        for tok in (tags or "").split():
            if tok.startswith("rpce::concept::"):
                buckets.setdefault(tok.rsplit("::", 1)[-1], []).append(correct)
    return {cid: mean(v) for cid, v in buckets.items() if v}


def _concept_weighted_projection(col: Collection) -> tuple[float, int, int]:
    """Exam projection over ALL performance-expectation concepts, based on how
    well you get NEW questions right.

    Returns ``(point, seen, total)``: ``point`` is the domain-exam-weighted mean
    of each concept's FIRST-ATTEMPT correctness (:func:`_concept_correctness`),
    with every concept you've never practised counting as 0. So it projects your
    exam score on fresh questions across the whole blueprint — strong first-try
    accuracy lifts it, unpractised concepts (new to you) drag it down. Each domain
    keeps its exam weight, split evenly across its concepts."""
    from collections import Counter

    from . import concepts as _concepts

    cs = _concepts.all_concepts()
    total = len(cs)
    if total == 0:
        return 0.0, 0, 0
    weights = topic_weights(col)
    total_weight = sum(weights.values()) or 1.0
    per_domain = Counter(c.domain for c in cs)
    correctness = _concept_correctness(col)
    num = 0.0
    denom = 0.0
    seen = 0
    for c in cs:
        # domain exam weight, split evenly over that domain's concepts
        w = (weights.get(domain_tag(c.domain), 0.0) / total_weight) / (
            per_domain[c.domain] or 1
        )
        denom += w
        acc = correctness.get(c.id)
        if acc is not None:  # concept practised -> credit its first-try accuracy
            seen += 1
            num += w * acc
        # never-practised concept counts as 0 (a new concept you'd likely miss)
    return (num / denom if denom else 0.0), seen, total


def performance_score(col: Collection) -> ScoreRange:
    """Concept-weighted exam projection based on getting NEW questions right.

    Generalises to the whole blueprint: a projection over all 210
    performance-expectation concepts of your FIRST-ATTEMPT correctness, with every
    concept you've never practised counting as 0. So it estimates your score on
    fresh exam questions — distinct from Memory (recall of what you've drilled)."""
    point, seen, total = _concept_weighted_projection(col)
    if seen == 0:
        sr = ScoreRange(
            None,
            0.0,  # abstain, but still carry the full-uncertainty 0-100% range
            1.0,
            CONFIDENCE_ABSTAIN,
            "No questions answered yet — this projects your exam score from how "
            "often you get new questions right once you've practised.",
        )
        sr.confidence_label = confidence_label(sr.confidence)
        sr.elaboration = _performance_prose(
            None, concept_coverage_pct(col), best_next_topic(col)
        )
        return sr
    cov = concept_coverage_pct(col)
    # Wider band when coverage is low (less certain about unseen material).
    margin = 0.1 + 0.4 * (1.0 - cov)
    weakest = best_next_topic(col)
    explanation = (
        f"Concept-weighted projection across all {total} performance expectations, "
        f"from your first-attempt correctness; {seen} practised and every "
        f"un-practised concept counts as 0. Weakest area: {weakest}. The range "
        f"widens when coverage is low ({cov:.0%} covered)."
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
    cov = concept_coverage_pct(col)
    reviews = graded_reviews(col)
    scenarios = graded_scenarios(col)
    next_topic = best_next_topic(col)

    # Section II is the scenario half; Section I does not require scenarios.
    needs_scenarios = section == "II"
    missing: list[str] = []
    if reviews < rule.min_graded_reviews:
        missing.append(
            f"{rule.min_graded_reviews - reviews} more graded reviews needed "
            f"({reviews}/{rule.min_graded_reviews})."
        )
    if cov < rule.min_coverage:
        missing.append(f"Concept coverage {cov:.0%} of {rule.min_coverage:.0%} needed.")
    if needs_scenarios and scenarios < rule.min_scenarios:
        missing.append(
            f"{rule.min_scenarios - scenarios} more graded scenarios needed "
            f"({scenarios}/{rule.min_scenarios})."
        )

    if missing:
        return ReadinessSnapshot(
            section=section,
            p_pass=None,
            range_low=0.0,  # abstain, but still show the full-uncertainty range
            range_high=1.0,
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
            range_low=0.0,  # abstain, but still show the full-uncertainty range
            range_high=1.0,
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
        f"Maps a {perf.point:.0%} performance projection through the 80% section "
        f"bar to a pass probability. Evidence: {reviews} reviews across "
        f"{cov:.0%} of concepts{scen_note}. Focus next on {next_topic}."
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
