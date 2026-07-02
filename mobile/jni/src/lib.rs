// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! JNI bridge for the Android companion.
//!
//! Runs the **shared** Anki Rust engine (`anki` crate, including the RPCE
//! points-at-stake queue) on-device and exposes it to Kotlin. It mirrors the
//! desktop/PyO3 path: hold one `Backend` and drive it through
//! `run_service_method(service, method, protobuf_bytes)` — the exact same
//! protobuf API the desktop uses — so the phone shares the engine rather than
//! reimplementing the scheduler (spec §3).
//!
//! Kotlin sees a small JSON API (open/import/select/review/answer/sync); all
//! protobuf handling stays here in Rust. Build for a device/emulator ABI with:
//!     cargo ndk -t x86_64 -t arm64-v8a -o <jniLibs> build -p speedrun_jni --release

use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use anki::backend::{init_backend, Backend};
use anki_proto::scheduler::queued_cards::QueuedCard;
use jni::objects::{JClass, JString};
use jni::sys::jstring;
use jni::JNIEnv;
use prost::Message;

// (service, method) indices from out/pylib/anki/_backend_generated.py.
const SVC_SYNC: u32 = 1;
const SVC_COLLECTION: u32 = 3;
const SVC_DECKS: u32 = 7;
const SVC_SCHEDULER: u32 = 13;
const SVC_CARD_RENDERING: u32 = 27;
const SVC_IMPORT_EXPORT: u32 = 39;

static BACKEND: Mutex<Option<Backend>> = Mutex::new(None);
// The card currently shown by `nextCard`, cached so `answerCard` can build the
// CardAnswer from its precomputed scheduling states without a round-trip.
static LAST_CARD: Mutex<Option<QueuedCard>> = Mutex::new(None);

fn now_millis() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// Run a protobuf service method against the shared backend.
fn run(service: u32, method: u32, input: Vec<u8>) -> Result<Vec<u8>, String> {
    let guard = BACKEND.lock().map_err(|_| "backend lock poisoned".to_string())?;
    let backend = guard.as_ref().ok_or_else(|| "collection not open".to_string())?;
    backend
        .run_service_method(service, method, &input)
        .map_err(|err_bytes| {
            // Decode the protobuf BackendError for a human-readable message.
            anki_proto::backend::BackendError::decode(err_bytes.as_slice())
                .map(|e| e.message)
                .unwrap_or_else(|_| "backend error".to_string())
        })
}

fn jstr(env: &mut JNIEnv, s: &JString) -> String {
    env.get_string(s).map(|s| s.into()).unwrap_or_default()
}

fn reply(env: JNIEnv, json: String) -> jstring {
    env.new_string(json)
        .map(|s| s.into_raw())
        .unwrap_or(std::ptr::null_mut())
}

fn ok() -> String {
    "{\"ok\":true}".to_string()
}

fn err(msg: &str) -> String {
    serde_json::json!({ "ok": false, "error": msg }).to_string()
}

/// Concatenate rendered template nodes into an HTML string.
fn nodes_to_html(nodes: &[anki_proto::card_rendering::RenderedTemplateNode]) -> String {
    use anki_proto::card_rendering::rendered_template_node::Value;
    let mut out = String::new();
    for node in nodes {
        match &node.value {
            Some(Value::Text(t)) => out.push_str(t),
            Some(Value::Replacement(r)) => out.push_str(&r.current_text),
            None => {}
        }
    }
    out
}

#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_engineInfo(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    let info = format!(
        "Speedrun shared engine ready — anki {} ({})",
        anki::version::version(),
        anki::version::buildhash(),
    );
    reply(env, info)
}

/// Open (or create) the collection at `path`. Initialises the backend once.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_openCollection(
    mut env: JNIEnv,
    _class: JClass,
    path: JString,
) -> jstring {
    let path = jstr(&mut env, &path);
    // Ensure the backend exists.
    {
        let mut guard = match BACKEND.lock() {
            Ok(g) => g,
            Err(_) => return reply(env, err("backend lock poisoned")),
        };
        if guard.is_none() {
            let init = anki_proto::backend::BackendInit {
                preferred_langs: vec!["en".to_string()],
                server: false,
                ..Default::default()
            };
            match init_backend(&init.encode_to_vec()) {
                Ok(b) => *guard = Some(b),
                Err(e) => return reply(env, err(&e)),
            }
        }
    }
    let req = anki_proto::collection::OpenCollectionRequest {
        collection_path: path.clone(),
        media_folder_path: format!("{path}.media"),
        media_db_path: format!("{path}.mdb"),
        ..Default::default()
    };
    match run(SVC_COLLECTION, 0, req.encode_to_vec()) {
        Ok(_) => reply(env, ok()),
        Err(e) => reply(env, err(&e)),
    }
}

/// Import a bundled .apkg so the phone has a real, reviewable deck offline.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_importPackage(
    mut env: JNIEnv,
    _class: JClass,
    path: JString,
) -> jstring {
    let path = jstr(&mut env, &path);
    let req = anki_proto::import_export::ImportAnkiPackageRequest {
        package_path: path,
        options: Some(anki_proto::import_export::ImportAnkiPackageOptions {
            merge_notetypes: true,
            with_scheduling: true,
            with_deck_configs: true,
            ..Default::default()
        }),
    };
    match run(SVC_IMPORT_EXPORT, 2, req.encode_to_vec()) {
        Ok(_) => reply(env, ok()),
        Err(e) => reply(env, err(&e)),
    }
}

/// Select a deck by name so the review queue is scoped to it. Returns the id.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_selectDeck(
    mut env: JNIEnv,
    _class: JClass,
    name: JString,
) -> jstring {
    let name = jstr(&mut env, &name);
    let req = anki_proto::generic::String { val: name };
    let did = match run(SVC_DECKS, 7, req.encode_to_vec()) {
        Ok(bytes) => match anki_proto::decks::DeckId::decode(bytes.as_slice()) {
            Ok(d) => d.did,
            Err(_) => 0,
        },
        Err(e) => return reply(env, err(&e)),
    };
    if did == 0 {
        return reply(env, serde_json::json!({ "ok": true, "found": false }).to_string());
    }
    let set = anki_proto::decks::DeckId { did };
    match run(SVC_DECKS, 22, set.encode_to_vec()) {
        Ok(_) => reply(
            env,
            serde_json::json!({ "ok": true, "found": true, "deckId": did }).to_string(),
        ),
        Err(e) => reply(env, err(&e)),
    }
}

/// Due/new/learning counts for the current deck's queue.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_deckCounts(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    let req = anki_proto::scheduler::GetQueuedCardsRequest {
        fetch_limit: 1,
        intraday_learning_only: false,
    };
    match run(SVC_SCHEDULER, 3, req.encode_to_vec()) {
        Ok(bytes) => match anki_proto::scheduler::QueuedCards::decode(bytes.as_slice()) {
            Ok(q) => reply(
                env,
                serde_json::json!({
                    "ok": true,
                    "new": q.new_count,
                    "learning": q.learning_count,
                    "review": q.review_count,
                })
                .to_string(),
            ),
            Err(_) => reply(env, err("decode counts failed")),
        },
        Err(e) => reply(env, err(&e)),
    }
}

/// Fetch and render the next due card. Caches it for `answerCard`.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_nextCard(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    let req = anki_proto::scheduler::GetQueuedCardsRequest {
        fetch_limit: 1,
        intraday_learning_only: false,
    };
    let queued = match run(SVC_SCHEDULER, 3, req.encode_to_vec()) {
        Ok(bytes) => match anki_proto::scheduler::QueuedCards::decode(bytes.as_slice()) {
            Ok(q) => q,
            Err(_) => return reply(env, err("decode queue failed")),
        },
        Err(e) => return reply(env, err(&e)),
    };
    let Some(qc) = queued.cards.into_iter().next() else {
        if let Ok(mut last) = LAST_CARD.lock() {
            *last = None;
        }
        return reply(env, serde_json::json!({ "ok": true, "hasCard": false }).to_string());
    };
    let card_id = qc.card.as_ref().map(|c| c.id).unwrap_or(0);
    // Cache for answering.
    if let Ok(mut last) = LAST_CARD.lock() {
        *last = Some(qc);
    }
    let render_req = anki_proto::card_rendering::RenderExistingCardRequest {
        card_id,
        browser: false,
        partial_render: false,
    };
    match run(SVC_CARD_RENDERING, 6, render_req.encode_to_vec()) {
        Ok(bytes) => match anki_proto::card_rendering::RenderCardResponse::decode(bytes.as_slice()) {
            Ok(r) => reply(
                env,
                {
                    let (concept, domain) = card_concept_domain(card_id);
                    serde_json::json!({
                        "ok": true,
                        "hasCard": true,
                        "cardId": card_id,
                        "question": nodes_to_html(&r.question_nodes),
                        "answer": nodes_to_html(&r.answer_nodes),
                        "css": r.css,
                        "concept": concept,
                        "domain": domain,
                    })
                    .to_string()
                },
            ),
            Err(_) => reply(env, err("decode render failed")),
        },
        Err(e) => reply(env, err(&e)),
    }
}

/// Answer the cached card. rating: 0=Again 1=Hard 2=Good 3=Easy.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_answerCard(
    env: JNIEnv,
    _class: JClass,
    rating: i32,
) -> jstring {
    let qc = match LAST_CARD.lock() {
        Ok(g) => g.clone(),
        Err(_) => return reply(env, err("card lock poisoned")),
    };
    let Some(qc) = qc else {
        return reply(env, err("no current card"));
    };
    let card_id = qc.card.as_ref().map(|c| c.id).unwrap_or(0);
    let states = match qc.states {
        Some(s) => s,
        None => return reply(env, err("card has no scheduling states")),
    };
    let new_state = match rating {
        0 => states.again,
        1 => states.hard,
        3 => states.easy,
        _ => states.good,
    };
    let answer = anki_proto::scheduler::CardAnswer {
        card_id,
        current_state: states.current,
        new_state,
        rating,
        answered_at_millis: now_millis(),
        milliseconds_taken: 0,
    };
    match run(SVC_SCHEDULER, 5, answer.encode_to_vec()) {
        Ok(_) => {
            if let Ok(mut last) = LAST_CARD.lock() {
                *last = None;
            }
            reply(env, ok())
        }
        Err(e) => reply(env, err(&e)),
    }
}

/// Log in to a sync server; returns the auth hkey to reuse for syncing.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_syncLogin(
    mut env: JNIEnv,
    _class: JClass,
    username: JString,
    password: JString,
    endpoint: JString,
) -> jstring {
    let username = jstr(&mut env, &username);
    let password = jstr(&mut env, &password);
    let endpoint = jstr(&mut env, &endpoint);
    let req = anki_proto::sync::SyncLoginRequest {
        username,
        password,
        endpoint: if endpoint.is_empty() { None } else { Some(endpoint) },
    };
    match run(SVC_SYNC, 3, req.encode_to_vec()) {
        Ok(bytes) => match anki_proto::sync::SyncAuth::decode(bytes.as_slice()) {
            Ok(auth) => reply(
                env,
                serde_json::json!({
                    "ok": true,
                    "hkey": auth.hkey,
                    "endpoint": auth.endpoint.unwrap_or_default(),
                })
                .to_string(),
            ),
            Err(_) => reply(env, err("decode auth failed")),
        },
        Err(e) => reply(env, err(&e)),
    }
}

/// Normal two-way collection sync. Reports whether a full sync is required.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_syncCollection(
    mut env: JNIEnv,
    _class: JClass,
    hkey: JString,
    endpoint: JString,
) -> jstring {
    let hkey = jstr(&mut env, &hkey);
    let endpoint = jstr(&mut env, &endpoint);
    let auth = anki_proto::sync::SyncAuth {
        hkey,
        endpoint: if endpoint.is_empty() { None } else { Some(endpoint) },
        io_timeout_secs: None,
    };
    let req = anki_proto::sync::SyncCollectionRequest {
        auth: Some(auth),
        sync_media: false,
    };
    match run(SVC_SYNC, 5, req.encode_to_vec()) {
        Ok(bytes) => match anki_proto::sync::SyncCollectionResponse::decode(bytes.as_slice()) {
            Ok(r) => reply(
                env,
                serde_json::json!({
                    "ok": true,
                    "required": r.required,
                    "hostNumber": r.host_number,
                    "serverMessage": r.server_message,
                })
                .to_string(),
            ),
            Err(_) => reply(env, err("decode sync response failed")),
        },
        Err(e) => reply(env, err(&e)),
    }
}

/// Full upload or download, needed the first time a device joins (or after a
/// schema change). `upload=true` pushes this device's collection to the server.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_fullSync(
    mut env: JNIEnv,
    _class: JClass,
    hkey: JString,
    endpoint: JString,
    upload: bool,
) -> jstring {
    let hkey = jstr(&mut env, &hkey);
    let endpoint = jstr(&mut env, &endpoint);
    let auth = anki_proto::sync::SyncAuth {
        hkey,
        endpoint: if endpoint.is_empty() { None } else { Some(endpoint) },
        io_timeout_secs: None,
    };
    let req = anki_proto::sync::FullUploadOrDownloadRequest {
        auth: Some(auth),
        upload,
        server_usn: None,
    };
    match run(SVC_SYNC, 6, req.encode_to_vec()) {
        Ok(_) => reply(env, ok()),
        Err(e) => reply(env, err(&e)),
    }
}

// ---------------------------------------------------------------------------
// The three RPCE scores (memory / performance / readiness) + give-up rule.
// Ported from pylib/anki/rpce/scores.py so the phone shows the SAME honest
// payload as the desktop, computed on-device from the shared collection.
// ---------------------------------------------------------------------------

/// The seven Performance-Expectation domains (code, name). Weights default to an
/// equal 1/7 split, matching the desktop default (anki.rpce.DOMAINS).
const DOMAINS: [(i64, &str); 7] = [
    (1, "Motions in General and Main Motions"),
    (2, "Subsidiary and Privileged Motions"),
    (3, "Incidental Motions and Motions that Bring a Question Again Before the Assembly"),
    (4, "Organization and Conduct of Meetings"),
    (5, "Voting, Nominations, and Elections"),
    (6, "Being and Serving as a Professional Parliamentarian and Teaching Parliamentary Procedure"),
    (7, "Boards and Committees, and Writing and Interpreting Bylaws"),
];

const MIN_REVIEWS: i64 = 200;
const MIN_COVERAGE: f64 = 0.5;
const MIN_SCENARIOS: i64 = 100;

/// Run a read-only SQL query through the shared backend's db command.
fn db_query(sql: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
    let payload = serde_json::json!({
        "kind": "query", "sql": sql, "args": args, "first_row_only": false,
    });
    let bytes = serde_json::to_vec(&payload).map_err(|e| e.to_string())?;
    let guard = BACKEND.lock().map_err(|_| "backend lock poisoned".to_string())?;
    let backend = guard.as_ref().ok_or_else(|| "collection not open".to_string())?;
    let out = backend
        .run_db_command_bytes(&bytes)
        .map_err(|e| String::from_utf8_lossy(&e).into_owned())?;
    serde_json::from_slice(&out).map_err(|e| e.to_string())
}

fn recall_estimate(reps: i64, lapses: i64) -> f64 {
    (reps - lapses + 1) as f64 / (reps + 2) as f64
}

/// Recall estimates for cards matching an optional tag pattern (reps > 0).
fn recalls(tag_like: Option<&str>) -> Vec<f64> {
    let (sql, args) = match tag_like {
        Some(pat) => (
            "SELECT c.reps, c.lapses FROM cards c JOIN notes n ON c.nid = n.id \
             WHERE c.reps > 0 AND n.tags LIKE ?1"
                .to_string(),
            serde_json::json!([pat]),
        ),
        None => (
            "SELECT reps, lapses FROM cards WHERE reps > 0".to_string(),
            serde_json::json!([]),
        ),
    };
    let rows = match db_query(&sql, args) {
        Ok(v) => v,
        Err(_) => return vec![],
    };
    rows.as_array()
        .map(|rows| {
            rows.iter()
                .filter_map(|r| {
                    let a = r.as_array()?;
                    let reps = a.first()?.as_i64()?;
                    let lapses = a.get(1)?.as_i64()?;
                    Some(recall_estimate(reps, lapses))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn mean(v: &[f64]) -> f64 {
    if v.is_empty() {
        0.0
    } else {
        v.iter().sum::<f64>() / v.len() as f64
    }
}

fn pstdev(v: &[f64]) -> f64 {
    if v.len() < 2 {
        return 0.0;
    }
    let m = mean(v);
    (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / v.len() as f64).sqrt()
}

fn confidence_for_n(n: usize) -> &'static str {
    if n >= 200 {
        "high"
    } else if n >= 50 {
        "medium"
    } else {
        "low"
    }
}

/// Mean with a 95% interval and sample-size confidence (scores.py `_range_from`).
fn range_from(v: &[f64]) -> (Option<f64>, Option<f64>, Option<f64>, &'static str) {
    if v.is_empty() {
        // No data: abstain from a point but still show the full-uncertainty
        // range (0-100%) so memory/performance always carry a range.
        return (None, Some(0.0), Some(1.0), "abstain");
    }
    let point = mean(v);
    let n = v.len();
    let se = if n > 1 { pstdev(v) / (n as f64).sqrt() } else { 0.5 };
    let margin = 1.96 * se;
    (
        Some(point),
        Some((point - margin).max(0.0)),
        Some((point + margin).min(1.0)),
        confidence_for_n(n),
    )
}

fn domain_pattern(code: i64) -> String {
    format!("%rpce::domain::{code}%")
}

fn card_count(tag_like: &str) -> i64 {
    db_query(
        "SELECT count() FROM cards c JOIN notes n ON c.nid = n.id WHERE n.tags LIKE ?1",
        serde_json::json!([tag_like]),
    )
    .ok()
    .and_then(|v| v.as_array()?.first()?.as_array()?.first()?.as_i64())
    .unwrap_or(0)
}

fn scalar_i64(sql: &str) -> i64 {
    db_query(sql, serde_json::json!([]))
        .ok()
        .and_then(|v| v.as_array()?.first()?.as_array()?.first()?.as_i64())
        .unwrap_or(0)
}

/// The RPCE concept id + readable domain name for a card, from its note tags
/// ('rpce::concept::<id>' / 'rpce::domain::<code>'). Empty strings when unknown;
/// feeds the session-complete concept breakdown (mirrors the desktop).
fn card_concept_domain(card_id: i64) -> (String, String) {
    let tags = db_query(
        "SELECT n.tags FROM notes n JOIN cards c ON c.nid = n.id WHERE c.id = ?",
        serde_json::json!([card_id]),
    )
    .ok()
    .and_then(|v| {
        Some(
            v.as_array()?
                .first()?
                .as_array()?
                .first()?
                .as_str()?
                .to_string(),
        )
    })
    .unwrap_or_default();
    let (mut concept, mut domain) = (String::new(), String::new());
    for t in tags.split_whitespace() {
        if let Some(id) = t.strip_prefix("rpce::concept::") {
            concept = id.to_string();
        } else if let Some(code) = t.strip_prefix("rpce::domain::") {
            if let Ok(c) = code.parse::<i64>() {
                if let Some((_, name)) = DOMAINS.iter().find(|(dc, _)| *dc == c) {
                    domain = (*name).to_string();
                }
            }
        }
    }
    (concept, domain)
}

fn logistic_pass(performance: f64) -> f64 {
    let k = 12.0;
    1.0 / (1.0 + (-k * (performance - 0.8)).exp())
}

/// The whole honest readiness payload as JSON (mirrors readiness_summary).
fn scores_json() -> String {
    // Per-domain recall + coverage.
    let weight = 1.0 / DOMAINS.len() as f64; // equal default split
    let mut perf_point = 0.0;
    let mut seen_any = false;
    let mut seen = 0;
    let mut covered = 0;
    let mut best: Option<(f64, &str)> = None;
    let mut coverage_arr = Vec::new();
    for (code, name) in DOMAINS {
        let rc = recalls(Some(&domain_pattern(code)));
        let cards = card_count(&domain_pattern(code));
        if cards > 0 {
            covered += 1;
        }
        let recall = if rc.is_empty() { None } else { Some(mean(&rc)) };
        if let Some(r) = recall {
            seen_any = true;
            seen += 1;
            perf_point += weight * r;
        }
        let gap = recall.map(|r| 1.0 - r).unwrap_or(1.0);
        let value = weight * gap;
        if best.map(|(bv, _)| value > bv).unwrap_or(true) {
            best = Some((value, name));
        }
        coverage_arr.push(serde_json::json!({ "code": code, "name": name, "cards": cards }));
    }
    let cov_pct = covered as f64 / DOMAINS.len() as f64;
    let best_next = best.map(|(_, n)| n).unwrap_or("");
    let n_domains = DOMAINS.len();

    // Reviews of cards that still exist (a re-seed can leave orphaned revlog rows;
    // excluding them keeps this in step with the performance estimate) + the
    // concrete graded-review target shown on abstaining cards.
    let reviews = scalar_i64("SELECT count() FROM revlog WHERE cid IN (SELECT id FROM cards)");
    let review_need = if reviews < MIN_REVIEWS {
        format!(
            " {} more graded reviews needed ({reviews}/{MIN_REVIEWS}).",
            MIN_REVIEWS - reviews
        )
    } else {
        String::new()
    };

    // Memory (with the main reasons behind the number, spec §4).
    let mem_recalls = recalls(None);
    let mem_n = mem_recalls.len();
    let (mem_p, mem_lo, mem_hi, mem_conf) = range_from(&mem_recalls);
    let mem_explain = if mem_n == 0 {
        format!(
            "No reviewed cards yet — study some flashcards to build a memory \
             estimate.{review_need}"
        )
    } else {
        format!(
            "Mean recall over {mem_n} reviewed card(s) using each card's recall \
             estimate. The range is a 95% interval; confidence rises with more reviews."
        )
    };

    // Performance (exam-weighted recall; unseen domains count as 0).
    let (perf_p, perf_lo, perf_hi, perf_conf, perf_explain) = if seen_any {
        let conf = if cov_pct >= 0.8 {
            "high"
        } else if cov_pct >= 0.5 {
            "medium"
        } else {
            "low"
        };
        let margin = 0.1 + 0.4 * (1.0 - cov_pct);
        let explain = format!(
            "Exam-weighted recall across the {n_domains} domains; {seen}/{n_domains} \
             have review history and unseen domains count as 0 (so incomplete coverage \
             lowers the score). Weakest area: {best_next}. The range widens when \
             coverage is low ({:.0}% covered).",
            cov_pct * 100.0
        );
        (
            Some(perf_point),
            Some((perf_point - margin).max(0.0)),
            Some((perf_point + margin).min(1.0)),
            conf,
            explain,
        )
    } else {
        (
            None,
            Some(0.0),  // full-uncertainty abstain range (0-100%)
            Some(1.0),
            "abstain",
            format!(
                "No domain has review history yet — this bridges memory to new \
                 exam-style questions once you have practised.{review_need}"
            ),
        )
    };

    let scenarios = scalar_i64(
        "SELECT CAST(val AS INTEGER) FROM config WHERE key = 'rpce:graded_scenarios'",
    );

    // Readiness per section with the give-up rule.
    let section = |needs_scenarios: bool| -> serde_json::Value {
        let mut missing: Vec<String> = Vec::new();
        if reviews < MIN_REVIEWS {
            missing.push(format!(
                "{} more graded reviews needed ({reviews}/{MIN_REVIEWS})",
                MIN_REVIEWS - reviews
            ));
        }
        if cov_pct < MIN_COVERAGE {
            missing.push(format!(
                "domain coverage {:.0}% of {:.0}% needed",
                cov_pct * 100.0,
                MIN_COVERAGE * 100.0
            ));
        }
        if needs_scenarios && scenarios < MIN_SCENARIOS {
            missing.push(format!(
                "{} more graded scenarios needed ({scenarios}/{MIN_SCENARIOS})",
                MIN_SCENARIOS - scenarios
            ));
        }
        if !missing.is_empty() {
            return serde_json::json!({
                "abstained": true,
                "confidence": "abstain",
                "low": 0.0,  // full-uncertainty range so every score shows one
                "high": 1.0,
                "evidence": format!("Not enough data: {}", missing.join("; ")),
            });
        }
        // The review/coverage gates can pass while performance has no recall
        // history to score from (they measure different things) — abstain
        // rather than report a bogus 0% pass probability (mirrors desktop).
        let p = match perf_p {
            Some(p) => p,
            None => {
                return serde_json::json!({
                    "abstained": true,
                    "confidence": "abstain",
                    "low": 0.0,  // full-uncertainty range so every score shows one
                    "high": 1.0,
                    "evidence": "Not enough performance data yet — practise more to score.",
                });
            }
        };
        let scen_note = if needs_scenarios {
            format!(", {scenarios} graded scenarios")
        } else {
            String::new()
        };
        serde_json::json!({
            "abstained": false,
            "pPass": logistic_pass(p),
            "low": logistic_pass(perf_lo.unwrap_or(p)),
            "high": logistic_pass(perf_hi.unwrap_or(p)),
            "confidence": perf_conf,
            "evidence": format!(
                "Maps a {:.0}% performance estimate through the 80% section bar to a \
                 pass probability. Evidence: {reviews} reviews across {:.0}% of \
                 domains{scen_note}. Focus next on {best_next}.",
                p * 100.0,
                cov_pct * 100.0
            ),
        })
    };

    serde_json::json!({
        "ok": true,
        "memory": { "point": mem_p, "low": mem_lo, "high": mem_hi, "confidence": mem_conf, "explanation": mem_explain },
        "performance": { "point": perf_p, "low": perf_lo, "high": perf_hi, "confidence": perf_conf, "explanation": perf_explain },
        "sectionI": section(false),
        "sectionII": section(true),
        "coveragePct": cov_pct,
        "reviews": reviews,
        "scenarios": scenarios,
        "bestNext": best_next,
        "coverage": coverage_arr,
    })
    .to_string()
}

/// Compute the three RPCE scores on-device from the shared collection.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_scores(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    reply(env, scores_json())
}

/// Increment the graded-scenario counter (Section II) via the syncing config,
/// mirroring desktop `scores.record_scenario`. Feeds the give-up rule.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_recordScenario(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    const KEY: &str = "rpce:graded_scenarios";
    // Read current count (missing key -> 0).
    let current = {
        let req = anki_proto::generic::String { val: KEY.to_string() };
        match run(9, 0, req.encode_to_vec()) {
            Ok(bytes) => anki_proto::generic::Json::decode(bytes.as_slice())
                .ok()
                .and_then(|j| serde_json::from_slice::<i64>(&j.json).ok())
                .unwrap_or(0),
            Err(_) => 0, // key not set yet
        }
    };
    let next = current + 1;
    let req = anki_proto::config::SetConfigJsonRequest {
        key: KEY.to_string(),
        value_json: next.to_string().into_bytes(),
        undoable: false,
    };
    match run(9, 1, req.encode_to_vec()) {
        Ok(_) => reply(env, serde_json::json!({ "ok": true, "count": next }).to_string()),
        Err(e) => reply(env, err(&e)),
    }
}

/// Read an integer config value (missing key -> 0), via the syncing config.
fn config_int(key: &str) -> i64 {
    let req = anki_proto::generic::String { val: key.to_string() };
    match run(9, 0, req.encode_to_vec()) {
        Ok(bytes) => anki_proto::generic::Json::decode(bytes.as_slice())
            .ok()
            .and_then(|j| serde_json::from_slice::<i64>(&j.json).ok())
            .unwrap_or(0),
        Err(_) => 0,
    }
}

/// Increment an integer config counter by 1 and persist it via the SYNCING
/// config, so counts (e.g. Section II answers graded) combine across devices.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_incrConfig(
    mut env: JNIEnv,
    _class: JClass,
    key: JString,
) -> jstring {
    let key = jstr(&mut env, &key);
    let next = config_int(&key) + 1;
    let req = anki_proto::config::SetConfigJsonRequest {
        key,
        value_json: next.to_string().into_bytes(),
        undoable: false,
    };
    match run(9, 1, req.encode_to_vec()) {
        Ok(_) => reply(env, serde_json::json!({ "ok": true, "count": next }).to_string()),
        Err(e) => reply(env, err(&e)),
    }
}

/// Read an integer config value (for display); returns {ok, value}.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_configInt(
    mut env: JNIEnv,
    _class: JClass,
    key: JString,
) -> jstring {
    let key = jstr(&mut env, &key);
    reply(env, serde_json::json!({ "ok": true, "value": config_int(&key) }).to_string())
}

/// Ensure the RPCE deck has NO daily new-card cap and keeps the add-order.
/// The apkg import maps the deck to the Default deck config (Anki's 20-new/day
/// limit + template order), so without this the same ~20 cards recycle every
/// session. Idempotent — safe to call on every launch. Sets the Default config
/// (the deck the import assigns) to perDay 9999 + NO_SORT.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_configureDeck(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    // DeckConfig service = 11: get legacy = method 3, add/update legacy = 0.
    let getreq = anki_proto::deck_config::DeckConfigId { dcid: 1 };
    let json = match run(11, 3, getreq.encode_to_vec()) {
        Ok(b) => match anki_proto::generic::Json::decode(b.as_slice()) {
            Ok(j) => j.json,
            Err(_) => return reply(env, err("decode deck config")),
        },
        Err(e) => return reply(env, err(&e)),
    };
    let mut v: serde_json::Value = match serde_json::from_slice(&json) {
        Ok(v) => v,
        Err(_) => return reply(env, err("parse deck config")),
    };
    v["new"]["perDay"] = serde_json::json!(9999);
    v["rev"]["perDay"] = serde_json::json!(9999);
    v["newSortOrder"] = serde_json::json!(1); // NEW_CARD_SORT_ORDER_NO_SORT
    let out = match serde_json::to_vec(&v) {
        Ok(b) => b,
        Err(_) => return reply(env, err("encode deck config")),
    };
    match run(11, 0, anki_proto::generic::Json { json: out }.encode_to_vec()) {
        Ok(_) => reply(env, ok()),
        Err(e) => reply(env, err(&e)),
    }
}

/// Sanity self-check callable from host tests: confirms engine symbols link.
pub fn engine_info() -> String {
    format!("anki {} ({})", anki::version::version(), anki::version::buildhash())
}

#[cfg(test)]
mod tests {
    use super::engine_info;

    #[test]
    fn engine_info_reports_version() {
        assert!(engine_info().starts_with("anki "));
    }
}
