# The Rust Engine Change — Points-at-Stake Queue

Spec deliverable for §7a: a real change inside Anki's Rust core (not just the
Python screens), with tests, undo/corruption safety, a rationale, and a
touched-files list.

## What it does

Adds a new **review order** that sorts the _due_ cards by
`topic exam-weight × student weakness`, so the highest-value cards for the RPCE
surface first. It is exposed as a new protobuf RPC and called from Python.

- **Weight** comes from a caller-supplied map of card **tag → exam weight**
  (e.g. the seven RPCE domain tags). Cards matching no tag use a `default_weight`.
- **Weakness** is a Laplace-smoothed failure rate `(lapses + 1) / (reps + 2)`,
  blended 50/50 with FSRS difficulty when a memory state is present. Higher =
  weaker. Bounded in `(0, 1]`.
- **Points at stake** = `weight × weakness`; the queue is sorted descending,
  ties broken by card id for determinism.

## Why this belongs in Rust, not Python

1. **Shared by both apps.** The change lives in `rslib` below the protobuf
   boundary, so the _same_ compiled logic ships to the desktop app and the
   Android companion. Implementing it in Python would not reach the phone and
   would violate the spec's "share the engine, don't rewrite it" rule (§3).
2. **Scheduling hot path.** Ordering due cards is core scheduler work that must
   meet the §10 speed targets on large decks; it belongs next to FSRS in the
   engine, not behind the Python FFI.
3. **Single source of truth.** Card data (reps, lapses, FSRS memory state) and
   due-selection already live in Rust; computing weakness there avoids copying
   the whole due set across the boundary just to re-sort it.

## Undo & corruption safety

The query is **read-only**: it calls `search_cards("is:due")` and reads each
card and its note. It performs **no writes**, opens no transaction, and mutates
no scheduling state — so it cannot corrupt the collection and there is nothing
for undo to revert. FSRS intervals and the normal queue are untouched; this is
an _ordering view_ layered on top of due-selection.

## Tests

- **Rust unit tests** (`rslib/src/scheduler/points_at_stake.rs`, 6 tests):
  ordering by weight×weakness, weakness tie-breaking, default weight, `limit`
  truncation, weakness monotonicity/bounds, and exclusion of not-due cards.
- **Python-calling test** (`pylib/tests/test_points_at_stake.py`, 2 tests):
  calls `col._backend.get_points_at_stake_queue(...)` end to end and checks the
  ordering, `matched_tag`, and `limit`.

Run them with:

```bash
cargo test -p anki points_at_stake
tools\ninja check:pytest:pylib    # or: just test-py
```

## Upstream files touched (merge-difficulty notes)

| File                                     | Change                                           | Merge risk                                        |
| ---------------------------------------- | ------------------------------------------------ | ------------------------------------------------- |
| `proto/anki/scheduler.proto`             | Added one RPC to `SchedulerService` + 2 messages | **Low** — additive; new lines near existing RPCs. |
| `rslib/src/scheduler/mod.rs`             | Added `pub mod points_at_stake;`                 | **Low** — one line in the module list.            |
| `rslib/src/scheduler/service/mod.rs`     | Implemented `get_points_at_stake_queue`          | **Low** — one new trait method; isolated.         |
| `rslib/src/scheduler/points_at_stake.rs` | **New file** — all queue logic + tests           | **None** — new file, no upstream conflict.        |

The Python binding (`get_points_at_stake_queue`) is **auto-generated** from the
proto by the build, so no hand-written client code needs maintaining.
