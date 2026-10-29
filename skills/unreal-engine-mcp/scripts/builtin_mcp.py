#!/usr/bin/env python3
"""Small stdlib client for Unreal Engine 5.8's built-in MCP HTTP server."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_PROTOCOL = "2025-11-25"


class McpError(RuntimeError):
    pass


class SessionExpired(McpError):
    """The server rejected the session id (HTTP 404); the request was not executed."""


def _decode_response(body: bytes, content_type: str) -> Any:
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    if "text/event-stream" not in content_type.lower() and not text.startswith("event:"):
        return json.loads(text)

    messages: list[Any] = []
    for block in re.split(r"\r?\n\r?\n", text):
        data_lines = []
        for line in block.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            messages.append(json.loads("\n".join(data_lines)))
    if not messages:
        raise McpError("MCP server returned an SSE response without a data event")
    return messages[-1]


def default_state_dir() -> Path:
    """Per-user client state: UE_MCP_CACHE_DIR, else LOCALAPPDATA / XDG cache."""
    override = os.environ.get("UE_MCP_CACHE_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "unreal-engine-mcp"


def default_cache_dir() -> Path:
    return default_state_dir() / "schemas"


def default_session_dir() -> Path:
    return default_state_dir() / "sessions"


class UnrealMcpClient:
    def __init__(self, url: str, protocol: str, timeout: float, *,
                 cache_dir: Path | None = None, refresh_schema: bool = False,
                 session_dir: Path | None = None, expected_project: str | None = None) -> None:
        self.url = url
        self.protocol = protocol
        self.timeout = timeout
        self.session_id: str | None = None
        self.next_id = 1
        self.initialize_result: dict[str, Any] | None = None
        self._tools: list[dict[str, Any]] | None = None
        self._toolsets: list[dict[str, Any]] | None = None
        self._schemas: dict[str, Any] = {}
        # Search-mode toolset schemas can be hundreds of KB; cache them per live inventory.
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.refresh_schema = refresh_schema
        self._schema_source: dict[str, str] = {}
        self._fingerprint: str | None = None
        # Reusing a session across CLI runs skips initialize, discovery and close (~300 ms each).
        # A session the server still accepts proves the same editor process, so the inventory and
        # editor identity saved with it stay valid; an expired one returns 404 and is re-initialized.
        self.session_dir = Path(session_dir) if session_dir else None
        self.session_reused = False
        self.expected_project = expected_project
        self._owner: dict[str, Any] | None = None

    def _request(self, payload: dict[str, Any], *, expect_body: bool = True) -> Any:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
            headers["Mcp-Protocol-Version"] = self.protocol
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_session = response.headers.get("Mcp-Session-Id")
                if response_session:
                    self.session_id = response_session
                body = response.read()
                if not body and not expect_body:
                    return None
                return _decode_response(body, response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404 and self.session_id:
                raise SessionExpired(f"Unknown MCP session {self.session_id}") from exc
            raise McpError(f"HTTP {exc.code} from {self.url}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise McpError(f"Cannot connect to Unreal MCP at {self.url}: {exc.reason}") from exc

    def _streaming_request(self, payload: dict[str, Any]) -> Any:
        """Call ``tools/call`` over either UE's SSE or JSON response mode.

        UE 5.8 builds differ here: some return a multi-write
        ``text/event-stream`` response, while others return one ordinary
        ``application/json`` response even when the client advertises both.
        Keep curl for the former (urllib can stop at the first empty SSE
        write), but parse the latter as a normal JSON body instead of waiting
        forever for a ``data:`` event.
        """
        curl = shutil.which("curl")
        if not curl:
            raise McpError("curl is required for UE MCP tools/call streaming responses")
        command = [
            curl,
            "--silent",
            "--show-error",
            "--no-buffer",
            "--include",
            "--request",
            "POST",
            self.url,
            "--header",
            "Content-Type: application/json",
            "--header",
            "Accept: application/json, text/event-stream",
        ]
        if self.session_id:
            command.extend(["--header", f"Mcp-Session-Id: {self.session_id}"])
            command.extend(["--header", f"Mcp-Protocol-Version: {self.protocol}"])
        command.extend(["--data-binary", json.dumps(payload, ensure_ascii=False)])
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lines: queue.Queue[bytes | None] = queue.Queue()

        def pump_stdout() -> None:
            assert process.stdout is not None
            for line in iter(process.stdout.readline, b""):
                lines.put(line)
            lines.put(None)

        threading.Thread(target=pump_stdout, daemon=True).start()

        def decode_native(data: bytes) -> str:
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("gb18030", errors="replace")

        deadline = time.monotonic() + self.timeout
        status: int | None = None
        content_type = ""
        in_body = False
        event_lines: list[str] = []
        body_lines: list[str] = []
        response: Any = None
        try:
            while time.monotonic() < deadline:
                try:
                    raw_line = lines.get(timeout=max(0.05, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if raw_line is None:
                    break
                line = decode_native(raw_line).rstrip("\r\n")
                if not in_body:
                    if status is None and line.startswith("HTTP/"):
                        fields = line.split()
                        if len(fields) >= 2 and fields[1].isdigit():
                            status = int(fields[1])
                    if line.lower().startswith("content-type:"):
                        content_type = line.split(":", 1)[1].strip().lower()
                    if line == "":
                        in_body = True
                    continue
                if "application/json" in content_type:
                    body_lines.append(line)
                    continue
                if line == "":
                    data = "\n".join(item[5:].lstrip() for item in event_lines if item.startswith("data:"))
                    event_lines.clear()
                    if data:
                        candidate = json.loads(data)
                        if isinstance(candidate, dict) and candidate.get("id") == payload.get("id"):
                            response = candidate
                            break
                    continue
                event_lines.append(line)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                _, stderr_bytes = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr_bytes = process.communicate()

        if status == 404 and self.session_id:
            raise SessionExpired(f"Unknown MCP session {self.session_id}")
        if status is not None and status >= 400:
            raise McpError(f"HTTP {status} from {self.url}")
        if response is None and "application/json" in content_type:
            body = "\n".join(body_lines).strip()
            if body:
                try:
                    candidate = json.loads(body)
                except json.JSONDecodeError as exc:
                    raise McpError(f"UE MCP returned invalid JSON: {exc}") from exc
                if isinstance(candidate, dict) and candidate.get("id") == payload.get("id"):
                    response = candidate
        if response is not None:
            return response
        stderr = decode_native(stderr_bytes).strip()
        if stderr:
            raise McpError(f"curl failed for {self.url}: {stderr}")
        raise McpError(f"Timed out waiting for the final SSE event from {self.url}")

    def initialize(self) -> dict[str, Any]:
        response = self._request(
            {
                "jsonrpc": "2.0",
                "id": self.next_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": self.protocol,
                    "capabilities": {},
                    "clientInfo": {"name": "codex-unreal-engine-mcp", "version": "1.0"},
                },
            }
        )
        self.next_id += 1
        if not isinstance(response, dict) or "result" not in response:
            raise McpError(f"Invalid initialize response: {response!r}")
        if response.get("error"):
            raise McpError(f"MCP initialize failed: {response['error']}")
        self.initialize_result = response["result"]
        negotiated = self.initialize_result.get("protocolVersion")
        if negotiated:
            self.protocol = negotiated
        self._request(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            expect_body=False,
        )
        return self.initialize_result

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.session_id:
            self.initialize()
        request_id = self.next_id
        self.next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        send = self._streaming_request if method == "tools/call" else self._request
        try:
            response = send(payload)
        except SessionExpired:
            if not self.session_reused:
                raise
            # A rejected session never executed the request, so re-sending after re-initializing is safe.
            self.reinitialize()
            request_id = payload["id"] = self.next_id
            self.next_id += 1
            response = send(payload)
        if not isinstance(response, dict):
            raise McpError(f"Invalid MCP response: {response!r}")
        if "error" in response:
            raise McpError(json.dumps(response["error"], ensure_ascii=False))
        if response.get("id") != request_id:
            raise McpError(f"MCP response id mismatch: expected {request_id}, got {response.get('id')}")
        return response.get("result")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return self.call("tools/call", {"name": name, "arguments": arguments or {}})

    def list_tools(self) -> list[dict[str, Any]]:
        """Read all pages; native-tool mode can exceed one tools/list page."""
        if self._tools is None:
            items: list[dict[str, Any]] = []
            params: dict[str, Any] = {}
            seen: set[str] = set()
            while True:
                page = self.call("tools/list", params)
                if not isinstance(page, dict) or not isinstance(page.get("tools"), list):
                    raise McpError("Invalid tools/list response")
                items.extend(page["tools"])
                cursor = page.get("nextCursor")
                if not cursor:
                    break
                if cursor in seen:
                    raise McpError("Repeated tools/list pagination cursor")
                seen.add(cursor)
                params = {"cursor": cursor}
            self._tools = items
        return self._tools

    def search_mode(self) -> bool:
        return {"list_toolsets", "describe_toolset", "call_tool"}.issubset(
            {tool["name"] for tool in self.list_tools()}
        )

    def list_toolsets(self) -> list[dict[str, Any]]:
        if self._toolsets is None:
            if self.search_mode():
                result = self.call_tool("list_toolsets")
                _check_tool_result(result)
                self._toolsets = _parse_toolsets(_extract_text(result))
            else:
                groups: dict[str, list[dict[str, Any]]] = {}
                for tool in self.list_tools():
                    prefix, sep, _ = tool["name"].rpartition(".")
                    if sep:
                        groups.setdefault(prefix, []).append(tool)
                self._toolsets = [
                    {"name": name, "description": "", "tool_count": len(items)}
                    for name, items in sorted(groups.items())
                ]
        return self._toolsets

    def resolve_toolset(self, name: str) -> str:
        names = [item["name"] for item in self.list_toolsets()]
        if name in names:
            return name
        # Match class suffixes, never an old hard-coded module namespace.
        matches = [item for item in names if item.rsplit(".", 1)[-1] == name]
        if len(matches) != 1:
            raise McpError(f"Toolset {name!r} is absent or ambiguous; matches: {matches}. Run list-toolsets.")
        return matches[0]

    def _url_key(self) -> str:
        return hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:8]

    def schema_fingerprint(self) -> str:
        """Hash of the live inventory; a changed plugin/toolset set invalidates cached schemas."""
        if self._fingerprint is None:
            inventory = {
                "tools": sorted((tool.get("name", ""), json.dumps(tool.get("inputSchema"), sort_keys=True))
                                for tool in self.list_tools()),
                "toolsets": self.list_toolsets(),
            }
            text = json.dumps(inventory, sort_keys=True, ensure_ascii=False)
            self._fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return self._fingerprint

    def _cache_file(self, name: str) -> Path | None:
        if not self.cache_dir or not self.search_mode():
            return None  # Native mode already carries every schema in tools/list.
        return self.cache_dir / f"{self._url_key()}-{self.schema_fingerprint()}" / f"{name}.json"

    def _write_cache(self, path: Path, schema: Any) -> None:
        try:
            if self.cache_dir and self.cache_dir.is_dir():
                prefix = f"{self._url_key()}-"
                for stale in self.cache_dir.iterdir():
                    if stale.is_dir() and stale.name.startswith(prefix) and stale != path.parent:
                        shutil.rmtree(stale, ignore_errors=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            temp.replace(path)
        except OSError:
            pass  # The cache is an optimisation; never fail a call because of it.

    def invalidate_schema(self, name: str) -> None:
        self._schemas.pop(name, None)
        self._schema_source.pop(name, None)
        path = self._cache_file(name)
        if path:
            path.unlink(missing_ok=True)

    def describe_toolset(self, name: str) -> Any:
        name = self.resolve_toolset(name)
        if name not in self._schemas:
            cache = self._cache_file(name)
            if cache and cache.is_file() and not self.refresh_schema:
                try:
                    self._schemas[name] = json.loads(cache.read_text(encoding="utf-8"))
                    self._schema_source[name] = "cache"
                    return self._schemas[name]
                except (OSError, json.JSONDecodeError):
                    pass
            if self.search_mode():
                result = self.call_tool("describe_toolset", {"toolset_name": name})
                _check_tool_result(result)
                schema = _decode_text_value(result)
                if not isinstance(schema, dict):
                    raise McpError(f"Invalid schema returned for {name}")
            else:
                schema = {"tools": [
                    tool for tool in self.list_tools()
                    if tool["name"].rpartition(".")[0] == name
                ]}
            self._schemas[name] = schema
            self._schema_source[name] = "live"
            if cache:
                self._write_cache(cache, schema)
        return self._schemas[name]

    def find_tool(self, toolset: str, tool: str) -> dict[str, Any] | None:
        """The tool's schema entry, or None. A cache miss is re-checked against the live schema."""
        toolset = self.resolve_toolset(toolset)
        for attempt in range(2):
            candidates = [
                item for item in _schema_tools(self.describe_toolset(toolset))
                if item.get("name") in {tool, f"{toolset}.{tool}"}
            ]
            if len(candidates) == 1:
                return candidates[0]
            if attempt == 0 and self._schema_source.get(toolset) == "cache":
                self.invalidate_schema(toolset)
                continue
            return None
        return None

    def call_resolved_tool(self, toolset: str, tool: str, arguments: dict[str, Any]) -> Any:
        toolset = self.resolve_toolset(toolset)
        entry = self.find_tool(toolset, tool)
        if entry is None:
            raise McpError(f"Tool {tool!r} not found in live schema for {toolset}; run describe-toolset.")
        if self.search_mode():
            result = self.call_tool("call_tool", {
                "toolset_name": toolset, "tool_name": tool, "arguments": arguments,
            })
        else:
            result = self.call_tool(entry["name"], arguments)
        if isinstance(result, dict) and result.get("isError") and self._schema_source.get(toolset) == "cache":
            # The call may have failed on a stale cached schema; refresh it for the next run, never retry here.
            self.invalidate_schema(toolset)
        _check_tool_result(result)
        return result

    def run_tool_script(self, script: str) -> Any:
        """Run a ProgrammaticToolset script (``def run() -> dict``) in one round trip.

        Inside the script, ``execute_tool(full_tool_name, json_text)`` calls any
        registered tool. Returns the decoded dict from ``run()``.
        """
        result = self.call_resolved_tool("ProgrammaticToolset", "execute_tool_script", {"script": script})
        value = _decode_text_value(result)
        if isinstance(value, dict) and set(value) == {"returnValue"}:
            value = value["returnValue"]
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        return value

    def _session_file(self) -> Path | None:
        return self.session_dir / f"{self._url_key()}.json" if self.session_dir else None

    def open(self) -> "UnrealMcpClient":
        """Resume a saved session when one exists, else initialize a new one."""
        path = self._session_file()
        record: dict[str, Any] = {}
        if path and path.is_file():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                record = {}
        if record.get("url") == self.url and record.get("session_id"):
            self.session_id = record["session_id"]
            self.protocol = record.get("protocol") or self.protocol
            self.initialize_result = record.get("initialize_result")
            self._tools = record.get("tools")
            self._toolsets = record.get("toolsets")
            self._owner = record.get("owner")
            self.session_reused = True
            # Fresh JSON-RPC ids so concurrent runs sharing a session never collide.
            self.next_id = secrets.randbelow(10**9) + 1000
        else:
            self.initialize()
        try:
            self._check_expected_project()
        except McpError:
            if not self.session_reused:
                raise
            self.reinitialize()  # The saved identity may predate an editor switch; re-check against a fresh session.
        return self

    def reinitialize(self) -> None:
        self.session_id = None
        self.session_reused = False
        self._tools = self._toolsets = self._owner = self._fingerprint = None
        self._schemas.clear()
        self._schema_source.clear()
        self.initialize()
        self._check_expected_project()

    def editor_owner(self) -> dict[str, Any]:
        if self._owner is None:
            self._owner = endpoint_owner(self.url)
        return self._owner

    def _check_expected_project(self) -> None:
        if self.expected_project:
            check_expected_project(self.editor_owner(), self.expected_project)

    def save_session(self) -> None:
        path = self._session_file()
        if not path or not self.session_id:
            return
        record = {
            "url": self.url, "session_id": self.session_id, "protocol": self.protocol,
            "initialize_result": self.initialize_result, "tools": self._tools,
            "toolsets": self._toolsets, "owner": self._owner, "saved_at": time.time(),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(f".{os.getpid()}.tmp")
            temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            temp.replace(path)
        except OSError:
            pass

    def close(self) -> None:
        if not self.session_id:
            return
        if self.session_dir:
            self.save_session()  # Keep the session open for the next run.
            return
        headers = {
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": self.session_id,
            "Mcp-Protocol-Version": self.protocol,
        }
        request = urllib.request.Request(self.url, headers=headers, method="DELETE")
        try:
            urllib.request.urlopen(request, timeout=min(self.timeout, 5)).close()
        except Exception:
            pass
        self.session_id = None


def _extract_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    parts = []
    for item in result.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    return "\n".join(parts)


def _decode_text_value(result: Any) -> Any:
    """Decode the JSON string that many UE toolsets wrap inside MCP text content."""
    text = _extract_text(result)
    if not text:
        return result
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _check_tool_result(result: Any) -> None:
    if isinstance(result, dict) and result.get("isError"):
        raise McpError(_extract_text(result) or "UE MCP tool returned isError=true")


def _parse_toolsets(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        match = re.match(r"^- ([A-Za-z0-9_.]+)(?::\s*(.*))?$", line)
        if match:
            current = {"name": match.group(1), "description": (match.group(2) or "").strip()}
            entries.append(current)
        elif current and line.strip():
            current["description"] += ("\n" if current["description"] else "") + line.rstrip()
    return entries


def _schema_tools(described: Any) -> list[dict[str, Any]]:
    tools = described.get("tools", []) if isinstance(described, dict) else []
    if isinstance(tools, dict):
        tools = [{"name": name, **value} for name, value in tools.items()]
    return [tool for tool in tools if isinstance(tool, dict)]


def _type_label(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "any"
    if schema.get("type") == "array":
        return f"list[{_type_label(schema.get('items'))}]"
    title = schema.get("title")
    if title:
        # UObject references are titled with their class path, e.g. /Script/Engine.Material.
        return title.rsplit(".", 1)[-1] if title.startswith("/Script/") else title
    return str(schema.get("type") or "any")


def brief_tools(described: Any) -> list[dict[str, Any]]:
    """Compact signatures: name, params (required first), return type, first description line."""
    rows = []
    for tool in _schema_tools(described):
        schema = tool.get("inputSchema") or {}
        required = set(schema.get("required") or [])
        params = [
            {"name": key, "type": _type_label(value), "required": key in required}
            for key, value in (schema.get("properties") or {}).items()
        ]
        params.sort(key=lambda item: not item["required"])
        output = ((tool.get("outputSchema") or {}).get("properties") or {}).get("returnValue")
        summary = next((line.strip() for line in (tool.get("description") or "").splitlines() if line.strip()), "")
        rows.append({
            "name": tool.get("name", "").rsplit(".", 1)[-1],
            "params": params,
            "returns": _type_label(output) if output else "",
            "summary": summary[:120],
        })
    return rows


def render_brief(toolset: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"{toolset} ({len(rows)} tools; * = required; describe-tool <toolset> <tool> for the full schema)"]
    for row in rows:
        params = ", ".join(f"{p['name']}{'*' if p['required'] else ''}: {p['type']}" for p in row["params"])
        returns = f" -> {row['returns']}" if row["returns"] else ""
        lines.append(f"  {row['name']}({params}){returns}  # {row['summary']}")
    return "\n".join(lines)


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


def load_batch(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL batch: one {"toolset", "tool", "args"?, "readback"?, "expect"?, "label"?} per line."""
    entries = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            entry = json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpError(f"{path}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(entry, dict):
            raise McpError(f"{path}:{number}: each line must be a JSON object")
        entries.append({**entry, "_line": number})
    return entries


def _unwrap(result: Any) -> Any:
    value = _decode_text_value(result)
    return value["returnValue"] if isinstance(value, dict) and set(value) == {"returnValue"} else value


def _expectation_met(expect: Any, actual: Any) -> bool:
    if isinstance(expect, dict) and isinstance(actual, dict):
        return all(key in actual and _expectation_met(value, actual[key]) for key, value in expect.items())
    if isinstance(expect, list) and isinstance(actual, list):
        return len(expect) == len(actual) and all(map(_expectation_met, expect, actual))
    if isinstance(expect, bool) or isinstance(actual, bool):
        return type(expect) is type(actual) and expect == actual
    numbers = (int, float)
    if isinstance(expect, numbers) and isinstance(actual, numbers):
        # UE stores most values as float32: 0.4 reads back as 0.4000000059604645.
        return math.isclose(expect, actual, rel_tol=1e-6, abs_tol=1e-6)
    return expect == actual


def validate_batch(client: UnrealMcpClient, entries: list[dict[str, Any]]) -> list[str]:
    """Check every call and readback against the live schema before anything runs."""
    problems = []
    for entry in entries:
        for step, spec in (("call", entry), ("readback", entry.get("readback"))):
            if spec is None:
                continue
            where = f"line {entry['_line']} {step}"
            if not isinstance(spec, dict) or not spec.get("toolset") or not spec.get("tool"):
                problems.append(f"{where}: needs \"toolset\" and \"tool\"")
                continue
            if not isinstance(spec.get("args", {}), dict):
                problems.append(f"{where}: \"args\" must be an object")
                continue
            try:
                schema = client.find_tool(spec["toolset"], spec["tool"])
            except McpError as exc:
                problems.append(f"{where}: {exc}")
                continue
            if schema is None:
                problems.append(f"{where}: tool {spec['tool']!r} not in {spec['toolset']}")
                continue
            # UE marks some documented-optional fields required; pass explicit empty values for them.
            required = (schema.get("inputSchema") or {}).get("required") or []
            missing = [key for key in required if key not in (spec.get("args") or {})]
            if missing:
                problems.append(f"{where}: {spec['tool']} is missing required args {missing}")
        if "expect" in entry and not entry.get("readback"):
            problems.append(f"line {entry['_line']}: \"expect\" needs a \"readback\"")
    return problems


def run_batch(client: UnrealMcpClient, entries: list[dict[str, Any]], *,
              dry_run: bool = False, continue_on_error: bool = False) -> dict[str, Any]:
    """Run calls sequentially in one session; stop at the first failure unless told otherwise.

    Unlike ProgrammaticToolset scripts, each call is a separate request with its own result,
    so earlier successful steps are reported even when a later one fails. Nothing is retried.
    """
    problems = validate_batch(client, entries)
    if problems or dry_run:
        return {"ok": not problems, "validated": not problems, "dry_run": dry_run, "problems": problems,
                "planned": [f"{e['toolset']}.{e['tool']}" for e in entries if not problems]}
    results: list[dict[str, Any]] = []
    stopped = False
    for index, entry in enumerate(entries):
        row: dict[str, Any] = {"index": index, "line": entry["_line"], "label": entry.get("label", ""),
                               "tool": f"{entry['toolset']}.{entry['tool']}"}
        if stopped:
            results.append({**row, "status": "skipped"})
            continue
        try:
            row["result"] = _unwrap(client.call_resolved_tool(entry["toolset"], entry["tool"], entry.get("args") or {}))
            row["status"] = "ok"
        except McpError as exc:
            row.update(status="error", error=str(exc))
        readback = entry.get("readback")
        if row["status"] == "ok" and readback:
            try:
                actual = _unwrap(client.call_resolved_tool(readback["toolset"], readback["tool"], readback.get("args") or {}))
                row["readback"] = {"tool": f"{readback['toolset']}.{readback['tool']}", "result": actual}
                if "expect" in entry and not _expectation_met(entry["expect"], actual):
                    row.update(status="mismatch", error=f"readback {actual!r} does not match expect {entry['expect']!r}")
            except McpError as exc:
                row.update(status="readback_error", error=str(exc))
        results.append(row)
        stopped = row["status"] != "ok" and not continue_on_error
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"ok": counts.get("ok", 0) == len(results), "validated": True, "counts": counts, "results": results}


def _connect(args: argparse.Namespace) -> UnrealMcpClient:
    client = UnrealMcpClient(
        args.url, args.protocol, args.timeout,
        cache_dir=None if args.no_cache else default_cache_dir(),
        refresh_schema=args.refresh_schema,
        session_dir=None if args.new_session else default_session_dir(),
        expected_project=args.expect_project,
    )
    try:
        client.open()
    except McpError as exc:
        if args.command != "ensure":
            raise
        raise McpError(
            f"{exc}. Official MCP is unavailable. Enable Epic's ModelContextProtocol plugin and set "
            "bAutoStartServer=true in Editor > General > ModelContextProtocolSettings, or launch with "
            "-ModelContextProtocolStartServer -ModelContextProtocolPort=8000. This client never starts "
            "or relaunches an editor."
        ) from exc
    return client


def _current_level(client: UnrealMcpClient) -> str:
    try:
        value = _decode_text_value(client.call_resolved_tool("SceneTools", "get_current_level", {}))
    except McpError:
        return ""
    value = value.get("returnValue", value) if isinstance(value, dict) else value
    return value.get("refPath", "") if isinstance(value, dict) else str(value or "")


def _load_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise McpError(f"Invalid JSON arguments: {exc}") from exc
    if not isinstance(parsed, dict):
        raise McpError("Tool arguments must be a JSON object")
    return parsed


def _emit(value: Any, as_json: bool) -> None:
    if as_json or not isinstance(value, str):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Print the complete MCP result as JSON")
    parser.add_argument("--expect-project", default=os.environ.get("UE_MCP_PROJECT"),
                        help="Fail unless the endpoint is served by this project (name or .uproject); env UE_MCP_PROJECT")
    parser.add_argument("--no-cache", action="store_true", help="Do not read or write the toolset schema cache")
    parser.add_argument("--refresh-schema", action="store_true", help="Ignore cached schemas and fetch them live")
    parser.add_argument("--new-session", action="store_true",
                        help="Do not resume or keep a saved MCP session; initialize and close a fresh one")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Initialize a session and print server capabilities")
    sub.add_parser("ensure", help="Check official MCP; show native startup guidance if unavailable")
    sub.add_parser("list-tools", help="List top-level MCP tools")
    sub.add_parser("list-resources", help="List MCP resources")
    sub.add_parser("list-toolsets", help="List discoverable Unreal toolsets")
    describe = sub.add_parser("describe-toolset", help="Describe every tool in one Unreal toolset")
    describe.add_argument("toolset_name")
    describe.add_argument("--brief", action="store_true", help="One signature line per tool instead of the full schema")
    describe_tool = sub.add_parser("describe-tool", help="Full schema of one tool")
    describe_tool.add_argument("toolset_name")
    describe_tool.add_argument("tool_name")
    call = sub.add_parser("call", help="Call a top-level MCP tool or a toolset tool")
    call.add_argument("tool_name")
    call.add_argument("--toolset")
    call.add_argument("--args", default="{}", help="JSON object with tool arguments")
    call.add_argument("--args-file", help="Read UTF-8 JSON arguments from a file (recommended on PowerShell)")
    script = sub.add_parser("run-script", help="Run a ProgrammaticToolset script file (def run() -> dict) in one round trip")
    batch = sub.add_parser("batch", help="Run a JSONL file of calls sequentially in one session, with optional readback")
    batch.add_argument("batch_file")
    batch.add_argument("--dry-run", action="store_true", help="Only validate tools and required args against the live schema")
    batch.add_argument("--continue-on-error", action="store_true", help="Keep going after a failed step")
    batch.add_argument("--out", help="Write the full results here and print only a summary")
    script.add_argument("script_file")
    inventory = sub.add_parser("inventory", help="Describe every discoverable toolset")
    inventory.add_argument("--output", help="Optional UTF-8 JSON output path")
    args = parser.parse_args()

    client: UnrealMcpClient | None = None
    exit_code = 0
    try:
        client = _connect(args)
        if args.command in {"status", "ensure"}:
            value = {
                "url": args.url,
                "sessionId": client.session_id,
                **(client.initialize_result or {}),
                "session": "reused" if client.session_reused else "new",
                "editor": {**client.editor_owner(), "current_level": _current_level(client)},
            }
        elif args.command == "list-tools":
            value = {"tools": client.list_tools()}
        elif args.command == "list-resources":
            value = client.call("resources/list")
        elif args.command == "list-toolsets":
            value = client.list_toolsets()
        elif args.command == "describe-toolset":
            described = client.describe_toolset(args.toolset_name)
            if args.brief:
                rows = brief_tools(described)
                value = rows if args.json else render_brief(client.resolve_toolset(args.toolset_name), rows)
            else:
                value = described
        elif args.command == "describe-tool":
            value = client.find_tool(args.toolset_name, args.tool_name)
            if value is None:
                raise McpError(f"Tool {args.tool_name!r} not found in {client.resolve_toolset(args.toolset_name)}; "
                               "run describe-toolset --brief.")
        elif args.command == "call":
            arguments = _load_json_object(Path(args.args_file).read_text(encoding="utf-8-sig") if args.args_file else args.args)
            if args.toolset:
                result = client.call_resolved_tool(args.toolset, args.tool_name, arguments)
            else:
                result = client.call_tool(args.tool_name, arguments)
                _check_tool_result(result)
            value = result if args.json else _decode_text_value(result)
        elif args.command == "run-script":
            value = client.run_tool_script(Path(args.script_file).read_text(encoding="utf-8-sig"))
        elif args.command == "batch":
            value = run_batch(client, load_batch(args.batch_file), dry_run=args.dry_run,
                              continue_on_error=args.continue_on_error)
            if args.out:
                output = Path(args.out)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                value = {key: value[key] for key in ("ok", "validated", "counts", "problems") if key in value}
                value["out"] = str(output.resolve())
            exit_code = 0 if value["ok"] else 1
        elif args.command == "inventory":
            toolsets = [dict(item) for item in client.list_toolsets()]
            for index, toolset in enumerate(toolsets, start=1):
                described = client.describe_toolset(toolset["name"])
                toolset["schema"] = described
                toolset["details"] = json.dumps(described, ensure_ascii=False)
                toolset["tool_count"] = len(described.get("tools", []))
                toolset["index"] = index
            value = {
                "url": args.url,
                "protocolVersion": client.protocol,
                "count": len(toolsets),
                "tool_count": sum(item["tool_count"] for item in toolsets),
                "discovery_mode": "search" if client.search_mode() else "native",
                "server": client.initialize_result,
                "toolsets": toolsets,
            }
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                value = {"output": str(output.resolve()), "count": len(toolsets), "tool_count": value["tool_count"], "discovery_mode": value["discovery_mode"]}
        else:
            raise AssertionError(args.command)
        _emit(value, args.json)
        return exit_code
    except (McpError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
