# Question-authoring rules (RPCE)

Every RPCE practice question — generated or hand-written — must obey these. They
are enforced in `pylib/tools/rpce_generate_questions.py` where possible and
checked by the quality audit (subagents) for the parts a machine can't judge.

## R1 — Hints never reveal spelling

A cloze hint may name the answer's *category* (e.g. "a voting threshold", "a
number or length of time") but must **never** disclose its length, its first
letter, or its word count. When no safe category hint exists, show a plain "?"
and let the sentence + citation carry the recall. Enforced in `_cloze_hint`.

## R2 — No "which section" recall

A question must never require the candidate to remember which RONR section a rule
comes from. Section references (e.g. "10:5", "§23", "Section 4") may appear only
in the **answer's** citation/quote, never in the stem or options. Enforced by
`_SECTION_RE` / `mentions_section` (stems and spans that leak a section are
rejected or stripped).

## R3 — Solvable without new context

A question must be answerable from the information it presents, plus general RONR
knowledge — never from a source paragraph the candidate can't see. If a question
can't be solved without additional context, it is removed. Machine checks catch
obvious cases (dangling clozes, pronoun-only stems); the subagent audit tests the
rest by attempting each question cold.

## R4 — MCQ style follows the sample bank

Multiple-choice questions should match the form of
`data/RPCE-Sample-Questions-v4-100625.md`: a concrete, self-contained scenario
(named body, realistic situation) that asks what is proper / what the chair
should say / what happens next, with full-sentence options exactly one of which
is correct. Avoid bare "fill in the blank from the rulebook" phrasing.

## R5 — No two-option MCQs

Never ship a two-option multiple-choice question. Binary facts (a motion is
debatable or not, needs a second or not) belong in **cloze** form or the
Reference tables, not a 50/50 MCQ. MCQs carry at least four options.

## R6 — Questions are authored, not scripted

Questions are written by the model (directly or via subagents), not emitted by a
template script. A generator can extract corpus sentences but can't write a
self-contained scenario that reads like the sample bank, so authored questions
are the source of truth. They live in a curated dataset the deck builder reads;
the old `rpce_generate_questions.py` template output is retired for shipping.

## Testing

Quality is verified by re-attempting questions with no access to the source
corpus (see the audit workflow). A question that a fresh solver can't answer, or
that violates any rule above, is dropped from the bank via the generator's
removal blocklist (as with `_IMPOSSIBLE_CLOZE_GUIDS`).
