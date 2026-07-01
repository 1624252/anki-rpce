// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

package com.rpce.speedrun

/**
 * Loads the shared Anki/RPCE Rust engine (libspeedrun_jni.so) and exposes it.
 * Every call drives the same protobuf backend the desktop uses — the phone
 * shares the engine, it does not reimplement the scheduler (spec §3).
 *
 * All methods return a JSON string; callers parse it with [org.json.JSONObject].
 * Errors come back as {"ok":false,"error":"..."}.
 */
object NativeBridge {
    init {
        System.loadLibrary("speedrun_jni")
    }

    /** Engine version + build hash (proves the shared engine runs on device). */
    external fun engineInfo(): String

    /** Open (or create) the collection at [path]. */
    external fun openCollection(path: String): String

    /** Import a .apkg (used to seed the RPCE deck on first run). */
    external fun importPackage(path: String): String

    /** Select a deck by name so the review queue is scoped to it. */
    external fun selectDeck(name: String): String

    /** {new, learning, review} counts for the current deck. */
    external fun deckCounts(): String

    /** Next due card rendered to HTML: {hasCard, cardId, question, answer, css}. */
    external fun nextCard(): String

    /** Answer the current card. rating: 0=Again 1=Hard 2=Good 3=Easy. */
    external fun answerCard(rating: Int): String

    /** Log in to a sync server; returns {hkey, endpoint}. */
    external fun syncLogin(username: String, password: String, endpoint: String): String

    /** Normal two-way sync; reports {required} if a full sync is needed. */
    external fun syncCollection(hkey: String, endpoint: String): String

    /** Full upload/download (first join or after a schema change). */
    external fun fullSync(hkey: String, endpoint: String, upload: Boolean): String
}
