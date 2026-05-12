from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


def build_ue_script(path_prefix: str, max_results: int, include_graph: bool) -> str:
    return f"""
import json
import unreal

MAT = unreal.UnrealBridgeMaterialLibrary
items = []
for item in MAT.list_material_functions({path_prefix!r}, {max_results}):
    info = MAT.get_material_function(item.path)
    row = {{
        "name": info.name,
        "path": info.path,
        "description": info.description,
        "expose_to_library": info.expose_to_library,
        "library_category": info.library_category,
        "num_expressions": info.num_expressions,
        "inputs": [
            {{
                "name": port.name,
                "description": port.description,
                "port_type": port.port_type,
                "sort_priority": port.sort_priority,
                "default_value": port.default_value,
                "use_preview_value_as_default": port.use_preview_value_as_default,
            }}
            for port in info.inputs
        ],
        "outputs": [
            {{
                "name": port.name,
                "description": port.description,
                "port_type": port.port_type,
                "sort_priority": port.sort_priority,
            }}
            for port in info.outputs
        ],
    }}
    if {str(include_graph)}:
        graph = MAT.get_material_graph(item.path)
        row["graph"] = {{
            "found": graph.found,
            "nodes": [
                {{
                    "class_name": node.class_name,
                    "caption": node.caption,
                    "desc": node.desc,
                    "key_properties": node.key_properties,
                }}
                for node in graph.nodes
            ]
        }}
    items.append(row)
print(json.dumps({{"functions": items}}, ensure_ascii=False))
""".strip()


def lint_function(item: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not item.get("inputs"):
        add("info", "no_inputs", "Material function has no declared inputs.")
    for port in item.get("inputs") or []:
        if not port.get("name"):
            add("warning", "unnamed_input", "Material function has an unnamed input.")
        if port.get("use_preview_value_as_default") and not port.get("default_value"):
            add("warning", "preview_default", f"Input `{port.get('name')}` uses preview value as default but default text is empty.")
    if not item.get("outputs"):
        add("warning", "no_outputs", "Material function has no declared outputs.")
    if item.get("num_expressions", 0) > 80:
        add("info", "large_function", "Material function is large enough that it may want to be split or reviewed for reuse boundaries.")
    graph = item.get("graph") or {}
    node_blob = " ".join(
        f"{node.get('class_name','')} {node.get('caption','')} {node.get('key_properties','')}"
        for node in graph.get("nodes") or []
    ).lower()
    if node_blob.count("staticswitch") >= 3:
        add("warning", "switch_sprawl", "Material function appears to contain many static switches; review permutation cost.")
    return findings


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Material Function Linter", ""]
    for item in report["functions"]:
        lines.extend(
            [
                f"## {item['path']}",
                "",
                f"- Inputs: `{len(item.get('inputs') or [])}`",
                f"- Outputs: `{len(item.get('outputs') or [])}`",
                f"- Expressions: `{item.get('num_expressions')}`",
                "Findings:",
            ]
        )
        if item["findings"]:
            lines.extend(f"- [{f['severity']}] `{f['rule']}` {f['message']}" for f in item["findings"])
        else:
            lines.append("- No first-pass findings.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.path_prefix, args.max_results, args.include_graph))
    for item in raw["functions"]:
        item["findings"] = lint_function(item)
    out = Path(args.out) if args.out else default_report_path(ctx, "function-lints", slugify(args.path_prefix or "all"), "material-function-linter", ".json")
    save_json(out, raw)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(raw))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint Unreal material functions for common TA/system issues.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--path-prefix", default="")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--include-graph", action="store_true")
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
