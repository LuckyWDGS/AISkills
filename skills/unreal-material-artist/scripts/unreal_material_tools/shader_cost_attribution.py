from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import (
    _num,
    _text,
    evidence_rows,
    load_json,
    package_report_paths,
    resolve_path,
    rows_by_tool,
    severity_counts,
)


CATEGORY_RULES = {
    "texture_samples": ("texturesample", "texture sample", "sampletexture", "virtual texture"),
    "static_switches": ("staticswitch", "static switch", "static bool"),
    "function_calls": ("materialfunctioncall", "function call", "material function"),
    "custom_hlsl": ("materialexpressioncustom", "custom hlsl", "custom expression"),
    "expensive_math": ("noise", "sine", "sin(", "power", "pow", "fresnel", "normalize", "ddx", "ddy"),
    "depth_scene_reads": ("depthfade", "scene depth", "scenedepth", "pixeldepth", "distancefield"),
}

WEIGHTS = {
    "texture_samples": 4.0,
    "static_switches": 2.0,
    "function_calls": 3.0,
    "custom_hlsl": 8.0,
    "expensive_math": 2.5,
    "depth_scene_reads": 3.5,
}


def collect_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if args.package:
        package_path = resolve_path(args.package, base=Path.cwd())
        package = load_json(package_path)
        paths.extend(package_report_paths(package, package_path=package_path))
    for value in args.audit_report:
        paths.append(resolve_path(value, base=Path.cwd()))
    return evidence_rows(paths)


def graph_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for key in ("raw_graph", "graph"):
        graph = payload.get(key) if isinstance(payload.get(key), dict) else {}
        for item in graph.get("nodes") or []:
            if isinstance(item, dict):
                nodes.append(item)
    return nodes


def node_text(node: dict[str, Any]) -> str:
    parts = []
    for key in ("class_name", "caption", "desc", "name", "key_properties"):
        value = node.get(key)
        if isinstance(value, (dict, list)):
            parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
        else:
            parts.append(str(value or ""))
    return " ".join(parts).lower()


def classify_node(node: dict[str, Any]) -> list[str]:
    blob = node_text(node)
    categories = []
    for category, tokens in CATEGORY_RULES.items():
        if any(token in blob for token in tokens):
            categories.append(category)
    return categories


def route_risk(payload: dict[str, Any]) -> str:
    info = payload.get("material_info") if isinstance(payload.get("material_info"), dict) else {}
    blend = _text(info.get("blend_mode")).lower()
    domain = _text(info.get("material_domain")).lower()
    if blend in {"additive", "translucent", "alphacomposite", "alpha composite"}:
        return "translucency_overdraw"
    if domain in {"deferreddecal", "decal", "postprocess", "post process"}:
        return "special_domain"
    return ""


def attribution_for_audit(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload") or {}
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    nodes = graph_nodes(payload)
    categories: dict[str, dict[str, Any]] = {
        name: {"node_count": 0, "estimated_weight": 0.0, "examples": []}
        for name in CATEGORY_RULES
    }
    uncategorized = 0
    for node in nodes:
        node_categories = classify_node(node)
        if not node_categories:
            uncategorized += 1
            continue
        for category in node_categories:
            row_data = categories[category]
            row_data["node_count"] += 1
            row_data["estimated_weight"] += WEIGHTS[category]
            if len(row_data["examples"]) < 8:
                row_data["examples"].append(
                    {
                        "class_name": node.get("class_name", ""),
                        "caption": node.get("caption", ""),
                        "desc": node.get("desc", ""),
                    }
                )
    sampler_count = _num(analysis.get("sampler_count"))
    if sampler_count is not None and categories["texture_samples"]["node_count"] == 0:
        categories["texture_samples"]["node_count"] = int(sampler_count)
        categories["texture_samples"]["estimated_weight"] = float(sampler_count) * WEIGHTS["texture_samples"]
    risk = route_risk(payload)
    if risk:
        categories.setdefault("route_overdraw", {"node_count": 1, "estimated_weight": 6.0, "examples": [{"risk": risk}]})
    total_weight = sum(float(item.get("estimated_weight") or 0) for item in categories.values())
    ranked = sorted(
        [
            {
                "category": name,
                "node_count": item["node_count"],
                "estimated_weight": round(float(item["estimated_weight"]), 3),
                "share": round(float(item["estimated_weight"]) / total_weight, 4) if total_weight else 0.0,
                "examples": item["examples"],
            }
            for name, item in categories.items()
            if item["node_count"]
        ],
        key=lambda item: item["estimated_weight"],
        reverse=True,
    )
    return {
        "audit_report": row["path"],
        "material_path": payload.get("material_path") or ((payload.get("material_info") or {}).get("path") if isinstance(payload.get("material_info"), dict) else ""),
        "analysis": {
            "max_instructions": analysis.get("max_instructions"),
            "sampler_count": analysis.get("sampler_count"),
            "shader_stats_ready": analysis.get("shader_stats_ready"),
        },
        "node_count": len(nodes),
        "uncategorized_node_count": uncategorized,
        "categories": ranked,
    }


def build_findings(attributions: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not attributions:
        add("error", "missing_audit", "No material_audit reports were available for cost attribution.")
    for item in attributions:
        analysis = item.get("analysis") or {}
        if analysis.get("shader_stats_ready") is False:
            add("warning", "shader_stats_not_ready", f"Shader stats were not ready in {item.get('audit_report')}.")
        if _num(analysis.get("max_instructions")) is not None and float(analysis["max_instructions"]) > args.instruction_warning:
            add("warning", "instruction_pressure", f"{item.get('material_path')} has {analysis.get('max_instructions')} instructions.")
        if _num(analysis.get("sampler_count")) is not None and float(analysis["sampler_count"]) > args.sampler_warning:
            add("warning", "sampler_pressure", f"{item.get('material_path')} uses {analysis.get('sampler_count')} samplers.")
        top = (item.get("categories") or [{}])[0]
        if top.get("category") == "custom_hlsl":
            add("info", "custom_hlsl_top_cost", "Custom HLSL is the top heuristic cost contributor; inspect it before cutting visible layers.")
        if top.get("category") == "texture_samples":
            add("info", "texture_samples_top_cost", "Texture sampling is the top heuristic cost contributor; check packing, sharing, and resolution before graph cuts.")
    return findings


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    rows = collect_rows(args)
    audit_rows = rows_by_tool(rows, "material_audit")
    attributions = [attribution_for_audit(row) for row in audit_rows if not row.get("load_error")]
    findings = build_findings(attributions, args)
    counts = severity_counts(findings)
    effect = args.effect or (attributions[0].get("material_path") if attributions else "shader-cost")
    report = {
        "tool": "shader_cost_attribution",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "mode": "heuristic",
        "important_note": "UnrealBridge audit data does not expose exact per-node instruction cost here; attribution is a heuristic triage map.",
        "attributions": attributions,
        "summary": {
            **counts,
            "audit_count": len(audit_rows),
            "attributed_material_count": len(attributions),
        },
        "gate": {
            "passed": counts["errors"] == 0,
            "optimization_ready": bool(attributions) and counts["errors"] == 0,
            "requires_triage": bool(counts["warnings"]),
        },
        "evidence": {
            "package": str(resolve_path(args.package, base=Path.cwd())) if args.package else "",
            "audit_reports": [row["path"] for row in audit_rows],
        },
        "findings": findings,
        "next_actions": next_actions(findings),
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "shader-cost", effect, "shader-cost-attribution", ".json")
    return report, out


def next_actions(findings: list[dict[str, str]]) -> list[str]:
    rules = {item.get("rule") for item in findings}
    actions: list[str] = []
    if "missing_audit" in rules:
        actions.append("Run material_audit.py with graph data before attempting cost attribution.")
    if "sampler_pressure" in rules or "texture_samples_top_cost" in rules:
        actions.append("Check channel packing, shared samplers, texture reuse, and whether minor layers can be baked or quality-switched.")
    if "instruction_pressure" in rules or "custom_hlsl_top_cost" in rules:
        actions.append("Review the top heuristic categories before removing visible features; preserve the accepted look first.")
    if not actions:
        actions.append("Use the ranked heuristic categories as the first optimization triage map.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# Shader Cost Attribution: {report.get('effect')}",
        "",
        f"- Mode: `{report.get('mode')}`",
        f"- Audits: `{summary.get('audit_count')}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Ranked Contributors",
        "",
    ]
    for attribution in report.get("attributions") or []:
        lines.append(f"### {attribution.get('material_path')}")
        for category in attribution.get("categories") or []:
            lines.append(
                f"- `{category.get('category')}` nodes=`{category.get('node_count')}` weight=`{category.get('estimated_weight')}` share=`{category.get('share')}`"
            )
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
    parser = argparse.ArgumentParser(description="Attribute shader cost pressure to graph feature buckets using material_audit.py evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--package", default="")
    parser.add_argument("--audit-report", action="append", default=[])
    parser.add_argument("--instruction-warning", type=float, default=160.0)
    parser.add_argument("--sampler-warning", type=float, default=8.0)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.package or args.audit_report):
        parser.error("Provide --package or at least one --audit-report.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
