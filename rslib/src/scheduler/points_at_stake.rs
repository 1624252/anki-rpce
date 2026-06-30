// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! RPCE "points-at-stake" review order.
//!
//! A credentialing exam rewards spending limited study time where it matters
//! most. This orders the *due* cards by `topic exam-weight × student weakness`
//! so the highest-value cards surface first. It is a read-only query layered on
//! top of FSRS due-selection — it never mutates the collection, so it is
//! undo-safe and cannot corrupt scheduling state.

use std::collections::HashMap;

use crate::prelude::*;
use crate::search::SortMode;

/// One due card scored by points-at-stake.
#[derive(Debug, Clone)]
pub struct PointsAtStakeEntry {
    pub card_id: CardId,
    /// `weight * weakness`; the descending sort key.
    pub points_at_stake: f64,
    /// Student weakness for this card, in (0, 1]; higher = weaker.
    pub weakness: f64,
    /// The exam weight applied to this card.
    pub weight: f64,
    /// Tag that supplied the weight, or empty if the default was used.
    pub matched_tag: String,
}

impl Collection {
    /// Return the due cards ordered by points-at-stake, highest first.
    ///
    /// `topic_weights` maps a tag (e.g. an RPCE domain tag) to its exam weight;
    /// `default_weight` is used for cards matching none. `limit` caps the
    /// result (0 = all due cards). Ties break by card id for a
    /// deterministic order.
    pub fn points_at_stake_queue(
        &mut self,
        topic_weights: &HashMap<String, f64>,
        default_weight: f64,
        limit: usize,
    ) -> Result<Vec<PointsAtStakeEntry>> {
        let cids = self.search_cards("is:due", SortMode::NoOrder)?;
        let mut entries = Vec::with_capacity(cids.len());
        for cid in cids {
            let card = self.storage.get_card(cid)?.or_not_found(cid)?;
            let note = self
                .storage
                .get_note(card.note_id)?
                .or_not_found(card.note_id)?;
            let (weight, matched_tag) = best_weight(&note.tags, topic_weights, default_weight);
            let weakness = card_weakness(&card);
            entries.push(PointsAtStakeEntry {
                card_id: cid,
                points_at_stake: weight * weakness,
                weakness,
                weight,
                matched_tag,
            });
        }
        entries.sort_by(|a, b| {
            b.points_at_stake
                .partial_cmp(&a.points_at_stake)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.card_id.0.cmp(&b.card_id.0))
        });
        if limit > 0 {
            entries.truncate(limit);
        }
        Ok(entries)
    }
}

/// Student weakness in (0, 1]: a Laplace-smoothed failure rate (more lapses per
/// review = weaker). When FSRS difficulty is known it is blended in equally,
/// since a high-difficulty card is weak even with few reviews.
fn card_weakness(card: &Card) -> f64 {
    let fail_ratio = (card.lapses as f64 + 1.0) / (card.reps as f64 + 2.0);
    match card.memory_state {
        Some(state) => 0.5 * fail_ratio + 0.5 * state.difficulty() as f64,
        None => fail_ratio,
    }
}

/// Pick the highest exam weight among the card's tags, falling back to
/// `default_weight` when no tag matches.
fn best_weight(
    tags: &[String],
    weights: &HashMap<String, f64>,
    default_weight: f64,
) -> (f64, String) {
    let mut best: Option<(f64, &String)> = None;
    for tag in tags {
        if let Some(&w) = weights.get(tag) {
            let better = match best {
                Some((bw, _)) => w > bw,
                None => true,
            };
            if better {
                best = Some((w, tag));
            }
        }
    }
    match best {
        Some((w, tag)) => (w, tag.clone()),
        None => (default_weight, String::new()),
    }
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use crate::prelude::*;
    use crate::scheduler::points_at_stake::card_weakness;
    use crate::tests::NoteAdder;

    /// Adds a card, tags its note, and makes it a review card due today with
    /// the given review history so it is gathered by `is:due`.
    fn add_due_card(
        col: &mut Collection,
        front: &str,
        tags: &[&str],
        reps: u32,
        lapses: u32,
    ) -> CardId {
        let mut note = NoteAdder::basic(col).fields(&[front, ""]).note();
        note.tags = tags.iter().map(|t| t.to_string()).collect();
        col.add_note(&mut note, DeckId(1)).unwrap();
        let cid = col.storage.card_ids_of_notes(&[note.id]).unwrap()[0];

        let mut card = col.storage.get_card(cid).unwrap().unwrap();
        card.ctype = crate::card::CardType::Review;
        card.queue = crate::card::CardQueue::Review;
        card.due = 0; // due today on a fresh collection (days_elapsed == 0)
        card.interval = 1;
        card.reps = reps;
        card.lapses = lapses;
        col.storage.update_card(&card).unwrap();
        cid
    }

    fn weights(pairs: &[(&str, f64)]) -> HashMap<String, f64> {
        pairs.iter().map(|(t, w)| (t.to_string(), *w)).collect()
    }

    #[test]
    fn orders_by_weight_times_weakness_highest_first() {
        let mut col = Collection::new();
        // Same weakness (no history), different domain weights => weight decides.
        let low = add_due_card(&mut col, "low", &["domain::1"], 0, 0);
        let high = add_due_card(&mut col, "high", &["domain::2"], 0, 0);

        let w = weights(&[("domain::1", 0.1), ("domain::2", 0.9)]);
        let queue = col.points_at_stake_queue(&w, 0.0, 0).unwrap();

        assert_eq!(queue.len(), 2);
        assert_eq!(queue[0].card_id, high, "higher-weight domain comes first");
        assert_eq!(queue[1].card_id, low);
        assert!(queue[0].points_at_stake > queue[1].points_at_stake);
        assert_eq!(queue[0].matched_tag, "domain::2");
    }

    #[test]
    fn weakness_breaks_ties_within_equal_weight() {
        let mut col = Collection::new();
        // Equal weight; the weaker card (more lapses per rep) must rank higher.
        let strong = add_due_card(&mut col, "strong", &["domain::1"], 10, 0);
        let weak = add_due_card(&mut col, "weak", &["domain::1"], 10, 8);

        let w = weights(&[("domain::1", 0.5)]);
        let queue = col.points_at_stake_queue(&w, 0.0, 0).unwrap();

        assert_eq!(queue[0].card_id, weak, "weaker card is higher value");
        assert_eq!(queue[1].card_id, strong);
    }

    #[test]
    fn default_weight_used_when_no_tag_matches() {
        let mut col = Collection::new();
        let tagged = add_due_card(&mut col, "tagged", &["domain::1"], 0, 0);
        let untagged = add_due_card(&mut col, "untagged", &["unrelated"], 0, 0);

        // domain::1 weight (0.8) beats the default (0.2), so tagged ranks first.
        let w = weights(&[("domain::1", 0.8)]);
        let queue = col.points_at_stake_queue(&w, 0.2, 0).unwrap();

        assert_eq!(queue[0].card_id, tagged);
        assert_eq!(queue[1].card_id, untagged);
        assert_eq!(
            queue[1].matched_tag, "",
            "default weight has no matched tag"
        );
        assert!((queue[1].weight - 0.2).abs() < f64::EPSILON);
    }

    #[test]
    fn limit_truncates_to_highest_value_cards() {
        let mut col = Collection::new();
        add_due_card(&mut col, "a", &["domain::1"], 0, 0);
        let mid = add_due_card(&mut col, "b", &["domain::2"], 0, 0);
        let top = add_due_card(&mut col, "c", &["domain::3"], 0, 0);

        let w = weights(&[("domain::1", 0.1), ("domain::2", 0.5), ("domain::3", 0.9)]);
        let queue = col.points_at_stake_queue(&w, 0.0, 2).unwrap();

        assert_eq!(queue.len(), 2, "limit caps the queue length");
        assert_eq!(queue[0].card_id, top);
        assert_eq!(queue[1].card_id, mid);
    }

    #[test]
    fn weakness_increases_with_lapses_and_is_bounded() {
        let strong = Card {
            reps: 10,
            lapses: 0,
            ..Default::default()
        };
        let weak = Card {
            reps: 10,
            lapses: 9,
            ..Default::default()
        };

        let ws = card_weakness(&strong);
        let ww = card_weakness(&weak);
        assert!(ww > ws, "more lapses => weaker");
        assert!(ws > 0.0 && ww <= 1.0, "weakness stays within (0, 1]");
    }

    #[test]
    fn excludes_cards_that_are_not_due() {
        let mut col = Collection::new();
        let due = add_due_card(&mut col, "due", &["domain::1"], 0, 0);
        // A brand-new (not-yet-due) card should not appear in the queue.
        let mut note = NoteAdder::basic(&mut col).fields(&["new", ""]).note();
        note.tags = vec!["domain::1".to_string()];
        col.add_note(&mut note, DeckId(1)).unwrap();

        let w = weights(&[("domain::1", 0.5)]);
        let queue = col.points_at_stake_queue(&w, 0.0, 0).unwrap();

        assert_eq!(queue.len(), 1, "only the due card is returned");
        assert_eq!(queue[0].card_id, due);
    }
}
