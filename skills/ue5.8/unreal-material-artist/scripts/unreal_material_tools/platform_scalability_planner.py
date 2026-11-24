from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import _num, _text, evidence_rows, load_json, package_report_paths, resolve_path, rows_by_tool, severity_counts


PLATFORM_BUDGETS = {
    "pc": {"instruction_budget": 180, "sampler_budget": 8, "max_texture_dimension": 2048, "overdraw": "medium"},
    "android": {"instruction_budget": 90, "sampler_budget": 4, "max_texture_dimension": 1024, "overdraw": "low"},
    "low_end": {"instruction_budget": 60, "sampler_budget": 3, "max_texture_dimension": 512, "overdraw": "low"},
}


def split_platforms(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(item.strip().lower() for item in value.split(",") if item.strip())
    return result or ["pc", "android", "low_end"]


def collect_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if args.package:
        package_path = resolve_path(args.package, base=Path.cwd())
        package = load_json(package_path)
        paths.extend(package_report_paths(package, package_path=package_path))
        paths.append(package_path)
    for values in (
        args.acceptance_report,
        args.audit_report,
        args.texture_set_report,
        args.shader_cost_report,
        args.source_provenance_report,
        args.project_health_report,
    ):
        for value in values:
            paths.append(resolve_path(value, base=Path.cwd()))
    return evidence_rows(paths)


def first_payload(rows: list[dict[str, Any]], *tools: str) -> dict[str, Any] | None:
    for row in rows_by_tool(rows, *tools):
        if not row.get("load_error"):
            return row.get("payload") or {}
    return None


def measured_cost(rows: list[dict[str, Any]]) -> dict[str, Any]:
    audit = first_payload(rows, "material_audit")
    analysis = audit.get("analysis") if isinstance((audit or {}).get("analysis"), dict) else {}
    if not analysis:
        acceptance = first_payload(rows, "material_acceptance_gate", "material_acceptance_gate_v2")
        measured = (((acceptance or {}).get("budget") or {}).get("measured")) if isinstance((acceptance or {}).get("budget"), dict) else {}
        analysis = measured if isinstance(measured, dict) else {}
    return {
        "max_instructions": _num(analysis.get("max_instructions")),
        "sampler_count": _num(analysis.get("sampler_count")),
        "shader_stats_ready": analysis.get("shader_stats_ready"),
    }


def texture_pressure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    texture_set = first_payload(rows, "texture_set_pipeline")
    slots = texture_set.get("slots") if isinstance((texture_set or {}).get("slots"), dict) else {}
    dimensions = []
    for item in slots.values():
        if not isinstance(item, dict):
            continue
        file_info = item.get("file") if isinstance(item.get("file"), dict) else {}
        width = file_info.get("width")
        height = file_info.get("height")
        if isinstance(width, int) and isinstance(height, int):
            dimensions.append({"slot": item.get("slot"), "width": width, "height": height, "max": max(width, height)})
    max_dimension = max((item["max"] for item in dimensions), default=None)
    return {"max_dimension": max_dimension, "dimensions": dimensions}


def route_risk(rows: list[dict[str, Any]]) -> dict[str, Any]:
    package = first_payload(rows, "delivery_packager") or {}
    route = package.get("route") if isinstance(package.get("route"), dict) else {}
    blend = _text(route.get("blend_mode")).lower()
    carrier = _text(route.get("carrier")).lower()
    translucent = blend in {"additive", "translucent", "alphacomposite", "alpha composite"} or carrier in {"sprite", "ribbon", "decal"}
    return {"blend_mode": blend, "carrier": carrier, "translucent_or_vfx": translucent}


def platform_plan(platform: str, cost: dict[str, Any], textures: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    budget = PLATFORM_BUDGETS.get(platform, PLATFORM_BUDGETS["pc"])
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    instructions = cost.get("max_instructions")
    samplers = cost.get("sampler_count")
    max_dim = textures.get("max_dimension")
    if instructions is None:
        add("warning", "missing_instruction_count", "Instruction count is unavailable; rerun material_audit.py with shader stats.")
    elif instructions > budget["instruction_budget"]:
        add("warning", "instruction_budget_pressure", f"Instructions {instructions:g} exceed {platform} target {budget['instruction_budget']}.")
    if samplers is None:
        add("warning", "missing_sampler_count", "Sampler count is unavailable.")
    elif samplers > budget["sampler_budget"]:
        add("warning", "sampler_budget_pressure", f"Samplers {samplers:g} exceed {platform} target {budget['sampler_budget']}.")
    if max_dim and max_dim > budget["max_texture_dimension"]:
        add("warning", "texture_dimension_pressure", f"Texture dimension {max_dim} exceeds {platform} target {budget['max_texture_dimension']}.")
    if risk.get("translucent_or_vfx") and platform in {"android", "low_end"}:
        add("warning", "transparent_overdraw_pressure", "Transparent/VFX route needs tighter bounds, lower spawn density, and fallback opacity/emissive tiers on this platform.")

    recommendations = []
    if platform == "pc":
        recommendations.append("Keep the accepted look as the hero tier; use quality switches only for optional detail layers.")
    if platform == "android":
        recommendations.extend(
            [
                "Prefer <=1024 textures for VFX atlases unless the effect is hero-critical.",
                "Target <=4 samplers and move optional detail/distortion into a quality switch or fallback MI.",
                "Validate additive/translucent overdraw on bright and busy backgrounds, not only black.",
            ]
        )
    if platform == "low_end":
        recommendations.extend(
            [
                "Create a gameplay-safe fallback MI with reduced emissive/opacity intensity and fewer optional samples.",
                "Prefer <=512 non-hero masks/atlases and disable costly custom HLSL/noise branches.",
                "Treat translucent full-screen coverage as a blocker unless bounds and spawn density are proven.",
            ]
        )
    if not findings:
        recommendations.append("No immediate platform pressure detected from available evidence.")
    counts = severity_counts(findings)
    return {
        "platform": platform,
        "budget": budget,
        "measured": cost,
        "texture_pressure": textures,
        "route_risk": risk,
        "findings": findings,
        "recommendations": recommendations,
        "ready": counts["errors"] == 0 and counts["warnings"] == 0,
    }


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    rows = collect_rows(args)
    cost = measured_cost(rows)
    textures = texture_pressure(rows)
    risk = route_risk(rows)
    platforms = split_platforms(args.platform)
    plans = [platform_plan(platform, cost, textures, risk) for platform in platforms]
    findings = [
        {"platform": plan["platform"], **finding}
        for plan in plans
        for finding in plan.get("findings") or []
    ]
    counts = severity_counts(findings)
    effect = args.effect or ((first_payload(rows, "delivery_packager") or {}).get("effect")) or "platform-scalability"
    report = {
        "tool": "platform_scalability_planner",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "platforms": plans,
        "summary": {
            **counts,
            "platform_count": len(plans),
            "ready_platform_count": sum(1 for plan in plans if plan.get("ready")),
        },
        "gate": {
            "passed": counts["errors"] == 0,
            "all_platforms_ready": all(plan.get("ready") for plan in plans),
            "requires_triage": bool(counts["warnings"] or counts["errors"]),
        },
        "evidence": {
            "package": str(resolve_path(args.package, base=Path.cwd())) if args.package else "",
            "all_reports": [row["path"] for row in rows],
        },
        "findings": findings,
        "next_actions": next_actions(findings),
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "scalability", effect, "platform-scalability-planner", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {item.get("rule") for item in findings}
    actions = []
    if "instruction_budget_pressure" in rules:
        actions.append("Use shader_cost_attribution.py to decide which feature bucket gets a quality switch or fallback.")
    if "sampler_budget_pressure" in rules:
        actions.append("Pack masks/RMA, share samples, or split optional layers into platform-specific MIs.")
    if "texture_dimension_pressure" in rules:
        actions.append("Author platform texture LOD targets and import limits for Android/low-end packages.")
    if "transparent_overdraw_pressure" in rules:
        actions.append("Pair the material fallback plan with Niagara bounds/spawn-density validation in niagara-vfx-artist.")
    if not actions:
        actions.append("Platform scalability plan is clear; promote the selected fallback tiers into delivery notes.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# Platform Scalability Planner: {report.get('effect')}",
        "",
        f"- Platforms: `{summary.get('platform_count')}`",
        f"- Ready platforms: `{summary.get('ready_platform_count')}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Platforms",
        "",
        "| Platform | Ready | Instruction Budget | Sampler Budget | Max Texture | Findings |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for plan in report.get("platforms") or []:
        budget = plan.get("budget") or {}
        lines.append(
            f"| `{plan.get('platform')}` | `{plan.get('ready')}` | {budget.get('instruction_budget')} | "
            f"{budget.get('sampler_budget')} | {budget.get('max_texture_dimension')} | {len(plan.get('findings') or [])} |"
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
    if args.strict and not (report.get("gate") or {}).get("all_platforms_ready"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate PC/Android/low-end material scalability recommendations from delivery evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--package", default="")
    parser.add_argument("--acceptance-report", action="append", default=[])
    parser.add_argument("--audit-report", action="append", default=[])
    parser.add_argument("--texture-set-report", action="append", default=[])
    parser.add_argument("--shader-cost-report", action="append", default=[])
    parser.add_argument("--source-provenance-report", action="append", default=[])
    parser.add_argument("--project-health-report", action="append", default=[])
    parser.add_argument("--platform", action="append", default=[])
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.package or args.acceptance_report or args.audit_report or args.texture_set_report or args.shader_cost_report):
        parser.error("Provide --package or supporting report paths.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
