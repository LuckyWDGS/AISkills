"""Background client for Epic's PythonScriptPlugin Remote Execution.

Use only for an operation the built-in MCP does not cover. It loads the
``remote_execution`` module shipped with the selected engine, discovers
editors over loopback multicast, requires exactly one matching target and
runs a script without touching editor UI.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any


MODULE_RELATIVE = Path("Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py")


class RemoteError(RuntimeError):
    pass


def _engine_version(root: Path) -> tuple[int, ...]:
    for base in (root, root / "Engine"):
        try:
            data = json.loads((base / "Build" / "Build.version").read_text(encoding="utf-8"))
            return (int(data["MajorVersion"]), int(data["MinorVersion"]), int(data["PatchVersion"]))
        except (OSError, KeyError, ValueError):
            continue
    return (0,)


def _running_engine_roots(project: str | None = None) -> list[Path]:
    """Engine roots of running UnrealEditor processes (Windows only).

    The editor whose command line names ``project`` comes first, then newer engines:
    the client module is only a transport, but newer copies carry fixes.
    """
    if sys.platform != "win32":
        return []
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | "
        "Select-Object ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, check=False,
        )
        rows = json.loads(proc.stdout) if proc.stdout.strip() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    rows = rows if isinstance(rows, list) else [rows]
    wanted = (project or "").replace("\\", "/").lower().rsplit("/", 1)[-1].removesuffix(".uproject")
    ranked: dict[Path, tuple[bool, tuple[int, ...]]] = {}
    for row in rows:
        exe = Path(str(row.get("ExecutablePath") or ""))
        # <root>/Engine/Binaries/Win64/UnrealEditor.exe
        if exe.name.lower() == "unrealeditor.exe" and len(exe.parents) >= 4:
            root = exe.parents[3]
            serves = bool(wanted) and wanted in str(row.get("CommandLine") or "").replace("\\", "/").lower()
            best = ranked.get(root, (False, (0,)))
            ranked[root] = (serves or best[0], _engine_version(root))
    return sorted(ranked, key=lambda root: ranked[root], reverse=True)


def _complete_messages(module: ModuleType) -> None:
    """Make Epic's command channel read whole messages.

    UE 5.3 reads one 8 KB ``recv``; UE 5.8 stops at the first short read. Either
    truncates results larger than ~8 KB. Keep reading until the bytes parse as JSON.
    """
    connection = getattr(module, "_RemoteExecutionCommandConnection", None)
    if connection is None or getattr(connection, "_ue_mcp_complete_messages", False):
        return

    def _receive_message(self, expected_type):
        data = b""
        while True:
            part = self._command_channel_socket.recv(module.DEFAULT_RECEIVE_BUFFER_SIZE)
            if not part:
                break
            data += part
            try:
                json.loads(data.decode("utf-8"))
                break
            except (UnicodeDecodeError, ValueError):
                continue
        if data:
            message = module._RemoteExecutionMessage(None, None)
            if message.from_json_bytes(data) and message.passes_receive_filter(self._node_id) and message.type_ == expected_type:
                return message
        raise RuntimeError("Remote party failed to send a valid response!")

    connection._receive_message = _receive_message
    connection._ue_mcp_complete_messages = True


def load_remote_module(engine_root: str | None = None, project: str | None = None) -> ModuleType:
    candidates = [Path(item) for item in (engine_root, os.environ.get("UE_ENGINE_ROOT")) if item]
    candidates += _running_engine_roots(project)
    for root in candidates:
        # Accept either <install> or <install>/Engine.
        for base in (root, root / "Engine"):
            path = base / MODULE_RELATIVE
            if path.is_file():
                spec = importlib.util.spec_from_file_location("ue_remote_execution", path)
                module = importlib.util.module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(module)
                _complete_messages(module)
                return module
    raise RemoteError(
        "Cannot locate Epic's remote_execution.py; pass --engine-root or set UE_ENGINE_ROOT "
        f"(looked for <engine>/{MODULE_RELATIVE.as_posix()})"
    )


def _matches(node: dict[str, Any], project: str | None) -> bool:
    if not project:
        return True
    wanted = project.replace("\\", "/").lower().rstrip("/")
    name = str(node.get("project_name", "")).lower()
    root = str(node.get("project_root", "")).replace("\\", "/").lower().rstrip("/")
    if wanted.endswith(".uproject"):
        wanted = wanted.rsplit("/", 1)[0] if "/" in wanted else wanted[: -len(".uproject")]
    return wanted in {name, root} or (bool(root) and root.endswith("/" + wanted))


class PythonRemote:
    """Context manager around one discovery session and one command connection."""

    def __init__(self, *, project: str | None = None, engine_root: str | None = None,
                 discovery_timeout: float = 5.0) -> None:
        self.project = project
        self.discovery_timeout = discovery_timeout
        self._module = load_remote_module(engine_root, project)
        self._remote = self._module.RemoteExecution()
        self.node: dict[str, Any] | None = None

    def __enter__(self) -> "PythonRemote":
        self._remote.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._remote.stop()

    def discover(self) -> list[dict[str, Any]]:
        """Wait until nodes stop appearing or the deadline passes."""
        deadline = time.monotonic() + self.discovery_timeout
        nodes: list[dict[str, Any]] = []
        stable_since = time.monotonic()
        while time.monotonic() < deadline:
            current = list(self._remote.remote_nodes)
            if len(current) != len(nodes):
                nodes, stable_since = current, time.monotonic()
            elif nodes and time.monotonic() - stable_since > 1.5:
                break
            time.sleep(0.1)
        return nodes

    def connect(self) -> dict[str, Any]:
        nodes = self.discover()
        matches = [node for node in nodes if _matches(node, self.project)]
        if len(matches) != 1:
            described = [f"{n.get('project_name')} ({n.get('engine_version')}) {n.get('project_root')}" for n in nodes]
            if not nodes:
                raise RemoteError(
                    "No editor answered Python Remote Execution discovery. Enable it in the target project "
                    "(Project Settings > Plugins > Python > Enable Remote Execution, bind 127.0.0.1, TTL 0); "
                    "see references/official-python-remote.md."
                )
            raise RemoteError(
                f"Need exactly one editor matching --project={self.project!r}; found {len(matches)} of: {described}"
            )
        self.node = matches[0]
        self._remote.open_command_connection(self.node["node_id"])
        return self.node

    def run(self, script: str, *, mode: str = "ExecuteFile") -> dict[str, Any]:
        if self.node is None:
            self.connect()
        return self._remote.run_command(script, unattended=True, exec_mode=mode)


def run_python(script: str, *, project: str | None = None, engine_root: str | None = None,
               discovery_timeout: float = 5.0) -> dict[str, Any]:
    """Run one script and return Epic's ``command_result`` plus the target node."""
    with PythonRemote(project=project, engine_root=engine_root, discovery_timeout=discovery_timeout) as remote:
        node = remote.connect()
        result = remote.run(script)
        return {"node": node, **result}


def stdout_of(result: dict[str, Any], *, kinds: tuple[str, ...] = ("Info",)) -> str:
    """Join the log lines of a ``command_result`` whose type is in ``kinds``.

    ``print`` output arrives as ``Info``; Python warnings as ``Warning`` and
    tracebacks as ``Error``.
    """
    return "\n".join(
        str(item.get("output", "")).rstrip("\r\n")
        for item in result.get("output", [])
        if item.get("type") in kinds
    )


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Project name, root folder or .uproject path; required with several editors")
    parser.add_argument("--engine-root", help="Engine install used to load remote_execution.py")
    parser.add_argument("--discovery-timeout", type=float, default=5.0)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("nodes", help="List editors that answer discovery")
    run = sub.add_parser("exec", help="Run a Python script in the matching editor")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="UTF-8 script file")
    source.add_argument("--code", help="Inline script text")
    source.add_argument("--stdin", action="store_true", help="Read the script from stdin")
    run.add_argument("--mode", default="ExecuteFile", choices=["ExecuteFile", "ExecuteStatement", "EvaluateStatement"])
    args = parser.parse_args()

    try:
        with PythonRemote(project=args.project, engine_root=args.engine_root,
                          discovery_timeout=args.discovery_timeout) as remote:
            if args.command == "nodes":
                print(json.dumps(remote.discover(), ensure_ascii=False, indent=2))
                return 0
            if args.file:
                script = Path(args.file).read_text(encoding="utf-8-sig")
            elif args.stdin:
                script = sys.stdin.read()
            else:
                script = args.code
            remote.connect()
            result = remote.run(script, mode=args.mode)
            print(json.dumps({"node": remote.node, **result}, ensure_ascii=False, indent=2))
            return 0 if result.get("success") else 1
    except RemoteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
