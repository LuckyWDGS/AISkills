"""Editor Python execution for legacy pipelines, over Epic's Python Remote Execution.

UnrealBridge (custom plugin + TCP) is retired. ``BridgeClient`` keeps its old
interface so stock-``unreal.*`` scripts still run through Epic's
PythonScriptPlugin endpoint; scripts that call ``UnrealBridge*Library`` fail
fast and must be ported to built-in MCP tools.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


RETIRED_LIBRARY = re.compile(r"\bUnrealBridge\w*Library\b|\bunreal_bridge\b")


class BridgeError(RuntimeError):
    pass


class RetiredTool(BridgeError):
    """A tool whose live step has not been ported from UnrealBridge to MCP yet."""


def _print_bridge_errors(kind, value, traceback) -> None:
    # Uncaught BridgeErrors are user-facing conditions, not bugs: one line instead of a traceback.
    if isinstance(value, BridgeError):
        print(f"error: {value}", file=sys.stderr)
    else:
        _default_excepthook(kind, value, traceback)


_default_excepthook = sys.excepthook
sys.excepthook = _print_bridge_errors


def retired_tool(skill_root: Path, tool: str) -> dict[str, str] | None:
    """The registry entry for ``tool`` in ``<skill>/scripts/retired_tools.json``, if it is retired."""
    path = Path(skill_root) / "scripts" / "retired_tools.json"
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = registry.get(tool)
    return entry if isinstance(entry, dict) else None


def _caller_tool(depth: int = 2) -> str:
    """Module short name of the code constructing the client, e.g. ``material_domain_audit``."""
    return str(sys._getframe(depth).f_globals.get("__name__", "")).rsplit(".", 1)[-1]


@dataclass(slots=True)
class BridgeResult:
    stdout: str
    stderr: str


def _load_python_remote(skill_root: Path) -> ModuleType:
    del skill_root  # Kept for callers and tests; the package ships its own Remote Execution client.
    from . import remote
    return remote


def parse_json_output(text: str) -> Any:
    """Return the last complete JSON value printed, compact or indented."""
    stripped = text.strip()
    if not stripped:
        raise BridgeError("Editor script printed nothing")
    decoder = json.JSONDecoder()
    lines = stripped.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if not lines[index].lstrip().startswith(("{", "[")):
            continue
        tail = "\n".join(lines[index:]).lstrip()
        try:
            value, end = decoder.raw_decode(tail)
        except json.JSONDecodeError:
            continue
        if not tail[end:].strip():
            return value
    raise BridgeError(f"Unable to parse JSON from editor output:\n{stripped}")


class BridgeClient:
    def __init__(
        self,
        skill_root: Path,
        project: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        # Constructing the client is where a tool's live step begins; refuse retired tools here,
        # before any network call, and say what to use instead.
        tool = _caller_tool()
        entry = retired_tool(Path(skill_root), tool)
        if entry:
            offline = entry.get("offline", "none")
            raise RetiredTool(
                f"{tool}'s live editor step is not ported to MCP yet (it used the retired UnrealBridge plugin). "
                f"Instead: {entry.get('instead', 'use builtin_mcp.py')}."
                + (f" Still works offline: {offline}." if offline and offline != "none" else "")
            )
        if endpoint:
            raise BridgeError("--endpoint targeted the retired UnrealBridge TCP server; select the editor with --project")
        self._remote = _load_python_remote(Path(skill_root))
        self.project = project
        self.timeout_seconds = timeout_seconds

    def ping(self) -> Any:
        try:
            with self._remote.PythonRemote(project=self.project) as remote:
                return remote.connect()
        except self._remote.RemoteError as exc:
            raise BridgeError(str(exc)) from exc

    def exec_python(self, script_text: str, *, no_preflight: bool = False) -> BridgeResult:
        del no_preflight  # The UnrealBridge AST preflight no longer exists.
        retired = sorted(set(RETIRED_LIBRARY.findall(script_text)))
        if retired:
            raise BridgeError(
                f"This pipeline calls retired UnrealBridge APIs ({', '.join(retired)}). "
                "Perform the operation with Epic's built-in MCP tools (unreal-engine-mcp/scripts/builtin_mcp.py) instead."
            )
        try:
            result = self._remote.run_python(script_text, project=self.project)
        except self._remote.RemoteError as exc:
            raise BridgeError(str(exc)) from exc
        stdout = self._remote.stdout_of(result)
        errors = self._remote.stdout_of(result, kinds=("Warning", "Error"))
        if not result.get("success"):
            raise BridgeError(errors or str(result.get("result")) or "Editor script failed")
        return BridgeResult(stdout=stdout, stderr=errors)

    def exec_json(self, script_text: str, *, no_preflight: bool = False) -> Any:
        result = self.exec_python(script_text, no_preflight=no_preflight)
        return parse_json_output(result.stdout)
