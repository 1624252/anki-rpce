# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the 3-build study-feature experiment harness (spec §8)."""

import pytest

from anki.rpce import experiment as exp


def test_mean_ci_basic():
    est = exp.mean_ci([0.5, 0.5, 0.5])
    assert est.mean == 0.5
    assert est.low == est.high == 0.5  # zero variance


def test_feature_helped_when_full_clearly_beats_ablation():
    full = [0.9, 0.92, 0.88, 0.91, 0.9]
    ablation = [0.6, 0.58, 0.62, 0.59, 0.61]
    plain = [0.55, 0.5, 0.57, 0.52, 0.53]
    report = exp.compare(full, ablation, plain)
    assert report.feature_helped is True
    assert report.feature_effect.low > 0
    assert report.metric == exp.MAIN_METRIC


def test_inconclusive_reported_honestly_as_none():
    # Overlapping distributions => difference CI straddles 0 => null result.
    full = [0.70, 0.72, 0.68, 0.71, 0.69]
    ablation = [0.69, 0.71, 0.70, 0.68, 0.72]
    plain = [0.5, 0.5, 0.5, 0.5, 0.5]
    report = exp.compare(full, ablation, plain)
    assert report.feature_helped is None, "no difference is an honest null result"
    assert report.feature_effect.low <= 0 <= report.feature_effect.high


def test_feature_hurt_detected():
    full = [0.5, 0.52, 0.48, 0.51, 0.49]
    ablation = [0.9, 0.91, 0.89, 0.92, 0.9]
    plain = [0.4, 0.41, 0.39, 0.42, 0.4]
    report = exp.compare(full, ablation, plain)
    assert report.feature_helped is False
    assert report.feature_effect.high < 0


def test_compare_requires_observations():
    with pytest.raises(ValueError):
        exp.compare([], [0.5], [0.5])
