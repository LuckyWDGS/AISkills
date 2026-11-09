"""Identify the local editor process behind an MCP endpoint."""

from __future__ import annotations

import json
import ntpath
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from .protocol import McpError


def endpoint_owner(url: str) -> dict[str, Any]:
    """Identify the local editor process listening on a loopback MCP URL.

    Returns pid, executable, .uproject, project name and engine version when
    they can be read; ``{"known": False, ...}`` otherwise. Read-only.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return {"known": False, "reason": "non-local endpoint"}
    port = parsed.port or 80
    try:
        if sys.platform == "win32":
            # netstat finds the listener in ~50 ms; Get-NetTCPConnection takes over a second.
            listing = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                                     errors="replace", timeout=10).stdout
            pid = next((int(cols[-1]) for cols in (line.split() for line in listing.splitlines())
                        if len(cols) >= 5 and cols[-2].upper() == "LISTENING"
                        and cols[1].rsplit(":", 1)[-1] == str(port)), None)
            if pid is None:
                return {"known": False, "reason": f"no process is listening on port {port}"}
            script = (f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | "
                      "Select-Object ExecutablePath,CommandLine,CreationDate | ConvertTo-Json -Compress")
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            info = json.loads(proc.stdout) if proc.stdout.strip() else {}
            exe, command = info.get("ExecutablePath") or "", info.get("CommandLine") or ""
            started = info.get("CreationDate")
        else:
            proc = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fp"],
                                  capture_output=True, text=True, timeout=10)
            pids = [line[1:] for line in proc.stdout.splitlines() if line.startswith("p")]
            if not pids:
                return {"known": False, "reason": f"no process is listening on port {port}"}
            pid = int(pids[0])
            command = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                                     capture_output=True, text=True, timeout=10).stdout.strip()
            exe = command.split(" ", 1)[0]
            started = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                                     capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"known": False, "reason": f"process lookup failed: {exc}"}

    match = re.search(r'"([^"]+\.uproject)"|(\S+\.uproject)', command, re.IGNORECASE)
    uproject = (match.group(1) or match.group(2)) if match else ""
    owner: dict[str, Any] = {
        "known": bool(uproject), "pid": pid, "process_started": started,
        "executable": exe, "uproject": uproject,
        "project": Path(uproject).stem if uproject else "",
    }
    exe_path = Path(exe)
    if exe_path.name.lower().startswith("unrealeditor") and len(exe_path.parents) >= 4:
        build = exe_path.parents[2] / "Build" / "Build.version"  # <root>/Engine/Binaries/<Platform>/<exe>
        try:
            version = json.loads(build.read_text(encoding="utf-8"))
            owner["engine_version"] = f"{version['MajorVersion']}.{version['MinorVersion']}.{version['PatchVersion']}"
        except (OSError, KeyError, json.JSONDecodeError):
            pass
    if not uproject:
        owner["reason"] = "listener has no .uproject on its command line"
    return owner


def connection_hint(url: str) -> str:
    """What to check when nothing answered at ``url``: who holds the port, or how to start MCP."""
    parsed = urllib.parse.urlparse(url)
    owner = endpoint_owner(url)
    if owner.get("pid"):
        who = owner.get("project") or Path(str(owner.get("executable") or "")).name or "a process"
        return (f"Port {parsed.port} is held by {who} (pid {owner['pid']}) but it did not answer MCP at "
                f"{parsed.path or '/'}; check that editor's ModelContextProtocolSettings (ServerUrlPath /mcp).")
    if owner.get("reason") == "non-local endpoint":
        return "Check that the remote editor runs the ModelContextProtocol server and is reachable."
    return (f"Nothing is listening on port {parsed.port or 80}. Start the editor with the ModelContextProtocol "
            "plugin and bAutoStartServer=true, or launch it with -ModelContextProtocolStartServer; "
            "`builtin_mcp.py ensure` explains the options.")


def _project_path(value: str) -> str:
    """Normalize Windows project paths even when the offline tests run on Unix."""
    if re.match(r"^[a-zA-Z]:[/\\]", value) or value.startswith(("\\\\", "//")):
        return ntpath.normcase(ntpath.normpath(value))
    return os.path.normcase(os.path.abspath(value))


def same_editor_process(saved: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    """Only reuse an inventory when the OS identifies the same editor instance.

    Session acceptance is insufficient: UE can accept a token saved before a
    restart. Creation time also distinguishes recycled process ids. Older
    records without this information get one fresh initialization.
    """
    if not isinstance(saved, dict) or not saved.get("known") or not current.get("known"):
        return False
    keys = ("pid", "process_started", "executable", "uproject")
    return (all(saved.get(key) and current.get(key) for key in keys)
            and all(saved[key] == current[key] for key in keys)
            and saved.get("engine_version") == current.get("engine_version"))


def check_expected_project(owner: dict[str, Any], expected: str) -> None:
    if not owner.get("known"):
        raise McpError(f"Cannot confirm the MCP endpoint serves {expected!r}: {owner.get('reason')}")
    if "/" in expected or "\\" in expected:
        matches = bool(owner.get("uproject")) and _project_path(owner["uproject"]) == _project_path(expected)
    else:
        wanted = expected.lower().removesuffix(".uproject")
        matches = str(owner.get("project", "")).lower() == wanted
    if not matches:
        raise McpError(
            f"MCP endpoint is served by project {owner['project']!r} ({owner['uproject']}), not {expected!r}. "
            "Close or reconfigure the other editor, or point --url at the intended one."
        )
