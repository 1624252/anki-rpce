#!/usr/bin/env python
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Self-contained two-way sync proof (spec §7b) — one command.

Spins up a temporary local Anki sync server, runs :mod:`rpce_sync_test` against
it (the exact backend calls both the desktop and the phone use), then shuts the
server down. Exits non-zero if the round-trip or conflict resolution fails, so
it is safe to wire into CI. No network/AnkiWeb account needed.

    just rpce-sync-test        # or: out/pyenv/Scripts/python pylib/tools/rpce_sync_test_run.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOST = "127.0.0.1"


def _free_port() -> str:
    """An unused localhost port, so repeated runs never collide (WinError 10048)."""
    with socket.socket() as s:
        s.bind((HOST, 0))
        return str(s.getsockname()[1])


def _port_open(host: str, port: str) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, int(port))) == 0


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    port = _free_port()
    env = dict(os.environ)
    # The subprocesses import the built engine from out/pylib.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in ("out/pylib", env.get("PYTHONPATH", "")) if p
    )
    env.update(
        SYNC_USER1="rpce:rpcepass",
        SYNC_BASE=tempfile.mkdtemp(prefix="rpce_sync_"),
        SYNC_HOST=HOST,
        SYNC_PORT=port,
        RPCE_SYNC_ENDPOINT=f"http://{HOST}:{port}/",
    )

    server = subprocess.Popen(
        [sys.executable, "-c", "import anki.syncserver as s; s.run_sync_server()"],
        cwd=repo,
        env=env,
    )
    try:
        for _ in range(60):  # wait up to ~30s for the server to bind
            if _port_open(HOST, port):
                break
            if server.poll() is not None:
                print("sync server exited before binding", file=sys.stderr)
                return 1
            time.sleep(0.5)
        else:
            print("sync server did not start in time", file=sys.stderr)
            return 1
        return subprocess.run(
            [sys.executable, str(repo / "pylib" / "tools" / "rpce_sync_test.py")],
            cwd=repo,
            env=env,
            check=False,
        ).returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
