"""Entry points the material, Niagara and flipbook skills use through their mcp.py shims."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType
from typing import Any

from . import remote as _remote
from .client import UnrealMcpClient
from .paths import default_cache_dir, default_session_dir
from .protocol import DEFAULT_PROTOCOL, DEFAULT_URL, _decode_text_value


DEFAULT_MCP_URL = os.environ.get("UNREAL_MCP_URL", DEFAULT_URL)


def builtin_mcp(skill_root: Path | None = None) -> ModuleType:
    """The ``ue_mcp`` package (client, batch runner, result helpers). ``skill_root`` is accepted for old callers."""
    del skill_root
    return importlib.import_module(__package__)


def python_remote(skill_root: Path | None = None) -> ModuleType:
    """Epic Python Remote Execution helpers (``run_python``, ``stdout_of``, ...)."""
    del skill_root
    return _remote


def connect(skill_root: Path | None = None, *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
            project: str | None = None) -> UnrealMcpClient:
    """An opened client with the CLI's defaults: schema cache, resumed session, optional project guard.

    Call ``close()`` when done; it keeps the session for the next run.
    """
    del skill_root
    client = UnrealMcpClient(
        url, DEFAULT_PROTOCOL, timeout,
        cache_dir=default_cache_dir(), session_dir=default_session_dir(),
        expected_project=project or os.environ.get("UE_MCP_PROJECT"),
    )
    return client.open()


def run_tool_script(skill_root: Path | None, script: str, *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
                    project: str | None = None) -> Any:
    """Run one ProgrammaticToolset script; any failing tool call fails the whole script."""
    client = connect(skill_root, url=url, timeout=timeout, project=project)
    try:
        return client.run_tool_script(script)
    finally:
        client.close()


def call_tool(skill_root: Path | None, toolset: str, tool: str, arguments: dict[str, Any], *,
              url: str = DEFAULT_MCP_URL, timeout: float = 60, project: str | None = None) -> Any:
    """Call one tool and return the decoded result."""
    client = connect(skill_root, url=url, timeout=timeout, project=project)
    try:
        return _decode_text_value(client.call_resolved_tool(toolset, tool, arguments))
    finally:
        client.close()
