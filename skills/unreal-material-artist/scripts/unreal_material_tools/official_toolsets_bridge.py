from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


TOOLSET_ALIASES = {
    "asset": "toolset_registry.toolsets.core.asset.AssetTools",
    "material": "toolset_registry.toolsets.core.material.MaterialTools",
    "material_instance": "toolset_registry.toolsets.core.material_instance.MaterialInstanceTools",
    "texture": "toolset_registry.toolsets.core.texture.TextureTools",
    "scene": "toolset_registry.toolsets.core.scene.SceneTools",
    "actor": "toolset_registry.toolsets.core.actor.ActorTools",
    "blueprint": "toolset_registry.toolsets.core.blueprint.BlueprintTools",
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


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Official Toolset Call",
        "",
        f"- Tool: `{report['qualified_tool']}`",
        f"- Success: `{report['success']}`",
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
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()

    qualified_tool = _qualify_tool_name(args.tool)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else {}
    script = (
        "import json\n"
        "import unreal\n"
        f"payload = {json.dumps(payload, ensure_ascii=False)!r}\n"
        f"result = unreal.UnrealBridgeToolsetRegistryLibrary.execute_qualified_tool({qualified_tool!r}, json.dumps(payload, ensure_ascii=False), True)\n"
        "output = None\n"
        "if result.json_output:\n"
        "    try:\n"
        "        output = json.loads(result.json_output)\n"
        "    except Exception:\n"
        "        output = result.json_output\n"
        "print(json.dumps({\n"
        "  'success': result.success,\n"
        "  'error': result.error,\n"
        "  'qualified_tool': result.qualified_tool_name,\n"
        "  'requested_toolset_name': result.requested_toolset_name,\n"
        "  'resolved_toolset_name': result.resolved_toolset_name,\n"
        "  'tool_name': result.tool_name,\n"
        "  'json_input': result.json_input,\n"
        "  'output': output,\n"
        "}, ensure_ascii=False))\n"
    )
    raw = client.exec_json(script)

    report = {
        "tool": "official_toolsets_bridge",
        "qualified_tool": qualified_tool,
        "success": raw["success"],
        "error": raw["error"],
        "input": payload,
        "output": raw.get("output"),
    }
    effect = slugify(args.effect or qualified_tool)
    stem = slugify(args.stem or qualified_tool.split(".")[-1])
    out = Path(args.out) if args.out else default_report_path(ctx, "official-toolsets", effect, stem, ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), _render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute confirmed editor/toolset operations through UnrealBridge and save a structured report.")
    parser.add_argument("tool", help="Qualified tool name or alias form like asset:duplicate, material:create, material_instance:set_scalar_parameter.")
    parser.add_argument("--input", help="Path to a JSON payload file. Defaults to {}.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
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
