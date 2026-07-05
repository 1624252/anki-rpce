# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the held-out memory-model calibration runner (spec §9 Step 1)."""

import math
import sys
from pathlib import Path

# The runner lives under pylib/tools, which is not on the package path.
_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import rpce_calibration as cal  # noqa: E402


def test_metrics_finite_and_in_range():
    result, _svg = cal.run()
    assert 0.0 <= result["brier"] <= 1.0
    assert math.isfinite(result["log_loss"]) and result["log_loss"] >= 0.0
    assert 0.0 <= result["ece"] <= 1.0
    assert result["n"] == cal.N_CARDS


def test_bins_partition_all_samples():
    result, _svg = cal.run()
    assert sum(b["count"] for b in result["bins"]) == result["n"]
    assert len(result["bins"]) == cal.N_BINS


def test_deterministic_across_runs():
    a, _ = cal.run()
    b, _ = cal.run()
    assert a["brier"] == b["brier"]
    assert a["log_loss"] == b["log_loss"]
    assert a["ece"] == b["ece"]
    assert [x["count"] for x in a["bins"]] == [x["count"] for x in b["bins"]]


def test_svg_is_valid_ish_xml_with_diagonal():
    _result, svg = cal.run()
    assert svg.startswith("<?xml") or svg.startswith("<svg")
    assert "<svg" in svg and svg.rstrip().endswith("</svg>")
    # The perfect-calibration reference line must be present.
    assert 'id="diagonal"' in svg
    assert "y=x" in svg


def test_write_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "_ARTIFACT_DIR", str(tmp_path))
    result, svg = cal.run()
    json_path, svg_path = cal.write_artifacts(result, svg)
    assert json_path.endswith("calibration.json")
    assert svg_path.endswith("calibration.svg")
    with open(svg_path, encoding="utf-8") as f:
        assert f.read().startswith("<?xml")
    import json

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["source"] == "seeded-synthetic"
    assert data["n"] == cal.N_CARDS
