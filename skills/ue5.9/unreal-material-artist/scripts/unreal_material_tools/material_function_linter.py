"""Lint Unreal material functions for common TA/system issues through Epic's built-in MCP.

One ProgrammaticToolset script lists the MaterialFunctions under a folder and reads
each one's description, library exposure, expressions and FunctionInput /
FunctionOutput ports.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, run_tool_script


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "material_function_linter/2"
INPUT_PROPS = ["inputName", "description", "inputType", "sortPriority", "bUsePreviewValueAsDefault"]
OUTPUT_PROPS = ["outputName", "description", "sortPriority"]


def build_collect_script(folder: str, max_results: int, include_graph: bool) -> str:
    return textwrap.dedent(
        """
        import json
        import re

        FOLDER = __FOLDER__
        MAX = __MAX__
        INCLUDE_GRAPH = __GRAPH__
        INPUT_PROPS = __INPUT_PROPS__
        OUTPUT_PROPS = __OUTPUT_PROPS__
        A = "editor_toolset.toolsets.asset.AssetTools."
        O = "editor_toolset.toolsets.object.ObjectTools."
        M = "editor_toolset.toolsets.material.MaterialTools."

        def call(tool, **args):
            return json.loads(json.dumps(execute_tool(tool, json.dumps(args))["returnValue"]))

        def props(path, names):
            value = call(O + "get_properties", instance={"refPath": path}, properties=names)
            return json.loads(value) if isinstance(value, str) else value

        def ref_of(value):
            return value.get("refPath", "") if isinstance(value, dict) else str(value or "")

        def short_class(path):
            name = re.sub(r"_\\d+$", "", path.rsplit(":", 1)[-1])
            return name[len("MaterialExpression"):] if name.startswith("MaterialExpression") else name

        def run():
            paths = call(A + "find_assets", folder_path=FOLDER, name="", recursive=True, tags=None,
                         asset_type={"refPath": "/Script/Engine.MaterialFunction"})
            rows = []
            for path in paths[:MAX] if MAX > 0 else paths:
                leaf = path.rsplit("/", 1)[-1]
                obj = path + "." + leaf
                info = props(obj, ["description", "bExposeToLibrary", "libraryCategoriesText"])
                exprs = [ref_of(item) for item in call(M + "get_expressions", material_or_function={"refPath": obj})]
                inputs, outputs, nodes = [], [], []
                for expr in exprs:
                    cls = short_class(expr)
                    nodes.append({"class_name": cls})
                    if cls == "FunctionInput":
                        inputs.append(props(expr, INPUT_PROPS))
                    elif cls == "FunctionOutput":
                        outputs.append(props(expr, OUTPUT_PROPS))
                row = {"path": path, "name": leaf, "info": info, "num_expressions": len(exprs),
                       "inputs": inputs, "outputs": outputs}
                if INCLUDE_GRAPH:
                    row["graph"] = {"found": True, "nodes": nodes}
                else:
                    row["static_switch_nodes"] = sum(1 for node in nodes if "StaticSwitch" in node["class_name"])
                rows.append(row)
            return {"functions": rows, "total": len(paths)}
        """
    ).strip().replace("__FOLDER__", json.dumps(folder)).replace("__MAX__", str(int(max_results))) \
        .replace("__GRAPH__", "True" if include_graph else "False") \
        .replace("__INPUT_PROPS__", json.dumps(INPUT_PROPS)).replace("__OUTPUT_PROPS__", json.dumps(OUTPUT_PROPS))


def function_row(raw: dict[str, Any]) -> dict[str, Any]:
    """A collected function in the report's (UnrealBridge-era) field names."""
    info = raw.get("info") or {}
    categories = info.get("libraryCategoriesText") or []
    row = {
        "name": raw["name"],
        "path": raw["path"],
        "description": info.get("description") or "",
        "expose_to_library": bool(info.get("bExposeToLibrary")),
        "library_category": ", ".join(str(item) for item in categories) if isinstance(categories, list) else str(categories),
        "num_expressions": raw.get("num_expressions", 0),
        "inputs": [{"name": port.get("inputName") or "", "description": port.get("description") or "",
                    "port_type": port.get("inputType") or "", "sort_priority": port.get("sortPriority"),
                    "use_preview_value_as_default": bool(port.get("bUsePreviewValueAsDefault"))}
                   for port in raw.get("inputs") or []],
        "outputs": [{"name": port.get("outputName") or "", "description": port.get("description") or "",
                     "sort_priority": port.get("sortPriority")} for port in raw.get("outputs") or []],
    }
    if "graph" in raw:
        row["graph"] = raw["graph"]
    else:
        row["static_switch_nodes"] = raw.get("static_switch_nodes", 0)
    return row


def lint_function(item: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not item.get("inputs"):
        add("info", "no_inputs", "Material function has no declared inputs.")
    names = [port.get("name") for port in item.get("inputs") or []]
    for port in item.get("inputs") or []:
        if not port.get("name"):
            add("warning", "unnamed_input", "Material function has an unnamed input.")
        elif not port.get("description"):
            add("info", "undocumented_input", f"Input `{port['name']}` has no description tooltip.")
    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    if duplicates:
        add("warning", "duplicate_input", f"Duplicate input names: {', '.join(duplicates)}.")
    if not item.get("outputs"):
        add("warning", "no_outputs", "Material function has no declared outputs.")
    if item.get("num_expressions", 0) > 80:
        add("info", "large_function", "Material function is large enough that it may want to be split or reviewed for reuse boundaries.")
    graph = item.get("graph") or {}
    switches = item.get("static_switch_nodes")
    if switches is None:
        switches = sum(1 for node in graph.get("nodes") or [] if "staticswitch" in str(node.get("class_name", "")).lower())
    if switches >= 3:
        add("warning", "switch_sprawl", "Material function appears to contain many static switches; review permutation cost.")
    return findings


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Material Function Linter", "", f"- Folder: `{report['folder']}` "
             f"({len(report['functions'])}/{report['functions_total']} functions)", ""]
    for item in report["functions"]:
        lines.extend([
            f"## {item['path']}", "",
            f"- Inputs: `{len(item.get('inputs') or [])}`",
            f"- Outputs: `{len(item.get('outputs') or [])}`",
            f"- Expressions: `{item.get('num_expressions')}`",
            "Findings:",
        ])
        lines += [f"- [{f['severity']}] `{f['rule']}` {f['message']}" for f in item["findings"]] or ["- No first-pass findings."]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_report(raw: dict[str, Any], folder: str) -> dict[str, Any]:
    functions = [function_row(item) for item in raw["functions"]]
    for item in functions:
        item["findings"] = lint_function(item)
    return {"tool": "material_function_linter", "schema_version": SCHEMA_VERSION,
            "transport": "epic-mcp ProgrammaticToolset", "folder": folder,
            "functions_total": raw.get("total", len(functions)), "functions": functions}


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    folder = (args.path_prefix or "/Game").rstrip("/") or "/Game"
    raw = run_tool_script(ctx.skill_root, build_collect_script(folder, args.max_results, args.include_graph),
                          url=args.mcp_url, timeout=args.timeout, project=args.project)
    report = build_report(raw, folder)
    out = Path(args.out) if args.out else default_report_path(ctx, "function-lints", slugify(folder), "material-function-linter", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint Unreal material functions for common TA/system issues.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project", help="Refuse to run unless the MCP endpoint is served by this project.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--path-prefix", default="/Game", help="Content folder to scan recursively.")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--include-graph", action="store_true", help="Keep each function's node classes in the report.")
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
