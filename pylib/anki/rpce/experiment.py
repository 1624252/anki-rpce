# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Study-feature experiment harness for the Transfer Ladder (spec §8).

The spec requires testing one study feature by building three variants and
comparing them on the same questions at equal study time:

1. **full** — the app with the Transfer Ladder on,
2. **ablation** — the same app with the ladder off (single format),
3. **plain** — unmodified Anki (the baseline).

`full vs ablation` isolates the feature's effect; `full vs plain` shows whether
the whole app beats the obvious alternative. The pre-stated main metric is
accuracy on new, reworded scenario questions. We report a range (95% interval)
and label inconclusive results honestly — "no difference" is a valid result
(spec §8), so :attr:`ExperimentReport.feature_helped` is ``None`` when the
difference interval straddles zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Pre-registered primary metric (stated before looking at results, spec §8).
MAIN_METRIC = "accuracy on new, reworded scenario questions"


@dataclass
class Estimate:
    mean: float
    low: float
    high: float


def mean_ci(values: list[float], z: float = 1.96) -> Estimate:
    """Mean with a normal 95% confidence interval."""
    if not values:
        raise ValueError("need at least one observation")
    n = len(values)
    mu = sum(values) / n
    if n == 1:
        return Estimate(mu, mu, mu)
    var = sum((v - mu) ** 2 for v in values) / (n - 1)
    se = math.sqrt(var) / math.sqrt(n)
    return Estimate(mu, mu - z * se, mu + z * se)


def _diff_ci(a: list[float], b: list[float], z: float = 1.96) -> Estimate:
    """CI for the difference of means (mean(a) - mean(b)), unpaired."""
    na, nb = len(a), len(b)
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((v - ma) ** 2 for v in a) / (na - 1) if na > 1 else 0.0
    vb = sum((v - mb) ** 2 for v in b) / (nb - 1) if nb > 1 else 0.0
    se = math.sqrt(va / na + vb / nb)
    diff = ma - mb
    return Estimate(diff, diff - z * se, diff + z * se)


@dataclass
class ExperimentReport:
    metric: str
    full: Estimate
    ablation: Estimate
    plain: Estimate
    feature_effect: Estimate  # full - ablation
    vs_plain: Estimate  # full - plain
    #: True if the feature helped (effect CI fully > 0), False if it hurt
    #: (CI fully < 0), None if inconclusive (CI includes 0) — an honest null.
    feature_helped: bool | None


def compare(
    full: list[float], ablation: list[float], plain: list[float]
) -> ExperimentReport:
    """Run the three-way comparison on the pre-stated metric."""
    if not (full and ablation and plain):
        raise ValueError("each build needs at least one observation")
    effect = _diff_ci(full, ablation)
    if effect.low > 0:
        helped: bool | None = True
    elif effect.high < 0:
        helped = False
    else:
        helped = None  # interval includes 0 -> inconclusive / null result
    return ExperimentReport(
        metric=MAIN_METRIC,
        full=mean_ci(full),
        ablation=mean_ci(ablation),
        plain=mean_ci(plain),
        feature_effect=effect,
        vs_plain=_diff_ci(full, plain),
        feature_helped=helped,
    )
