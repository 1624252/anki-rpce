// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

package com.rpce.speedrun

import android.graphics.Color
import android.os.Bundle
import android.webkit.WebView
import androidx.appcompat.app.AppCompatActivity

/**
 * RPCE home screen. Renders the same deep-blue themed banner as the desktop app
 * (assets/home.html) in a WebView so the two apps look like one product. The
 * shared Rust engine is loaded via [NativeBridge]; its version/build hash proves
 * the "one engine" runs on device (spec §3). Live scores arrive with the
 * review/sync UI.
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val engine = try {
            NativeBridge.engineInfo()
        } catch (e: Throwable) {
            "engine unavailable: ${e.message}"
        }

        val html = assets.open("home.html").bufferedReader().use { it.readText() }
            .replace("{{ENGINE}}", engine)

        val web = WebView(this)
        // Match the page background so there's no white flash before load.
        web.setBackgroundColor(Color.parseColor("#050c1c"))
        web.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "utf-8", null)
        setContentView(web)
    }
}
