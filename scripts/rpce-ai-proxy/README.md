# RPCE AI grading proxy

Keeps your **single OpenAI key server-side** so it never ships inside the
downloadable APK / MSI (a bundled key is extractable; a proxy key is not). The
apps send an OpenAI chat-completions request to your proxy URL; the proxy adds
the key and forwards to OpenAI.

```
app  ──POST messages──▶  your proxy (holds the key)  ──▶  OpenAI
```

## Option A — Cloudflare Worker (free, no server to run)

```bash
npm i -g wrangler
cd scripts/rpce-ai-proxy
wrangler secret put OPENAI_API_KEY     # paste your key — stored server-side only
wrangler secret put APP_TOKEN          # optional: a shared secret the apps send
wrangler deploy                        # prints https://rpce-ai-proxy.<you>.workers.dev
```

## Option B — self-host (VPS)

```bash
pip install flask requests
OPENAI_API_KEY=sk-... APP_TOKEN=optional python server.py   # :8787
# put HTTPS in front (nginx/caddy); the public URL is your proxy URL
```

## Point the apps at it

```bash
# Bundles the proxy URL (NOT the key) into desktop + phone builds:
python pylib/tools/rpce_embed_key.py --proxy https://<your-proxy-url> [--app-token <token>]
# then build the APK / MSI as usual. To go back to no-AI/per-user: --clear
```

When a proxy URL is bundled, the apps call the proxy and **no key is embedded**.
Rotate, rate-limit, cap, or revoke the key on your side without touching any
installed app. Also set a **hard monthly budget** on the key in the OpenAI
dashboard as a safety net.
