// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

package com.rpce.speedrun

/**
 * Loads the shared Anki/RPCE Rust engine (libspeedrun_jni.so, built with
 * `cargo ndk ... -p speedrun_jni`) and exposes native calls into it. This is
 * the "one engine" the desktop app also uses — not a reimplementation.
 */
object NativeBridge {
    init {
        System.loadLibrary("speedrun_jni")
    }

    /** Returns engine info (Anki version + build hash) from the native engine. */
    external fun engineInfo(): String
}
