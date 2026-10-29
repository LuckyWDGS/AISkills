#!/usr/bin/env python3
"""Background client for Epic's PythonScriptPlugin Remote Execution (CLI).

The implementation is ``ue_mcp/remote.py``; use only for an operation the
built-in MCP does not cover.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ue_mcp.remote import (  # noqa: E402,F401
    PythonRemote, RemoteError, _matches, load_remote_module, main, run_python, stdout_of,
)


if __name__ == "__main__":
    raise SystemExit(main())
