#!/usr/bin/env python3
"""Command line for Epic's built-in Unreal Engine MCP server.

The implementation is the ``ue_mcp`` package next to this file; this module
keeps the historical import surface (``from builtin_mcp import ...``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)  # Also when another skill loads this file by path.

from ue_mcp import *  # noqa: E402,F401,F403
from ue_mcp import _check_tool_result, _decode_text_value, _expectation_met, _extract_text, _schema_tools  # noqa: E402,F401
from ue_mcp.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
