from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BridgeError(RuntimeError):
    pass


@dataclass(slots=True)
class BridgeResult:
    stdout: str
    stderr: str


def find_bridge_script(skill_root: Path) -> Path:
    candidates = [
        os.environ.get("UNREAL_BRIDGE_SCRIPT"),
        str(Path.home() / ".codex" / "skills" / "unreal-bridge" / "scripts" / "bridge.py"),
        str(skill_root.parent / "unreal-bridge" / "scripts" / "bridge.py"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    raise BridgeError("Unable to locate unreal-bridge/scripts/bridge.py")


def parse_json_output(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise BridgeError("Bridge returned empty stdout")
    for line in reversed(stripped.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"Unable to parse JSON from bridge stdout:\n{stripped}") from exc


class BridgeClient:
    def __init__(self, skill_root: Path, project: str | None = None, timeout_seconds: int = 120) -> None:
        self.bridge_script = find_bridge_script(skill_root)
        self.project = project
        self.timeout_seconds = timeout_seconds

    def _base_command(self) -> list[str]:
        command = [sys.executable, str(self.bridge_script)]
        if self.project:
            command.append(f"--project={self.project}")
        command.append(f"--timeout={self.timeout_seconds}")
        return command

    def ping(self) -> Any:
        command = self._base_command() + ["--json", "ping"]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        last_error = ""
        for attempt in range(3):
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(self.timeout_seconds, 15),
                env=env,
                check=False,
            )
            if proc.returncode == 0:
                return parse_json_output(proc.stdout)
            last_error = proc.stderr.strip() or proc.stdout.strip() or "Bridge ping failed"
            if "no UnrealBridge editors found" not in last_error or attempt == 2:
                break
            time.sleep(1.0 + attempt)
        raise BridgeError(last_error)

    def exec_python(self, script_text: str) -> BridgeResult:
        command = self._base_command() + ["exec", "--stdin"]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            command,
            input=script_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout_seconds,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            raise BridgeError(proc.stderr.strip() or proc.stdout.strip() or "Bridge exec failed")
        return BridgeResult(stdout=proc.stdout, stderr=proc.stderr)

    def exec_json(self, script_text: str) -> Any:
        result = self.exec_python(script_text)
        return parse_json_output(result.stdout)
