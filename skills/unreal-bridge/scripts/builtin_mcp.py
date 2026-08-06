#!/usr/bin/env python3
"""Small stdlib client for Unreal Engine 5.8's built-in MCP HTTP server."""

from __future__ import annotations

import argparse
import json
import queue
import re
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


class UnrealMcpClient:
    def __init__(self, url: str, protocol: str, timeout: float) -> None:
        self.url = url
        self.protocol = protocol
        self.timeout = timeout
        self.session_id: str | None = None
        self.next_id = 1
        self.initialize_result: dict[str, Any] | None = None

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
                    "clientInfo": {"name": "codex-unreal-bridge", "version": "1.0"},
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
        response = self._streaming_request(payload) if method == "tools/call" else self._request(payload)
        if not isinstance(response, dict):
            raise McpError(f"Invalid MCP response: {response!r}")
        if "error" in response:
            raise McpError(json.dumps(response["error"], ensure_ascii=False))
        if response.get("id") != request_id:
            raise McpError(f"MCP response id mismatch: expected {request_id}, got {response.get('id')}")
        return response.get("result")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return self.call("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self) -> None:
        if not self.session_id:
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


def _parse_toolsets(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        match = re.match(r"^- ([A-Za-z0-9_.]+):\s*(.*)$", line)
        if match:
            current = {"name": match.group(1), "description": match.group(2).strip()}
            entries.append(current)
        elif current and line.strip():
            current["description"] += ("\n" if current["description"] else "") + line.rstrip()
    return entries


def _start_via_bridge(url: str, timeout: float) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise McpError("Refusing to start an MCP listener for a non-local URL")
    port = parsed.port or 8000
    bridge = Path(__file__).with_name("bridge.py")
    code = (
        "from unreal_bridge import Editor; "
        f"print(Editor.execute_console_command(command='ModelContextProtocol.StartServer {port}'))"
    )
    process = subprocess.run(
        [sys.executable, str(bridge), "--json", "--timeout", str(max(5, int(timeout))), "exec", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout + 5,
    )
    if process.returncode != 0:
        raise McpError(f"Failed to start Unreal MCP through UnrealBridge: {process.stderr or process.stdout}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        return {"success": True, "output": process.stdout.strip()}


def _connect(args: argparse.Namespace, *, start_if_needed: bool = False) -> UnrealMcpClient:
    client = UnrealMcpClient(args.url, args.protocol, args.timeout)
    try:
        client.initialize()
        return client
    except McpError:
        if not start_if_needed:
            raise
    _start_via_bridge(args.url, args.timeout)
    deadline = time.monotonic() + min(max(args.timeout, 3), 20)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        client = UnrealMcpClient(args.url, args.protocol, args.timeout)
        try:
            client.initialize()
            return client
        except McpError as exc:
            last_error = exc
            time.sleep(0.5)
    raise McpError(f"Unreal MCP did not become ready after start: {last_error}")


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Print the complete MCP result as JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Initialize a session and print server capabilities")
    sub.add_parser("ensure", help="Emergency bootstrap: start official UE MCP through UnrealBridge only if unavailable")
    sub.add_parser("list-tools", help="List top-level MCP tools")
    sub.add_parser("list-resources", help="List MCP resources")
    sub.add_parser("list-toolsets", help="List discoverable Unreal toolsets")
    describe = sub.add_parser("describe-toolset", help="Describe every tool in one Unreal toolset")
    describe.add_argument("toolset_name")
    call = sub.add_parser("call", help="Call a top-level MCP tool or a toolset tool")
    call.add_argument("tool_name")
    call.add_argument("--toolset")
    call.add_argument("--args", default="{}", help="JSON object with tool arguments")
    inventory = sub.add_parser("inventory", help="Describe every discoverable toolset")
    inventory.add_argument("--output", help="Optional UTF-8 JSON output path")
    args = parser.parse_args()

    client: UnrealMcpClient | None = None
    try:
        client = _connect(args, start_if_needed=args.command == "ensure")
        if args.command in {"status", "ensure"}:
            value = {
                "url": args.url,
                "sessionId": client.session_id,
                **(client.initialize_result or {}),
            }
        elif args.command == "list-tools":
            value = client.call("tools/list")
        elif args.command == "list-resources":
            value = client.call("resources/list")
        elif args.command == "list-toolsets":
            result = client.call_tool("list_toolsets")
            value = result if args.json else _parse_toolsets(_extract_text(result))
        elif args.command == "describe-toolset":
            result = client.call_tool("describe_toolset", {"toolset_name": args.toolset_name})
            value = result if args.json else _decode_text_value(result)
        elif args.command == "call":
            arguments = _load_json_object(args.args)
            if args.toolset:
                result = client.call_tool(
                    "call_tool",
                    {"toolset_name": args.toolset, "tool_name": args.tool_name, "arguments": arguments},
                )
            else:
                result = client.call_tool(args.tool_name, arguments)
            value = result if args.json else _decode_text_value(result)
        elif args.command == "inventory":
            listed = client.call_tool("list_toolsets")
            toolsets = _parse_toolsets(_extract_text(listed))
            for index, toolset in enumerate(toolsets, start=1):
                described = client.call_tool("describe_toolset", {"toolset_name": toolset["name"]})
                toolset["details"] = _extract_text(described)
                toolset["index"] = index
            value = {
                "url": args.url,
                "protocolVersion": client.protocol,
                "count": len(toolsets),
                "toolsets": toolsets,
            }
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                value = {"output": str(output.resolve()), "count": len(toolsets)}
        else:
            raise AssertionError(args.command)
        _emit(value, args.json)
        return 0
    except (McpError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
