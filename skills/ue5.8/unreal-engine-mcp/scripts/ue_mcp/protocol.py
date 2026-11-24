"""JSON-RPC/MCP message helpers and errors shared by the client and tools."""

from __future__ import annotations

import json
import re
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


def unwrap_result(result: Any) -> Any:
    """A tool's return value: one JSON text layer and ``returnValue`` removed, JSON-string payloads parsed."""
    value = _decode_text_value(result)
    if isinstance(value, dict) and set(value) == {"returnValue"}:
        value = value["returnValue"]
    if isinstance(value, str) and value.lstrip()[:1] in ("{", "["):
        try:
            value = json.loads(value)  # e.g. ObjectTools.get_properties returns a JSON string.
        except json.JSONDecodeError:
            pass
    return value
