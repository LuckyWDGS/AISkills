from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


def build_ue_script(path_prefix: str, max_results: int) -> str:
    return f"""
import json
import unreal

AL = unreal.UnrealBridgeAssetLibrary
MAT = unreal.UnrealBridgeMaterialLibrary
paths = AL.get_assets_by_class('/Script/Engine.MaterialInstanceConstant', False)
rows = []
count = 0
for soft in paths:
    path = soft.export_text()
    if {path_prefix!r} and not path.startswith({path_prefix!r}):
        continue
    chain = MAT.list_material_instance_chain(path)
    info = MAT.get_material_info(path)
    mi = MAT.get_material_instance_parameters(path)
    row = {{
        "path": path,
        "base_path": info.base_path,
        "parent_path": info.parent_path,
        "usage_flags": list(info.usage_flags),
        "chain_depth": len(chain.layers),
        "override_parameters": [
            {{"name": p.name, "param_type": p.param_type, "value": p.value}}
            for p in mi.parameters
        ],
    }}
    rows.append(row)
    count += 1
    if {max_results} > 0 and count >= {max_results}:
        break
print(json.dumps({{"instances": rows}}, ensure_ascii=False))
""".strip()


def build_report(raw: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for item in raw["instances"]:
        switches = sorted(
            [
                f"{param['name']}={param['value']}"
                for param in item.get("override_parameters") or []
                if str(param.get("param_type") or "").lower() == "staticswitch"
            ]
        )
        key = f"{item.get('base_path')}|{'|'.join(switches)}"
        group = groups.setdefault(
            key,
            {
                "base_path": item.get("base_path"),
                "switch_signature": switches,
                "instances": [],
                "max_chain_depth": 0,
            },
        )
        group["instances"].append(item["path"])
        group["max_chain_depth"] = max(group["max_chain_depth"], int(item.get("chain_depth") or 0))
    return {
        "tool": "shader_permutation_report",
        "groups": sorted(groups.values(), key=lambda g: (-len(g["instances"]), g["base_path"] or "")),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Shader Permutation Report", ""]
    for group in report["groups"]:
        lines.extend(
            [
                f"## {group['base_path']}",
                "",
                f"- Instances: `{len(group['instances'])}`",
                f"- Max chain depth: `{group['max_chain_depth']}`",
                f"- Switch signature: `{', '.join(group['switch_signature']) or 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.path_prefix, args.max_results))
    report = build_report(raw)
    out = Path(args.out) if args.out else default_report_path(ctx, "permutations", slugify(args.path_prefix or "all"), "shader-permutation-report", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Group material instances by static-switch signature to expose permutation sprawl.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--path-prefix", default="")
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
