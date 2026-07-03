// RPCE AI grading proxy — Cloudflare Worker.
//
// Keeps your (single) OpenAI key SERVER-SIDE so it never ships in the APK/MSI.
// The apps POST an OpenAI chat-completions body here; this Worker adds the key
// and forwards to OpenAI, returning the response unchanged. Deploy:
//
//   1. npm i -g wrangler
//   2. wrangler secret put OPENAI_API_KEY      # paste your key (server-side only)
//   3. (optional) wrangler secret put APP_TOKEN # a shared secret the apps send
//   4. wrangler deploy
//   5. run:  python pylib/tools/rpce_embed_key.py --proxy https://<your-worker-url>
//      (this bundles the URL, NOT the key, into the apps)
//
// The key lives only in the Worker secret; rotate/cap/revoke it without touching
// any installed app. Set a hard monthly budget on the key in the OpenAI dashboard.

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors() });
    }
    if (request.method !== "POST") {
      return json({ error: "POST only" }, 405);
    }
    // Optional shared-secret gate so random traffic can't spend your key.
    if (env.APP_TOKEN && request.headers.get("x-app-token") !== env.APP_TOKEN) {
      return json({ error: "unauthorized" }, 401);
    }
    if (!env.OPENAI_API_KEY) {
      return json({ error: "proxy missing OPENAI_API_KEY secret" }, 500);
    }
    const body = await request.text();
    const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + env.OPENAI_API_KEY,
        "Content-Type": "application/json",
      },
      body,
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json", ...cors() },
    });
  },
};

function cors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, x-app-token",
  };
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...cors() },
  });
}
