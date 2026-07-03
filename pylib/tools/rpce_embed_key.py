# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Configure AI grading for the shipping desktop + phone builds.

RECOMMENDED — proxy mode (the key never ships in the binary):
    python pylib/tools/rpce_embed_key.py --proxy https://<your-proxy> [--app-token T]
Bundles ONLY the proxy URL (+ optional shared token). See scripts/rpce-ai-proxy/.

Fallback — bundled-key mode (obfuscation, NOT security; the key is extractable):
    python pylib/tools/rpce_embed_key.py            # embed the local key
Reads the key from $RPCE_AI_KEY / $OPENAI_API_KEY, else ~/.rpce/openai_key, and
writes the obfuscated blob (anki.rpce._keybundle).

Both modes write to GIT-IGNORED files (never committed):
    pylib/anki/rpce/{_bundled_key,_ai_proxy,_ai_token}
    mobile/app/app/src/main/assets/{rpce_key,rpce_ai_proxy,rpce_ai_token}

    python pylib/tools/rpce_embed_key.py --clear    # remove everything (no AI / per-user)
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RPCE = ROOT / "pylib" / "anki" / "rpce"
ASSETS = ROOT / "mobile" / "app" / "app" / "src" / "main" / "assets"
KEY_FILE = Path.home() / ".rpce" / "openai_key"

# (desktop path, mobile path) per artifact.
KEY = (RPCE / "_bundled_key", ASSETS / "rpce_key")
PROXY = (RPCE / "_ai_proxy", ASSETS / "rpce_ai_proxy")
TOKEN = (RPCE / "_ai_token", ASSETS / "rpce_ai_token")


def _read_key() -> str:
    for env in ("RPCE_AI_KEY", "OPENAI_API_KEY"):
        v = os.environ.get(env, "").strip()
        if v:
            return v
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write(paths: tuple[Path, Path], text: str) -> None:
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")


def _clear(paths: tuple[Path, Path]) -> None:
    for p in paths:
        if p.exists():
            p.unlink()
            print(f"removed {p}")


def _opt(argv: list[str], flag: str) -> str | None:
    return (
        argv[argv.index(flag) + 1]
        if flag in argv and argv.index(flag) + 1 < len(argv)
        else None
    )


def main(argv: list[str]) -> int:
    if "--clear" in argv:
        for paths in (KEY, PROXY, TOKEN):
            _clear(paths)
        print("cleared all AI config — builds ship no key/proxy (offline / per-user).")
        return 0

    proxy = _opt(argv, "--proxy")
    if proxy:
        # Proxy mode: bundle the URL (+ token), NOT the key. Clear any old key blob
        # so the shipped app holds no key at all.
        _clear(KEY)
        _write(PROXY, proxy.strip())
        token = _opt(argv, "--app-token")
        if token:
            _write(TOKEN, token.strip())
        else:
            _clear(TOKEN)
        print(
            f"proxy mode: apps call {proxy.strip()} — the OpenAI key stays on your proxy."
        )
        return 0

    # Bundled-key mode (obfuscation, not security).
    sys.path.insert(0, str(ROOT / "pylib"))
    from anki.rpce._keybundle import deobfuscate, obfuscate

    key = _read_key()
    if not key:
        print(
            "ERROR: no key found. Use --proxy <url> (recommended), or set "
            f"RPCE_AI_KEY / OPENAI_API_KEY or write {KEY_FILE}.",
            file=sys.stderr,
        )
        return 2
    blob = obfuscate(key)
    assert deobfuscate(blob) == key, "obfuscation round-trip failed"
    _clear(PROXY)
    _write(KEY, blob)
    print(
        f"bundled-key mode: fingerprint sha256[:8] = {hashlib.sha256(key.encode()).hexdigest()[:8]}"
    )
    print("WARNING: a bundled key is extractable from the binary. Prefer --proxy.")
    print("REMINDER: these blob files are git-ignored — do NOT commit them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
