from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .mcp import builtin_mcp, connect
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


TOOLSET_ALIASES = {
    "asset": "AssetTools",
    "material": "MaterialTools",
    "material_instance": "MaterialInstanceTools",
    "texture": "TextureTools",
    "object": "ObjectTools",
    "programmatic": "ProgrammaticToolset",
    "scene": "SceneTools",
    "actor": "ActorTools",
    "blueprint": "BlueprintTools",
}


def _qualify_tool_name(tool: str) -> str:
    if "." in tool:
        return tool
    if ":" not in tool:
        raise SystemExit("Tool must be either a fully qualified tool name or use alias form like `asset:exists`.")
    alias, local_tool = tool.split(":", 1)
    toolset = TOOLSET_ALIASES.get(alias.strip().lower())
    if not toolset:
        raise SystemExit(f"Unknown toolset alias `{alias}`. Expected one of: {sorted(TOOLSET_ALIASES)}")
    return f"{toolset}.{local_tool.strip()}"


def call_official(skill_root: Path, qualified_tool: str, payload: dict[str, Any], url: str, timeout: int) -> dict[str, Any]:
    """Call Epic directly. No plugin discovery, bootstrap, or automatic retry."""
    module = builtin_mcp(skill_root)
    client = connect(skill_root, url=url, timeout=timeout)
    try:
        toolset, _, tool = qualified_tool.rpartition(".")
        resolved = client.resolve_toolset(toolset)
        result = client.call_resolved_tool(resolved, tool, payload)
        return {
            "success": True, "error": "", "transport": "epic-mcp-http",
            "resolved_toolset_name": resolved, "output": module._decode_text_value(result),
        }
    finally:
        client.close()


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Official Toolset Call",
        "",
        f"- Tool: `{report['qualified_tool']}`",
        f"- Success: `{report['success']}`",
        f"- Transport: `{report.get('transport', 'unknown')}`",
        f"- Resolved toolset: `{report.get('resolved_toolset_name') or ''}`",
    ]
    if report.get("error"):
        lines.append(f"- Error: `{report['error']}`")
    lines.extend(
        [
            "",
            "## Input",
            "",
            "```json",
            json.dumps(report["input"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Output",
            "",
            "```json",
            json.dumps(report.get("output"), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    qualified_tool = _qualify_tool_name(args.tool)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig")) if args.input else {}
    if not isinstance(payload, dict):
        raise SystemExit("Input must be a JSON object.")
    try:
        raw = call_official(ctx.skill_root, qualified_tool, payload, args.mcp_url, args.timeout)
    except Exception as exc:
        raw = {"success": False, "error": str(exc), "transport": "epic-mcp-http"}

    report = {
        "tool": "official_toolsets_bridge",
        "qualified_tool": qualified_tool,
        "success": raw["success"],
        "error": raw["error"],
        "input": payload,
        "output": raw.get("output"),
        "transport": raw["transport"],
        "resolved_toolset_name": raw.get("resolved_toolset_name"),
    }
    effect = slugify(args.effect or qualified_tool)
    stem = slugify(args.stem or qualified_tool.split(".")[-1])
    out = Path(args.out) if args.out else default_report_path(ctx, "official-toolsets", effect, stem, ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), _render_markdown(report))
    print(out)
    return 0 if report["success"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call Epic's live MCP tools directly and save structured evidence.")
    parser.add_argument("tool", help="Qualified tool name or alias form like asset:exists, material:create_material, material_instance:set_scalar_parameter.")
    parser.add_argument("--input", help="Path to a JSON payload file. Defaults to {}.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--mcp-url", default=os.environ.get("UNREAL_MCP_URL", "http://127.0.0.1:8000/mcp"))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--stem")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
