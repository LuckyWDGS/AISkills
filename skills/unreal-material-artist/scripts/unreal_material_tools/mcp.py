"""Access Epic's built-in MCP and Python Remote Execution via the sibling unreal-engine-mcp skill."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any


DEFAULT_MCP_URL = os.environ.get("UNREAL_MCP_URL", "http://127.0.0.1:8000/mcp")
_MODULES: dict[str, ModuleType] = {}


def _load(skill_root: Path, name: str) -> ModuleType:
    if name not in _MODULES:
        path = Path(skill_root).parent / "unreal-engine-mcp" / "scripts" / f"{name}.py"
        if not path.is_file():
            raise RuntimeError(f"Cannot find {path}; install the sibling unreal-engine-mcp skill.")
        spec = importlib.util.spec_from_file_location(f"ue_{name}", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        _MODULES[name] = module
    return _MODULES[name]


def builtin_mcp(skill_root: Path) -> ModuleType:
    return _load(skill_root, "builtin_mcp")


def python_remote(skill_root: Path) -> ModuleType:
    return _load(skill_root, "python_remote")


def run_tool_script(skill_root: Path, script: str, *, url: str = DEFAULT_MCP_URL, timeout: float = 180) -> Any:
    """Run one ProgrammaticToolset script; any failing tool call fails the whole script."""
    module = builtin_mcp(skill_root)
    client = module.UnrealMcpClient(url, module.DEFAULT_PROTOCOL, timeout, cache_dir=module.default_cache_dir())
    try:
        client.initialize()
        return client.run_tool_script(script)
    finally:
        client.close()


def call_tool(skill_root: Path, toolset: str, tool: str, arguments: dict[str, Any], *,
              url: str = DEFAULT_MCP_URL, timeout: float = 60) -> Any:
    """Call one tool in its own session and return the decoded result."""
    module = builtin_mcp(skill_root)
    client = module.UnrealMcpClient(url, module.DEFAULT_PROTOCOL, timeout, cache_dir=module.default_cache_dir())
    try:
        client.initialize()
        return module._decode_text_value(client.call_resolved_tool(toolset, tool, arguments))
    finally:
        client.close()
