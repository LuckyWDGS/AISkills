"""Legacy BridgeClient interface, now over Epic Python Remote Execution (shared: ue_mcp.legacy_bridge).

Scripts that call retired ``UnrealBridge*Library`` APIs fail fast; port them to MCP.
"""

from __future__ import annotations

from . import mcp  # noqa: F401  (puts unreal-engine-mcp/scripts on sys.path)
from ue_mcp.legacy_bridge import (  # noqa: E402,F401
    RETIRED_LIBRARY, BridgeClient, BridgeError, BridgeResult, parse_json_output,
)
