# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the §8 3-build experiment runner (pylib/tools/rpce_experiment_run.py).

Checks the pre-registered metric, equal study budget across arms, equal-length
samples, determinism (same seed => same means), and the JSON artifact."""

import json
import sys
from pathlib import Path

# The runner lives under pylib/tools, which is not on the package path.
_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import rpce_experiment_run as runner  # noqa: E402

from anki.rpce import experiment as exp  # noqa: E402


def test_run_returns_report_with_pre_registered_metric():
    result = runner.run()
    assert isinstance(result.report, exp.ExperimentReport)
    assert result.report.metric == exp.MAIN_METRIC


def test_arms_have_equal_budget_and_equal_length_samples():
    result = runner.run()
    # Equal study time is the §8 control: identical budget for every arm.
    budgets = set(result.budget_per_arm.values())
    assert len(budgets) == 1
    assert result.budget_per_arm["full"] == (
        result.study_steps_per_concept * result.n_concepts
    )
    # One accuracy observation per simulated learner, per arm.
    for arm in ("full", "ablation", "plain"):
        assert len(result.samples[arm]) == result.n_learners


def test_deterministic_same_seed_same_means():
    a = runner.run(seed=12345)
    b = runner.run(seed=12345)
    for arm in ("full", "ablation", "plain"):
        assert a.samples[arm] == b.samples[arm]
    assert a.report.feature_effect.mean == b.report.feature_effect.mean


def test_accuracy_samples_in_unit_range():
    result = runner.run()
    for arm in ("full", "ablation", "plain"):
        for acc in result.samples[arm]:
            assert 0.0 <= acc <= 1.0


def test_write_artifact_creates_json(tmp_path):
    result = runner.run()
    path = tmp_path / "experiment.json"
    runner.write_artifact(result, str(path))
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metric"] == exp.MAIN_METRIC
    assert data["equal_study_time"] is True
    assert set(data["arms"]) == {"full", "ablation", "plain"}
    # feature_helped is one of True / False / None (honest null allowed).
    assert data["feature_helped"] in (True, False, None)
