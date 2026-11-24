"""MCP helpers for this skill. The implementation is shared: unreal-engine-mcp/scripts/ue_mcp."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3] / "unreal-engine-mcp" / "scripts"
if not (_SCRIPTS / "ue_mcp").is_dir():
    raise ModuleNotFoundError(
        f"{Path(__file__).resolve().parents[2].name} needs the sibling skill unreal-engine-mcp installed next to it "
        f"(expected {_SCRIPTS / 'ue_mcp'}); its editor tools reach Unreal through that shared MCP client."
    )
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ue_mcp import unwrap_result  # noqa: E402,F401
from ue_mcp.remote import marker_json, run_python, stdout_of  # noqa: E402,F401
from ue_mcp.skill_api import connect  # noqa: E402,F401
