# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Re-runnable evaluation metrics for the RPCE models (spec §9, §7d).

Pure functions so anyone can re-run them on held-out data and get the same
numbers (spec's reproducibility requirement):

- **Calibration** of the memory model: Brier score, log loss, reliability bins
  for a calibration chart, and Expected Calibration Error (spec §9 Step 1).
- **Paraphrase gap**: recall on a card vs. accuracy on reworded questions of the
  same concept — proves the performance model isn't just echoing memory
  (spec §7d). A near-zero gap is a red flag.

These take ``(predictions, outcomes)`` / per-concept pairs directly, so they are
trivially testable; wiring real FSRS predictions and reworded-question results
into them is the integration step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_EPS = 1e-12


def _validate(predictions: list[float], outcomes: list[int]) -> None:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        raise ValueError("need at least one prediction")


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    """Mean squared error between predicted probabilities and 0/1 outcomes.
    0.0 is perfect; 1.0 is worst."""
    _validate(predictions, outcomes)
    return sum((p - y) ** 2 for p, y in zip(predictions, outcomes)) / len(predictions)


def log_loss(predictions: list[float], outcomes: list[int]) -> float:
    """Mean negative log-likelihood (binary cross-entropy), clipped to avoid
    infinities. Lower is better."""
    _validate(predictions, outcomes)
    total = 0.0
    for p, y in zip(predictions, outcomes):
        p = min(1 - _EPS, max(_EPS, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(predictions)


@dataclass
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    mean_actual: float


def calibration_bins(
    predictions: list[float], outcomes: list[int], n_bins: int = 10
) -> list[CalibrationBin]:
    """Reliability-diagram bins: for each predicted-probability band, the mean
    predicted probability vs. the observed frequency. Powers the chart."""
    _validate(predictions, outcomes)
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        # Last bin is inclusive of 1.0.
        members = [
            (p, y)
            for p, y in zip(predictions, outcomes)
            if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        if members:
            mp = sum(p for p, _ in members) / len(members)
            ma = sum(y for _, y in members) / len(members)
        else:
            mp = ma = 0.0
        bins.append(CalibrationBin(lo, hi, len(members), mp, ma))
    return bins


def expected_calibration_error(
    predictions: list[float], outcomes: list[int], n_bins: int = 10
) -> float:
    """Weighted average gap between confidence and accuracy across bins.
    0.0 means perfectly calibrated."""
    bins = calibration_bins(predictions, outcomes, n_bins)
    n = len(predictions)
    return sum(b.count / n * abs(b.mean_predicted - b.mean_actual) for b in bins)


@dataclass
class ParaphraseGap:
    mean_recall: float
    mean_reworded_accuracy: float
    gap: float  # recall - reworded; large positive => memory not transferring


def paraphrase_gap(pairs: list[tuple[float, float]]) -> ParaphraseGap:
    """Given per-concept ``(card_recall, reworded_question_accuracy)`` pairs,
    report the average gap. A gap near zero means the performance model is just
    mirroring memory (spec §7d); a clear positive gap is the expected signal
    that recognizing a card ≠ applying the concept to new wording."""
    if not pairs:
        raise ValueError("need at least one (recall, reworded) pair")
    mean_recall = sum(r for r, _ in pairs) / len(pairs)
    mean_reworded = sum(a for _, a in pairs) / len(pairs)
    return ParaphraseGap(mean_recall, mean_reworded, mean_recall - mean_reworded)
