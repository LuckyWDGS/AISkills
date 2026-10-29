"""Command line for Epic's built-in Unreal Engine MCP server (``builtin_mcp.py``)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .batch import load_batch, run_batch
from .client import UnrealMcpClient
from .paths import default_cache_dir, default_session_dir
from .protocol import DEFAULT_PROTOCOL, DEFAULT_URL, McpError, _check_tool_result, _decode_text_value
from .schema import brief_tools, render_brief


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


def _emit(value: Any, as_json: bool, save_to: str | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) if as_json or not isinstance(value, str) else value
    if save_to:
        # Write UTF-8 directly; piping through a GBK console or a default-encoding reader garbles CJK text.
        path = Path(save_to)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(json.dumps({"out": str(path.resolve()), "bytes": path.stat().st_size}))
    else:
        print(text)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Print the complete MCP result as JSON")
    parser.add_argument("--out", dest="save_to", help="Write the command's output to this UTF-8 file and print only its path")
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
    batch.add_argument("--allow-pie", action="store_true", help="Run even while Play-In-Editor is running (PIE-aware reads only)")
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
                raise McpError(client.missing_tool_message(client.resolve_toolset(args.toolset_name), args.tool_name))
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
                              continue_on_error=args.continue_on_error, allow_pie=args.allow_pie)
            if args.out:
                output = Path(args.out)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                value = {key: value[key] for key in ("ok", "validated", "counts", "problems", "left_dirty") if key in value}
                value["out"] = str(output.resolve())
            exit_code = 0 if value["ok"] and not value.get("left_dirty") else 1
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
        _emit(value, args.json, args.save_to)
        return exit_code
    except (McpError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()
