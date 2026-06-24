from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_contract import validate_contract


CHECK_ORDER = (
    "package",
    "contract",
    "preview",
    "audit",
    "texture_set",
    "regression",
    "budget",
    "usage_flags",
    "parameters",
)

NIAGARA_USAGE_BY_CARRIER = {
    "sprite": "NiagaraSprites",
    "ribbon": "NiagaraRibbons",
    "mesh": "NiagaraMeshParticles",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"JSON file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to load JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def try_load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"invalid_json: {exc}"
    if not isinstance(payload, dict):
        return None, "json_root_not_object"
    return payload, ""


def resolve_path(path_text: str, *, base: Path) -> Path:
    path = Path(str(path_text or "").strip())
    if path.is_absolute():
        return path
    candidate = (base / path).resolve()
    if candidate.exists():
        return candidate
    return path


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_asset_ref(value: Any) -> str:
    text = _text(value).strip("'\"")
    if not text:
        return ""
    if "'" in text and text.count("'") >= 2:
        parts = text.split("'")
        if len(parts) >= 2:
            text = parts[1]
    if text.startswith("/Game") and "." in text.rsplit("/", 1)[-1]:
        text = text.rsplit(".", 1)[0]
    return text


def asset_refs_match(left: Any, right: Any) -> bool:
    a = normalize_asset_ref(left)
    b = normalize_asset_ref(right)
    return bool(a and b and a == b)


def normalize_usage_flag(value: Any) -> str:
    text = "".join(ch for ch in _text(value) if ch.isalnum()).lower()
    for prefix in ("busedwith", "usedwith", "matusage"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    aliases = {
        "niagarasprite": "niagarasprites",
        "niagarasprites": "niagarasprites",
        "niagararibbon": "niagararibbons",
        "niagararibbons": "niagararibbons",
        "niagarameshparticle": "niagarameshparticles",
        "niagarameshparticles": "niagarameshparticles",
        "particlesprite": "particlesprites",
        "particlesprites": "particlesprites",
        "meshparticle": "meshparticles",
        "meshparticles": "meshparticles",
    }
    return aliases.get(text, text)


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity") or finding.get("level") or "info").lower()
        if severity in {"error", "fatal"}:
            counts["errors"] += 1
        elif severity in {"warning", "warn"}:
            counts["warnings"] += 1
        else:
            counts["info"] += 1
    return counts


def collect_findings(payload: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            raw = value.get("findings")
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and (item.get("severity") or item.get("level")):
                        findings.append(item)
            for key, child in value.items():
                if key != "findings":
                    walk(child)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return findings


def make_check(
    name: str,
    *,
    label: str,
    passed: bool,
    detail: str,
    errors: int = 0,
    warnings: int = 0,
    evidence: list[str] | None = None,
    action_needed: str = "No action needed.",
    required: bool = True,
    waived: bool = False,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not required and not evidence and passed:
        status = "not_applicable"
    elif errors:
        status = "fail"
    elif warnings:
        status = "warning"
    elif passed:
        status = "pass"
    else:
        status = "missing"
    return {
        "name": name,
        "label": label,
        "required": required,
        "waived": waived,
        "status": status,
        "passed": bool(passed and errors == 0),
        "errors": int(errors),
        "warnings": int(warnings),
        "detail": detail,
        "evidence": evidence or [],
        "action_needed": action_needed,
        "data": data or {},
    }


def package_report_paths(package: dict[str, Any], *, package_path: Path) -> list[Path]:
    paths: list[Path] = []
    reports = (((package.get("summaries") or {}).get("reports")) or {})
    if isinstance(reports, dict):
        for rows in reports.values():
            for row in rows or []:
                if isinstance(row, dict) and row.get("path"):
                    paths.append(resolve_path(str(row["path"]), base=package_path.parent))
    return unique_paths(paths)


def unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def evidence_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in unique_paths(paths):
        payload, error = try_load_json(path)
        rows.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "load_error": error,
                "tool": (payload or {}).get("tool", ""),
                "payload": payload,
            }
        )
    return rows


def rows_by_tool(rows: list[dict[str, Any]], *tools: str) -> list[dict[str, Any]]:
    wanted = set(tools)
    return [row for row in rows if row.get("tool") in wanted]


def contract_path_from_args(args: argparse.Namespace, package: dict[str, Any], package_path: Path) -> Path | None:
    if args.contract:
        return resolve_path(args.contract, base=Path.cwd())
    source = package.get("source") if isinstance(package.get("source"), dict) else {}
    if source.get("contract_path"):
        return resolve_path(str(source["contract_path"]), base=package_path.parent)
    return None


def package_material_path(args: argparse.Namespace, package: dict[str, Any]) -> str:
    return normalize_asset_ref(args.material_path or package.get("material_path") or "")


def infer_category_role(package: dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    route = package.get("route") if isinstance(package.get("route"), dict) else {}
    domain = _text(route.get("domain") or route.get("material_domain")).lower()
    carrier = _text(route.get("carrier")).lower()
    if args.category and args.role:
        return args.category, args.role
    if domain in {"deferreddecal", "deferred decal", "decal"}:
        return args.category or "decal", args.role or "decal-material"
    if domain in {"postprocess", "post process", "post_process"}:
        return args.category or "post_process", args.role or "post-process-material"
    if carrier in {"sprite", "ribbon", "mesh"}:
        return args.category or "other", args.role or f"niagara-{carrier}-material"
    if domain == "surface":
        return args.category or "surface", args.role or "surface-material"
    return args.category or "other", args.role or "material"


def material_route(package: dict[str, Any], contract: dict[str, Any] | None) -> dict[str, Any]:
    route = package.get("route") if isinstance(package.get("route"), dict) else {}
    material = (contract or {}).get("material") if isinstance((contract or {}).get("material"), dict) else {}
    domain = route.get("domain") or material.get("domain") or ""
    blend_mode = route.get("blend_mode") or material.get("blend_mode") or ""
    shading_model = route.get("shading_model") or material.get("shading_model") or ""
    shading_models = route.get("shading_models") or material.get("shading_models") or []
    if not shading_models and shading_model:
        shading_models = [shading_model]
    return {
        "carrier": route.get("carrier") or ((contract or {}).get("carrier") or {}).get("renderer") or "",
        "material_domain": domain,
        "blend_mode": blend_mode,
        "shading_model": shading_model,
        "shading_models": list(_as_list(shading_models)),
        "two_sided": route.get("two_sided") if "two_sided" in route else material.get("two_sided"),
        "expected_outputs": list(_as_list(route.get("expected_outputs") or material.get("expected_outputs"))),
        "usage_flags": list(_as_list(route.get("usage_flags") or material.get("usage_flags"))),
    }


def evaluate_package(package: dict[str, Any], package_path: Path, material_path: str) -> dict[str, Any]:
    errors = 0
    warnings = 0
    details: list[str] = []
    if package.get("tool") != "delivery_packager":
        errors += 1
        details.append(f"expected delivery_packager, got `{package.get('tool')}`")
    gate = package.get("gate") if isinstance(package.get("gate"), dict) else {}
    missing = gate.get("missing_required") or []
    if missing:
        errors += len(missing)
        details.append("missing required package evidence: " + ", ".join(str(item) for item in missing))
    if gate and gate.get("ready_for_handoff") is not True:
        errors += 1
        details.append("package gate is not ready_for_handoff")
    counts = gate.get("counts") if isinstance(gate.get("counts"), dict) else {}
    if int(counts.get("errors") or 0):
        errors += int(counts.get("errors") or 0)
        details.append("package contains report errors")
    if not material_path:
        errors += 1
        details.append("final material path is missing")
    return make_check(
        "package",
        label="Delivery Package",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail="; ".join(details) or "Delivery package is structurally ready.",
        evidence=[str(package_path)],
        action_needed="Rebuild delivery_packager.py with all required evidence before acceptance." if errors else "No action needed.",
        data={"gate": gate},
    )


def evaluate_contract(contract_row: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not contract_row:
        return (
            make_check(
                "contract",
                label="Material Contract",
                passed=False,
                errors=1,
                detail="No contract path was supplied or found in the package.",
                action_needed="Create or pass a material_contract.py report.",
            ),
            None,
        )
    if contract_row.get("load_error"):
        return (
            make_check(
                "contract",
                label="Material Contract",
                passed=False,
                errors=1,
                detail=f"Contract could not be loaded: {contract_row.get('load_error')}",
                evidence=[contract_row["path"]],
                action_needed="Fix the contract JSON path or regenerate material_contract.py.",
            ),
            None,
        )
    payload = contract_row.get("payload") or {}
    findings = validate_contract(payload)
    if payload.get("tool") != "material_contract":
        findings.append({"severity": "error", "rule": "wrong_tool", "message": f"Expected material_contract, got `{payload.get('tool')}`."})
    counts = severity_counts(findings)
    return (
        make_check(
            "contract",
            label="Material Contract",
            passed=counts["errors"] == 0,
            errors=counts["errors"],
            warnings=counts["warnings"],
            detail=f"Contract findings: errors={counts['errors']} warnings={counts['warnings']}.",
            evidence=[contract_row["path"]],
            action_needed="Fix contract errors/warnings or explicitly allow warnings before acceptance." if counts["errors"] or counts["warnings"] else "No action needed.",
            data={"findings": findings[:40]},
        ),
        payload,
    )


def preview_material_path(payload: dict[str, Any]) -> str:
    return normalize_asset_ref(payload.get("material_path") or payload.get("material_instance_path") or "")


def evaluate_preview(rows: list[dict[str, Any]], material_path: str) -> dict[str, Any]:
    preview_rows = rows_by_tool(rows, "material_preview")
    if not preview_rows:
        return make_check(
            "preview",
            label="Material Preview",
            passed=False,
            errors=1,
            detail="No material_preview report found.",
            action_needed="Run material_preview.py on the final material and include it in delivery_packager.py.",
        )
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    for row in preview_rows:
        payload = row.get("payload") or {}
        outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
        if row.get("load_error"):
            errors += 1
            findings.append({"severity": "error", "rule": "preview_load_error", "message": row["load_error"], "path": row["path"]})
            continue
        if material_path and not asset_refs_match(preview_material_path(payload), material_path):
            errors += 1
            findings.append({"severity": "error", "rule": "preview_material_mismatch", "message": "Preview material path does not match final material.", "path": row["path"]})
        if outputs.get("shaded_ok") is not True:
            errors += 1
            findings.append({"severity": "error", "rule": "preview_shaded_failed", "message": "Preview shaded capture did not pass.", "path": row["path"]})
        if outputs.get("complexity_ok") is False:
            warnings += 1
            findings.append({"severity": "warning", "rule": "preview_complexity_failed", "message": "Shader complexity capture failed or exceeded its gate.", "path": row["path"]})
        contract_scan = payload.get("contract_scan") if isinstance(payload.get("contract_scan"), dict) else {}
        counts = severity_counts(collect_findings(contract_scan))
        errors += counts["errors"]
        warnings += counts["warnings"]
    return make_check(
        "preview",
        label="Material Preview",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail=f"{len(preview_rows)} preview report(s), errors={errors}, warnings={warnings}.",
        evidence=[row["path"] for row in preview_rows],
        action_needed="Refresh material_preview.py on the final material and resolve preview/contract findings." if errors or warnings else "No action needed.",
        data={"findings": findings[:40]},
    )


def _material_audit_counts(row: dict[str, Any], material_path: str) -> tuple[int, int, list[dict[str, Any]]]:
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    payload = row.get("payload") or {}
    if row.get("load_error"):
        return 1, 0, [{"severity": "error", "rule": "audit_load_error", "message": row["load_error"], "path": row["path"]}]
    info = payload.get("material_info") if isinstance(payload.get("material_info"), dict) else {}
    if material_path and not asset_refs_match(payload.get("material_path") or info.get("path"), material_path):
        errors += 1
        findings.append({"severity": "error", "rule": "audit_material_mismatch", "message": "Material audit path does not match final material.", "path": row["path"]})
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    compile_errors = analysis.get("compile_errors") or []
    if compile_errors:
        errors += len(compile_errors)
        findings.append({"severity": "error", "rule": "compile_errors", "message": "; ".join(str(item) for item in compile_errors[:5]), "path": row["path"]})
    counts = severity_counts(analysis.get("findings") or [])
    errors += counts["errors"]
    warnings += counts["warnings"]
    dead_nodes = ((payload.get("graph_summary") or {}).get("dead_nodes")) if isinstance(payload.get("graph_summary"), dict) else []
    stale = payload.get("stale_overrides") or []
    if dead_nodes:
        warnings += len(dead_nodes)
        findings.append({"severity": "warning", "rule": "dead_nodes", "message": f"{len(dead_nodes)} dead material node(s).", "path": row["path"]})
    if stale:
        warnings += len(stale)
        findings.append({"severity": "warning", "rule": "stale_overrides", "message": f"{len(stale)} stale MI override(s).", "path": row["path"]})
    return errors, warnings, findings


def _domain_audit_counts(row: dict[str, Any], material_path: str) -> tuple[int, int, list[dict[str, Any]]]:
    payload = row.get("payload") or {}
    if row.get("load_error"):
        return 1, 0, [{"severity": "error", "rule": "domain_audit_load_error", "message": row["load_error"], "path": row["path"]}]
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    if material_path and not asset_refs_match(payload.get("material_path") or ((payload.get("material_info") or {}).get("path")), material_path):
        errors += 1
        findings.append({"severity": "error", "rule": "domain_audit_material_mismatch", "message": "Domain audit path does not match final material.", "path": row["path"]})
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary:
        errors += int(summary.get("errors") or 0)
        warnings += int(summary.get("warnings") or 0)
    else:
        counts = severity_counts(collect_findings(payload))
        errors += counts["errors"]
        warnings += counts["warnings"]
    return errors, warnings, findings


def evaluate_audit(rows: list[dict[str, Any]], material_path: str, *, require_domain_audit: bool) -> dict[str, Any]:
    material_rows = rows_by_tool(rows, "material_audit")
    domain_rows = rows_by_tool(rows, "material_domain_audit")
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    if not material_rows:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_material_audit", "message": "No material_audit report found."})
    for row in material_rows:
        row_errors, row_warnings, row_findings = _material_audit_counts(row, material_path)
        errors += row_errors
        warnings += row_warnings
        findings.extend(row_findings)
    if require_domain_audit and not domain_rows:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_domain_audit", "message": "No material_domain_audit report found."})
    for row in domain_rows:
        row_errors, row_warnings, row_findings = _domain_audit_counts(row, material_path)
        errors += row_errors
        warnings += row_warnings
        findings.extend(row_findings)
    return make_check(
        "audit",
        label="Material Audits",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail=f"material_audit={len(material_rows)}, material_domain_audit={len(domain_rows)}, errors={errors}, warnings={warnings}.",
        evidence=[row["path"] for row in material_rows + domain_rows],
        action_needed="Run/fix material_audit.py and material_domain_audit.py for the final material." if errors or warnings else "No action needed.",
        data={"findings": findings[:40]},
    )


def evaluate_texture_set(package: dict[str, Any], rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    requirements = package.get("texture_requirements") or []
    coverage = ((package.get("summaries") or {}).get("texture_coverage")) if isinstance(package.get("summaries"), dict) else {}
    texture_rows = rows_by_tool(rows, "texture_set_pipeline")
    if args.no_require_texture_set:
        return make_check(
            "texture_set",
            label="Texture Set",
            passed=True,
            required=False,
            detail="Texture-set requirement disabled by --no-require-texture-set.",
        )
    if args.texture_set_waiver:
        return make_check(
            "texture_set",
            label="Texture Set",
            passed=True,
            waived=True,
            detail=f"Texture-set requirement waived: {args.texture_set_waiver}",
            evidence=[row["path"] for row in texture_rows],
            data={"waiver": args.texture_set_waiver},
        )
    if not requirements and not texture_rows:
        return make_check(
            "texture_set",
            label="Texture Set",
            passed=True,
            required=False,
            detail="No texture requirements found; texture set is not applicable.",
        )
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    if not texture_rows:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_texture_set_pipeline", "message": "Texture requirements exist but no texture_set_pipeline report was found."})
    missing_coverage = int((coverage or {}).get("missing_count") or 0) if isinstance(coverage, dict) else 0
    if missing_coverage:
        errors += missing_coverage
        findings.append({"severity": "error", "rule": "texture_coverage_missing", "message": f"{missing_coverage} planned texture requirement(s) are uncovered."})
    for row in texture_rows:
        if row.get("load_error"):
            errors += 1
            findings.append({"severity": "error", "rule": "texture_set_load_error", "message": row["load_error"], "path": row["path"]})
            continue
        payload = row.get("payload") or {}
        gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
        counts = gate.get("counts") if isinstance(gate.get("counts"), dict) else {}
        errors += int(counts.get("errors") or 0)
        warnings += int(counts.get("warnings") or 0)
        if gate.get("passed") is not True:
            errors += 1
            findings.append({"severity": "error", "rule": "texture_set_gate_failed", "message": "texture_set_pipeline gate did not pass.", "path": row["path"]})
        if gate.get("ready_for_import") is False:
            warnings += 1
            findings.append({"severity": "warning", "rule": "texture_set_not_ready_for_import", "message": "texture_set_pipeline is not warning-clean for import.", "path": row["path"]})
    return make_check(
        "texture_set",
        label="Texture Set",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail=f"{len(texture_rows)} texture_set_pipeline report(s), requirements={len(requirements)}, errors={errors}, warnings={warnings}.",
        evidence=[row["path"] for row in texture_rows],
        action_needed="Run/fix texture_set_pipeline.py or pass an explicit waiver for textureless materials." if errors or warnings else "No action needed.",
        data={"findings": findings[:40], "texture_coverage": coverage or {}},
    )


def evaluate_regression(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    regression_rows = rows_by_tool(rows, "material_regression_compare")
    if args.no_require_regression:
        return make_check(
            "regression",
            label="Material Regression",
            passed=True,
            required=False,
            detail="Regression requirement disabled by --no-require-regression.",
            evidence=[row["path"] for row in regression_rows],
        )
    if not regression_rows:
        return make_check(
            "regression",
            label="Material Regression",
            passed=False,
            errors=1,
            detail="No material_regression compare report found.",
            action_needed="Run material_regression.py compare against the accepted baseline and include the report.",
        )
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    for row in regression_rows:
        if row.get("load_error"):
            errors += 1
            findings.append({"severity": "error", "rule": "regression_load_error", "message": row["load_error"], "path": row["path"]})
            continue
        gate = (row.get("payload") or {}).get("gate") if isinstance((row.get("payload") or {}).get("gate"), dict) else {}
        errors += int(gate.get("errors") or 0)
        warnings += int(gate.get("warnings") or 0)
        if gate.get("passed") is not True:
            errors += 1
            findings.append({"severity": "error", "rule": "regression_failed", "message": "Regression gate did not pass.", "path": row["path"]})
    return make_check(
        "regression",
        label="Material Regression",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail=f"{len(regression_rows)} regression comparison report(s), errors={errors}, warnings={warnings}.",
        evidence=[row["path"] for row in regression_rows],
        action_needed="Fix the regression or explicitly accept a new baseline before material reuse approval." if errors or warnings else "No action needed.",
        data={"findings": findings[:40]},
    )


def first_material_audit(rows: list[dict[str, Any]], material_path: str) -> dict[str, Any] | None:
    for row in rows_by_tool(rows, "material_audit"):
        payload = row.get("payload") or {}
        info = payload.get("material_info") if isinstance(payload.get("material_info"), dict) else {}
        if not material_path or asset_refs_match(payload.get("material_path") or info.get("path"), material_path):
            return payload
    return None


def evaluate_budget(package: dict[str, Any], rows: list[dict[str, Any]], material_path: str) -> dict[str, Any]:
    budgets = package.get("budgets") if isinstance(package.get("budgets"), dict) else {}
    audit = first_material_audit(rows, material_path)
    errors = 0
    warnings = 0
    findings: list[dict[str, Any]] = []
    instruction_budget = _num(budgets.get("instruction_budget"))
    sampler_budget = _num(budgets.get("sampler_budget"))
    if instruction_budget is None:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_instruction_budget", "message": "Instruction budget is missing."})
    if sampler_budget is None:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_sampler_budget", "message": "Sampler budget is missing."})
    if not audit:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_budget_audit", "message": "No matching material_audit report provides budget metrics."})
        analysis = {}
    else:
        analysis = audit.get("analysis") if isinstance(audit.get("analysis"), dict) else {}
    max_instructions = _num(analysis.get("max_instructions"))
    sampler_count = _num(analysis.get("sampler_count"))
    if max_instructions is None:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_instruction_count", "message": "Audit is missing max_instructions."})
    if sampler_count is None:
        errors += 1
        findings.append({"severity": "error", "rule": "missing_sampler_count", "message": "Audit is missing sampler_count."})
    if analysis.get("shader_stats_ready") is False:
        warnings += 1
        findings.append({"severity": "warning", "rule": "shader_stats_not_ready", "message": "Shader stats were not ready in material_audit."})
    if instruction_budget is not None and max_instructions is not None and max_instructions > instruction_budget:
        errors += 1
        findings.append({"severity": "error", "rule": "instruction_budget_exceeded", "message": f"Instructions {max_instructions:g} exceed budget {instruction_budget:g}."})
    if sampler_budget is not None and sampler_count is not None and sampler_count > sampler_budget:
        errors += 1
        findings.append({"severity": "error", "rule": "sampler_budget_exceeded", "message": f"Samplers {sampler_count:g} exceed budget {sampler_budget:g}."})
    return make_check(
        "budget",
        label="Budget",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail=f"instructions={max_instructions}, instruction_budget={instruction_budget}, samplers={sampler_count}, sampler_budget={sampler_budget}.",
        action_needed="Set budgets in the contract/package and rerun material_audit.py until measured cost is within budget." if errors or warnings else "No action needed.",
        data={"findings": findings[:40], "budgets": budgets, "measured": {"max_instructions": max_instructions, "sampler_count": sampler_count}},
    )


def actual_usage_flags(rows: list[dict[str, Any]]) -> set[str]:
    flags: set[str] = set()
    for row in rows_by_tool(rows, "material_audit"):
        info = (row.get("payload") or {}).get("material_info")
        if isinstance(info, dict):
            flags.update(normalize_usage_flag(item) for item in info.get("usage_flags") or [])
    for row in rows_by_tool(rows, "material_domain_audit"):
        contract = (row.get("payload") or {}).get("domain_contract")
        if isinstance(contract, dict):
            flags.update(normalize_usage_flag(item) for item in contract.get("usage_flags") or [])
    return {item for item in flags if item}


def expected_usage_flags(route: dict[str, Any], contract: dict[str, Any] | None) -> list[str]:
    flags: list[Any] = []
    flags.extend(route.get("usage_flags") or [])
    material = (contract or {}).get("material") if isinstance((contract or {}).get("material"), dict) else {}
    flags.extend(material.get("usage_flags") or [])
    carrier = _text(route.get("carrier") or ((contract or {}).get("carrier") or {}).get("renderer")).lower()
    if carrier in NIAGARA_USAGE_BY_CARRIER:
        flags.append(NIAGARA_USAGE_BY_CARRIER[carrier])
    normalized: list[str] = []
    for flag in flags:
        token = normalize_usage_flag(flag)
        if token and token not in normalized:
            normalized.append(token)
    return normalized


def evaluate_usage_flags(route: dict[str, Any], contract: dict[str, Any] | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected = expected_usage_flags(route, contract)
    actual = actual_usage_flags(rows)
    if not expected:
        return make_check(
            "usage_flags",
            label="Usage Flags",
            passed=True,
            required=False,
            detail="No usage flags are required by the material contract.",
            data={"expected": [], "actual": sorted(actual)},
        )
    missing = [flag for flag in expected if flag not in actual]
    errors = len(missing)
    return make_check(
        "usage_flags",
        label="Usage Flags",
        passed=not missing,
        errors=errors,
        detail=f"expected={expected}, actual={sorted(actual)}, missing={missing}.",
        action_needed="Set required material usage flags through the safe MaterialUsage setter and rerun audits." if missing else "No action needed.",
        data={"expected": expected, "actual": sorted(actual), "missing": missing},
    )


def parameter_rows(package: dict[str, Any], contract: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = package.get("parameters") if isinstance(package.get("parameters"), list) else []
    if not rows and contract and isinstance(contract.get("parameters"), list):
        rows = contract["parameters"]
    return [row for row in rows if isinstance(row, dict)]


def evaluate_parameters(package: dict[str, Any], contract: dict[str, Any] | None, args: argparse.Namespace) -> dict[str, Any]:
    rows = parameter_rows(package, contract)
    if args.no_require_parameters:
        return make_check(
            "parameters",
            label="Parameter Table",
            passed=True,
            required=False,
            detail="Parameter-table requirement disabled by --no-require-parameters.",
            data={"parameter_count": len(rows)},
        )
    if args.parameter_table_waiver:
        return make_check(
            "parameters",
            label="Parameter Table",
            passed=True,
            waived=True,
            detail=f"Parameter-table requirement waived: {args.parameter_table_waiver}",
            data={"parameter_count": len(rows), "waiver": args.parameter_table_waiver},
        )
    if not rows:
        return make_check(
            "parameters",
            label="Parameter Table",
            passed=False,
            errors=1,
            detail="No parameter table entries found in package or contract.",
            action_needed="Add the material parameter table to the plan/contract/package, or pass an explicit waiver for parameterless materials.",
        )
    names = [_text(row.get("name") or row.get("parameter") or row.get("id")) for row in rows]
    missing_names = [index for index, name in enumerate(names) if not name]
    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    warnings = len(duplicates)
    errors = len(missing_names)
    return make_check(
        "parameters",
        label="Parameter Table",
        passed=errors == 0,
        errors=errors,
        warnings=warnings,
        detail=f"{len(rows)} parameter row(s), missing_names={len(missing_names)}, duplicates={len(duplicates)}.",
        action_needed="Fix unnamed or duplicate material parameter rows before approving reuse." if errors or warnings else "No action needed.",
        data={"parameter_count": len(rows), "missing_name_rows": missing_names, "duplicate_names": duplicates},
    )


def collect_all_evidence(args: argparse.Namespace, package: dict[str, Any], package_path: Path, contract_path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = package_report_paths(package, package_path=package_path)
    if contract_path:
        paths.append(contract_path)
    for values in (
        args.preview_report,
        args.audit_report,
        args.domain_audit_report,
        args.texture_set_report,
        args.regression_report,
    ):
        for value in values:
            paths.append(resolve_path(value, base=Path.cwd()))
    rows = evidence_rows(paths)
    evidence = {
        "package": str(package_path),
        "contract": str(contract_path or ""),
        "preview_reports": [row["path"] for row in rows_by_tool(rows, "material_preview")],
        "audit_reports": [row["path"] for row in rows_by_tool(rows, "material_audit")],
        "domain_audit_reports": [row["path"] for row in rows_by_tool(rows, "material_domain_audit")],
        "texture_set_reports": [row["path"] for row in rows_by_tool(rows, "texture_set_pipeline")],
        "regression_reports": [row["path"] for row in rows_by_tool(rows, "material_regression_compare")],
        "all_reports": [row["path"] for row in rows],
    }
    return rows, evidence


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package_path = resolve_path(args.package, base=Path.cwd())
    package = load_json(package_path)
    material_path = package_material_path(args, package)
    contract_path = contract_path_from_args(args, package, package_path)
    all_rows, evidence = collect_all_evidence(args, package, package_path, contract_path)
    contract_row = next((row for row in all_rows if contract_path and row["path"] == str(contract_path)), None)

    contract_check, contract = evaluate_contract(contract_row)
    route = material_route(package, contract)
    category, role = infer_category_role(package, args)
    checks = {
        "package": evaluate_package(package, package_path, material_path),
        "contract": contract_check,
        "preview": evaluate_preview(all_rows, material_path),
        "audit": evaluate_audit(all_rows, material_path, require_domain_audit=not args.no_require_domain_audit),
        "texture_set": evaluate_texture_set(package, all_rows, args),
        "regression": evaluate_regression(all_rows, args),
        "budget": evaluate_budget(package, all_rows, material_path),
        "usage_flags": evaluate_usage_flags(route, contract, all_rows),
        "parameters": evaluate_parameters(package, contract, args),
    }
    ordered_checks = [checks[name] for name in CHECK_ORDER]
    total_errors = sum(int(item.get("errors") or 0) for item in ordered_checks)
    total_warnings = sum(int(item.get("warnings") or 0) for item in ordered_checks)
    approved = total_errors == 0 and (args.allow_warnings or total_warnings == 0)
    failed_checks = [item["name"] for item in ordered_checks if item["errors"]]
    warning_checks = [item["name"] for item in ordered_checks if item["warnings"]]
    next_actions = [
        item["action_needed"]
        for item in ordered_checks
        if (item["errors"] or (item["warnings"] and not args.allow_warnings)) and item["action_needed"] != "No action needed."
    ]
    if total_warnings and not args.allow_warnings:
        next_actions.append("Either resolve all warnings or rerun material_acceptance_gate.py with --allow-warnings and a documented reason in the package notes.")
    if not next_actions and approved:
        next_actions.append("Material delivery is approved for reuse; pass this report to niagara-vfx-artist delivery_package.py.")

    report = {
        "tool": "material_acceptance_gate",
        "schema": "material_delivery_report",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": package.get("effect") or "",
        "layer": package.get("layer") or "",
        "asset": {
            "ue_asset_path": material_path,
            "category": category,
            "role": role,
            "material_domain": route.get("material_domain") or "",
            "blend_mode": route.get("blend_mode") or "",
            "shading_models": route.get("shading_models") or [],
            "carrier": route.get("carrier") or "",
            "two_sided": route.get("two_sided"),
        },
        "delivery_summary": {
            "approved_for_reuse": approved,
            "ready": approved,
            "report_gate_passed": total_errors == 0,
            "warnings_allowed": bool(args.allow_warnings),
            "warnings": total_warnings,
            "errors": total_errors,
            "report_count": len(evidence["all_reports"]),
        },
        "evidence": evidence,
        "checks": ordered_checks,
        "gate": {
            "approved_for_reuse": approved,
            "ready": approved,
            "require_ready": bool(args.require_ready),
            "allow_warnings": bool(args.allow_warnings),
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "required_checks": [item["name"] for item in ordered_checks if item.get("required")],
        },
        "route": route,
        "budget": checks["budget"].get("data") or {},
        "usage_flags": checks["usage_flags"].get("data") or {},
        "parameters": checks["parameters"].get("data") or {},
        "source_package": package_path.as_posix() if package_path.is_absolute() else str(package_path),
        "next_actions": next_actions,
        "boundary": {
            "material_side": "This report approves material-side evidence only.",
            "niagara_side": "Real Niagara System/Emitter/Renderer integration remains owned by niagara-vfx-artist and niagara_material_integration_probe.py.",
        },
    }
    stem = slugify(material_path or f"{report['effect']}-{report['layer']}" or "material")
    out = Path(args.out) if args.out else default_report_path(ctx, "deliveries", stem, "delivery", ".json")
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
        f"# Material Acceptance Gate: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Approved for reuse: `{delivery.get('approved_for_reuse')}`",
        f"- Ready: `{delivery.get('ready')}`",
        f"- Material: `{asset.get('ue_asset_path')}`",
        f"- Category/Role: `{asset.get('category')}` / `{asset.get('role')}`",
        f"- Domain: `{asset.get('material_domain')}`",
        f"- Carrier: `{asset.get('carrier')}`",
        f"- Errors: `{delivery.get('errors')}`",
        f"- Warnings: `{delivery.get('warnings')}`",
        "",
        "## Checks",
        "",
        "| Gate | Status | Errors | Warnings | Detail |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for check in report.get("checks") or []:
        detail = str(check.get("detail") or "").replace("|", "\\|")
        lines.append(
            f"| {check.get('label')} | `{health_badge(str(check.get('status') or ''))}` | "
            f"{check.get('errors', 0)} | {check.get('warnings', 0)} | {detail} |"
        )
    lines.extend(["", "## Evidence", ""])
    evidence = report.get("evidence") or {}
    for key in ("package", "contract"):
        lines.append(f"- `{key}`: `{evidence.get(key) or 'none'}`")
    for key in ("preview_reports", "audit_reports", "domain_audit_reports", "texture_set_reports", "regression_reports"):
        values = evidence.get(key) or []
        lines.append(f"- `{key}`: `{len(values)}`")
        for value in values[:8]:
            lines.append(f"- `{value}`")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Material acceptance is not real Niagara system integration proof.",
            "- Hand this report plus the material contract/package to `niagara-vfx-artist` for `niagara_material_integration_probe.py` and final VFX delivery gating.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.require_ready and not (report.get("delivery_summary") or {}).get("approved_for_reuse"):
        print(f"Material acceptance is not ready: {out}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Approve material-side delivery evidence and emit a Niagara-consumable material delivery report."
    )
    parser.add_argument("--root", default="auto")
    parser.add_argument("--package", required=True, help="delivery_packager.py JSON report.")
    parser.add_argument("--contract", help="Optional material_contract.py JSON override.")
    parser.add_argument("--material-path", default="", help="Override final UE material path.")
    parser.add_argument("--preview-report", action="append", default=[], help="Additional material_preview.py report.")
    parser.add_argument("--audit-report", action="append", default=[], help="Additional material_audit.py report.")
    parser.add_argument("--domain-audit-report", action="append", default=[], help="Additional material_domain_audit.py report.")
    parser.add_argument("--texture-set-report", action="append", default=[], help="Additional texture_set_pipeline.py report.")
    parser.add_argument("--regression-report", action="append", default=[], help="Additional material_regression.py compare report.")
    parser.add_argument("--category", default="", help="Delivery asset category override.")
    parser.add_argument("--role", default="", help="Delivery asset role override.")
    parser.add_argument("--allow-warnings", action="store_true", help="Allow warnings to still produce approved_for_reuse=true.")
    parser.add_argument("--no-require-domain-audit", action="store_true")
    parser.add_argument("--no-require-regression", action="store_true")
    parser.add_argument("--no-require-texture-set", action="store_true")
    parser.add_argument("--texture-set-waiver", default="", help="Documented waiver for textureless or nonstandard texture routes.")
    parser.add_argument("--no-require-parameters", action="store_true")
    parser.add_argument("--parameter-table-waiver", default="", help="Documented waiver for parameterless materials.")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--require-ready", action="store_true", help="Return non-zero unless approved_for_reuse=true.")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
