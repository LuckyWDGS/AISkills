"""Streamable-HTTP client for Epic's built-in Unreal Engine MCP server."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .editor import check_expected_project, connection_hint, endpoint_owner
from .protocol import (
    McpError, SessionExpired, _check_tool_result, _decode_response, _decode_text_value,
    _extract_text, _parse_toolsets, unwrap_result,
)
from .schema import _schema_tools, argument_problems, signature, suggest


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
            if exc.code == 404 and "route_handler_not_found" in detail:
                path = urllib.parse.urlparse(self.url).path or "/"
                raise McpError(f"The server at {self.url} has no handler for {path!r}; UE's MCP route is /mcp "
                               "(ModelContextProtocolSettings.ServerUrlPath).") from exc
            raise McpError(f"HTTP {exc.code} from {self.url}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise McpError(f"Cannot connect to Unreal MCP at {self.url}: {exc.reason}. {connection_hint(self.url)}") from exc

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
            hint = f". {connection_hint(self.url)}" if "connect" in stderr.lower() else ""
            raise McpError(f"curl failed for {self.url}: {stderr.rstrip('.')}{hint}")
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
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise McpError(f"Toolset {name!r} is ambiguous: {matches}. Pass the full name.")
        hint = suggest(name, [item.rsplit(".", 1)[-1] for item in names])
        raise McpError(f"Toolset {name!r} is not in the live inventory"
                       + (f"; did you mean {hint!r}?" if hint else "; run list-toolsets.")
                       + " A missing toolset can also mean its Epic plugin is disabled.")

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

    def missing_tool_message(self, toolset: str, tool: str) -> str:
        names = [item.get("name", "").rsplit(".", 1)[-1] for item in _schema_tools(self.describe_toolset(toolset))]
        hint = suggest(tool, names)
        return (f"Tool {tool!r} is not in {toolset.rsplit('.', 1)[-1]}"
                + (f"; did you mean {hint!r}?" if hint else f"; run describe-toolset {toolset.rsplit('.', 1)[-1]} --brief."))

    def call_resolved_tool(self, toolset: str, tool: str, arguments: dict[str, Any]) -> Any:
        toolset = self.resolve_toolset(toolset)
        entry = self.find_tool(toolset, tool)
        if entry is None:
            raise McpError(self.missing_tool_message(toolset, tool))
        problems = argument_problems(entry, arguments)
        if problems:
            raise McpError(f"{toolset.rsplit('.', 1)[-1]}.{tool}: {'; '.join(problems)}. Expected {signature(entry)}")
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

    def pie_running(self) -> bool:
        """Whether Play-In-Editor (or Simulate) runs; asset queries are unreliable while it does."""
        return bool(unwrap_result(self.call_resolved_tool("EditorAppToolset", "IsPIERunning", {})))

    def package_dirty(self, package: str) -> bool | None:
        """Unsaved state of one package; None when it does not exist (yet)."""
        try:
            return bool(unwrap_result(self.call_resolved_tool("AssetTools", "is_dirty", {"asset_path": package})))
        except McpError:
            return None

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
