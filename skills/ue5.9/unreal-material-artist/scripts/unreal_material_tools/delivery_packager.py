from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text


REPORT_GROUPS = ("texture", "preview", "audit", "other")


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"invalid_json: {exc}"
    if not isinstance(payload, dict):
        return None, "json_root_not_object"
    return payload, ""


def default_plan_path(ctx, effect: str, layer: str) -> Path:
    return default_report_path(ctx, "plans", slugify(f"{effect}-{layer}"), "reference-to-material-plan", ".json")


def default_contract_path(ctx, effect: str, layer: str) -> Path:
    return default_report_path(ctx, "contracts", slugify(f"{effect}-{layer}"), "material-contract", ".json")


def _finding_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("severity") or "").lower(),
        str(item.get("rule") or item.get("rule_id") or ""),
        str(item.get("message") or ""),
    )


def collect_findings(payload: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            raw_findings = value.get("findings")
            if isinstance(raw_findings, list):
                for item in raw_findings:
                    if isinstance(item, dict) and item.get("severity"):
                        findings.append(item)
            for child_key, child_value in value.items():
                if child_key == "findings":
                    continue
                walk(child_value)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in findings:
        key = _finding_key(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def normalize_severity(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"error", "errors", "fatal"}:
        return "error"
    if lowered in {"warning", "warnings", "warn"}:
        return "warning"
    if lowered in {"ok", "pass", "passed"}:
        return "ok"
    return "info"


def report_counts(payload: dict[str, Any]) -> dict[str, int]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary and any(key in summary for key in ("errors", "warnings", "info", "ok")):
        return {
            "errors": int(summary.get("errors") or 0),
            "warnings": int(summary.get("warnings") or 0),
            "info": int(summary.get("info") or 0),
            "ok": int(summary.get("ok") or 0),
        }

    counts = {"errors": 0, "warnings": 0, "info": 0, "ok": 0}
    for finding in collect_findings(payload):
        severity = normalize_severity(str(finding.get("severity") or "info"))
        if severity == "error":
            counts["errors"] += 1
        elif severity == "warning":
            counts["warnings"] += 1
        elif severity == "ok":
            counts["ok"] += 1
        else:
            counts["info"] += 1

    compile_errors = ((payload.get("analysis") or {}).get("compile_errors")) if isinstance(payload.get("analysis"), dict) else []
    if isinstance(compile_errors, list):
        counts["errors"] += len(compile_errors)

    if payload.get("tool") == "texture_asset_report":
        for texture in payload.get("textures") or []:
            if isinstance(texture, dict):
                counts["warnings"] += len(texture.get("warnings") or [])

    if payload.get("tool") == "material_preview":
        outputs = payload.get("outputs") or {}
        if outputs.get("shaded_ok") is False:
            counts["errors"] += 1
        if outputs.get("complexity_ok") is False:
            counts["warnings"] += 1

    return counts


def classify_report(payload: dict[str, Any], requested_group: str) -> str:
    if requested_group in {"texture", "preview", "audit"}:
        return requested_group
    tool = str(payload.get("tool") or "").lower()
    if tool == "texture_asset_report" or "texture" in tool:
        return "texture"
    if tool == "material_preview" or "preview" in tool:
        return "preview"
    if "audit" in tool or "linter" in tool or "permutation" in tool:
        return "audit"
    return "other"


def report_key_fields(payload: dict[str, Any]) -> dict[str, Any]:
    tool = str(payload.get("tool") or "")
    if tool == "texture_asset_report":
        return {
            "role": payload.get("role"),
            "grid": payload.get("grid"),
            "texture_count": len(payload.get("textures") or []),
            "textures": [
                {
                    "path": item.get("path"),
                    "role": item.get("role"),
                    "size": f"{item.get('width')}x{item.get('height')}",
                    "power_of_two": item.get("power_of_two"),
                    "has_alpha": item.get("has_alpha"),
                    "warnings": len(item.get("warnings") or []),
                }
                for item in payload.get("textures") or []
                if isinstance(item, dict)
            ],
        }
    if tool == "texture_set_pipeline":
        slots = payload.get("slots") or {}
        return {
            "effect": payload.get("effect"),
            "layer": payload.get("layer"),
            "profile": payload.get("profile"),
            "packed_convention": payload.get("packed_convention"),
            "passed": (payload.get("gate") or {}).get("passed"),
            "ready_for_import": (payload.get("gate") or {}).get("ready_for_import"),
            "slot_count": len(slots),
            "slots": [
                {
                    "slot": slot,
                    "label": item.get("label"),
                    "file_path": item.get("file_path"),
                    "asset_path": item.get("asset_path"),
                    "size": f"{((item.get('file') or {}).get('width'))}x{((item.get('file') or {}).get('height'))}",
                    "findings": len(item.get("findings") or []),
                    "required": item.get("required"),
                }
                for slot, item in slots.items()
                if isinstance(item, dict)
            ],
        }
    if tool == "material_preview":
        outputs = payload.get("outputs") or {}
        options = payload.get("options") or {}
        return {
            "mode": payload.get("mode"),
            "material_path": payload.get("material_path"),
            "carrier": options.get("carrier"),
            "preview_route": options.get("preview_route"),
            "shaded_png": outputs.get("shaded_png"),
            "shaded_ok": outputs.get("shaded_ok"),
            "complexity_png": outputs.get("complexity_png"),
            "complexity_ok": outputs.get("complexity_ok"),
        }
    if tool == "material_audit":
        info = payload.get("material_info") or {}
        analysis = payload.get("analysis") or {}
        graph_summary = payload.get("graph_summary") or {}
        return {
            "material_path": payload.get("material_path"),
            "domain": info.get("material_domain"),
            "blend_mode": info.get("blend_mode"),
            "shading_models": info.get("shading_models"),
            "instructions": analysis.get("max_instructions"),
            "samplers": analysis.get("sampler_count"),
            "compile_errors": len(analysis.get("compile_errors") or []),
            "dead_nodes": len(graph_summary.get("dead_nodes") or []),
            "stale_overrides": len(payload.get("stale_overrides") or []),
        }
    if tool == "material_domain_audit":
        contract = payload.get("domain_contract") or {}
        analysis = payload.get("analysis") or {}
        return {
            "material_path": payload.get("material_path"),
            "domain": contract.get("domain") or analysis.get("material_domain"),
            "blend_mode": contract.get("blend_mode"),
            "shading_models": contract.get("shading_models") or analysis.get("shading_models"),
            "wired_outputs": contract.get("wired_outputs"),
            "instructions": analysis.get("max_instructions"),
            "samplers": analysis.get("sampler_count"),
        }
    return {
        "effect": payload.get("effect"),
        "layer": payload.get("layer"),
        "material_path": payload.get("material_path"),
    }


def summarize_report(path: Path, requested_group: str) -> dict[str, Any]:
    payload, error = load_json(path)
    if payload is None:
        return {
            "path": str(path),
            "exists": path.exists(),
            "group": requested_group,
            "tool": "",
            "load_error": error,
            "counts": {"errors": 1 if error else 0, "warnings": 0, "info": 0, "ok": 0},
            "key_fields": {},
            "findings": [],
        }
    group = classify_report(payload, requested_group)
    findings = collect_findings(payload)
    return {
        "path": str(path),
        "exists": True,
        "group": group,
        "tool": payload.get("tool", ""),
        "load_error": "",
        "counts": report_counts(payload),
        "key_fields": report_key_fields(payload),
        "findings": [
            {
                "severity": item.get("severity"),
                "rule": item.get("rule") or item.get("rule_id"),
                "message": item.get("message"),
            }
            for item in findings[:20]
        ],
    }


def texture_report_blob(report: dict[str, Any]) -> str:
    fields = report.get("key_fields") or {}
    parts: list[str] = []
    for item in fields.get("textures") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("path") or ""))
            parts.append(str(item.get("role") or ""))
    for item in fields.get("slots") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("slot") or ""))
            parts.append(str(item.get("label") or ""))
            parts.append(str(item.get("file_path") or ""))
            parts.append(str(item.get("asset_path") or ""))
    parts.append(str(fields.get("role") or ""))
    parts.append(str(fields.get("profile") or ""))
    parts.append(str(fields.get("packed_convention") or ""))
    return " ".join(parts).lower()


def build_texture_coverage(plan: dict[str, Any] | None, texture_reports: list[dict[str, Any]]) -> dict[str, Any]:
    requirements = list((plan or {}).get("texture_requirements") or [])
    rows = []
    for requirement in requirements:
        name = str(requirement.get("name") or "").lower()
        role = str(requirement.get("role") or "").lower()
        matches = []
        for report in texture_reports:
            blob = texture_report_blob(report)
            if (name and name in blob) or (role and role in blob and len(requirements) == 1):
                matches.append(report["path"])
        rows.append(
            {
                "name": requirement.get("name"),
                "role": requirement.get("role"),
                "required": True,
                "covered": bool(matches),
                "matched_reports": matches,
            }
        )
    return {
        "required_count": len(rows),
        "covered_count": sum(1 for item in rows if item["covered"]),
        "missing_count": sum(1 for item in rows if not item["covered"]),
        "items": rows,
    }


def route_summary(plan: dict[str, Any] | None, contract: dict[str, Any] | None) -> dict[str, Any]:
    route = dict((plan or {}).get("material_route") or {})
    contract_material = dict((contract or {}).get("material") or {})
    carrier = dict((plan or {}).get("carrier_contract") or {})
    contract_carrier = dict((contract or {}).get("carrier") or {})
    return {
        "carrier": carrier.get("carrier") or contract_carrier.get("renderer") or "",
        "uv_expectations": carrier.get("uv_expectations") or contract_carrier.get("uv_expectations") or "",
        "domain": route.get("domain") or contract_material.get("domain") or "",
        "blend_mode": route.get("blend_mode") or contract_material.get("blend_mode") or "",
        "shading_model": route.get("shading_model") or contract_material.get("shading_model") or "",
        "two_sided": route.get("two_sided") if "two_sided" in route else contract_material.get("two_sided"),
        "expected_outputs": route.get("expected_outputs") or contract_material.get("expected_outputs") or [],
        "usage_flags": route.get("usage_flags") or contract_material.get("usage_flags") or [],
    }


def build_gate(
    *,
    plan_summary: dict[str, Any],
    contract_summary: dict[str, Any],
    reports_by_group: dict[str, list[dict[str, Any]]],
    texture_coverage: dict[str, Any],
    material_path: str,
    require_material: bool,
    require_preview: bool,
    require_audit: bool,
    require_textures: bool,
) -> dict[str, Any]:
    missing: list[str] = []
    warnings: list[str] = []
    if not plan_summary.get("exists"):
        missing.append("plan")
    if not contract_summary.get("exists"):
        missing.append("contract")
    if require_preview and not reports_by_group["preview"]:
        missing.append("preview_report")
    if require_audit and not reports_by_group["audit"]:
        missing.append("audit_report")
    if require_textures and texture_coverage["missing_count"]:
        missing.append("texture_reports")
    if require_material and not material_path.strip():
        missing.append("material_path")

    total_counts = {"errors": 0, "warnings": 0, "info": 0, "ok": 0}
    for summary in [plan_summary, contract_summary]:
        for key, value in (summary.get("counts") or {}).items():
            if key in total_counts:
                total_counts[key] += int(value or 0)
    for reports in reports_by_group.values():
        for report in reports:
            for key, value in (report.get("counts") or {}).items():
                if key in total_counts:
                    total_counts[key] += int(value or 0)

    if plan_summary.get("exists") and plan_summary.get("counts", {}).get("warnings"):
        warnings.append("plan_has_warnings")
    if contract_summary.get("exists") and contract_summary.get("counts", {}).get("warnings"):
        warnings.append("contract_has_warnings")

    return {
        "ready_for_handoff": not missing and total_counts["errors"] == 0,
        "missing_required": missing,
        "warnings": warnings,
        "counts": total_counts,
        "required_checks": {
            "plan": bool(plan_summary.get("exists")),
            "contract": bool(contract_summary.get("exists")),
            "material_path": bool(material_path.strip()),
            "preview_report": bool(reports_by_group["preview"]),
            "audit_report": bool(reports_by_group["audit"]),
            "texture_reports": texture_coverage["missing_count"] == 0,
        },
    }


def collect_report_inputs(args: argparse.Namespace) -> dict[str, list[Path]]:
    result = {
        "texture": [Path(item) for item in args.texture_report],
        "preview": [Path(item) for item in args.preview_report],
        "audit": [Path(item) for item in args.audit_report],
        "other": [Path(item) for item in args.report],
    }
    return result


def build_package(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    plan_path = Path(args.plan) if args.plan else None
    plan_payload: dict[str, Any] | None = None
    if plan_path is not None:
        plan_payload, _ = load_json(plan_path)

    effect = args.effect or str((plan_payload or {}).get("effect") or "Material")
    layer = args.layer or str((plan_payload or {}).get("layer") or "MainMaterial")

    if plan_path is None:
        plan_path = default_plan_path(ctx, effect, layer)
        plan_payload, _ = load_json(plan_path)

    if plan_payload is None and plan_path.exists():
        plan_payload, _ = load_json(plan_path)

    contract_path = Path(args.contract) if args.contract else None
    if contract_path is None and plan_payload:
        candidate = str(plan_payload.get("material_contract_path") or "").strip()
        contract_path = Path(candidate) if candidate else None
    if contract_path is None:
        contract_path = default_contract_path(ctx, effect, layer)

    contract_payload, _ = load_json(contract_path)

    plan_summary = summarize_report(plan_path, "other")
    contract_summary = summarize_report(contract_path, "other")
    report_inputs = collect_report_inputs(args)
    reports_by_group: dict[str, list[dict[str, Any]]] = {key: [] for key in REPORT_GROUPS}
    for requested_group, paths in report_inputs.items():
        for path in paths:
            summary = summarize_report(path, requested_group)
            reports_by_group[summary["group"]].append(summary)

    texture_coverage = build_texture_coverage(plan_payload, reports_by_group["texture"])
    package = {
        "tool": "delivery_packager",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "material_path": args.material_path,
        "delivery_notes": args.note,
        "risk_notes": args.risk_note,
        "manual_next_steps": args.next_step,
        "source": {
            "plan_path": str(plan_path),
            "contract_path": str(contract_path),
        },
        "route": route_summary(plan_payload, contract_payload),
        "visual_contract": (plan_payload or {}).get("visual_contract") or {},
        "texture_requirements": (plan_payload or {}).get("texture_requirements") or (contract_payload or {}).get("textures") or [],
        "parameters": (plan_payload or {}).get("parameters") or (contract_payload or {}).get("parameters") or [],
        "budgets": (plan_payload or {}).get("budgets") or (contract_payload or {}).get("budgets") or {},
        "summaries": {
            "plan": plan_summary,
            "contract": contract_summary,
            "reports": reports_by_group,
            "texture_coverage": texture_coverage,
        },
        "gate": {},
        "next_actions": [],
    }
    package["gate"] = build_gate(
        plan_summary=plan_summary,
        contract_summary=contract_summary,
        reports_by_group=reports_by_group,
        texture_coverage=texture_coverage,
        material_path=args.material_path,
        require_material=not args.no_require_material,
        require_preview=not args.no_require_preview,
        require_audit=not args.no_require_audit,
        require_textures=not args.no_require_textures,
    )
    generated_next = []
    missing = package["gate"]["missing_required"]
    if "plan" in missing:
        generated_next.append("Create a reference_to_material_plan for this effect/layer.")
    if "contract" in missing:
        generated_next.append("Emit or validate a material contract for the planned route.")
    if "texture_reports" in missing:
        generated_next.append("Run texture_asset_report.py for each required texture and rebuild the package.")
    if "material_path" in missing:
        generated_next.append("Set --material-path to the final Unreal material or material instance asset.")
    if "preview_report" in missing:
        generated_next.append("Render a material_preview.py report on the intended carrier.")
    if "audit_report" in missing:
        generated_next.append("Run material_audit.py and material_domain_audit.py for the final material.")
    if package["gate"]["counts"]["errors"]:
        generated_next.append("Fix report errors before considering the material handoff-ready.")
    package["next_actions"] = generated_next + args.next_step

    stem = slugify(f"{effect}-{layer}")
    out = Path(args.out) if args.out else default_report_path(ctx, "packages", stem, "material-delivery-package", ".json")
    return package, out


def render_markdown(package: dict[str, Any]) -> str:
    gate = package["gate"]
    route = package.get("route") or {}
    summaries = package.get("summaries") or {}
    reports = summaries.get("reports") or {}
    texture_coverage = summaries.get("texture_coverage") or {}
    lines = [
        f"# Material Delivery Package: {package.get('effect')} / {package.get('layer')}",
        "",
        f"- Ready for handoff: `{gate.get('ready_for_handoff')}`",
        f"- Material path: `{package.get('material_path') or 'unset'}`",
        f"- Plan: `{package['source'].get('plan_path')}`",
        f"- Contract: `{package['source'].get('contract_path')}`",
        f"- Missing required: `{', '.join(gate.get('missing_required') or []) or 'none'}`",
        f"- Errors: `{gate['counts'].get('errors')}`",
        f"- Warnings: `{gate['counts'].get('warnings')}`",
        "",
        "## Route",
        "",
        f"- Carrier: `{route.get('carrier')}`",
        f"- Domain: `{route.get('domain')}`",
        f"- Blend mode: `{route.get('blend_mode')}`",
        f"- Shading model: `{route.get('shading_model')}`",
        f"- Outputs: {', '.join(route.get('expected_outputs') or []) or 'unset'}",
        "",
        "## Evidence",
        "",
        f"- Texture reports: `{len(reports.get('texture') or [])}`",
        f"- Preview reports: `{len(reports.get('preview') or [])}`",
        f"- Audit reports: `{len(reports.get('audit') or [])}`",
        f"- Texture coverage: `{texture_coverage.get('covered_count', 0)}/{texture_coverage.get('required_count', 0)}`",
    ]
    if texture_coverage.get("items"):
        lines.extend(["", "Texture Coverage:"])
        for item in texture_coverage["items"]:
            lines.append(f"- `{item.get('name')}` role=`{item.get('role')}` covered=`{item.get('covered')}`")

    for group in REPORT_GROUPS:
        group_reports = reports.get(group) or []
        if not group_reports:
            continue
        lines.extend(["", f"## {group.title()} Reports", ""])
        for report in group_reports:
            counts = report.get("counts") or {}
            lines.append(
                f"- `{report.get('path')}` tool=`{report.get('tool') or 'unknown'}` "
                f"errors=`{counts.get('errors', 0)}` warnings=`{counts.get('warnings', 0)}`"
            )

    if package.get("risk_notes"):
        lines.extend(["", "## Risk Notes", ""])
        lines.extend(f"- {item}" for item in package["risk_notes"])

    lines.extend(["", "## Next Actions", ""])
    if package.get("next_actions"):
        lines.extend(f"- {item}" for item in package["next_actions"])
    else:
        lines.append("- No next actions generated.")
    return "\n".join(lines).rstrip() + "\n"


def command_build(args: argparse.Namespace) -> int:
    package, out = build_package(args)
    save_json(out, package)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(package))
    print(out)
    if args.strict and not package["gate"]["ready_for_handoff"]:
        return 1
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.package)
    package, error = load_json(path)
    if package is None:
        print(json.dumps({"valid": False, "error": error}, ensure_ascii=False, indent=2))
        return 1
    gate = package.get("gate") or {}
    result = {
        "valid": package.get("tool") == "delivery_packager" and "ready_for_handoff" in gate,
        "ready_for_handoff": gate.get("ready_for_handoff"),
        "missing_required": gate.get("missing_required") or [],
        "counts": gate.get("counts") or {},
    }
    if args.markdown:
        out = Path(args.out) if args.out else path.with_suffix(".md")
        write_text(out, render_markdown(package))
        print(out)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] and (result["ready_for_handoff"] or not args.strict) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gather material plan, contract, reports, and risks into one delivery package.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a material delivery package.")
    build.add_argument("--root", default="auto")
    build.add_argument("--effect")
    build.add_argument("--layer")
    build.add_argument("--plan")
    build.add_argument("--contract")
    build.add_argument("--material-path", default="")
    build.add_argument("--texture-report", action="append", default=[])
    build.add_argument("--preview-report", action="append", default=[])
    build.add_argument("--audit-report", action="append", default=[])
    build.add_argument("--report", action="append", default=[], help="Additional JSON report; group is inferred from its tool field.")
    build.add_argument("--note", action="append", default=[])
    build.add_argument("--risk-note", action="append", default=[])
    build.add_argument("--next-step", action="append", default=[])
    build.add_argument("--no-require-preview", action="store_true")
    build.add_argument("--no-require-audit", action="store_true")
    build.add_argument("--no-require-textures", action="store_true")
    build.add_argument("--no-require-material", action="store_true")
    build.add_argument("--out")
    build.add_argument("--markdown", action="store_true")
    build.add_argument("--strict", action="store_true", help="Return non-zero when the package is not handoff-ready.")
    build.set_defaults(func=command_build)

    validate = sub.add_parser("validate", help="Validate an existing delivery package.")
    validate.add_argument("package")
    validate.add_argument("--out")
    validate.add_argument("--markdown", action="store_true")
    validate.add_argument("--strict", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
