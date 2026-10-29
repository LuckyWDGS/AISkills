"""Client for Epic's built-in Unreal Engine MCP server and Python Remote Execution.

Modules: ``protocol`` (messages, errors), ``client`` (HTTP session, discovery,
schema cache, session reuse), ``schema`` (brief views), ``editor`` (which
editor serves an endpoint), ``batch`` (ordered steps with readback), ``remote``
(Epic Python Remote Execution), ``legacy_bridge`` (old BridgeClient interface),
``skill_api`` (what sibling skills import), ``cli`` (``builtin_mcp.py``).
"""

import sys

if sys.version_info < (3, 10):  # dataclass(slots=True), str.removesuffix
    raise SystemExit(f"The UE skills need Python 3.10 or newer; {sys.executable} is {sys.version.split()[0]}.")

from .batch import _expectation_met, load_batch, run_batch, validate_batch
from .client import UnrealMcpClient
from .editor import check_expected_project, endpoint_owner
from .paths import default_cache_dir, default_session_dir, default_state_dir
from .protocol import (
    DEFAULT_PROTOCOL, DEFAULT_URL, McpError, SessionExpired, _check_tool_result, _decode_text_value, _extract_text,
    unwrap_result,
)
from .schema import _schema_tools, brief_tools, render_brief

__all__ = [
    "DEFAULT_PROTOCOL", "DEFAULT_URL", "McpError", "SessionExpired", "UnrealMcpClient", "brief_tools",
    "check_expected_project", "default_cache_dir", "default_session_dir", "default_state_dir", "endpoint_owner",
    "load_batch", "render_brief", "run_batch", "unwrap_result", "validate_batch",
]
