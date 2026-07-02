# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the §7d paraphrase harness (pylib/tools/rpce_paraphrase.py).

Checks the authored dataset shape (≥30 cards, 2 reworded questions each) and
that the deterministic harness produces a sane memory-vs-performance gap via
``anki.rpce.metrics.paraphrase_gap``."""

import sys
from pathlib import Path

# The harness lives under pylib/tools, which is not on the package path.
_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import rpce_paraphrase as para  # noqa: E402

from anki.rpce import metrics  # noqa: E402


def test_dataset_has_at_least_30_cards_each_with_two_paraphrases():
    assert len(para.DATASET) >= 30
    for card in para.DATASET:
        assert len(card.paraphrases) == 2, card.id
        for p in card.paraphrases:
            assert p.question.strip() and p.answer.strip(), card.id


def test_card_ids_unique_and_recall_in_unit_range():
    ids = [c.id for c in para.DATASET]
    assert len(ids) == len(set(ids)), "card ids must be unique"
    for c in para.DATASET:
        assert 0.0 <= c.recall <= 1.0, c.id


def test_run_reports_sane_paraphrase_gap():
    results, gap = para.run()
    # One result per card; each reworded accuracy is a mean over exactly 2 graded
    # questions, so it can only be 0.0, 0.5 or 1.0.
    assert len(results) == len(para.DATASET)
    for res in results:
        assert res.reworded_accuracy in (0.0, 0.5, 1.0), res.card.id

    # Means stay in range and the gap is exactly recall - reworded (metrics contract).
    assert 0.0 <= gap.mean_recall <= 1.0
    assert 0.0 <= gap.mean_reworded_accuracy <= 1.0
    assert (
        gap.gap
        == metrics.paraphrase_gap(
            [(r.recall, r.reworded_accuracy) for r in results]
        ).gap
    )


def test_gap_is_positive_and_above_red_flag_threshold():
    # Memory should outpace transfer here; a near-zero gap is the §7d red flag.
    _results, gap = para.run()
    assert gap.gap > para.MIN_GAP
    assert gap.mean_recall > gap.mean_reworded_accuracy
