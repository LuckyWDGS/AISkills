from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import (
    _text,
    collect_findings,
    evidence_rows,
    load_json,
    material_route,
    package_report_paths,
    resolve_path,
    rows_by_tool,
    severity_counts,
)


TRANSLUCENT_BLENDS = {"additive", "translucent", "alphacomposite", "alpha composite", "modulate"}
TRANSLUCENT_CARRIERS = {"sprite", "ribbon", "decal"}
TRANSLUCENT_DOMAINS = {"deferreddecal", "deferred decal", "decal"}


def contract_path_from_package(package: dict[str, Any], package_path: Path, explicit: str = "") -> Path | None:
    if explicit:
        return resolve_path(explicit, base=Path.cwd())
    source = package.get("source") if isinstance(package.get("source"), dict) else {}
    if source.get("contract_path"):
        return resolve_path(str(source["contract_path"]), base=package_path.parent)
    return None


def collect_rows(args: argparse.Namespace, package: dict[str, Any], package_path: Path, contract_path: Path | None) -> list[dict[str, Any]]:
    paths = package_report_paths(package, package_path=package_path) if package else []
    if contract_path:
        paths.append(contract_path)
    for values in (
        args.audit_report,
        args.domain_audit_report,
        args.preview_report,
        args.material_integration_probe,
        args.niagara_audit_report,
    ):
        for value in values:
            paths.append(resolve_path(value, base=Path.cwd()))
    return evidence_rows(paths)


def route_is_applicable(route: dict[str, Any]) -> bool:
    blend = _text(route.get("blend_mode")).replace("_", "").lower()
    carrier = _text(route.get("carrier")).lower()
    domain = _text(route.get("material_domain")).replace("_", "").lower()
    return blend in TRANSLUCENT_BLENDS or carrier in TRANSLUCENT_CARRIERS or domain in TRANSLUCENT_DOMAINS


def node_blob(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        payload = row.get("payload") or {}
        if row.get("tool") == "material_audit":
            raw = payload.get("raw_graph") if isinstance(payload.get("raw_graph"), dict) else {}
            graph = payload.get("graph") if isinstance(payload.get("graph"), dict) else {}
            for node in list(raw.get("nodes") or []) + list(graph.get("nodes") or []):
                if isinstance(node, dict):
                    parts.extend(str(node.get(key) or "") for key in ("class_name", "caption", "desc", "key_properties"))
            graph_summary = payload.get("graph_summary") if isinstance(payload.get("graph_summary"), dict) else {}
            for node in graph_summary.get("dead_nodes") or []:
                if isinstance(node, dict):
                    parts.extend(str(node.get(key) or "") for key in ("class_name", "caption", "desc", "key_properties"))
        if row.get("tool") == "material_domain_audit":
            evidence = payload.get("node_evidence") if isinstance(payload.get("node_evidence"), dict) else {}
            parts.append(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
            parts.extend(str(item.get("message") or "") for item in collect_findings(payload) if isinstance(item, dict))
    return "\n".join(parts).lower()


def has_any(blob: str, *tokens: str) -> bool:
    return any(token.lower() in blob for token in tokens)


def sorting_contract_text(package: dict[str, Any], contract: dict[str, Any] | None) -> str:
    carrier = (contract or {}).get("carrier") if isinstance((contract or {}).get("carrier"), dict) else {}
    parts = [
        carrier.get("sort_or_depth_notes") if isinstance(carrier, dict) else "",
        " ".join(str(item) for item in package.get("risk_notes") or []),
        " ".join(str(item) for item in package.get("delivery_notes") or []),
    ]
    return " ".join(str(part or "") for part in parts).strip()


def probe_blob(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        if row.get("tool") not in {"niagara_material_integration_probe", "niagara_audit"}:
            continue
        payload = row.get("payload") or {}
        parts.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts).lower()


def integration_probe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows_by_tool(rows, "niagara_material_integration_probe")


def niagara_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows_by_tool(rows, "niagara_audit")


def fixed_bounds_present(rows: list[dict[str, Any]], blob: str) -> bool:
    if has_any(blob, "fixedbounds", "fixed bounds"):
        return True
    for row in niagara_audit_rows(rows):
        system_props = (row.get("payload") or {}).get("system_properties")
        if isinstance(system_props, dict):
            text = str(((system_props.get("FixedBounds") or {}).get("text")) if isinstance(system_props.get("FixedBounds"), dict) else "")
            if text.strip():
                return True
    return False


def integration_sorting_present(rows: list[dict[str, Any]], blob: str) -> bool:
    if has_any(blob, "sortmode", "customsortingbinding", "sortkey", "sorting") and not has_any(blob, "sorting_unproven"):
        return True
    for row in integration_probe_rows(rows):
        for finding in (row.get("payload") or {}).get("findings") or []:
            if isinstance(finding, dict) and finding.get("rule") == "sorting" and finding.get("severity") == "ok":
                return True
    return False


def add_finding(findings: list[dict[str, Any]], severity: str, rule: str, message: str, evidence: str = "") -> None:
    findings.append({"severity": severity, "rule": rule, "message": message, "evidence": evidence})


def build_findings(args: argparse.Namespace, package: dict[str, Any], contract: dict[str, Any] | None, rows: list[dict[str, Any]], route: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    applicable = route_is_applicable(route)
    if not applicable:
        add_finding(findings, "ok", "not_translucent_route", "Route is not Additive/Translucent/Ribbon/Decal, so sorting probe is not required.")
        return findings

    blend = _text(route.get("blend_mode"))
    carrier = _text(route.get("carrier"))
    domain = _text(route.get("material_domain"))
    add_finding(findings, "info", "translucency_route", "Route needs translucency/depth/sorting evidence.", f"blend={blend} carrier={carrier} domain={domain}")

    graph_blob = node_blob(rows)
    live_blob = probe_blob(rows)
    has_depth_fade = has_any(graph_blob, "depthfade", "depth fade", "scenedepth", "pixeldepth", "softparticle", "soft particle")
    has_soft_particle = has_any(graph_blob, "softparticle", "soft particle") or has_depth_fade
    if has_depth_fade:
        add_finding(findings, "ok", "depth_fade", "Material graph has DepthFade/scene-depth style mitigation evidence.")
    else:
        severity = "error" if args.require_depth_fade else "warning"
        add_finding(findings, severity, "depth_fade_missing", "No material-side DepthFade/SoftParticle evidence was found.")
    if has_soft_particle:
        add_finding(findings, "ok", "soft_particle", "Soft-particle style edge mitigation is present or covered by DepthFade.")

    sort_text = sorting_contract_text(package, contract)
    if sort_text:
        add_finding(findings, "ok", "sorting_contract", "Sorting/depth notes are documented in the material contract/package.", sort_text)
    else:
        severity = "error" if args.require_proven else "warning"
        add_finding(findings, severity, "sorting_contract_missing", "No sort/depth notes were found in the material contract/package.")

    sorting_present = integration_sorting_present(rows, live_blob)
    if sorting_present:
        add_finding(findings, "ok", "system_sorting", "Niagara probe/audit evidence includes SortMode, CustomSortingBinding, SortKey, or equivalent sorting proof.")
    else:
        severity = "error" if args.require_proven else "warning"
        add_finding(findings, severity, "sorting_unproven", "System-level sorting remains unproven; provide niagara_material_integration_probe.py or niagara_audit.py evidence.")

    bounds_present = fixed_bounds_present(rows, live_blob)
    if bounds_present:
        add_finding(findings, "ok", "bounds", "Bounds evidence exists for the translucent/VFX route.")
    else:
        severity = "error" if args.require_bounds else "warning"
        add_finding(findings, severity, "bounds_unproven", "Bounds evidence is missing or unproven for a translucent/VFX route.")

    if has_any(live_blob, "customsortingbinding", "custom sorting"):
        add_finding(findings, "ok", "custom_sorting", "Custom sorting binding evidence exists.")
    elif _text(carrier).lower() == "ribbon":
        add_finding(findings, "info", "custom_sorting_not_required", "Ribbon route has no custom sorting evidence; this can be acceptable if SortMode and bounds are documented.")

    overdraw_risk = _text(((contract or {}).get("budgets") or {}).get("overdraw_risk") or package.get("overdraw_risk")).lower()
    if overdraw_risk in {"high", "very_high", "very high"} and not has_depth_fade:
        add_finding(findings, "warning", "overdraw_risk", "High overdraw risk without DepthFade/SoftParticle mitigation.")
    elif overdraw_risk:
        add_finding(findings, "info", "overdraw_risk", f"Overdraw risk is documented as `{overdraw_risk}`.")

    if not integration_probe_rows(rows):
        add_finding(findings, "info", "niagara_probe_boundary", "Material-side probe can flag risk, but real renderer sorting proof should come from niagara-vfx-artist.")
    return findings


def counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    return severity_counts(findings)


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package_path = resolve_path(args.package, base=Path.cwd()) if args.package else None
    package = load_json(package_path) if package_path else {}
    contract_path = contract_path_from_package(package, package_path or Path.cwd(), args.contract)
    contract = load_json(contract_path) if contract_path else None
    rows = collect_rows(args, package, package_path or Path.cwd(), contract_path)
    route = material_route(package, contract)
    if args.material_path:
        route["material_path"] = args.material_path
    findings = build_findings(args, package, contract, rows, route)
    summary = counts(findings)
    applicable = route_is_applicable(route)
    warning_block = bool(args.fail_on_warning and summary["warnings"])
    passed = summary["errors"] == 0 and not warning_block
    sorting_proven = bool(
        not applicable
        or (
            summary["errors"] == 0
            and not any(item.get("rule") in {"sorting_unproven", "bounds_unproven", "sorting_contract_missing"} and item.get("severity") in {"warning", "error"} for item in findings)
        )
    )
    report = {
        "tool": "translucency_sorting_probe",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": args.effect or package.get("effect") or "",
        "layer": args.layer or package.get("layer") or "",
        "material_path": args.material_path or package.get("material_path") or "",
        "route": route,
        "evidence": {
            "package": str(package_path or ""),
            "contract": str(contract_path or ""),
            "material_audits": [row["path"] for row in rows_by_tool(rows, "material_audit")],
            "domain_audits": [row["path"] for row in rows_by_tool(rows, "material_domain_audit")],
            "previews": [row["path"] for row in rows_by_tool(rows, "material_preview")],
            "material_integration_probes": [row["path"] for row in integration_probe_rows(rows)],
            "niagara_audits": [row["path"] for row in niagara_audit_rows(rows)],
        },
        "findings": findings,
        "summary": summary,
        "gate": {
            "applicable": applicable,
            "passed": passed,
            "sorting_proven": sorting_proven,
            "requires_triage": bool(summary["errors"] or summary["warnings"]),
            "material_preview_is_system_proof": False,
        },
        "next_actions": next_actions(findings),
    }
    stem = slugify(args.effect or package.get("effect") or args.material_path or "translucency-sorting")
    out = Path(args.out) if args.out else default_report_path(ctx, "translucency-sorting", stem, "translucency-sorting-probe", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {str(item.get("rule") or "") for item in findings if item.get("severity") in {"error", "warning"}}
    actions: list[str] = []
    if "depth_fade_missing" in rules:
        actions.append("Add DepthFade/SoftParticle mitigation or document why the translucent edge should remain hard.")
    if "sorting_contract_missing" in rules:
        actions.append("Record sorting/depth behavior in material_contract.py carrier.sort_or_depth_notes.")
    if "sorting_unproven" in rules:
        actions.append("Run niagara_material_integration_probe.py or provide Niagara audit renderer SortMode/CustomSorting evidence.")
    if "bounds_unproven" in rules:
        actions.append("Provide FixedBounds evidence from Niagara or document the non-Niagara carrier bounds policy.")
    if not actions:
        actions.append("No translucency sorting blockers detected by this probe.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    lines = [
        f"# Translucency Sorting Probe: {report.get('effect') or report.get('material_path')}",
        "",
        f"- Applicable: `{gate.get('applicable')}`",
        f"- Passed: `{gate.get('passed')}`",
        f"- Sorting proven: `{gate.get('sorting_proven')}`",
        f"- Errors: `{summary.get('errors', 0)}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Findings",
        "",
    ]
    for item in report.get("findings") or []:
        lines.append(f"- [{item.get('severity')}] `{item.get('rule')}` {item.get('message')} {item.get('evidence') or ''}".rstrip())
    lines.extend(["", "## Evidence", ""])
    for key, value in (report.get("evidence") or {}).items():
        if isinstance(value, list):
            lines.append(f"- `{key}`: `{len(value)}`")
            for path in value[:8]:
                lines.append(f"- `{path}`")
        else:
            lines.append(f"- `{key}`: `{value or 'none'}`")
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
    if args.require_proven and not (report.get("gate") or {}).get("sorting_proven"):
        print(f"Translucency sorting remains unproven: {out}", file=sys.stderr)
        return 2
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check material-side and optional Niagara evidence for translucent/additive/ribbon/decal sorting risk.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--package", default="", help="delivery_packager.py JSON report.")
    parser.add_argument("--contract", default="", help="material_contract.py JSON report.")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--audit-report", action="append", default=[])
    parser.add_argument("--domain-audit-report", action="append", default=[])
    parser.add_argument("--preview-report", action="append", default=[])
    parser.add_argument("--material-integration-probe", action="append", default=[], help="niagara_material_integration_probe.py JSON evidence.")
    parser.add_argument("--niagara-audit-report", action="append", default=[], help="niagara_audit.py JSON evidence.")
    parser.add_argument("--require-depth-fade", action="store_true")
    parser.add_argument("--require-bounds", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--require-proven", action="store_true", help="Return 2 unless sorting_proven=true.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.package or args.audit_report or args.domain_audit_report):
        parser.error("Provide --package or material audit/domain-audit evidence.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
