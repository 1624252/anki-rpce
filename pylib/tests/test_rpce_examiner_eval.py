# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The held-out reworded examiner eval must actually discriminate: it grades
paraphrased answers (not verbatim), so a keyword grader can no longer score a
flat 100%, and the offline graders separate. The AI row is not tested here (it
needs the network + is non-deterministic); this locks in the deterministic
baselines and the answer-key integrity."""

import os
import sys

from anki.rpce import examiner

_TOOLS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"
)
sys.path.insert(0, _TOOLS)
import rpce_examiner_eval as ev  # noqa: E402


def test_answer_key_points_at_real_items():
    # Every WRONG label must reference a real (card_id, paraphrase index).
    by_id = {c.id: c for c in ev.DATASET}
    for cid, idx in ev.WRONG:
        assert cid in by_id, cid
        assert 0 <= idx < len(by_id[cid].paraphrases)


def test_positive_and_negative_counts():
    items = ev._items()
    pos = [x for x in items if x[2]]
    neg = [x for x in items if not x[2]]
    # 32 concepts x 2 reworded answers, 22 labelled wrong.
    assert len(items) == 64
    assert len(neg) == len(ev.WRONG) == 22
    assert len(pos) == 42


def test_reworded_eval_no_longer_pins_at_100_percent():
    # The whole point: on reworded answers, keyword overlap drops well below the
    # flat 100% it scored on verbatim gold answers.
    kw = ev._score("keyword", examiner.BaselineExaminer())
    assert kw.accuracy < 1.0


def test_offline_graders_separate_and_are_stable():
    # Deterministic snapshot so a regression in the offline graders is caught.
    rubric = ev._score("rubric", examiner.KeywordExaminer())
    keyword = ev._score("keyword", examiner.BaselineExaminer())
    assert (rubric.pos_pass, rubric.neg_pass) == (34, 5)  # 81% acc / 23% fp
    assert (keyword.pos_pass, keyword.neg_pass) == (28, 3)  # 67% acc / 14% fp
