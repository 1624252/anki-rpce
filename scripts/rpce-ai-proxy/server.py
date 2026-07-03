#!/usr/bin/env python
# RPCE AI grading proxy — minimal VPS/self-host alternative to the Cloudflare
# Worker (worker.js). Keeps your OpenAI key SERVER-SIDE so it never ships in the
# apps. Reads the key from its OWN environment (never the repo).
#
#   pip install flask requests
#   OPENAI_API_KEY=sk-...  [APP_TOKEN=...]  python server.py   # listens on :8787
#   # then front it with HTTPS (nginx/caddy) and run:
#   #   python pylib/tools/rpce_embed_key.py --proxy https://<your-host>/
#
# The apps POST an OpenAI chat-completions body to "/"; this adds the key and
# forwards to OpenAI. Set a hard monthly budget on the key in the OpenAI dashboard.

import os

import requests
from flask import Flask, Response, request

app = Flask(__name__)
OPENAI = "https://api.openai.com/v1/chat/completions"


@app.route("/", methods=["POST"])
def grade():
    token = os.environ.get("APP_TOKEN")
    if token and request.headers.get("x-app-token") != token:
        return Response('{"error":"unauthorized"}', 401, mimetype="application/json")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return Response('{"error":"no key"}', 500, mimetype="application/json")
    r = requests.post(
        OPENAI,
        data=request.get_data(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30,
    )
    return Response(r.content, r.status_code, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8787")))
