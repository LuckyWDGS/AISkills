"""Identify the local editor process behind an MCP endpoint."""

from __future__ import annotations

import json
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
                      "Select-Object ExecutablePath,CommandLine | ConvertTo-Json -Compress")
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            info = json.loads(proc.stdout) if proc.stdout.strip() else {}
            exe, command = info.get("ExecutablePath") or "", info.get("CommandLine") or ""
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
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"known": False, "reason": f"process lookup failed: {exc}"}

    match = re.search(r'"([^"]+\.uproject)"|(\S+\.uproject)', command, re.IGNORECASE)
    uproject = (match.group(1) or match.group(2)) if match else ""
    owner: dict[str, Any] = {
        "known": bool(uproject), "pid": pid, "executable": exe, "uproject": uproject,
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


def check_expected_project(owner: dict[str, Any], expected: str) -> None:
    wanted = expected.replace("\\", "/").lower()
    wanted = wanted.rsplit("/", 1)[-1]
    wanted = wanted[: -len(".uproject")] if wanted.endswith(".uproject") else wanted
    if not owner.get("known"):
        raise McpError(f"Cannot confirm the MCP endpoint serves {expected!r}: {owner.get('reason')}")
    if owner["project"].lower() != wanted:
        raise McpError(
            f"MCP endpoint is served by project {owner['project']!r} ({owner['uproject']}), not {expected!r}. "
            "Close or reconfigure the other editor, or point --url at the intended one."
        )
