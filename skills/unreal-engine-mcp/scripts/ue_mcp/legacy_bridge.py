"""Editor Python execution for legacy pipelines, over Epic's Python Remote Execution.

UnrealBridge (custom plugin + TCP) is retired. ``BridgeClient`` keeps its old
interface so stock-``unreal.*`` scripts still run through Epic's
PythonScriptPlugin endpoint; scripts that call ``UnrealBridge*Library`` fail
fast and must be ported to built-in MCP tools.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


RETIRED_LIBRARY = re.compile(r"\bUnrealBridge\w*Library\b|\bunreal_bridge\b")


class BridgeError(RuntimeError):
    pass


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
