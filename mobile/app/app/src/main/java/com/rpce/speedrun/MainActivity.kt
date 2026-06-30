// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

package com.rpce.speedrun

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Minimal companion entry point: proves the shared engine loads and runs on the
 * device by calling into the native bridge. The full review/sync UI is built on
 * top of this (reusing AnkiDroid's review surfaces over the same engine).
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val view = TextView(this)
        view.textSize = 16f
        view.setPadding(48, 96, 48, 48)
        view.text = try {
            "Speedrun for the RPCE\n\nShared engine running on device:\n" +
                NativeBridge.engineInfo()
        } catch (e: Throwable) {
            "Engine failed to load: ${e.message}"
        }
        setContentView(view)
    }
}
