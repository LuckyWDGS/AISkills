"""Group material instances by static-switch signature through Epic's built-in MCP.

One ProgrammaticToolset script reads each MaterialInstanceConstant under a folder:
its parent chain (asset tags), whether it compiles its own static permutation
(``HasStaticPermutationResource``), and the effective value of every static
switch (``MaterialInstanceTools.get_static_switch_parameter``). Instances sharing
a base material and switch values share shaders; each group is one permutation.
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, run_tool_script


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "shader_permutation_report/2"


def build_collect_script(folder: str, max_results: int) -> str:
    return textwrap.dedent(
        """
        import json

        FOLDER = __FOLDER__
        MAX = __MAX__
        A = "editor_toolset.toolsets.asset.AssetTools."
        MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools."

        def call(tool, **args):
            return json.loads(json.dumps(execute_tool(tool, json.dumps(args))["returnValue"]))

        def ref(path):
            leaf = path.rsplit("/", 1)[-1]
            return {"refPath": path if "." in leaf else path + "." + leaf}

        def run():
            paths = call(A + "find_assets", folder_path=FOLDER, name="", recursive=True, tags=None,
                         asset_type={"refPath": "/Script/Engine.MaterialInstanceConstant"})
            rows = []
            for path in paths[:MAX] if MAX > 0 else paths:
                tags = call(A + "get_asset_tags", asset_path=path)
                switches = {}
                for param in call(MI + "list_parameters", material=ref(path)):
                    if param.get("type") == "StaticSwitch":
                        switches[param["name"]] = call(MI + "get_static_switch_parameter", instance=ref(path), name=param["name"])
                chain = [tags.get("Parent", "")]
                while chain[-1] and "MaterialInstance" in chain[-1].split("'", 1)[0] and len(chain) < 16:
                    parent = chain[-1].split("'")[1].split(".")[0]
                    chain.append(call(A + "get_asset_tags", asset_path=parent).get("Parent", ""))
                rows.append({"path": path, "parents": chain, "switches": switches,
                             "has_static_permutation": tags.get("HasStaticPermutationResource") == "True"})
            return {"instances": rows, "total": len(paths)}
        """
    ).strip().replace("__FOLDER__", json.dumps(folder)).replace("__MAX__", str(int(max_results)))


def _object_path(tag: str) -> str:
    """"/Script/Engine.Material'/Game/M/M_X.M_X'" -> '/Game/M/M_X.M_X'."""
    match = re.search(r"'([^']+)'", tag or "")
    return match.group(1) if match else str(tag or "")


def build_report(raw: dict[str, Any], folder: str) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for item in raw["instances"]:
        parents = [_object_path(tag) for tag in item.get("parents") or [] if tag]
        base = parents[-1] if parents else ""
        switches = sorted(f"{name}={str(value).lower()}" for name, value in (item.get("switches") or {}).items())
        group = groups.setdefault(f"{base}|{'|'.join(switches)}", {
            "base_path": base, "switch_signature": switches, "instances": [], "max_chain_depth": 0,
            "own_permutation_instances": [],
        })
        group["instances"].append(item["path"])
        group["max_chain_depth"] = max(group["max_chain_depth"], len(parents))
        if item.get("has_static_permutation"):
            group["own_permutation_instances"].append(item["path"])
    ordered = sorted(groups.values(), key=lambda g: (-len(g["instances"]), g["base_path"]))
    return {
        "tool": "shader_permutation_report",
        "schema_version": SCHEMA_VERSION,
        "transport": "epic-mcp ProgrammaticToolset",
        "folder": folder,
        "instances_scanned": len(raw["instances"]),
        "instances_total": raw.get("total", len(raw["instances"])),
        "groups": ordered,
        "summary": {
            "groups": len(ordered),
            "bases": len({group["base_path"] for group in ordered}),
            "own_permutation_instances": sum(len(group["own_permutation_instances"]) for group in ordered),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Shader Permutation Report", "",
        f"- Folder: `{report['folder']}` ({report['instances_scanned']}/{report['instances_total']} instances scanned)",
        f"- Groups: `{summary['groups']}` across `{summary['bases']}` base material(s); "
        f"`{summary['own_permutation_instances']}` instance(s) compile their own static permutation",
        "",
    ]
    for group in report["groups"]:
        lines.extend([
            f"## {group['base_path']}", "",
            f"- Instances: `{len(group['instances'])}` (own permutation: `{len(group['own_permutation_instances'])}`)",
            f"- Max chain depth: `{group['max_chain_depth']}`",
            f"- Switch signature: `{', '.join(group['switch_signature']) or 'none'}`",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    folder = (args.path_prefix or "/Game").rstrip("/") or "/Game"
    raw = run_tool_script(ctx.skill_root, build_collect_script(folder, args.max_results),
                          url=args.mcp_url, timeout=args.timeout, project=args.project)
    report = build_report(raw, folder)
    out = Path(args.out) if args.out else default_report_path(ctx, "permutations", slugify(folder), "shader-permutation-report", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Group material instances by static-switch signature to expose permutation sprawl.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project", help="Refuse to run unless the MCP endpoint is served by this project.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--path-prefix", default="/Game", help="Content folder to scan recursively.")
    parser.add_argument("--max-results", type=int, default=0)
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
