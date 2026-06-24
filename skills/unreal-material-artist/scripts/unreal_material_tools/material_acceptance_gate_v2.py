from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from . import material_acceptance_gate as v1
from .material_acceptance_gate import (
    evidence_rows,
    make_check,
    package_report_paths,
    resolve_path,
    rows_by_tool,
    severity_counts,
)
from .translucency_sorting_probe import route_is_applicable


V2_CHECK_ORDER = (
    "v1_acceptance",
    "parameter_schema",
    "source_provenance",
    "translucency_sorting",
    "preview_matrix",
    "preview_readability",
    "shader_cost",
    "platform_scalability",
)


def load_optional_acceptance(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.acceptance_report:
        return None
    path = resolve_path(args.acceptance_report, base=Path.cwd())
    payload = v1.load_json(path)
    payload["_source_path"] = str(path)
    return payload


def build_or_load_v1(args: argparse.Namespace) -> dict[str, Any]:
    existing = load_optional_acceptance(args)
    if existing:
        return existing
    report, _ = v1.build_report(args)
    return report


def collect_rows(args: argparse.Namespace, v1_report: dict[str, Any]) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if args.package:
        package_path = resolve_path(args.package, base=Path.cwd())
        package = v1.load_json(package_path)
        paths.extend(package_report_paths(package, package_path=package_path))
    evidence = v1_report.get("evidence") if isinstance(v1_report.get("evidence"), dict) else {}
    for key in (
        "contract",
        "preview_reports",
        "audit_reports",
        "domain_audit_reports",
        "texture_set_reports",
        "regression_reports",
        "all_reports",
    ):
        value = evidence.get(key)
        values = value if isinstance(value, list) else [value] if value else []
        for item in values:
            if item:
                paths.append(resolve_path(str(item), base=Path.cwd()))
    for values in (
        args.parameter_schema_report,
        args.source_provenance_report,
        args.translucency_sorting_report,
        args.preview_matrix_report,
        args.preview_readability_report,
        args.shader_cost_report,
        args.platform_scalability_report,
    ):
        for item in values:
            paths.append(resolve_path(item, base=Path.cwd()))
    return evidence_rows(paths)


def first_row(rows: list[dict[str, Any]], *tools: str) -> dict[str, Any] | None:
    for row in rows_by_tool(rows, *tools):
        return row
    return None


def gate_check(
    rows: list[dict[str, Any]],
    *,
    name: str,
    label: str,
    tools: tuple[str, ...],
    gate_key: str,
    required: bool = True,
    action_needed: str,
) -> dict[str, Any]:
    row = first_row(rows, *tools)
    if not row:
        return make_check(
            name,
            label=label,
            passed=not required,
            required=required,
            errors=1 if required else 0,
            detail=f"No {label} report found.",
            action_needed=action_needed,
        )
    if row.get("load_error"):
        return make_check(
            name,
            label=label,
            passed=False,
            required=required,
            errors=1,
            evidence=[row["path"]],
            detail=f"{label} report could not be loaded: {row.get('load_error')}",
            action_needed=action_needed,
        )
    payload = row.get("payload") or {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    passed = gate.get(gate_key) is True
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    warnings = int(summary.get("warnings") or 0)
    errors = 0 if passed else 1
    return make_check(
        name,
        label=label,
        passed=passed,
        required=required,
        errors=errors,
        warnings=warnings if passed else 0,
        evidence=[row["path"]],
        detail=f"{gate_key}={gate.get(gate_key)}, summary_errors={summary.get('errors', 0)}, summary_warnings={summary.get('warnings', 0)}.",
        action_needed=action_needed if not passed or warnings else "No action needed.",
        data={"gate": gate, "summary": summary},
    )


def v1_check(v1_report: dict[str, Any]) -> dict[str, Any]:
    summary = v1_report.get("delivery_summary") if isinstance(v1_report.get("delivery_summary"), dict) else {}
    approved = summary.get("approved_for_reuse") is True
    return make_check(
        "v1_acceptance",
        label="Material Acceptance Gate v1",
        passed=approved,
        errors=0 if approved else 1,
        warnings=int(summary.get("warnings") or 0),
        evidence=[str(v1_report.get("_source_path") or v1_report.get("source_package") or "")],
        detail=f"approved_for_reuse={summary.get('approved_for_reuse')}, errors={summary.get('errors')}, warnings={summary.get('warnings')}.",
        action_needed="Pass material_acceptance_gate.py first; v2 only tightens a ready v1 delivery report." if not approved else "No action needed.",
        data={"delivery_summary": summary},
    )


def sorting_check(rows: list[dict[str, Any]], route: dict[str, Any]) -> dict[str, Any]:
    applicable = route_is_applicable(route)
    if not applicable:
        return make_check(
            "translucency_sorting",
            label="Translucency Sorting Probe",
            passed=True,
            required=False,
            detail="Route is not translucent/additive/ribbon/decal, so sorting proof is not required.",
            data={"applicable": False},
        )
    return gate_check(
        rows,
        name="translucency_sorting",
        label="Translucency Sorting Probe",
        tools=("translucency_sorting_probe",),
        gate_key="sorting_proven",
        required=True,
        action_needed="Run translucency_sorting_probe.py --require-proven and resolve sorting/bounds/depth evidence.",
    )


def optional_gate_check(
    rows: list[dict[str, Any]],
    *,
    name: str,
    label: str,
    tools: tuple[str, ...],
    gate_key: str,
    required: bool,
    action_needed: str,
) -> dict[str, Any]:
    if not required and not first_row(rows, *tools):
        return make_check(
            name,
            label=label,
            passed=True,
            required=False,
            detail=f"{label} is optional for this v2 gate run and no report was supplied.",
        )
    return gate_check(rows, name=name, label=label, tools=tools, gate_key=gate_key, required=required, action_needed=action_needed)


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    v1_report = build_or_load_v1(args)
    rows = collect_rows(args, v1_report)
    route = v1_report.get("route") if isinstance(v1_report.get("route"), dict) else {}
    checks = {
        "v1_acceptance": v1_check(v1_report),
        "parameter_schema": gate_check(
            rows,
            name="parameter_schema",
            label="Material Parameter Schema",
            tools=("material_parameter_schema",),
            gate_key="schema_complete",
            action_needed="Run material_parameter_schema.py --require-complete and fill missing parameter contract fields.",
        ),
        "source_provenance": gate_check(
            rows,
            name="source_provenance",
            label="Material Source Provenance",
            tools=("material_source_provenance",),
            gate_key="provenance_complete",
            action_needed="Run material_source_provenance.py --require-complete and attach texture source/import/repair proof.",
        ),
        "translucency_sorting": sorting_check(rows, route),
        "preview_matrix": gate_check(
            rows,
            name="preview_matrix",
            label="Preview Matrix",
            tools=("preview_matrix",),
            gate_key="ready_for_regression_coverage",
            action_needed="Run preview_matrix.py --execute on the final material or prepared variant MIs.",
        ),
        "preview_readability": optional_gate_check(
            rows,
            name="preview_readability",
            label="Preview Readability Score",
            tools=("preview_readability_score",),
            gate_key="readable",
            required=not args.no_require_readability,
            action_needed="Run preview_readability_score.py and fix almost-empty or low-contrast preview evidence.",
        ),
        "shader_cost": optional_gate_check(
            rows,
            name="shader_cost",
            label="Shader Cost Attribution",
            tools=("shader_cost_attribution",),
            gate_key="optimization_ready",
            required=args.require_shader_cost,
            action_needed="Run shader_cost_attribution.py from material_audit.py evidence.",
        ),
        "platform_scalability": optional_gate_check(
            rows,
            name="platform_scalability",
            label="Platform Scalability Planner",
            tools=("platform_scalability_planner",),
            gate_key="all_platforms_ready",
            required=args.require_platform_scalability,
            action_needed="Run platform_scalability_planner.py and document platform fallback plans.",
        ),
    }
    ordered = [checks[name] for name in V2_CHECK_ORDER]
    total_errors = sum(int(item.get("errors") or 0) for item in ordered)
    total_warnings = sum(int(item.get("warnings") or 0) for item in ordered)
    approved = total_errors == 0 and (args.allow_warnings or total_warnings == 0)
    failed_checks = [item["name"] for item in ordered if item.get("errors")]
    warning_checks = [item["name"] for item in ordered if item.get("warnings")]
    next_actions = [
        item.get("action_needed")
        for item in ordered
        if item.get("action_needed") and item.get("action_needed") != "No action needed." and (item.get("errors") or (item.get("warnings") and not args.allow_warnings))
    ]
    if not next_actions and approved:
        next_actions.append("Material delivery is v2-approved for reuse and can be consumed by downstream Niagara/gameplay/library gates.")
    asset = v1_report.get("asset") if isinstance(v1_report.get("asset"), dict) else {}
    report = {
        "tool": "material_acceptance_gate_v2",
        "schema": "material_delivery_report",
        "version": 2,
        "generated_utc": utc_now_iso(),
        "effect": v1_report.get("effect") or "",
        "layer": v1_report.get("layer") or "",
        "asset": asset,
        "delivery_summary": {
            "approved_for_reuse": approved,
            "ready": approved,
            "approval_level": "material_acceptance_gate_v2",
            "v1_approved": ((v1_report.get("delivery_summary") or {}).get("approved_for_reuse") is True),
            "warnings_allowed": bool(args.allow_warnings),
            "warnings": total_warnings,
            "errors": total_errors,
            "report_count": len(rows),
        },
        "checks": ordered,
        "gate": {
            "approved_for_reuse": approved,
            "ready": approved,
            "require_ready": bool(args.require_ready),
            "allow_warnings": bool(args.allow_warnings),
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "required_checks": [item["name"] for item in ordered if item.get("required")],
        },
        "evidence": {
            "v1_acceptance_report": str(v1_report.get("_source_path") or ""),
            "package": str(resolve_path(args.package, base=Path.cwd())) if args.package else str(v1_report.get("source_package") or ""),
            "all_reports": [row["path"] for row in rows],
        },
        "route": route,
        "v1_summary": v1_report.get("delivery_summary") or {},
        "next_actions": next_actions,
        "boundary": {
            "material_side": "This v2 report approves material-side reuse evidence only.",
            "niagara_side": "Real Niagara System/Emitter/Renderer integration remains owned by niagara-vfx-artist.",
        },
    }
    stem = slugify(asset.get("ue_asset_path") or report["effect"] or "material")
    out = Path(args.out) if args.out else default_report_path(ctx, "deliveries", stem, "delivery-v2", ".json")
    return report, out


def health_badge(status: str) -> str:
    return {
        "pass": "PASS",
        "warning": "WARNING",
        "fail": "FAIL",
        "missing": "MISSING",
        "not_applicable": "N/A",
    }.get(status, str(status or "UNKNOWN").upper())


def render_markdown(report: dict[str, Any]) -> str:
    delivery = report.get("delivery_summary") or {}
    asset = report.get("asset") or {}
    lines = [
        f"# Material Acceptance Gate v2: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Approved for reuse: `{delivery.get('approved_for_reuse')}`",
        f"- Material: `{asset.get('ue_asset_path')}`",
        f"- Errors: `{delivery.get('errors')}`",
        f"- Warnings: `{delivery.get('warnings')}`",
        "",
        "## Checks",
        "",
        "| Gate | Status | Required | Errors | Warnings | Detail |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for check in report.get("checks") or []:
        detail = str(check.get("detail") or "").replace("|", "\\|")
        lines.append(
            f"| {check.get('label')} | `{health_badge(str(check.get('status') or ''))}` | `{check.get('required')}` | "
            f"{check.get('errors', 0)} | {check.get('warnings', 0)} | {detail} |"
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
    if args.require_ready and not (report.get("delivery_summary") or {}).get("approved_for_reuse"):
        print(f"Material acceptance v2 is not ready: {out}", file=sys.stderr)
        return 2
    return 0


def add_v1_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--package", required=False, help="delivery_packager.py JSON report.")
    parser.add_argument("--contract", help="Optional material_contract.py JSON override.")
    parser.add_argument("--material-path", default="", help="Override final UE material path.")
    parser.add_argument("--preview-report", action="append", default=[])
    parser.add_argument("--audit-report", action="append", default=[])
    parser.add_argument("--domain-audit-report", action="append", default=[])
    parser.add_argument("--texture-set-report", action="append", default=[])
    parser.add_argument("--regression-report", action="append", default=[])
    parser.add_argument("--category", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--no-require-domain-audit", action="store_true")
    parser.add_argument("--no-require-regression", action="store_true")
    parser.add_argument("--no-require-texture-set", action="store_true")
    parser.add_argument("--texture-set-waiver", default="")
    parser.add_argument("--no-require-parameters", action="store_true")
    parser.add_argument("--parameter-table-waiver", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strict v2 material reuse gate requiring schema/provenance/sorting/matrix/readability evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--acceptance-report", default="", help="Existing material_acceptance_gate.py report. If omitted, v1 is evaluated from --package.")
    add_v1_args(parser)
    parser.add_argument("--parameter-schema-report", action="append", default=[])
    parser.add_argument("--source-provenance-report", action="append", default=[])
    parser.add_argument("--translucency-sorting-report", action="append", default=[])
    parser.add_argument("--preview-matrix-report", action="append", default=[])
    parser.add_argument("--preview-readability-report", action="append", default=[])
    parser.add_argument("--shader-cost-report", action="append", default=[])
    parser.add_argument("--platform-scalability-report", action="append", default=[])
    parser.add_argument("--require-shader-cost", action="store_true")
    parser.add_argument("--require-platform-scalability", action="store_true")
    parser.add_argument("--no-require-readability", action="store_true")
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.acceptance_report or args.package):
        parser.error("Provide --acceptance-report or --package.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
