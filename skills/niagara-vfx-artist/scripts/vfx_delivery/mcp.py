"""MCP helpers for this skill. The implementation is shared: unreal-engine-mcp/scripts/ue_mcp."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3] / "unreal-engine-mcp" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ue_mcp.skill_api import (  # noqa: E402,F401
    DEFAULT_MCP_URL, builtin_mcp, call_tool, connect, python_remote, run_tool_script,
)
