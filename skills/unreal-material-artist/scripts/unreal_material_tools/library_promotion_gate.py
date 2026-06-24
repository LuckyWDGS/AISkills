from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import resolve_path, severity_counts
from .material_asset_library import load_catalog, save_catalog


REQUIRED_TOOLS = {
    "material_acceptance_gate": "delivery_summary.approved_for_reuse",
    "material_acceptance_gate_v2": "delivery_summary.approved_for_reuse",
    "material_parameter_schema": "gate.schema_complete",
    "material_source_provenance": "gate.provenance_complete",
    "preview_matrix": "gate.ready_for_regression_coverage",
    "preview_readability_score": "gate.readable",
}


def load_report(path_text: str) -> dict[str, Any]:
    path = resolve_path(path_text, base=Path.cwd())
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    payload["_source_path"] = str(path)
    return payload


def dotted_value(payload: dict[str, Any], dotted: str) -> Any:
    cursor: Any = payload
    for key in dotted.split("."):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def collect_reports(args: argparse.Namespace) -> list[dict[str, Any]]:
    return [load_report(item) for item in args.report_path]


def library_record(asset_id: str) -> dict[str, Any] | None:
    catalog = load_catalog()
    return next((item for item in catalog.get("assets") or [] if isinstance(item, dict) and item.get("id") == asset_id), None)


def findings_from_reports(reports: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    by_tool = {str(report.get("tool") or ""): report for report in reports}

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    acceptance = by_tool.get("material_acceptance_gate_v2") or by_tool.get("material_acceptance_gate")
    if not acceptance:
        add("error", "missing_acceptance_gate", "No material acceptance report was provided.")
    elif not bool(((acceptance.get("delivery_summary") or {}).get("approved_for_reuse"))):
        add("error", "acceptance_not_ready", "Material acceptance report is not approved_for_reuse=true.")

    for tool, gate_key in REQUIRED_TOOLS.items():
        if tool not in by_tool:
            if tool == "material_acceptance_gate":
                continue
            add("error", "missing_required_report", f"Required report `{tool}` is missing.")
            continue
        if tool == "material_acceptance_gate" and "material_acceptance_gate_v2" in by_tool:
            continue
        if dotted_value(by_tool[tool], gate_key) is not True:
            add("error", "gate_not_ready", f"`{tool}` did not pass `{gate_key}`.")

    if args.require_platform_scalability:
        planner = by_tool.get("platform_scalability_planner")
        if not planner:
            add("error", "missing_platform_scalability", "platform_scalability_planner report is required for promotion.")
        elif not bool(((planner.get("gate") or {}).get("all_platforms_ready"))):
            add("warning", "platform_scalability_unready", "Platform scalability plan exists but not all target platforms are ready.")

    if args.require_shader_cost:
        cost = by_tool.get("shader_cost_attribution")
        if not cost:
            add("error", "missing_shader_cost", "shader_cost_attribution report is required for promotion.")
        elif not bool(((cost.get("gate") or {}).get("optimization_ready"))):
            add("warning", "shader_cost_unready", "Shader cost attribution exists but is not optimization_ready.")

    if args.asset_id:
        record = library_record(args.asset_id)
        if not record:
            add("warning", "library_record_missing", f"Asset id `{args.asset_id}` is not yet in the material asset library catalog.")
        elif record.get("stage") == "approved":
            add("info", "already_approved", "Library record is already in the approved stage.")
    return findings


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    reports = collect_reports(args)
    findings = findings_from_reports(reports, args)
    counts = severity_counts(findings)
    approved = counts["errors"] == 0 and (args.allow_warnings or counts["warnings"] == 0)
    acceptance = next((report for report in reports if report.get("tool") in {"material_acceptance_gate_v2", "material_acceptance_gate"}), {})
    asset = acceptance.get("asset") if isinstance(acceptance.get("asset"), dict) else {}
    record = library_record(args.asset_id) if args.asset_id else None
    report = {
        "tool": "library_promotion_gate",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "asset_id": args.asset_id,
        "asset": asset,
        "library_record": record or {},
        "delivery_summary": {
            "approved_for_library": approved,
            "ready": approved,
            "errors": counts["errors"],
            "warnings": counts["warnings"],
            "report_count": len(reports),
        },
        "evidence": {"report_paths": [report["_source_path"] for report in reports]},
        "findings": findings,
        "gate": {
            "approved_for_library": approved,
            "require_platform_scalability": bool(args.require_platform_scalability),
            "require_shader_cost": bool(args.require_shader_cost),
            "allow_warnings": bool(args.allow_warnings),
        },
        "next_actions": next_actions(findings),
    }
    stem = slugify(args.asset_id or asset.get("ue_asset_path") or acceptance.get("effect") or "library-promotion")
    out = Path(args.out) if args.out else default_report_path(ctx, "library-promotion", stem, "library-promotion-gate", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {item.get("rule") for item in findings}
    actions: list[str] = []
    if "missing_acceptance_gate" in rules or "acceptance_not_ready" in rules:
        actions.append("Promote to reusable library only after material_acceptance_gate_v2 passes.")
    if "missing_required_report" in rules or "gate_not_ready" in rules:
        actions.append("Attach the missing evidence reports and rerun the relevant material-side gates before promotion.")
    if "library_record_missing" in rules:
        actions.append("Register the material candidate in material_asset_library.py before asking for approved stock promotion.")
    if not actions:
        actions.append("Evidence bundle is strong enough for reusable library promotion; apply the catalog stage change if desired.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("delivery_summary") or {}
    lines = [
        "# Library Promotion Gate",
        "",
        f"- Approved for library: `{summary.get('approved_for_library')}`",
        f"- Errors: `{summary.get('errors')}`",
        f"- Warnings: `{summary.get('warnings')}`",
        "",
        "## Findings",
        "",
    ]
    if report.get("findings"):
        for item in report["findings"]:
            lines.append(f"- [{item.get('severity')}] `{item.get('rule')}` {item.get('message')}")
    else:
        lines.append("- No promotion findings.")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def apply_promotion(args: argparse.Namespace, report: dict[str, Any]) -> None:
    if not args.apply or not args.asset_id or not report["delivery_summary"]["approved_for_library"]:
        return
    catalog = load_catalog()
    target = next((item for item in catalog.get("assets") or [] if isinstance(item, dict) and item.get("id") == args.asset_id), None)
    if not target:
        return
    target["stage"] = "approved"
    target["qa_status"] = "approved"
    target["updated_utc"] = utc_now_iso()
    existing = list(target.get("report_paths") or [])
    if args.link_report and args.link_report not in existing:
        existing.append(args.link_report)
    target["report_paths"] = existing
    save_catalog(catalog)


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    apply_promotion(args, report)
    print(out)
    if args.require_ready and not report["delivery_summary"]["approved_for_library"]:
        print(f"Library promotion gate is not ready: {out}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decide whether a material evidence bundle is strong enough for reusable library promotion.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--asset-id", default="")
    parser.add_argument("--report-path", action="append", default=[], help="Evidence reports such as acceptance/schema/provenance/matrix/readability.")
    parser.add_argument("--require-platform-scalability", action="store_true")
    parser.add_argument("--require-shader-cost", action="store_true")
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--apply", action="store_true", help="If ready and asset-id exists, mark the existing library record approved.")
    parser.add_argument("--link-report", default="", help="Optional report path to append to the library record when --apply succeeds.")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.report_path:
        parser.error("Provide at least one --report-path.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
