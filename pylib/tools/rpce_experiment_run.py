#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""§8 study-feature experiment RUNNER — the Transfer Ladder, three builds, equal
study time.

The spec (§8) and the Sunday deliverable ask for one study feature tested with
three builds at *equal study time*, reported with a range, honestly. The
statistics live in :mod:`anki.rpce.experiment` (``compare`` + honest-null when
the effect interval straddles zero). This runner supplies the missing piece: it
produces the three arms' accuracy samples on the pre-registered metric and calls
``compare``.

Three builds, IDENTICAL study budget (same concepts, same number of study steps
per concept):

1. **full**     — Transfer Ladder ON: a concept resurfaces in *rotating* formats
                  (cloze → mcq → scenario → advising). Varied practice is modelled
                  as building transferable understanding fastest (Spiky POV 2,
                  Insight 1).
2. **ablation** — Transfer Ladder OFF: the same concept is drilled in a *single*
                  format. Builds format familiarity that does not transfer to a
                  new wording, so less transfer mastery per step.
3. **plain**    — unmodified-Anki-style baseline: no ladder, no concept linking;
                  rote card memorisation, the least transfer per step.

Pre-registered metric (stated before results, spec §8):
:data:`anki.rpce.experiment.MAIN_METRIC` — accuracy on new, reworded scenario
questions. The item bank is the authored RPCE reworded-question set from
:mod:`rpce_paraphrase` (real RONR content); the test format (reworded scenario)
is one NONE of the arms drilled, so it measures transfer, not format practice.

HONESTY: the "learner" is a deterministic, seeded parametric simulation — NOT
real students. It demonstrates a fair, re-runnable protocol at equal study time.
The transfer advantage is a modelled *parameter*, not a measurement; set the
per-arm learning rates equal and the harness returns an honest null. Real learner
data is required to draw a substantive conclusion.

    just rpce-experiment
    # or: PYTHONPATH=out/pylib python pylib/tools/rpce_experiment_run.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass


def _bootstrap_paths() -> None:
    """Make the built ``anki`` package and the sibling tool modules importable."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    built = os.path.join(repo, "out", "pylib")
    if os.path.isdir(built):
        sys.path.insert(0, built)
    if here not in sys.path:
        sys.path.insert(0, here)  # for `import rpce_paraphrase`
    os.environ.setdefault("ANKI_TEST_MODE", "1")


# --- Pre-registered design (fixed in code; stated BEFORE results) ------------

#: Fixed seed so every run reproduces identically (no Math.random / argless Date).
SEED = 20260705

#: Simulated students per arm. Each produces one accuracy observation per arm.
N_LEARNERS = 40

#: Study steps spent on EACH concept — identical across all three arms, so total
#: study budget is equal by construction (the §8 "equal study time" control).
STUDY_STEPS_PER_CONCEPT = 6

#: Reworded questions scored per concept (from the authored paraphrase set).
QUESTIONS_PER_CONCEPT = 2

#: Per-step transfer-mastery learning rate by arm (diminishing returns toward a
#: per-concept ceiling). The ONLY thing that differs between arms. These encode
#: the hypothesis; they are a modelled parameter, not a measurement. Make them
#: equal and the experiment returns an honest null (the harness does not rig it).
RATE_VARIED = 0.30  # full: rotating formats force transfer
RATE_SINGLE = 0.20  # ablation: single-format drill transfers less
RATE_PLAIN = 0.13  # plain: rote card memorisation, least transfer

#: Spread of per-learner aptitude (applied equally to all three arms for the same
#: learner, so the comparison is fair/within-subject).
APTITUDE_SD = 0.06

HYPOTHESIS = (
    "Rotating a concept through escalating formats (Transfer Ladder ON) yields "
    "higher accuracy on NEW, reworded scenario questions than drilling one format "
    "(ladder OFF) or plain card memorisation, at equal study time, because varied "
    "practice builds transferable understanding while single-format drill builds "
    "format familiarity that does not transfer (Spiky POV 2; Insight 1)."
)

HONESTY = (
    "This is a DETERMINISTIC, SEEDED SIMULATED learner demonstrating a fair, "
    "re-runnable 3-build test at EQUAL study time - NOT real students. The "
    "transfer advantage is a modelled parameter; real learner data is needed to "
    "draw a substantive conclusion."
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


@dataclass(frozen=True)
class Concept:
    """One RPCE concept the learner studies, with a transfer difficulty derived
    from the authored memory baseline (harder concepts transfer less readily)."""

    id: str
    recall: float  # authored memory baseline (0..1), NOT a measured value
    n_questions: int

    @property
    def base(self) -> float:
        """Starting transfer mastery (prior knowledge: RPCE candidates already
        passed the RONRIB membership exam, so it is moderate, not zero)."""
        return 0.30 + 0.20 * self.recall

    @property
    def ceiling(self) -> float:
        """Attainable transfer mastery (easier concepts reach higher)."""
        return 0.55 + 0.40 * self.recall


def load_concepts() -> list[Concept]:
    """Build the item bank from the authored reworded-question dataset."""
    import rpce_paraphrase as para

    return [Concept(c.id, c.recall, len(c.paraphrases)) for c in para.DATASET]


def _study(concept: Concept, steps: int, rate: float) -> float:
    """Transfer mastery after ``steps`` study steps at learning ``rate``
    (diminishing returns toward the concept ceiling)."""
    m = concept.base
    for _ in range(steps):
        m += rate * (concept.ceiling - m)
    return m


def _arm_accuracy(
    concepts: list[Concept], rate: float, aptitude: float, rng: random.Random
) -> float:
    """One simulated learner's accuracy on the reworded-question test for one arm.

    Studies every concept (equal steps), then answers its reworded questions with
    probability = mastery + aptitude, drawn as Bernoulli trials."""
    correct = total = 0
    for concept in concepts:
        mastery = _study(concept, STUDY_STEPS_PER_CONCEPT, rate)
        p = _clamp(mastery + aptitude, 0.02, 0.98)
        for _ in range(concept.n_questions):
            total += 1
            if rng.random() < p:
                correct += 1
    return correct / total if total else 0.0


@dataclass
class RunResult:
    """The experiment output: the statistical report plus the raw samples and the
    equal-budget accounting the test/report rely on."""

    report: "object"  # anki.rpce.experiment.ExperimentReport
    samples: dict[str, list[float]]
    seed: int
    n_learners: int
    n_concepts: int
    study_steps_per_concept: int
    #: Total study steps per arm — equal across arms is the §8 control.
    budget_per_arm: dict[str, int]


def run(seed: int = SEED) -> RunResult:
    """Run the 3-build comparison at equal study time and return the report."""
    from anki.rpce import experiment as exp

    concepts = load_concepts()
    arms = {"full": RATE_VARIED, "ablation": RATE_SINGLE, "plain": RATE_PLAIN}
    samples: dict[str, list[float]] = {arm: [] for arm in arms}

    for i in range(N_LEARNERS):
        # Same aptitude for a learner across all arms => fair within-subject test.
        aptitude = random.Random(seed + i).gauss(0.0, APTITUDE_SD)
        for arm_idx, (arm, rate) in enumerate(arms.items()):
            rng = random.Random(seed * 7919 + i * 31 + arm_idx)
            samples[arm].append(_arm_accuracy(concepts, rate, aptitude, rng))

    report = exp.compare(samples["full"], samples["ablation"], samples["plain"])
    budget = STUDY_STEPS_PER_CONCEPT * len(concepts)
    return RunResult(
        report=report,
        samples=samples,
        seed=seed,
        n_learners=N_LEARNERS,
        n_concepts=len(concepts),
        study_steps_per_concept=STUDY_STEPS_PER_CONCEPT,
        budget_per_arm={arm: budget for arm in arms},
    )


def _artifact_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(repo, "docs", "rpce", "artifacts", "experiment.json")


def _est(e) -> dict[str, float]:
    return {"mean": e.mean, "low": e.low, "high": e.high}


def write_artifact(result: RunResult, path: str | None = None) -> str:
    """Write the experiment result to docs/rpce/artifacts/experiment.json."""
    path = path or _artifact_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = result.report
    payload = {
        "metric": r.metric,
        "hypothesis": HYPOTHESIS,
        "honesty": HONESTY,
        "seed": result.seed,
        "n_learners": result.n_learners,
        "n_concepts": result.n_concepts,
        "study_steps_per_concept": result.study_steps_per_concept,
        "budget_per_arm": result.budget_per_arm,
        "equal_study_time": len(set(result.budget_per_arm.values())) == 1,
        "arms": {
            "full": _est(r.full),
            "ablation": _est(r.ablation),
            "plain": _est(r.plain),
        },
        "feature_effect_full_minus_ablation": _est(r.feature_effect),
        "vs_plain_full_minus_plain": _est(r.vs_plain),
        "feature_helped": r.feature_helped,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path


def _verdict(helped: bool | None) -> str:
    if helped is True:
        return "YES - the feature helped (effect interval is entirely above 0)."
    if helped is False:
        return "NO - the feature hurt (effect interval is entirely below 0)."
    return (
        "NULL - inconclusive: the effect interval straddles 0, so at equal study "
        "time this run shows no reliable difference (an honest null, spec §8)."
    )


def main() -> int:
    _bootstrap_paths()
    result = run()
    r = result.report

    print("=" * 72)
    print("RPCE STUDY-FEATURE EXPERIMENT - Transfer Ladder, 3 builds, equal time")
    print("=" * 72)
    print("!! " + HONESTY)
    print("=" * 72)

    # State the pre-registration BEFORE printing any results (spec §8).
    print("\nPre-registered metric:  " + r.metric)
    print("Pre-registered hypothesis:")
    for line in HYPOTHESIS.split(". "):
        print("  " + line.strip().rstrip(".") + ".")
    print(
        f"\nEqual study budget: {result.study_steps_per_concept} steps/concept x "
        f"{result.n_concepts} concepts = {next(iter(result.budget_per_arm.values()))} "
        f"study steps per arm (identical across arms)."
    )
    print(
        f"Design: {result.n_learners} seeded simulated learners/arm; seed={result.seed}."
    )

    print("\n--- Results (mean accuracy on new, reworded scenario questions) ---")
    print(f"{'arm':<12}{'mean':>8}{'95% range':>22}")
    for name, e in (
        ("full", r.full),
        ("ablation", r.ablation),
        ("plain", r.plain),
    ):
        print(f"{name:<12}{e.mean:>8.3f}   [{e.low:.3f}, {e.high:.3f}]")

    fe, vp = r.feature_effect, r.vs_plain
    print("\n--- Effects (with 95% CI) ---")
    print(
        f"feature_effect (full - ablation): {fe.mean:+.3f}  "
        f"[{fe.low:+.3f}, {fe.high:+.3f}]"
    )
    print(
        f"vs_plain      (full - plain)    : {vp.mean:+.3f}  "
        f"[{vp.low:+.3f}, {vp.high:+.3f}]"
    )
    print(f"\nfeature_helped = {r.feature_helped}")
    print(_verdict(r.feature_helped))

    path = write_artifact(result)
    print(f"\nWrote artifact: {path}")
    print("=" * 72)
    print("!! " + HONESTY)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    _bootstrap_paths()
    sys.exit(main())
