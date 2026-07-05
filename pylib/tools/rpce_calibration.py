#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""§9 Step 1 — calibrate the memory model on HELD-OUT reviews, re-runnable.

Produces the Sunday deliverable: a **calibration score** (Brier, log loss,
Expected Calibration Error) *and* a **reliability-diagram chart** on held-out
reviews. Reproducible: a fixed seed in => the same numbers out.

HONESTY NOTE (read this):

- The **estimator** graded here is the production memory model —
  ``anki.rpce.scores._recall_estimate`` (the Laplace-smoothed recall
  ``(reps - lapses + 1) / (reps + 2)`` documented in SCORING.md), and the
  **metrics** are the production ``anki.rpce.metrics`` functions. Those halves
  are real code, not a re-implementation.
- The **review outcomes** are a SEEDED SYNTHETIC cohort, not real candidate
  data. Each of ``N_CARDS`` cards is given a fixed latent recall probability and
  a fixed number of training reviews (all from ``random.Random(SEED)``); the
  Laplace estimate is fit on those training reviews, then scored against ONE
  further, genuinely HELD-OUT review of the same card. So the train/held-out
  split is real, but the student it simulates is not.

Why synthetic rather than a live FSRS collection: the real scheduler advances
card intervals against the wall clock, which is non-deterministic — it would
break the "same seed => same numbers" requirement. This harness keeps the split
and the estimator honest while staying byte-for-byte reproducible.

    just rpce-calibration
    # or: PYTHONPATH=out/pylib python pylib/tools/rpce_calibration.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass

# --- Reproducibility knobs. Change SEED => a different (still deterministic) run.
SEED = 20260705
N_CARDS = 5000
N_BINS = 10
#: Below this Expected Calibration Error we call the memory model well-calibrated
#: ("when it says 80%, ~80% recall"). A round, defensible bar.
ECE_WELL_CALIBRATED = 0.05

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
_ARTIFACT_DIR = os.path.join(_REPO, "docs", "rpce", "artifacts")


def _bootstrap_paths() -> None:
    """Make the built ``anki`` package importable when run from the repo root."""
    built = os.path.join(_REPO, "out", "pylib")
    if os.path.isdir(built):
        sys.path.insert(0, built)
    os.environ.setdefault("ANKI_TEST_MODE", "1")


@dataclass(frozen=True)
class Dataset:
    """A held-out evaluation set: one predicted recall + one 0/1 outcome per card."""

    predictions: list[float]
    outcomes: list[int]


def build_holdout_dataset(seed: int = SEED, n_cards: int = N_CARDS) -> Dataset:
    """Seeded synthetic cohort with a real train/held-out split.

    For each card: draw a latent recall ``p`` and a training-review count ``k``;
    simulate ``k`` Bernoulli(p) reviews as the TRAINING history and fit the
    production Laplace estimator on them; the outcome is ONE further Bernoulli(p)
    review, HELD OUT (never seen by the estimator). Returns aligned
    ``(predictions, outcomes)`` for the metric functions.
    """
    # The real memory-model estimator; imported so we grade the shipped formula.
    from anki.rpce.scores import _recall_estimate

    rng = random.Random(seed)
    predictions: list[float] = []
    outcomes: list[int] = []
    for _ in range(n_cards):
        p = rng.uniform(0.02, 0.98)  # latent true recall, spread across [0,1]
        k = rng.randint(3, 25)  # training reviews; enough to fit, still varied
        passes = sum(1 for _ in range(k) if rng.random() < p)
        reps, lapses = k, k - passes
        predictions.append(_recall_estimate(reps, lapses))  # fit on TRAINING only
        outcomes.append(1 if rng.random() < p else 0)  # HELD-OUT review outcome
    return Dataset(predictions, outcomes)


# --- SVG reliability diagram (pure Python, no matplotlib) ---------------------

_W, _H = 560, 520  # canvas
_M = 70  # margin around the plot square
_PLOT = 400  # plot side length (square, so pixels-per-unit match on both axes)


def _x(u: float) -> float:
    """Predicted probability [0,1] -> pixel x."""
    return _M + u * _PLOT


def _y(v: float) -> float:
    """Observed frequency [0,1] -> pixel y (SVG y grows downward)."""
    return _M + (1.0 - v) * _PLOT


def _fmt(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


def render_svg(bins, brier: float, log_loss: float, ece: float, n: int) -> str:
    """A reliability diagram: predicted-probability bins (x) vs. observed pass
    frequency (y), the y=x perfect-calibration diagonal, and per-bin counts."""
    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}" '
        f'viewBox="0 0 {_W} {_H}" font-family="Segoe UI, Arial, sans-serif">'
    )
    parts.append(f'<rect width="{_W}" height="{_H}" fill="#ffffff"/>')
    parts.append(
        f'<text x="{_W / 2}" y="30" text-anchor="middle" font-size="18" '
        f'font-weight="bold" fill="#1a1a1a">RPCE memory-model calibration '
        f"(held-out)</text>"
    )

    # Gridlines + tick labels at 0, .25, .5, .75, 1.
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        gx, gy = _x(t), _y(t)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{_y(0):.1f}" x2="{gx:.1f}" y2="{_y(1):.1f}" '
            f'stroke="#e6e6e6" stroke-width="1"/>'
        )
        parts.append(
            f'<line x1="{_x(0):.1f}" y1="{gy:.1f}" x2="{_x(1):.1f}" y2="{gy:.1f}" '
            f'stroke="#e6e6e6" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{gx:.1f}" y="{_y(0) + 18:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#555">{_fmt(t)}</text>'
        )
        parts.append(
            f'<text x="{_x(0) - 10:.1f}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#555">{_fmt(t)}</text>'
        )

    # Plot border.
    parts.append(
        f'<rect x="{_x(0):.1f}" y="{_y(1):.1f}" width="{_PLOT}" height="{_PLOT}" '
        f'fill="none" stroke="#999" stroke-width="1"/>'
    )

    # The y=x perfect-calibration diagonal (id="diagonal" — tests look for this).
    parts.append("<!-- diagonal: y=x perfect calibration -->")
    parts.append(
        f'<line id="diagonal" x1="{_x(0):.1f}" y1="{_y(0):.1f}" '
        f'x2="{_x(1):.1f}" y2="{_y(1):.1f}" stroke="#c0392b" stroke-width="1.5" '
        f'stroke-dasharray="6 4"/>'
    )

    # Reliability curve: connect populated bins by (mean_predicted, mean_actual).
    pts = [(b.mean_predicted, b.mean_actual) for b in bins if b.count > 0]
    if len(pts) > 1:
        poly = " ".join(f"{_x(u):.1f},{_y(v):.1f}" for u, v in pts)
        parts.append(
            f'<polyline points="{poly}" fill="none" stroke="#2c6fbb" stroke-width="2"/>'
        )

    # Per-bin markers (radius scales with share of samples) + count labels.
    max_count = max((b.count for b in bins), default=1) or 1
    for b in bins:
        if b.count == 0:
            continue
        cx, cy = _x(b.mean_predicted), _y(b.mean_actual)
        r = 3 + 7 * (b.count / max_count)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#2c6fbb" '
            f'fill-opacity="0.75" stroke="#1a4c86" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{cy - r - 3:.1f}" text-anchor="middle" '
            f'font-size="9" fill="#333">n={b.count}</text>'
        )

    # Axis titles.
    parts.append(
        f'<text x="{_M + _PLOT / 2:.1f}" y="{_y(0) + 42:.1f}" text-anchor="middle" '
        f'font-size="13" fill="#1a1a1a">Predicted recall probability</text>'
    )
    parts.append(
        f'<text x="20" y="{_M + _PLOT / 2:.1f}" text-anchor="middle" font-size="13" '
        f'fill="#1a1a1a" transform="rotate(-90 20 {_M + _PLOT / 2:.1f})">'
        f"Observed pass frequency</text>"
    )

    # Metrics + legend footer.
    footer = (
        f"n={n} held-out reviews   Brier={brier:.4f}   "
        f"LogLoss={log_loss:.4f}   ECE={ece:.4f}"
    )
    parts.append(
        f'<text x="{_W / 2}" y="{_H - 22:.1f}" text-anchor="middle" font-size="12" '
        f'fill="#1a1a1a">{footer}</text>'
    )
    parts.append(
        f'<text x="{_W / 2}" y="{_H - 6:.1f}" text-anchor="middle" font-size="10" '
        f'fill="#888">dashed red = perfect calibration (y=x); blue = observed; '
        f"seeded synthetic cohort</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def evaluate(dataset: Dataset, n_bins: int = N_BINS) -> dict:
    """Run the production metrics on the held-out set and return a JSON-ready dict."""
    from anki.rpce import metrics

    preds, outs = dataset.predictions, dataset.outcomes
    bins = metrics.calibration_bins(preds, outs, n_bins)
    brier = metrics.brier_score(preds, outs)
    ll = metrics.log_loss(preds, outs)
    ece = metrics.expected_calibration_error(preds, outs, n_bins)
    return {
        "source": "seeded-synthetic",
        "note": (
            "Held-out split + production Laplace estimator + production metrics; "
            "review OUTCOMES are a seeded synthetic cohort, NOT real candidate data."
        ),
        "seed": SEED,
        "n": len(preds),
        "n_bins": n_bins,
        "brier": brier,
        "log_loss": ll,
        "ece": ece,
        "well_calibrated": ece < ECE_WELL_CALIBRATED,
        "ece_threshold": ECE_WELL_CALIBRATED,
        "bins": [
            {
                "lower": b.lower,
                "upper": b.upper,
                "count": b.count,
                "mean_predicted": b.mean_predicted,
                "mean_actual": b.mean_actual,
            }
            for b in bins
        ],
    }


def write_artifacts(result: dict, svg: str) -> tuple[str, str]:
    """Write calibration.json + calibration.svg under docs/rpce/artifacts/."""
    os.makedirs(_ARTIFACT_DIR, exist_ok=True)
    json_path = os.path.join(_ARTIFACT_DIR, "calibration.json")
    svg_path = os.path.join(_ARTIFACT_DIR, "calibration.svg")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return json_path, svg_path


def run() -> tuple[dict, str]:
    """Build the dataset, compute metrics, and render the SVG. Pure/deterministic."""
    dataset = build_holdout_dataset()
    result = evaluate(dataset)
    from anki.rpce import metrics

    bins = metrics.calibration_bins(
        dataset.predictions, dataset.outcomes, result["n_bins"]
    )
    svg = render_svg(
        bins, result["brier"], result["log_loss"], result["ece"], result["n"]
    )
    return result, svg


def main() -> int:
    _bootstrap_paths()
    result, svg = run()
    json_path, svg_path = write_artifacts(result, svg)

    print("§9 Step 1 — memory-model calibration on HELD-OUT reviews")
    print("(production Laplace estimator + production metrics; review outcomes are a")
    print(" SEEDED SYNTHETIC cohort, not real candidate data — see module docstring)\n")
    print(
        f"seed={result['seed']}  held-out reviews n={result['n']}  bins={result['n_bins']}"
    )
    print(f"  Brier score:              {result['brier']:.4f}   (0 best, 1 worst)")
    print(f"  Log loss:                 {result['log_loss']:.4f}   (lower better)")
    print(f"  Expected Calibration Err: {result['ece']:.4f}   (0 = perfect)\n")

    print(f"{'bin':>12} {'count':>7} {'mean_pred':>10} {'observed':>9}")
    for b in result["bins"]:
        rng = f"[{b['lower']:.1f},{b['upper']:.1f})"
        if b["count"] == 0:
            print(f"{rng:>12} {b['count']:>7} {'-':>10} {'-':>9}")
        else:
            print(
                f"{rng:>12} {b['count']:>7} {b['mean_predicted']:>10.3f} "
                f"{b['mean_actual']:>9.3f}"
            )

    print(f"\nwrote {json_path}")
    print(f"wrote {svg_path}")

    if result["well_calibrated"]:
        print(
            f"\nWELL-CALIBRATED: ECE {result['ece']:.4f} < "
            f"{result['ece_threshold']:.2f} on held-out reviews — the memory model's "
            "stated recall\nmatches observed recall (seeded synthetic demonstration)."
        )
        return 0
    print(
        f"\nNOT YET CALIBRATED: ECE {result['ece']:.4f} >= "
        f"{result['ece_threshold']:.2f} — predicted recall drifts from observed "
        "(seeded synthetic demonstration)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
