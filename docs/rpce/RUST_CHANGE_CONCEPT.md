# The Rust Engine Change — Concept Grouping (Same-Concept Burying)

Spec deliverable for §7a: a real change inside Anki's Rust core (not just the
Python screens), with tests, undo/corruption safety, a rationale, and a
touched-files list.

## What it does

Extends Anki's sibling burying to group cards by **concept** instead of by
note. Anki already buries the *siblings of a note* after you study one of them,
so you don't see the same material twice in a day. RPCE expresses one concept
across several notes and question TYPES (a cloze, an applied MCQ, a scenario…),
so studying any one of them should count as having seen the concept for the day
and bury the rest — even though they live on different notes.

- A concept is identified by an `rpce::concept::<id>` tag on the note (see
  `CONCEPT_TAG_PREFIX` in `pylib/anki/rpce/transfer_ladder.py`). The concept id
  is the tag suffix.
- New backend RPC `bury_concept_siblings(card_id)` looks up the studied card's
  concept tag, finds the **other** cards carrying the same concept tag that are
  still in a buryable state (not already buried, not suspended), and buries them
  using Anki's "bury for scheduling" operation. It returns the number of cards
  buried.
- A card with no `rpce::concept::<id>` tag has no concept, so the call buries
  nothing and returns 0.

The bury reuses `bury_or_suspend_cards_inner(..., BurySched)`, the exact
machinery Anki's own note-sibling burying uses, so buried cards land in the
`SchedBuried` queue and auto-unbury on the next day rollover just like normal
sibling burials.

## Why this belongs in Rust, not Python

1. **Shared by both apps.** The change lives in `rslib` below the protobuf
   boundary, so the *same* compiled logic ships to the desktop app and the
   Android companion. A Python implementation would not reach the phone and
   would violate the spec's "share the engine, don't rewrite it" rule (§3).
2. **It is scheduling.** Burying mutates the study queue and must interact
   correctly with day-rollover unburying, undo, and collection integrity. That
   state and its transaction/undo plumbing live in Rust; reimplementing queue
   writes in Python would risk corrupting the collection.
3. **Reuses existing engine primitives.** Tag search, card gathering, and the
   undoable bury operation already exist in `rslib`. The change is a thin layer
   that composes them — no data crosses the FFI boundary just to be re-buried.

## Undo & corruption safety

The RPC runs inside `Collection::transact(Op::Bury, …)` and performs its writes
**only** through `bury_or_suspend_cards_inner`, the same undoable primitive used
by Anki's built-in bury. Therefore:

- **Undoable.** `col.undo()` reverts the bury and returns the cards to their
  original queue. A dedicated test (`undo_restores_buried_siblings`) proves the
  buried sibling is restored and no cards remain buried after undo.
- **No corruption.** We never write card queues by hand. Suspended cards are
  skipped (burying them would silently unsuspend on rollover), and already
  `SchedBuried` cards are not re-touched, so the count is accurate and no card
  is double-buried.
- **Concept isolation.** The sibling search is scoped to the exact concept tag,
  so cards of a different concept (or with no concept) are never affected.

## Tests

- **Rust unit tests** (`rslib/src/scheduler/concept_bury.rs`, 7 tests):
  1. `buries_same_concept_siblings_across_different_notes` — studying one card
     buries a same-concept sibling that lives on a *different* note.
  2. `does_not_bury_cards_of_a_different_concept` — a different concept is left
     alone.
  3. `card_without_concept_tag_is_a_noop` — no concept tag ⇒ buries nothing,
     returns 0.
  4. `count_matches_number_of_buried_siblings` — count correctness with two
     siblings plus noise.
  5. `already_buried_siblings_are_not_double_counted` — a second call buries 0.
  6. `undo_restores_buried_siblings` — proof that `undo()` reverts the bury.
  7. `concept_of_tags_extracts_id_and_ignores_others` — tag-parsing unit.
- **Python-calling test** (`pylib/tests/test_concept_bury.py`, 2 tests): calls
  `col._backend.bury_concept_siblings(card_id=...)` end to end and asserts the
  concept-42 sibling is buried while a concept-99 card is not, plus the no-tag
  no-op case.

Run them with:

```bash
cargo test -p anki concept_bury
tools\ninja check:pytest:pylib    # or: just test-py  (rebuilds pylib first)
```

Because this adds a `.proto` RPC and message, the generated code must be
regenerated: `cargo test`/`cargo build` reruns the Rust build scripts
automatically, and the Python binding `col._backend.bury_concept_siblings` is
regenerated when pylib is rebuilt (`just wheels` / `tools\ninja check:pytest:pylib`).

## Upstream files touched (merge-difficulty notes)

| File                                    | Change                                                        | Merge risk                                                            |
| --------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------- |
| `proto/anki/scheduler.proto`            | Added one RPC to `SchedulerService` + 1 request message       | **Low** — additive; new lines near existing RPCs.                     |
| `rslib/src/scheduler/mod.rs`            | Added `pub mod concept_bury;`                                 | **Low** — one line in the module list.                                |
| `rslib/src/scheduler/service/mod.rs`    | Implemented `bury_concept_siblings` trait method              | **Low** — one new isolated method.                                    |
| `rslib/src/scheduler/bury_and_suspend.rs` | Widened `bury_or_suspend_cards_inner` to `pub(crate)`       | **Low** — visibility-only change; no behaviour change.                |
| `rslib/src/scheduler/concept_bury.rs`   | **New file** — all concept-bury logic + tests                 | **None** — new file, no upstream conflict.                            |

The Python binding (`bury_concept_siblings`) is **auto-generated** from the
proto by the build, so no hand-written client code needs maintaining.

## Wiring for the orchestrator

The app calls this after a card is answered. The generated backend method is:

```python
col._backend.bury_concept_siblings(card_id=<answered card id>)
```

It returns an `OpChangesWithCount` (`.count` = number buried). Call it right
after `answer_card` for RPCE decks; buried siblings drop out of the study queue
until the next day rollover, and it is part of the undo stack so the reviewer's
undo reverts both the answer and the concept bury.
</content>
