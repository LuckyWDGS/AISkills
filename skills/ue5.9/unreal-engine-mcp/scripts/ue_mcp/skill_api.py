"""Entry points the material, Niagara and flipbook skills use through their mcp.py shims."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType
from typing import Any

from . import remote as _remote
from .capture import capture_report, parse_pose  # noqa: F401  (re-exported for sibling skills)
from .client import UnrealMcpClient
from .editor import BUNDLE_ENGINE
from .paths import default_cache_dir, default_session_dir
from .protocol import DEFAULT_PROTOCOL, DEFAULT_URL, McpError, _decode_text_value


DEFAULT_MCP_URL = os.environ.get("UNREAL_MCP_URL", DEFAULT_URL)


def ensure_editor_idle(client: UnrealMcpClient) -> None:
    """Refuse writes during an existing PIE/Simulate session or an ambiguous state response."""
    from . import unwrap_result
    state = unwrap_result(client.call_resolved_tool("EditorAppToolset", "IsPIERunning", {}))
    if state is not False:
        raise RuntimeError("Editor is running PIE/Simulate or its state is unknown; no writes performed.")


def builtin_mcp(skill_root: Path | None = None) -> ModuleType:
    """The ``ue_mcp`` package (client, batch runner, result helpers). ``skill_root`` is accepted for old callers."""
    del skill_root
    return importlib.import_module(__package__)


def python_remote(skill_root: Path | None = None) -> ModuleType:
    """Epic Python Remote Execution helpers (``run_python``, ``stdout_of``, ...)."""
    del skill_root
    return _remote


def refuse_unported(client: UnrealMcpClient, helper: str = "") -> None:
    """Stop a helper that still calls UE 5.8 tool names before it sends anything to a UE 5.9 editor.

    Some of those helpers mix owners that still exist on 5.9 with names that do
    not, so letting one run could write first and fail afterwards.
    """
    names = {item["name"].rsplit(".", 1)[-1] for item in client.list_toolsets()}
    version = str(client.editor_owner().get("engine_version") or "")
    if version.startswith(f"{BUNDLE_ENGINE}.") or "PythonScriptingTools" in names:
        raise McpError(
            f"{helper or 'This helper'} is not ported to UE {BUNDLE_ENGINE}: it still calls UE 5.8 tool names and "
            "argument shapes. No tool call was sent. Use the native route in this skill's "
            f"references/ue-{BUNDLE_ENGINE}-*.md, or link skills/ue5.8 for a UE 5.8 editor "
            "(tools/install.ps1 -UEVersion 5.8)."
        )


def connect(skill_root: Path | None = None, *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
            project: str | None = None, contract: str = BUNDLE_ENGINE) -> UnrealMcpClient:
    """An opened client with the CLI's defaults: schema cache, resumed session, optional project guard.

    ``contract`` is the tool contract the caller was written for. A helper that
    is still on the UE 5.8 names passes ``"5.8"`` and is refused on a 5.9 editor.
    Call ``close()`` when done; it keeps the session for the next run.
    """
    del skill_root
    client = UnrealMcpClient(
        url, DEFAULT_PROTOCOL, timeout,
        cache_dir=default_cache_dir(), session_dir=default_session_dir(),
        expected_project=project or os.environ.get("UE_MCP_PROJECT"),
    )
    client.open()
    if contract != BUNDLE_ENGINE:
        try:
            refuse_unported(client)
        except McpError as exc:
            client.close()
            # A helper's own error handling expects editor failures, not this; end the run with one clear line.
            raise SystemExit(f"error: {exc}") from None
    return client


def run_tool_script(skill_root: Path | None, script: str, *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
                    project: str | None = None, contract: str = "5.8") -> Any:
    """Run one UE 5.8 ProgrammaticToolset script; refused on a UE 5.9 editor (use ``execute_python``)."""
    client = connect(skill_root, url=url, timeout=timeout, project=project, contract=contract)
    try:
        return client.run_tool_script(script)
    finally:
        client.close()


def call_tool(skill_root: Path | None, toolset: str, tool: str, arguments: dict[str, Any], *,
              url: str = DEFAULT_MCP_URL, timeout: float = 60, project: str | None = None,
              contract: str = BUNDLE_ENGINE) -> Any:
    """Call one tool and return the decoded result."""
    client = connect(skill_root, url=url, timeout=timeout, project=project, contract=contract)
    try:
        return _decode_text_value(client.call_resolved_tool(toolset, tool, arguments))
    finally:
        client.close()


def execute_python(skill_root: Path | None, script: str, *, url: str = DEFAULT_MCP_URL,
                   timeout: float = 180, project: str | None = None) -> Any:
    """Run a script through UE 5.9 ``PythonScriptingTools``; read ``read_me`` and look up the symbols first."""
    client = connect(skill_root, url=url, timeout=timeout, project=project)
    try:
        return client.execute_python(script)
    finally:
        client.close()
