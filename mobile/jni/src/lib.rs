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
                serde_json::json!({
                    "ok": true,
                    "hasCard": true,
                    "cardId": card_id,
                    "question": nodes_to_html(&r.question_nodes),
                    "answer": nodes_to_html(&r.answer_nodes),
                    "css": r.css,
                })
                .to_string(),
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
