from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import evidence_rows, load_json, package_report_paths, resolve_path, rows_by_tool, severity_counts


FUNCTION_CALL_TOKENS = ("materialfunctioncall", "material function", "function=")


def collect_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if args.package:
        package_path = resolve_path(args.package, base=Path.cwd())
        package = load_json(package_path)
        paths.extend(package_report_paths(package, package_path=package_path))
    for values in (args.function_linter_report, args.audit_report):
        for value in values:
            paths.append(resolve_path(value, base=Path.cwd()))
    return evidence_rows(paths)


def normalize_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("/"):
        return text.split(".")[0]
    return re.sub(r"\s+", " ", text)


def function_rows_from_linter(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    functions: dict[str, dict[str, Any]] = {}
    for row in rows_by_tool(rows, "material_function_linter"):
        payload = row.get("payload") or {}
        for item in payload.get("functions") or []:
            if not isinstance(item, dict):
                continue
            path = normalize_name(item.get("path") or item.get("name"))
            if not path:
                continue
            functions[path] = {
                "path": path,
                "name": item.get("name") or path.rsplit("/", 1)[-1],
                "description": item.get("description") or "",
                "library_category": item.get("library_category") or "",
                "expose_to_library": item.get("expose_to_library"),
                "num_expressions": item.get("num_expressions"),
                "input_count": len(item.get("inputs") or []),
                "output_count": len(item.get("outputs") or []),
                "findings": item.get("findings") or [],
                "source_report": row["path"],
            }
    return functions


def graph_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for key in ("raw_graph", "graph"):
        graph = payload.get(key) if isinstance(payload.get(key), dict) else {}
        for node in graph.get("nodes") or []:
            if isinstance(node, dict):
                nodes.append(node)
    return nodes


def node_blob(node: dict[str, Any]) -> str:
    return " ".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value or "")
        for value in (node.get("class_name"), node.get("caption"), node.get("desc"), node.get("key_properties"))
    )


def extract_function_name(node: dict[str, Any]) -> str:
    text = node_blob(node)
    lowered = text.lower()
    if not any(token in lowered for token in FUNCTION_CALL_TOKENS):
        return ""
    for pattern in (r"(/Game/[A-Za-z0-9_./-]+)", r"function['\"]?\s*[:=]\s*['\"]([^'\"]+)", r"caption['\"]?\s*[:=]\s*['\"]([^'\"]+)"):
        match = re.search(pattern, text)
        if match:
            return normalize_name(match.group(1))
    caption = str(node.get("caption") or node.get("desc") or "").strip()
    return normalize_name(caption)


def material_dependencies_from_audits(rows: list[dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    material_to_functions: dict[str, list[str]] = {}
    inferred_functions: dict[str, dict[str, Any]] = {}
    for row in rows_by_tool(rows, "material_audit"):
        payload = row.get("payload") or {}
        material = normalize_name(payload.get("material_path") or ((payload.get("material_info") or {}).get("path") if isinstance(payload.get("material_info"), dict) else ""))
        if not material:
            material = row["path"]
        deps: list[str] = []
        for node in graph_nodes(payload):
            dep = extract_function_name(node)
            if dep:
                deps.append(dep)
                inferred_functions.setdefault(
                    dep,
                    {
                        "path": dep,
                        "name": dep.rsplit("/", 1)[-1],
                        "description": "",
                        "library_category": "",
                        "expose_to_library": None,
                        "num_expressions": None,
                        "input_count": None,
                        "output_count": None,
                        "findings": [],
                        "source_report": row["path"],
                    },
                )
        material_to_functions[material] = sorted(set(deps))
    return material_to_functions, inferred_functions


def build_findings(functions: dict[str, dict[str, Any]], material_to_functions: dict[str, list[str]], args: argparse.Namespace) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(severity: str, rule: str, message: str, function: str = "") -> None:
        findings.append({"severity": severity, "rule": rule, "message": message, "function": function})

    if not functions and not material_to_functions:
        add("error", "missing_dependency_evidence", "No material function linter or audit function-call evidence was provided.")
    names: dict[str, list[str]] = {}
    for path, item in functions.items():
        names.setdefault(str(item.get("name") or path.rsplit("/", 1)[-1]).lower(), []).append(path)
        if item.get("num_expressions") is not None and int(item.get("num_expressions") or 0) > args.large_function_threshold:
            add("warning", "large_function", f"Function has {item.get('num_expressions')} expressions.", path)
        if not item.get("description"):
            add("info", "missing_description", "Function lacks a description.", path)
        if not item.get("output_count"):
            add("warning", "no_outputs", "Function has no outputs.", path)
        for finding in item.get("findings") or []:
            if isinstance(finding, dict) and finding.get("severity") in {"warning", "error"}:
                add(str(finding.get("severity")), f"linter:{finding.get('rule')}", str(finding.get("message") or ""), path)
    for name, paths in names.items():
        if len(paths) > 1:
            add("warning", "duplicate_function_name", f"Function name `{name}` appears at multiple paths: {paths}", paths[0])

    reuse_counts: dict[str, int] = {}
    for deps in material_to_functions.values():
        for dep in deps:
            reuse_counts[dep] = reuse_counts.get(dep, 0) + 1
    for dep, count in reuse_counts.items():
        if count >= args.hotspot_threshold:
            add("info", "reuse_hotspot", f"Function is used by {count} audited material(s).", dep)
    return findings


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    rows = collect_rows(args)
    functions = function_rows_from_linter(rows)
    material_to_functions, inferred = material_dependencies_from_audits(rows)
    for key, value in inferred.items():
        functions.setdefault(key, value)
    reuse_counts: dict[str, int] = {}
    for deps in material_to_functions.values():
        for dep in deps:
            reuse_counts[dep] = reuse_counts.get(dep, 0) + 1
    dependency_rows = [
        {
            "function": key,
            **value,
            "used_by_materials": sorted(material for material, deps in material_to_functions.items() if key in deps),
            "reuse_count": reuse_counts.get(key, 0),
        }
        for key, value in sorted(functions.items())
    ]
    findings = build_findings(functions, material_to_functions, args)
    counts = severity_counts(findings)
    effect = args.effect or "material-functions"
    report = {
        "tool": "material_function_dependency_map",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "functions": dependency_rows,
        "materials": [{"material": material, "functions": deps} for material, deps in sorted(material_to_functions.items())],
        "hotspots": sorted(
            [{"function": key, "reuse_count": count} for key, count in reuse_counts.items() if count >= args.hotspot_threshold],
            key=lambda item: item["reuse_count"],
            reverse=True,
        ),
        "summary": {
            **counts,
            "function_count": len(dependency_rows),
            "material_count": len(material_to_functions),
            "hotspot_count": sum(1 for count in reuse_counts.values() if count >= args.hotspot_threshold),
        },
        "gate": {
            "passed": counts["errors"] == 0,
            "map_ready": bool(dependency_rows or material_to_functions) and counts["errors"] == 0,
            "requires_triage": bool(counts["warnings"]),
        },
        "evidence": {"all_reports": [row["path"] for row in rows]},
        "findings": findings,
        "next_actions": next_actions(findings),
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "function-dependencies", effect, "material-function-dependency-map", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {item.get("rule") for item in findings}
    actions: list[str] = []
    if "missing_dependency_evidence" in rules:
        actions.append("Run material_function_linter.py --include-graph and material_audit.py before building a dependency map.")
    if "large_function" in rules or "linter:switch_sprawl" in rules:
        actions.append("Review large or switch-heavy material functions before they become master-material risk multipliers.")
    if "duplicate_function_name" in rules:
        actions.append("Rename or categorize duplicate functions so refactor plans can target the right dependency.")
    if not actions:
        actions.append("Use hotspots as the first candidates for documentation, optimization, or extraction into cleaner reusable functions.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Material Function Dependency Map",
        "",
        f"- Functions: `{summary.get('function_count')}`",
        f"- Materials: `{summary.get('material_count')}`",
        f"- Hotspots: `{summary.get('hotspot_count')}`",
        "",
        "## Hotspots",
        "",
    ]
    for item in report.get("hotspots") or []:
        lines.append(f"- `{item.get('function')}` used_by=`{item.get('reuse_count')}`")
    if not report.get("hotspots"):
        lines.append("- No reuse hotspots detected.")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a material-function dependency and hotspot map from linter and material audit evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--package", default="")
    parser.add_argument("--function-linter-report", action="append", default=[])
    parser.add_argument("--audit-report", action="append", default=[])
    parser.add_argument("--large-function-threshold", type=int, default=80)
    parser.add_argument("--hotspot-threshold", type=int, default=2)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.package or args.function_linter_report or args.audit_report):
        parser.error("Provide --package, --function-linter-report, or --audit-report.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
