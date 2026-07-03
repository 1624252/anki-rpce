# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Reversible obfuscation for the *bundled* OpenAI key shipped in the built
desktop (MSI) and phone (APK) artifacts.

IMPORTANT — this is obfuscation, NOT security. A bundled key in a downloadable
binary can be extracted by anyone who disassembles it; this only defeats a naive
``strings`` scan. The key is injected at BUILD time from the packager's local
``~/.rpce/openai_key`` (see ``pylib/tools/rpce_embed_key.py``); the obfuscated
blob files (``_bundled_key`` / ``assets/rpce_key``) are git-ignored and MUST
NEVER be committed. Users can always override with their own key, and AI is
never required (offline keyword grading always works).
"""

from __future__ import annotations

import base64

# A fixed pad. Not secret (it ships in the code) — it only turns the stored blob
# into non-obvious bytes so the raw key isn't greppable in the binary.
_PAD = b"rpce-speedrun::obfuscation-pad::not-a-security-boundary::v1"


def _xor(data: bytes) -> bytes:
    return bytes(b ^ _PAD[i % len(_PAD)] for i, b in enumerate(data))


def obfuscate(key: str) -> str:
    """key -> storable blob (base64 of xor'd bytes)."""
    return base64.b64encode(_xor(key.encode("utf-8"))).decode("ascii")


def deobfuscate(blob: str) -> str:
    """blob -> key, or "" if the blob is empty/corrupt."""
    blob = (blob or "").strip()
    if not blob:
        return ""
    try:
        return _xor(base64.b64decode(blob)).decode("utf-8")
    except Exception:
        return ""
