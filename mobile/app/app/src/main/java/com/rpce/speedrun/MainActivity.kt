// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

package com.rpce.speedrun

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.appcompat.app.AppCompatActivity
import java.io.File
import kotlin.concurrent.thread

/**
 * RPCE companion. Renders the deep-blue themed UI (assets/app.html) in a WebView
 * and drives the shared Rust engine through [NativeBridge]. The web layer calls
 * the engine via the injected `Engine` JavaScript interface — the phone runs the
 * same review loop / scheduler as the desktop (spec §3), not a reimplementation.
 */
class MainActivity : AppCompatActivity() {
    private lateinit var web: WebView

    companion object {
        /** Where AnkiWeb accounts are created (sign-up is web-only). */
        private const val SIGNUP_URL = "https://ankiweb.net/account/signup"
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        web.setBackgroundColor(Color.parseColor("#ffffff"))
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true // localStorage: persist sync auth + last-sync time
        web.addJavascriptInterface(EngineBridge(), "Engine")
        setContentView(web)

        // Open the collection + seed the deck off the UI thread, then load the UI.
        thread {
            val status = initEngine()
            runOnUiThread {
                web.loadUrl("file:///android_asset/app.html?status=$status")
            }
        }
    }

    /** Open (or create) the collection and ensure the RPCE deck is present. */
    private fun initEngine(): String {
        return try {
            val colPath = File(filesDir, "collection.anki2").absolutePath
            NativeBridge.openCollection(colPath)
            // Seed the deck from the bundled .apkg the first time only.
            if (!parseFound(NativeBridge.selectDeck("RPCE"))) {
                val apkg = File(filesDir, "rpce_starter.apkg")
                assets.open("rpce_starter.apkg").use { input ->
                    apkg.outputStream().use { input.copyTo(it) }
                }
                NativeBridge.importPackage(apkg.absolutePath)
                NativeBridge.selectDeck("RPCE")
            }
            "ready"
        } catch (e: Throwable) {
            "error"
        }
    }

    private fun parseFound(json: String): Boolean =
        json.contains("\"found\":true")

    /** Open the AnkiWeb sign-up page in the system browser. Returns false if
     *  no browser could handle the intent, so the web UI can explain. */
    private fun openSignupPage(): Boolean =
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(SIGNUP_URL))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            true
        } catch (e: Throwable) {
            false
        }

    /** Bridge the web UI calls straight into the shared engine. */
    inner class EngineBridge {
        @JavascriptInterface fun engineInfo(): String = NativeBridge.engineInfo()

        /** Open the AnkiWeb account sign-up page; true if a browser opened it. */
        @JavascriptInterface fun openSignup(): Boolean = openSignupPage()

        @JavascriptInterface fun deckCounts(): String = NativeBridge.deckCounts()

        @JavascriptInterface fun nextCard(): String = NativeBridge.nextCard()

        @JavascriptInterface fun answer(rating: Int): String = NativeBridge.answerCard(rating)

        @JavascriptInterface fun scores(): String = NativeBridge.scores()

        @JavascriptInterface fun recordScenario(): String = NativeBridge.recordScenario()

        /** The bundled Section II scenarios (mirrors anki.rpce.scenarios). */
        @JavascriptInterface
        fun scenarios(): String =
            assets.open("scenarios.json").bufferedReader().use { it.readText() }

        /** The bundled meeting simulations (mirrors anki.rpce.simulations). */
        @JavascriptInterface
        fun simulations(): String =
            assets.open("simulations.json").bufferedReader().use { it.readText() }

        /** Reference tables (order of precedence, motion characteristics). */
        @JavascriptInterface
        fun reference(): String =
            assets.open("reference.json").bufferedReader().use { it.readText() }

        /** Real device connectivity (navigator.onLine is unreliable in a WebView).
         *  Checks ANY network for INTERNET capability, not just the active default:
         *  on the emulator the default network can lack the INTERNET flag while
         *  cellular/Wi-Fi actually carries traffic, which wrongly read as offline. */
        @JavascriptInterface
        fun online(): Boolean {
            return try {
                val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
                cm.allNetworks.any { n ->
                    cm.getNetworkCapabilities(n)
                        ?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
                }
            } catch (e: Throwable) {
                true // assume online if we can't tell
            }
        }

        @JavascriptInterface
        fun syncLogin(user: String, pass: String, endpoint: String): String =
            NativeBridge.syncLogin(user, pass, endpoint)

        @JavascriptInterface
        fun syncCollection(hkey: String, endpoint: String): String =
            NativeBridge.syncCollection(hkey, endpoint)

        @JavascriptInterface
        fun fullSync(hkey: String, endpoint: String, upload: Boolean): String =
            NativeBridge.fullSync(hkey, endpoint, upload)
    }
}
