#!/usr/bin/env python3
"""Run the offline test suites of all four UE skills, with non-loopback networking blocked.

Each suite runs in its own process (two skills ship a package named ``vfx_delivery``).
The client tests talk to a fake MCP server on 127.0.0.1, so loopback stays allowed.
Used by CI (.github/workflows/ue-skills-tests.yml) and locally:

    python skills/unreal-engine-mcp/scripts/run_offline_tests.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
SUITES = ["unreal-engine-mcp", "unreal-material-artist", "niagara-vfx-artist", "vfx-flipbook-generator"]

# Loaded automatically by every child interpreter through PYTHONPATH.
SITECUSTOMIZE = '''
import socket

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_connect = socket.socket.connect
_create_connection = socket.create_connection


def _host(address):
    return address[0] if isinstance(address, tuple) else address


def connect(self, address):
    if _host(address) not in _LOOPBACK:
        raise AssertionError(f"Network forbidden during offline tests: {address!r}")
    return _connect(self, address)


def create_connection(address, *args, **kwargs):
    if _host(address) not in _LOOPBACK:
        raise AssertionError(f"Network forbidden during offline tests: {address!r}")
    return _create_connection(address, *args, **kwargs)


socket.socket.connect = connect
socket.create_connection = create_connection
'''

RUNNER = '''
import sys
import unittest

suite = unittest.defaultTestLoader.discover(".", pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
'''


def main() -> int:
    failed = []
    with tempfile.TemporaryDirectory(prefix="ue-offline-") as folder:
        Path(folder, "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        state = Path(folder, "state")
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(filter(None, [folder, os.environ.get("PYTHONPATH")])),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
            "UE_MCP_CACHE_DIR": str(state),  # never touch the user's real schema/session state
        }
        env.pop("UE_MCP_PROJECT", None)
        for name in SUITES:
            print(f"== {name}", flush=True)
            code = subprocess.run([sys.executable, "-c", RUNNER], cwd=SKILLS / name / "scripts", env=env).returncode
            if code:
                failed.append(name)
    print(f"\n{len(SUITES) - len(failed)}/{len(SUITES)} suites passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
