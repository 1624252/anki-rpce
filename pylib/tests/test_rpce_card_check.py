# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the AI card check (spec §7f): 3-bucket classifier + blocking cutoff
and the >=50-item gold set."""

from pathlib import Path

import pytest

from anki.rpce import card_check, examiner, gold
from anki.rpce.card_check import Bucket, Card

_GOLD_DATA = (
    Path(__file__).resolve().parents[2] / "data" / "RPCE-Sample-Questions-v4-100625.md"
)

# A verbatim RONR-style quote used as both the "corpus" and the card's citation,
# so the verbatim-citation check passes and we isolate the other checks.
_PQ_QUOTE = "The Previous Question requires a two-thirds vote and is not debatable."


def _mcq(answer: str, quote: str = _PQ_QUOTE, question: str = "") -> Card:
    return Card(
        question=question or "What vote does the Previous Question require?",
        answer=answer,
        citation="16:1",
        quote=quote,
        kind="mcq",
        options=("A majority", "Two-thirds", "Unanimous consent", "One-third"),
    )


# --- bucket 2: WRONG ----------------------------------------------------------


def test_wrong_fact_contradicting_quote_lands_in_bucket_2():
    # Answer asserts "majority" where the cited quote says "two-thirds".
    card = _mcq("a majority vote")
    v = card_check.classify_one(card, card_check._normalize_corpus(_PQ_QUOTE), [card])
    assert v.bucket is Bucket.WRONG


def test_fabricated_citation_lands_in_bucket_2():
    # A quote that is NOT in the corpus fails the verbatim-citation check.
    card = _mcq("two-thirds vote", quote="This sentence is not in Robert's Rules.")
    v = card_check.classify_one(card, card_check._normalize_corpus(_PQ_QUOTE), [card])
    assert v.bucket is Bucket.WRONG


# --- bucket 3: BAD_TEACHING ---------------------------------------------------


def test_vague_single_word_cloze_lands_in_bucket_3():
    quote = "The difference in the rules governing these two subclasses is only slight."
    card = Card(
        question="Fill the blank: The _____ in the rules is only slight.",
        answer="difference",  # a single generic (non-parliamentary) word
        citation="6:2",
        quote=quote,
        kind="cloze recall",
    )
    v = card_check.classify_one(card, card_check._normalize_corpus(quote), [card])
    assert v.bucket is Bucket.BAD_TEACHING


def test_near_duplicate_card_lands_in_bucket_3():
    q = "The chair recognizes a member before that member may speak in debate."
    stem = "In a meeting, what must happen before a member may speak in debate?"
    opts = (
        "The chair recognizes the member",
        "The member sits down",
        "A second is required",
        "The vote is taken",
    )
    # Two cards asking the same thing (specific answers, so not flagged vague).
    a = Card(
        stem, "the chair recognizes the member", "3:30", q, kind="mcq", options=opts
    )
    b = Card(
        stem, "the chair recognizes the member", "3:30", q, kind="mcq", options=opts
    )
    v = card_check.classify_one(b, card_check._normalize_corpus(q), [a, b])
    assert v.bucket is Bucket.BAD_TEACHING
    assert "duplicate" in v.reason


def test_two_option_mcq_is_trivially_guessable():
    card = Card(
        "Is a main motion debatable?",
        "Debatable",
        "10:7",
        "A main motion is debatable.",
        kind="mcq",
        options=("Debatable", "Not debatable"),  # only two options (violates R5)
    )
    v = card_check.classify_one(card, card_check._normalize_corpus(card.quote), [card])
    assert v.bucket is Bucket.BAD_TEACHING


# --- bucket 1: CORRECT_USEFUL -------------------------------------------------


def test_good_card_lands_in_bucket_1():
    card = _mcq("two-thirds vote")  # correct, grounded, verbatim, 4 options
    v = card_check.classify_one(card, card_check._normalize_corpus(_PQ_QUOTE), [card])
    assert v.bucket is Bucket.CORRECT_USEFUL


# --- the pre-set, blocking cutoff --------------------------------------------


def test_cutoff_blocks_a_batch_with_a_wrong_fact():
    good = _mcq("two-thirds vote")
    wrong = _mcq("a majority vote")  # a wrong fact
    report = card_check.classify([good, wrong], _PQ_QUOTE)
    assert report.wrong == 1
    assert not report.ok  # a single wrong fact blocks the batch


def test_cutoff_blocks_a_batch_over_the_bad_teaching_ratio():
    q = "A main motion is a motion whose introduction brings business before the assembly."
    dups = [
        Card(
            f"Fill blank {i}: A _____ is a motion whose introduction brings business.",
            "main motion",
            "6:1",
            q,
            kind="cloze",
        )
        for i in range(4)
    ]
    good = _mcq("two-thirds vote")
    report = card_check.classify(dups + [good], q + "\n\n" + _PQ_QUOTE)
    assert report.wrong == 0
    assert report.bad_teaching_ratio > card_check.BAD_TEACHING_RATIO_CUTOFF
    assert not report.ok


def test_clean_batch_passes_the_cutoff():
    cards = [
        _mcq("two-thirds vote", question="What vote does the Previous Question need?"),
    ]
    report = card_check.classify(cards, _PQ_QUOTE)
    assert report.wrong == 0
    assert report.ok


# --- parser -------------------------------------------------------------------


def test_parse_generated_bank_reads_question_answer_and_citation():
    text = (
        "**1.** `[C0157 · Cloze recall]` Fill the blank: A _____ is a motion.\n\n"
        "   *Answer:* main motion — “A main motion is a motion.”. "
        "See RONR (12th ed.) §6:1 — “A main motion is a motion.”\n\n"
        "**2.** `[K0049 · Applied multiple-choice]` What vote adopts a main motion?\n"
        "   A. Majority vote\n"
        "   B. Two-thirds vote\n"
        "   C. Unanimous consent\n"
        "   D. No vote\n\n"
        "   *Answer:* A) Majority vote. See RONR (12th ed.) §44:1 — “a majority vote.”\n"
    )
    cards = card_check.parse_generated_bank(text)
    assert len(cards) == 2
    assert cards[0].kind == "cloze"
    assert cards[0].answer == "main motion"
    assert cards[0].citation == "6:1"
    assert cards[1].kind == "mcq"
    assert cards[1].answer == "Majority vote"  # letter prefix stripped
    assert len(cards[1].options) == 4


# --- gold set >= 50 -----------------------------------------------------------


@pytest.mark.skipif(not _GOLD_DATA.exists(), reason="official gold data not present")
def test_augmented_gold_set_reaches_50_and_stays_clean():
    text = _GOLD_DATA.read_text(encoding="utf-8")
    gset = gold.augmented_gold(text, target=50)
    assert len(gset) >= 50, f"gold set only has {len(gset)} items"
    # Augmentation must not leak the gold prompts into study content.
    leaks = examiner.find_leaks(
        gold.training_texts(), [g.prompt for g in gset], threshold=0.8
    )
    assert leaks == [], f"gold set leaked into study content: {leaks}"


@pytest.mark.skipif(not _GOLD_DATA.exists(), reason="official gold data not present")
def test_authored_gold_questions_are_labelled_by_source():
    qs = gold.authored_gold_questions()
    assert qs, "expected authored-bank gold questions"
    for q in qs:
        assert "authored_questions.json" in q.domain
        assert q.correct and q.distractors
