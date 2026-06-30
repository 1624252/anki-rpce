# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the RPCE evaluation metrics (calibration + paraphrase gap)."""

import math

import pytest

from anki.rpce import metrics


def test_brier_score_bounds():
    assert metrics.brier_score([1.0, 0.0], [1, 0]) == 0.0  # perfect
    assert metrics.brier_score([0.0, 1.0], [1, 0]) == 1.0  # worst


def test_log_loss_is_finite_at_extremes():
    # Confident-and-wrong must be large but finite (clipping), not inf.
    loss = metrics.log_loss([1.0, 0.0], [0, 1])
    assert math.isfinite(loss) and loss > 0


def test_calibration_bins_partition_all_samples():
    preds = [0.05, 0.15, 0.25, 0.95, 1.0]
    outs = [0, 0, 1, 1, 1]
    bins = metrics.calibration_bins(preds, outs, n_bins=10)
    assert sum(b.count for b in bins) == len(preds), "every sample lands in a bin"


def test_ece_zero_for_perfectly_calibrated():
    # 100 preds at 0.0 (all fail) and 100 at 1.0 (all pass) => ECE 0.
    preds = [0.0] * 100 + [1.0] * 100
    outs = [0] * 100 + [1] * 100
    assert metrics.expected_calibration_error(preds, outs, n_bins=10) == 0.0


def test_paraphrase_gap_positive_when_memory_outpaces_transfer():
    # High card recall but low reworded accuracy => large positive gap.
    gap = metrics.paraphrase_gap([(0.9, 0.5), (0.8, 0.4)])
    assert gap.gap > 0
    assert gap.mean_recall > gap.mean_reworded_accuracy


def test_metrics_validate_input_lengths():
    with pytest.raises(ValueError):
        metrics.brier_score([0.5], [1, 0])
    with pytest.raises(ValueError):
        metrics.paraphrase_gap([])
