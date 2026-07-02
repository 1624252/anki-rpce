// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! RPCE "concept grouping" — same-concept sibling burying.
//!
//! Anki's built-in burying groups cards by *note*: after you study one card of
//! a note, its siblings (other templates of the same note) are buried so you
//! don't see the same material twice in a day. RPCE cards, however, express one
//! *concept* across several notes and question TYPES (a cloze, an applied MCQ,
//! a scenario…). Studying any one of them should count as having seen the
//! concept for the day, so the rest are buried until a later day — sibling
//! burying keyed on a **concept**, not a note.
//!
//! A concept is identified by an `rpce::concept::<id>` tag on the note (see
//! `pylib/anki/rpce/transfer_ladder.py`). A card whose note carries no such tag
//! has no concept, so burying is a no-op.
//!
//! The bury itself reuses Anki's existing "bury for scheduling" machinery
//! (`bury_or_suspend_cards_inner` with `BurySched`), so it is undoable and
//! collection-integrity safe — we never hand-roll queue writes.

use anki_proto::scheduler::bury_or_suspend_cards_request::Mode as BuryOrSuspendMode;

use crate::prelude::*;
use crate::search::JoinSearches;
use crate::search::Negated;
use crate::search::SearchNode;
use crate::search::StateKind;

/// Tag prefix marking a card's RPCE concept; the concept id is the suffix.
/// Mirrors `CONCEPT_TAG_PREFIX` in `pylib/anki/rpce/transfer_ladder.py`.
pub const CONCEPT_TAG_PREFIX: &str = "rpce::concept::";

/// Return the concept id encoded in a note's tags, if any.
///
/// The id is whatever follows `rpce::concept::` in the first matching tag.
/// Matching is case-insensitive on the prefix to tolerate tag canonicalisation.
fn concept_of_tags(tags: &[String]) -> Option<String> {
    tags.iter().find_map(|tag| {
        // Case-insensitive prefix match; `get` avoids panicking on a
        // non-char-boundary. The id keeps its original case.
        tag.get(..CONCEPT_TAG_PREFIX.len())
            .filter(|prefix| prefix.eq_ignore_ascii_case(CONCEPT_TAG_PREFIX))
            .map(|_| tag[CONCEPT_TAG_PREFIX.len()..].to_string())
            .filter(|id| !id.is_empty())
    })
}

impl Collection {
    /// Bury the other cards sharing `card_id`'s RPCE concept.
    ///
    /// Looks up the given card's `rpce::concept::<id>` tag and buries every
    /// *other* card whose note carries the same concept tag and that is
    /// currently in a buryable state (not already buried or suspended). Returns
    /// the number of cards buried. If the card has no concept tag, nothing is
    /// buried and the count is 0.
    ///
    /// The operation is wrapped in an undoable transaction, so `undo()` reverts
    /// it exactly like any other bury.
    pub fn bury_concept_siblings(&mut self, card_id: CardId) -> Result<OpOutput<usize>> {
        self.transact(Op::Bury, |col| col.bury_concept_siblings_inner(card_id))
    }

    fn bury_concept_siblings_inner(&mut self, card_id: CardId) -> Result<usize> {
        let card = self.storage.get_card(card_id)?.or_not_found(card_id)?;
        let note = self
            .storage
            .get_note(card.note_id)?
            .or_not_found(card.note_id)?;

        let Some(concept) = concept_of_tags(&note.tags) else {
            // No concept tag: nothing to group, nothing to bury.
            return Ok(0);
        };

        // Gather the other cards of this concept that are still buryable, i.e.
        // tagged with the concept but neither already buried nor suspended.
        let concept_tag = format!("{CONCEPT_TAG_PREFIX}{concept}");
        let search = SearchNode::from_tag_name(&concept_tag)
            .and(StateKind::Buried.negated())
            .and(StateKind::Suspended.negated());
        let siblings: Vec<Card> = self
            .all_cards_for_search(search)?
            .into_iter()
            .filter(|c| c.id != card_id)
            .collect();

        self.bury_or_suspend_cards_inner(siblings, BuryOrSuspendMode::BurySched)
    }
}

#[cfg(test)]
mod tests {
    use super::concept_of_tags;
    use crate::card::CardQueue;
    use crate::prelude::*;
    use crate::search::SortMode;
    use crate::search::StateKind;
    use crate::tests::NoteAdder;

    /// Add a basic note with the given tags and return its single card's id.
    fn add_card(col: &mut Collection, front: &str, tags: &[&str]) -> CardId {
        let mut note = NoteAdder::basic(col).fields(&[front, ""]).note();
        note.tags = tags.iter().map(|t| t.to_string()).collect();
        col.add_note(&mut note, DeckId(1)).unwrap();
        col.storage.card_ids_of_notes(&[note.id]).unwrap()[0]
    }

    fn queue_of(col: &mut Collection, cid: CardId) -> CardQueue {
        col.storage.get_card(cid).unwrap().unwrap().queue
    }

    #[test]
    fn buries_same_concept_siblings_across_different_notes() {
        let mut col = Collection::new();
        // Two DIFFERENT notes sharing one concept; each is its own card.
        let studied = add_card(&mut col, "cloze", &["rpce::concept::42"]);
        let sibling = add_card(&mut col, "mcq", &["rpce::concept::42"]);

        let out = col.bury_concept_siblings(studied).unwrap();

        assert_eq!(out.output, 1, "the one other concept card is buried");
        assert_eq!(
            queue_of(&mut col, sibling),
            CardQueue::SchedBuried,
            "sibling of the same concept is buried for scheduling"
        );
        assert_ne!(
            queue_of(&mut col, studied),
            CardQueue::SchedBuried,
            "the studied card itself is not buried"
        );
    }

    #[test]
    fn does_not_bury_cards_of_a_different_concept() {
        let mut col = Collection::new();
        let studied = add_card(&mut col, "a", &["rpce::concept::42"]);
        let other_concept = add_card(&mut col, "b", &["rpce::concept::99"]);

        let out = col.bury_concept_siblings(studied).unwrap();

        assert_eq!(out.output, 0, "no card shares the studied concept");
        assert_eq!(
            queue_of(&mut col, other_concept),
            CardQueue::New,
            "a different concept must not be buried"
        );
    }

    #[test]
    fn card_without_concept_tag_is_a_noop() {
        let mut col = Collection::new();
        let untagged = add_card(&mut col, "a", &["unrelated::tag"]);
        let other = add_card(&mut col, "b", &["unrelated::tag"]);

        let out = col.bury_concept_siblings(untagged).unwrap();

        assert_eq!(out.output, 0, "a card with no concept tag buries nothing");
        assert_eq!(queue_of(&mut col, other), CardQueue::New);
    }

    #[test]
    fn count_matches_number_of_buried_siblings() {
        let mut col = Collection::new();
        let studied = add_card(&mut col, "a", &["rpce::concept::7"]);
        let s1 = add_card(&mut col, "b", &["rpce::concept::7"]);
        let s2 = add_card(&mut col, "c", &["rpce::concept::7"]);
        // A card of another concept should stay put.
        let noise = add_card(&mut col, "d", &["rpce::concept::8"]);

        let out = col.bury_concept_siblings(studied).unwrap();

        assert_eq!(out.output, 2, "both same-concept siblings are counted");
        assert_eq!(queue_of(&mut col, s1), CardQueue::SchedBuried);
        assert_eq!(queue_of(&mut col, s2), CardQueue::SchedBuried);
        assert_eq!(queue_of(&mut col, noise), CardQueue::New);
    }

    #[test]
    fn already_buried_siblings_are_not_double_counted() {
        let mut col = Collection::new();
        let studied = add_card(&mut col, "a", &["rpce::concept::5"]);
        let s1 = add_card(&mut col, "b", &["rpce::concept::5"]);
        let s2 = add_card(&mut col, "c", &["rpce::concept::5"]);

        // First study buries both siblings.
        let first = col.bury_concept_siblings(studied).unwrap();
        assert_eq!(first.output, 2);

        // Studying again must not re-bury the already-buried siblings.
        let second = col.bury_concept_siblings(studied).unwrap();
        assert_eq!(second.output, 0, "already-buried cards are not re-buried");
        assert_eq!(queue_of(&mut col, s1), CardQueue::SchedBuried);
        assert_eq!(queue_of(&mut col, s2), CardQueue::SchedBuried);
    }

    #[test]
    fn undo_restores_buried_siblings() {
        let mut col = Collection::new();
        let studied = add_card(&mut col, "a", &["rpce::concept::42"]);
        let sibling = add_card(&mut col, "b", &["rpce::concept::42"]);

        let out = col.bury_concept_siblings(studied).unwrap();
        assert_eq!(out.output, 1);
        assert_eq!(queue_of(&mut col, sibling), CardQueue::SchedBuried);
        // sanity: exactly one buried card in the collection
        assert_eq!(
            col.search_cards(StateKind::Buried, SortMode::NoOrder)
                .unwrap()
                .len(),
            1
        );

        // Undo must revert the bury, proving the operation is undoable.
        col.undo().unwrap();
        assert_eq!(
            queue_of(&mut col, sibling),
            CardQueue::New,
            "undo returns the sibling to the queue"
        );
        assert_eq!(
            col.search_cards(StateKind::Buried, SortMode::NoOrder)
                .unwrap()
                .len(),
            0,
            "no cards remain buried after undo"
        );
    }

    #[test]
    fn concept_of_tags_extracts_id_and_ignores_others() {
        assert_eq!(
            concept_of_tags(&["rpce::concept::42".to_string()]),
            Some("42".to_string())
        );
        assert_eq!(
            concept_of_tags(&[
                "rpce::fmt::cloze".to_string(),
                "rpce::concept::abc".to_string(),
            ]),
            Some("abc".to_string()),
            "the concept id may be non-numeric"
        );
        assert_eq!(concept_of_tags(&["unrelated".to_string()]), None);
        // A bare prefix with no id is not a concept.
        assert_eq!(concept_of_tags(&["rpce::concept::".to_string()]), None);
    }
}
