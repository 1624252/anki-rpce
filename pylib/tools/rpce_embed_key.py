# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Embed the OpenAI key into the shipping desktop + phone builds (obfuscated).

Run this ONCE before packaging the MSI / APK. It reads the key from the
packager's local secret (``$RPCE_AI_KEY`` / ``$OPENAI_API_KEY`` env, else
``~/.rpce/openai_key``), obfuscates it (``anki.rpce._keybundle``), and writes the
blob to two GIT-IGNORED locations:

  * ``pylib/anki/rpce/_bundled_key``           -> packaged into the desktop app
  * ``mobile/app/app/src/main/assets/rpce_key`` -> packaged into the APK

SECURITY: this is obfuscation, not security — a determined user can extract the
key from the binary. Never commit the blob files (they are in .gitignore). To
remove a bundled key, run ``--clear``. Prints only a fingerprint, never the key.

Usage:
    python pylib/tools/rpce_embed_key.py            # embed from local secret
    python pylib/tools/rpce_embed_key.py --clear    # remove bundled blobs
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP_BLOB = ROOT / "pylib" / "anki" / "rpce" / "_bundled_key"
MOBILE_BLOB = ROOT / "mobile" / "app" / "app" / "src" / "main" / "assets" / "rpce_key"
KEY_FILE = Path.home() / ".rpce" / "openai_key"


def _read_key() -> str:
    for env in ("RPCE_AI_KEY", "OPENAI_API_KEY"):
        v = os.environ.get(env, "").strip()
        if v:
            return v
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def main(argv: list[str]) -> int:
    if "--clear" in argv:
        for p in (DESKTOP_BLOB, MOBILE_BLOB):
            if p.exists():
                p.unlink()
                print(f"removed {p}")
        return 0

    # Import the shared obfuscation from the source tree.
    sys.path.insert(0, str(ROOT / "pylib"))
    from anki.rpce._keybundle import deobfuscate, obfuscate

    key = _read_key()
    if not key:
        print(
            "ERROR: no key found. Set RPCE_AI_KEY / OPENAI_API_KEY or write "
            f"{KEY_FILE}.",
            file=sys.stderr,
        )
        return 2
    blob = obfuscate(key)
    assert deobfuscate(blob) == key, "obfuscation round-trip failed"
    for p in (DESKTOP_BLOB, MOBILE_BLOB):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(blob, encoding="utf-8")
        print(f"wrote {p} ({len(blob)} bytes)")
    print(f"embedded key fingerprint sha256[:8] = {_fingerprint(key)}")
    print("REMINDER: these blob files are git-ignored — do NOT commit them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
