# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Optional online AI (OpenAI) for the RPCE examiner.

Design rules (spec §5, §7g, §10, grading "AI checking and safety"):

- **Never required.** Everything degrades to the offline `KeywordExaminer`
  (`AutoExaminer` in ``examiner.py``). No key / offline / rate-limited / a
  timeout / malformed output → the app still grades and still scores.
- **The key is a secret.** It is read from the ``OPENAI_API_KEY`` env var or a
  local file at ``~/.rpce/openai_key`` — NEVER committed and NEVER written to
  the (syncing) collection config, so it can't leak to AnkiWeb or git.
- **Traceable source.** The model never supplies the RONR citation; the caller
  retrieves the supporting passage and passes it in, and we attach that
  citation to the result (spec: "AI claims with no traceable source" is zero).
- **Prompt-injection safe.** The student's answer and the source are passed as
  DATA with an explicit instruction to ignore any commands inside them.

Uses only the standard library (urllib) — no extra dependency.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

#: Local, git-ignored key file (outside any synced/tracked location).
KEY_PATH = Path.home() / ".rpce" / "openai_key"
#: Presence of this file means "AI off" — lets the user disable AI grading even
#: with a key configured and a connection available.
AI_OFF_PATH = Path.home() / ".rpce" / "ai_off"
#: Chat model; override with RPCE_OPENAI_MODEL.
MODEL = os.environ.get("RPCE_OPENAI_MODEL", "gpt-4o-mini")
#: Hard timeout (s): a slow/rate-limited API must fall back quickly, not hang.
TIMEOUT = float(os.environ.get("RPCE_OPENAI_TIMEOUT", "20"))
_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def openai_key() -> str:
    """The configured key, or "" if none. Env var wins over the local file."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def set_openai_key(key: str) -> None:
    """Persist (or clear) the key in the local file — never in the repo/config."""
    key = (key or "").strip()
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if key:
        KEY_PATH.write_text(key, encoding="utf-8")
    elif KEY_PATH.exists():
        KEY_PATH.unlink()


def ai_configured() -> bool:
    """True if a key is present (does not check connectivity)."""
    return bool(openai_key())


def ai_enabled() -> bool:
    """True unless the user turned AI off (a manual switch, independent of the
    key/connectivity). Off → the app uses the offline examiner even when online."""
    return not AI_OFF_PATH.exists()


def set_ai_enabled(on: bool) -> None:
    """Turn AI grading on/off. Stored as a local flag file (never synced)."""
    AI_OFF_PATH.parent.mkdir(parents=True, exist_ok=True)
    if on:
        AI_OFF_PATH.unlink(missing_ok=True)
    else:
        AI_OFF_PATH.write_text("off", encoding="utf-8")


def chat_json(system: str, user: str, *, max_tokens: int = 400) -> dict | None:
    """Call the chat API and parse a JSON object from the reply.

    Returns None on ANY problem (no key, offline, HTTP/rate-limit error,
    timeout, non-JSON output) so callers fall back cleanly. Requests strict
    JSON via response_format so a stray sentence can't derail parsing."""
    key = openai_key()
    if not key:
        return None
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.load(resp)
        content = data["choices"][0]["message"]["content"]
        obj = json.loads(content)
        return obj if isinstance(obj, dict) else None
    except (urllib.error.URLError, OSError, ValueError, KeyError, TimeoutError):
        # Offline / rate-limited / bad output → let the caller fall back.
        return None
