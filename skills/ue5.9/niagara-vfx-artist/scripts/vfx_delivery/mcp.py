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

from functools import partial  # noqa: E402

from ue_mcp import skill_api as _api  # noqa: E402
from ue_mcp.skill_api import (  # noqa: E402,F401
    DEFAULT_MCP_URL, builtin_mcp, capture_report, parse_pose, python_remote,
)

# Every editor-connected helper in this skill still calls UE 5.8 tool names. Declaring
# that contract makes the shared client refuse them on a UE 5.9 editor before any call.
# A helper ported to 5.9 imports ue_mcp.skill_api directly and drops out of this shim.
LEGACY_CONTRACT = "5.8"
connect = partial(_api.connect, contract=LEGACY_CONTRACT)
call_tool = partial(_api.call_tool, contract=LEGACY_CONTRACT)
run_tool_script = partial(_api.run_tool_script, contract=LEGACY_CONTRACT)
