from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .core import ensure_dir, resolve_root_context, save_json, slugify, utc_now_iso, write_text


SKIP_TOOLS = {"project_material_health"}
MATERIAL_TOOLS = {"material_audit", "material_domain_audit", "material_preview"}
TEXTURE_TOOLS = {"texture_asset_report", "texture_import_audit", "texture_set_pipeline"}


def load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"invalid_json: {exc}"
    if not isinstance(payload, dict):
        return None, "json_root_not_object"
    return payload, ""


def norm_path(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("/Game") and "." in text:
        return text.split(".", 1)[0]
    return text


def material_key(value: Any) -> str:
    return norm_path(value) or "unknown-material"


def texture_key(value: Any) -> str:
    return str(value or "").strip() or "unknown-texture"


def severity_score(severity: str) -> int:
    lowered = str(severity or "").lower()
    if lowered == "error":
        return 50
    if lowered == "warning":
        return 12
    if lowered == "high":
        return 35
    if lowered == "medium":
        return 18
    if lowered == "low":
        return 6
    return 1


def add_risk(target: dict[str, Any], points: int, category: str, message: str, evidence: str = "") -> None:
    if points <= 0:
        return
    target["risk_score"] = int(target.get("risk_score") or 0) + int(points)
    target.setdefault("risk_reasons", []).append(
        {
            "points": int(points),
            "category": category,
            "message": message,
            "evidence": evidence,
        }
    )


def report_roots(ctx, roots: list[str]) -> list[Path]:
    if roots:
        return [Path(root).expanduser() for root in roots]
    return [ctx.material_root]


def collect_json_reports(roots: list[Path]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root.is_file() and root.suffix.lower() == ".json":
            candidates = [root]
        elif root.exists():
            candidates = list(root.rglob("*.json"))
        else:
            candidates = []
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(path)
    return sorted(paths)


def metric_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def metric_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def report_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            raw = value.get("findings")
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and item.get("severity"):
                        findings.append(item)
            for key, child in value.items():
                if key != "findings":
                    walk(child)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return findings


def finding_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity") or "info").lower()
        if severity == "error":
            counts["errors"] += 1
        elif severity == "warning":
            counts["warnings"] += 1
        else:
            counts["info"] += 1
    return counts


def material_entry(store: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    entry = store.setdefault(
        key,
        {
            "material_path": key,
            "risk_score": 0,
            "risk_reasons": [],
            "reports": [],
            "metrics": {},
            "route": {},
            "parameters": {},
            "node_evidence": {},
            "findings": {"errors": 0, "warnings": 0, "info": 0},
            "regressions": [],
            "graph_diffs": [],
            "graph_refactor_applies": [],
            "previews": [],
        },
    )
    return entry


def texture_entry(store: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return store.setdefault(
        key,
        {
            "texture": key,
            "risk_score": 0,
            "risk_reasons": [],
            "reports": [],
            "role": "",
            "asset_path": "",
            "file_path": "",
            "width": None,
            "height": None,
            "resource_size_bytes": 0,
            "findings": {"errors": 0, "warnings": 0, "info": 0},
        },
    )


def update_counts(target: dict[str, Any], counts: dict[str, int]) -> None:
    existing = target.setdefault("findings", {"errors": 0, "warnings": 0, "info": 0})
    for key in ("errors", "warnings", "info"):
        existing[key] = int(existing.get(key) or 0) + int(counts.get(key) or 0)


def process_material_audit(
    path: Path,
    payload: dict[str, Any],
    materials: dict[str, dict[str, Any]],
    parameter_index: dict[str, list[dict[str, Any]]],
    args: argparse.Namespace,
) -> None:
    info = payload.get("material_info") or {}
    analysis = payload.get("analysis") or {}
    graph = payload.get("graph_summary") or {}
    key = material_key(payload.get("material_path") or info.get("path"))
    entry = material_entry(materials, key)
    entry["reports"].append(str(path))
    entry["route"].update(
        {
            "domain": info.get("material_domain"),
            "blend_mode": info.get("blend_mode"),
            "shading_models": info.get("shading_models") or [],
            "two_sided": info.get("two_sided"),
            "use_material_attributes": info.get("use_material_attributes"),
            "usage_flags": info.get("usage_flags") or [],
        }
    )
    metrics = entry.setdefault("metrics", {})
    metrics.update(
        {
            "instructions": metric_int(analysis.get("max_instructions")),
            "samplers": metric_int(analysis.get("sampler_count")),
            "expression_count": metric_int(analysis.get("expression_count")),
            "num_expressions": metric_int(info.get("num_expressions")),
            "num_function_calls": metric_int(info.get("num_function_calls")),
            "dead_nodes": len(graph.get("dead_nodes") or []),
            "stale_overrides": len(payload.get("stale_overrides") or []),
            "compile_errors": len(analysis.get("compile_errors") or []),
            "shader_stats_ready": analysis.get("shader_stats_ready"),
        }
    )
    params = {}
    for key_name in ("scalar_parameters", "vector_parameters", "texture_parameters", "static_switch_parameters"):
        rows = [item for item in info.get(key_name) or [] if isinstance(item, dict)]
        params[key_name] = len(rows)
        for item in rows:
            name = str(item.get("name") or "").strip()
            if name:
                parameter_index[name.lower()].append(
                    {
                        "name": name,
                        "type": item.get("param_type") or key_name.replace("_parameters", ""),
                        "value": item.get("value"),
                        "material_path": entry["material_path"],
                        "report": str(path),
                    }
                )
    entry["parameters"].update(params)

    findings = report_findings(payload)
    counts = finding_counts(findings)
    counts["errors"] += len(analysis.get("compile_errors") or [])
    update_counts(entry, counts)

    instructions = metrics["instructions"]
    samplers = metrics["samplers"]
    if instructions > args.instruction_budget:
        add_risk(entry, 30 + int((instructions - args.instruction_budget) / 10), "instructions", "Instruction count exceeds budget.", f"{instructions}>{args.instruction_budget}")
    elif instructions:
        add_risk(entry, min(20, int(instructions / 30)), "instructions", "Instruction count contributes to project cost.", str(instructions))
    if samplers > args.sampler_budget:
        add_risk(entry, 30 + (samplers - args.sampler_budget) * 4, "samplers", "Sampler count exceeds budget.", f"{samplers}>{args.sampler_budget}")
    if metrics["compile_errors"]:
        add_risk(entry, metrics["compile_errors"] * 60, "compile_errors", "Material has compile errors.")
    if metrics["dead_nodes"]:
        add_risk(entry, metrics["dead_nodes"] * 5, "dead_nodes", "Dead graph nodes need cleanup.", str(metrics["dead_nodes"]))
    if metrics["stale_overrides"]:
        add_risk(entry, metrics["stale_overrides"] * 8, "stale_overrides", "Material instance has stale overrides.", str(metrics["stale_overrides"]))
    if params.get("static_switch_parameters", 0):
        add_risk(entry, params["static_switch_parameters"] * 4, "static_switches", "Static switch parameters can create permutation pressure.", str(params["static_switch_parameters"]))
    for finding in findings:
        add_risk(entry, severity_score(str(finding.get("severity"))), "audit_finding", str(finding.get("message") or ""), str(finding.get("rule") or finding.get("rule_id") or ""))


def process_domain_audit(path: Path, payload: dict[str, Any], materials: dict[str, dict[str, Any]]) -> None:
    contract = payload.get("domain_contract") or {}
    analysis = payload.get("analysis") or {}
    key = material_key(payload.get("material_path") or analysis.get("path"))
    entry = material_entry(materials, key)
    entry["reports"].append(str(path))
    entry["route"].update(
        {
            "domain": contract.get("domain") or entry["route"].get("domain"),
            "blend_mode": contract.get("blend_mode") or entry["route"].get("blend_mode"),
            "shading_models": contract.get("shading_models") or entry["route"].get("shading_models", []),
            "two_sided": contract.get("two_sided", entry["route"].get("two_sided")),
            "use_material_attributes": contract.get("use_material_attributes", entry["route"].get("use_material_attributes")),
            "wired_outputs": contract.get("wired_outputs") or [],
        }
    )
    evidence = payload.get("node_evidence") or {}
    entry["node_evidence"].update({key: value for key, value in evidence.items() if key != "class_counts"})
    findings = payload.get("findings") or []
    counts = finding_counts([item for item in findings if isinstance(item, dict)])
    update_counts(entry, counts)
    for finding in findings:
        if isinstance(finding, dict):
            add_risk(entry, severity_score(str(finding.get("severity"))), "domain_finding", str(finding.get("message") or ""), str(finding.get("rule_id") or finding.get("rule") or ""))
    if evidence.get("custom_nodes"):
        add_risk(entry, int(evidence["custom_nodes"]) * 4, "custom_nodes", "Custom nodes increase audit and platform risk.", str(evidence["custom_nodes"]))
    if evidence.get("texture_sample_nodes", 0) >= 6:
        add_risk(entry, int(evidence["texture_sample_nodes"]) * 2, "texture_samples", "Many texture sample nodes detected.", str(evidence["texture_sample_nodes"]))


def process_preview(path: Path, payload: dict[str, Any], materials: dict[str, dict[str, Any]]) -> None:
    key = material_key(payload.get("material_path") or payload.get("material_instance_path"))
    entry = material_entry(materials, key)
    outputs = payload.get("outputs") or {}
    options = payload.get("options") or {}
    row = {
        "path": str(path),
        "mode": payload.get("mode"),
        "carrier": options.get("carrier"),
        "preview_route": options.get("preview_route"),
        "shaded_ok": outputs.get("shaded_ok"),
        "complexity_ok": outputs.get("complexity_ok"),
    }
    entry["previews"].append(row)
    if outputs.get("shaded_ok") is False:
        add_risk(entry, 35, "preview", "Preview shaded capture failed.", str(path))
    if outputs.get("complexity_ok") is False:
        add_risk(entry, 12, "preview", "Preview complexity capture failed.", str(path))


def process_texture_asset_report(path: Path, payload: dict[str, Any], textures: dict[str, dict[str, Any]], args: argparse.Namespace) -> None:
    role = payload.get("role") or ""
    for item in payload.get("textures") or []:
        if not isinstance(item, dict):
            continue
        key = texture_key(item.get("path"))
        entry = texture_entry(textures, key)
        entry["reports"].append(str(path))
        entry["role"] = str(item.get("role") or role or entry.get("role") or "")
        entry["file_path"] = str(item.get("path") or "")
        entry["width"] = item.get("width")
        entry["height"] = item.get("height")
        warnings = item.get("warnings") or []
        update_counts(entry, {"errors": 0 if item.get("exists", True) else 1, "warnings": len(warnings), "info": 0})
        for warning in warnings:
            add_risk(entry, 8, "texture_file", str(warning), entry["role"])
        width = metric_int(item.get("width"))
        height = metric_int(item.get("height"))
        if width > args.texture_max_dimension or height > args.texture_max_dimension:
            add_risk(entry, 25, "texture_size", "Texture exceeds max dimension.", f"{width}x{height}")
        if item.get("power_of_two") is False:
            add_risk(entry, 8, "texture_size", "Texture is non-power-of-two.", f"{width}x{height}")


def process_texture_import_audit(path: Path, payload: dict[str, Any], textures: dict[str, dict[str, Any]], args: argparse.Namespace) -> None:
    role = payload.get("role") or ""
    for item in payload.get("textures") or []:
        if not isinstance(item, dict):
            continue
        key = texture_key(item.get("asset_path"))
        entry = texture_entry(textures, key)
        entry["reports"].append(str(path))
        entry["role"] = str(item.get("role") or role or entry.get("role") or "")
        entry["asset_path"] = str(item.get("asset_path") or "")
        entry["width"] = item.get("width")
        entry["height"] = item.get("height")
        entry["resource_size_bytes"] = metric_int(item.get("resource_size_bytes"))
        findings = item.get("findings") or []
        counts = finding_counts([finding for finding in findings if isinstance(finding, dict)])
        update_counts(entry, counts)
        for finding in findings:
            if isinstance(finding, dict):
                add_risk(entry, severity_score(str(finding.get("severity"))), "texture_import", str(finding.get("message") or ""), str(finding.get("rule") or ""))
        width = metric_int(item.get("width"))
        height = metric_int(item.get("height"))
        if width > args.texture_max_dimension or height > args.texture_max_dimension:
            add_risk(entry, 25, "texture_size", "Imported texture exceeds max dimension.", f"{width}x{height}")


def process_texture_set(path: Path, payload: dict[str, Any], texture_sets: list[dict[str, Any]], textures: dict[str, dict[str, Any]]) -> None:
    gate = payload.get("gate") or {}
    counts = gate.get("counts") or {}
    findings = payload.get("findings") or []
    score = counts.get("errors", 0) * 50 + counts.get("warnings", 0) * 12 + counts.get("info", 0)
    row = {
        "effect": payload.get("effect"),
        "layer": payload.get("layer"),
        "path": str(path),
        "profile": payload.get("profile"),
        "packed_convention": payload.get("packed_convention"),
        "passed": gate.get("passed"),
        "ready_for_import": gate.get("ready_for_import"),
        "risk_score": score,
        "counts": counts,
        "findings": [
            {
                "scope": item.get("scope"),
                "severity": item.get("severity"),
                "rule": item.get("rule"),
                "message": item.get("message"),
            }
            for item in findings[:12]
            if isinstance(item, dict)
        ],
    }
    texture_sets.append(row)
    for slot, item in (payload.get("slots") or {}).items():
        if not isinstance(item, dict):
            continue
        if not item.get("asset_path") and not item.get("file_path"):
            continue
        key = texture_key(item.get("asset_path") or item.get("file_path"))
        entry = texture_entry(textures, key)
        entry["reports"].append(str(path))
        entry["role"] = str(slot)
        entry["asset_path"] = str(item.get("asset_path") or entry.get("asset_path") or "")
        entry["file_path"] = str(item.get("file_path") or entry.get("file_path") or "")
        file_info = item.get("file") or {}
        entry["width"] = file_info.get("width", entry.get("width"))
        entry["height"] = file_info.get("height", entry.get("height"))
        slot_findings = item.get("findings") or []
        counts = finding_counts([finding for finding in slot_findings if isinstance(finding, dict)])
        update_counts(entry, counts)
        for finding in slot_findings:
            if isinstance(finding, dict):
                add_risk(entry, severity_score(str(finding.get("severity"))), "texture_set", str(finding.get("message") or ""), f"{payload.get('effect')}/{payload.get('layer')}:{slot}")


def process_regression(path: Path, payload: dict[str, Any], regressions: list[dict[str, Any]], materials: dict[str, dict[str, Any]]) -> None:
    gate = payload.get("gate") or {}
    current = payload.get("current") or {}
    material_path = material_key(current.get("material_path"))
    score = int(gate.get("errors") or 0) * 55 + int(gate.get("warnings") or 0) * 12
    for comparison in payload.get("comparisons") or []:
        if isinstance(comparison, dict):
            metrics = comparison.get("metrics") or {}
            score += int(metric_float(metrics.get("mean_abs_rgb")) / 2)
            score += int(metric_float(metrics.get("changed_pixel_ratio")) * 20)
    row = {
        "path": str(path),
        "effect": payload.get("effect"),
        "layer": payload.get("layer"),
        "label": payload.get("label"),
        "material_path": material_path,
        "passed": gate.get("passed"),
        "errors": gate.get("errors", 0),
        "warnings": gate.get("warnings", 0),
        "risk_score": score,
        "findings": gate.get("findings") or [],
    }
    regressions.append(row)
    if material_path and gate.get("passed") is False:
        entry = material_entry(materials, material_path)
        entry["regressions"].append(row)
        add_risk(entry, score or 40, "regression", "Material preview regression failed.", str(path))


def process_graph_diff(path: Path, payload: dict[str, Any], graph_diffs: list[dict[str, Any]], materials: dict[str, dict[str, Any]]) -> None:
    gate = payload.get("gate") or {}
    identity = payload.get("identity") or {}
    after = identity.get("after") or {}
    material_path = material_key(after.get("material_path"))
    high = int(gate.get("high_causes") or 0)
    medium = int(gate.get("medium_causes") or 0)
    score = high * 35 + medium * 18 + (25 if gate.get("requires_review") else 0)
    row = {
        "path": str(path),
        "effect": payload.get("effect"),
        "layer": payload.get("layer"),
        "label": payload.get("label"),
        "material_path": material_path,
        "requires_review": gate.get("requires_review"),
        "explains_regression": gate.get("explains_regression"),
        "high_causes": high,
        "medium_causes": medium,
        "risk_score": score,
        "likely_causes": payload.get("likely_causes") or [],
    }
    graph_diffs.append(row)
    if material_path and gate.get("requires_review"):
        entry = material_entry(materials, material_path)
        entry["graph_diffs"].append(row)
        add_risk(entry, score or 25, "graph_diff", "Graph diff requires review.", str(path))


def process_graph_refactor_apply(
    path: Path,
    payload: dict[str, Any],
    graph_refactor_applies: list[dict[str, Any]],
    materials: dict[str, dict[str, Any]],
) -> None:
    gate = payload.get("gate") or {}
    validation = payload.get("validation") or {}
    ue_apply = payload.get("ue_apply") or {}
    apply_payload = payload.get("apply_payload") or {}
    operations = apply_payload.get("operations") or []
    ue_operations = ue_apply.get("operations") or []
    blocked_ops = len([item for item in operations if isinstance(item, dict) and item.get("executable") is False])
    skipped_ops = int(gate.get("operation_skipped") or len([item for item in ue_operations if isinstance(item, dict) and item.get("skipped")]))
    if not skipped_ops and not payload.get("execute"):
        skipped_ops = blocked_ops
    failed_ops = int(
        gate.get("operation_failures")
        or len([item for item in ue_operations if isinstance(item, dict) and not item.get("success") and not item.get("skipped")])
    )
    regression_status = str(gate.get("regression_status") or "")
    if not regression_status:
        regression = validation.get("regression") or {}
        if regression.get("skipped"):
            regression_status = "skipped"
        elif regression:
            summary = regression.get("summary") or {}
            regression_status = "passed" if summary.get("passed") is True else "failed"
        else:
            regression_status = "not_run"

    execute = bool(payload.get("execute"))
    ready = bool(gate.get("ready_for_acceptance"))
    structurally_valid = bool(gate.get("candidate_validated_without_regression"))
    score = 0
    if not ready:
        score += 25 if execute else 12
    if structurally_valid and regression_status in {"skipped", "not_run"}:
        score += 20
    if regression_status == "failed":
        score += 55
    elif regression_status == "skipped":
        score += 20
    elif regression_status == "not_run":
        score += 12
    score += failed_ops * 45
    score += skipped_ops * 18
    score += int(gate.get("after_domain_errors") or 0) * 50
    score += int(gate.get("after_domain_warnings") or 0) * 12
    score += int(gate.get("preview_contract_findings") or 0) * 12
    if gate.get("preview_shaded_ok") is False:
        score += 35

    row = {
        "path": str(path),
        "effect": payload.get("effect"),
        "layer": payload.get("layer"),
        "label": payload.get("label"),
        "execute": execute,
        "target_material": material_key(payload.get("target_material")),
        "candidate_path": material_key(payload.get("candidate_path") or ue_apply.get("candidate_path")),
        "backup_path": material_key(payload.get("backup_path") or ue_apply.get("backup_path")),
        "ready_for_acceptance": ready,
        "candidate_validated_without_regression": structurally_valid,
        "regression_status": regression_status,
        "operation_failures": failed_ops,
        "operation_skipped": skipped_ops,
        "blocked_operations": blocked_ops,
        "after_domain_errors": gate.get("after_domain_errors"),
        "after_domain_warnings": gate.get("after_domain_warnings"),
        "preview_shaded_ok": gate.get("preview_shaded_ok"),
        "preview_contract_findings": gate.get("preview_contract_findings"),
        "risk_score": score,
        "operations": [
            {
                "operation": item.get("operation"),
                "executable": item.get("executable"),
                "blocked_reason": item.get("blocked_reason") or "",
            }
            for item in operations
            if isinstance(item, dict)
        ],
    }
    graph_refactor_applies.append(row)

    material_path = row["target_material"]
    material_needs_risk = bool(
        execute
        and (
            not ready
            or failed_ops
            or skipped_ops
            or regression_status == "failed"
            or row.get("preview_shaded_ok") is False
            or metric_int(row.get("after_domain_errors")) > 0
        )
    )
    if material_path and material_needs_risk:
        entry = material_entry(materials, material_path)
        entry["graph_refactor_applies"].append(row)
        if failed_ops:
            add_risk(entry, failed_ops * 45, "graph_refactor_apply", "Graph refactor apply has failed operations.", str(path))
        if skipped_ops:
            add_risk(entry, skipped_ops * 18, "graph_refactor_apply", "Graph refactor apply skipped review-only operations.", str(path))
        if regression_status in {"skipped", "not_run"}:
            add_risk(entry, 20, "graph_refactor_apply", "Graph refactor apply lacks passing regression evidence.", str(path))
        elif regression_status == "failed":
            add_risk(entry, 55, "graph_refactor_apply", "Graph refactor apply regression failed.", str(path))


def process_permutation_report(path: Path, payload: dict[str, Any], permutations: list[dict[str, Any]]) -> None:
    for group in payload.get("groups") or []:
        if not isinstance(group, dict):
            continue
        instances = group.get("instances") or []
        switch_signature = group.get("switch_signature") or []
        score = len(instances) * max(1, len(switch_signature)) + int(group.get("max_chain_depth") or 0) * 2
        if len(instances) >= 10:
            score += 25
        if len(switch_signature) >= 4:
            score += 30
        permutations.append(
            {
                "path": str(path),
                "base_path": group.get("base_path"),
                "instances": instances,
                "instance_count": len(instances),
                "switch_signature": switch_signature,
                "switch_count": len(switch_signature),
                "max_chain_depth": group.get("max_chain_depth"),
                "risk_score": score,
            }
        )


def process_function_linter(path: Path, payload: dict[str, Any], functions: list[dict[str, Any]]) -> None:
    for item in payload.get("functions") or []:
        if not isinstance(item, dict):
            continue
        findings = item.get("findings") or []
        counts = finding_counts([finding for finding in findings if isinstance(finding, dict)])
        score = counts["errors"] * 50 + counts["warnings"] * 12 + counts["info"] + int(metric_int(item.get("num_expressions")) / 20)
        functions.append(
            {
                "path": item.get("path"),
                "report": str(path),
                "inputs": len(item.get("inputs") or []),
                "outputs": len(item.get("outputs") or []),
                "num_expressions": item.get("num_expressions"),
                "counts": counts,
                "risk_score": score,
                "findings": findings,
            }
        )


def parameter_collisions(parameter_index: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for normalized, items in parameter_index.items():
        materials = sorted({item["material_path"] for item in items})
        types = sorted({str(item.get("type") or "") for item in items})
        values = sorted({str(item.get("value") or "") for item in items if item.get("value") is not None})
        if len(items) <= 1:
            continue
        score = len(materials)
        if len(types) > 1:
            score += 40
        if len(values) > 4:
            score += 8
        rows.append(
            {
                "name": items[0].get("name") or normalized,
                "normalized": normalized,
                "occurrences": len(items),
                "material_count": len(materials),
                "types": types,
                "value_variants": len(values),
                "risk_score": score,
                "examples": items[:8],
            }
        )
    return sorted(rows, key=lambda item: (-item["risk_score"], item["normalized"]))


def sorted_top(rows: list[dict[str, Any]], key: str = "risk_score", limit: int = 20) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda item: (-metric_float(item.get(key)), str(item.get("material_path") or item.get("texture") or item.get("path") or "")))[:limit]


def material_metric_hotlist(rows: list[dict[str, Any]], group: str, metric: str, limit: int) -> list[dict[str, Any]]:
    return sorted(
        [row for row in rows if metric_float((row.get(group) or {}).get(metric)) > 0],
        key=lambda row: (-metric_float((row.get(group) or {}).get(metric)), str(row.get("material_path") or "")),
    )[:limit]


def suspicious_master_candidates(material_list: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in material_list:
        metrics = row.get("metrics") or {}
        params = row.get("parameters") or {}
        expressions = max(metric_int(metrics.get("num_expressions")), metric_int(metrics.get("expression_count")))
        function_calls = metric_int(metrics.get("num_function_calls"))
        static_switches = metric_int(params.get("static_switch_parameters"))
        texture_params = metric_int(params.get("texture_parameters"))
        reasons: list[str] = []
        score = 0
        if expressions >= args.master_expression_threshold:
            reasons.append(f"expressions={expressions}")
            score += expressions
        if static_switches >= args.master_switch_threshold:
            reasons.append(f"static_switches={static_switches}")
            score += static_switches * 20
        if texture_params >= args.master_texture_param_threshold:
            reasons.append(f"texture_parameters={texture_params}")
            score += texture_params * 10
        if function_calls:
            score += function_calls * 6
        if not reasons:
            continue
        candidate = dict(row)
        candidate["master_candidate_score"] = score
        candidate["master_candidate_reasons"] = reasons
        rows.append(candidate)
    return sorted(
        rows,
        key=lambda row: (
            -metric_float(row.get("master_candidate_score")),
            -metric_float(row.get("risk_score")),
            str(row.get("material_path") or ""),
        ),
    )[: args.max_items]


def material_rows(materials: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in materials.values():
        reasons = sorted(entry.get("risk_reasons") or [], key=lambda item: -int(item.get("points") or 0))
        row = {
            "material_path": entry.get("material_path"),
            "risk_score": entry.get("risk_score", 0),
            "route": entry.get("route") or {},
            "metrics": entry.get("metrics") or {},
            "parameters": entry.get("parameters") or {},
            "node_evidence": entry.get("node_evidence") or {},
            "findings": entry.get("findings") or {},
            "report_count": len(set(entry.get("reports") or [])),
            "top_reasons": reasons[:8],
            "regression_count": len(entry.get("regressions") or []),
            "graph_diff_count": len(entry.get("graph_diffs") or []),
            "graph_refactor_apply_count": len(entry.get("graph_refactor_applies") or []),
        }
        rows.append(row)
    return rows


def texture_rows(textures: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in textures.values():
        reasons = sorted(entry.get("risk_reasons") or [], key=lambda item: -int(item.get("points") or 0))
        rows.append(
            {
                "texture": entry.get("texture"),
                "risk_score": entry.get("risk_score", 0),
                "role": entry.get("role"),
                "asset_path": entry.get("asset_path"),
                "file_path": entry.get("file_path"),
                "width": entry.get("width"),
                "height": entry.get("height"),
                "resource_size_bytes": entry.get("resource_size_bytes"),
                "findings": entry.get("findings") or {},
                "report_count": len(set(entry.get("reports") or [])),
                "top_reasons": reasons[:8],
            }
        )
    return rows


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    roots = report_roots(ctx, args.report_root)
    report_paths = collect_json_reports(roots)
    materials: dict[str, dict[str, Any]] = {}
    textures: dict[str, dict[str, Any]] = {}
    parameter_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    texture_sets: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    graph_diffs: list[dict[str, Any]] = []
    graph_refactor_applies: list[dict[str, Any]] = []
    permutations: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    invalid_reports: list[dict[str, str]] = []
    tool_counts: Counter[str] = Counter()

    for path in report_paths:
        payload, error = load_json(path)
        if payload is None:
            invalid_reports.append({"path": str(path), "error": error})
            continue
        tool = str(payload.get("tool") or "")
        if tool in SKIP_TOOLS:
            continue
        tool_counts[tool or "unknown"] += 1
        if tool == "material_audit":
            process_material_audit(path, payload, materials, parameter_index, args)
        elif tool == "material_domain_audit":
            process_domain_audit(path, payload, materials)
        elif tool == "material_preview":
            process_preview(path, payload, materials)
        elif tool == "texture_asset_report":
            process_texture_asset_report(path, payload, textures, args)
        elif tool == "texture_import_audit":
            process_texture_import_audit(path, payload, textures, args)
        elif tool == "texture_set_pipeline":
            process_texture_set(path, payload, texture_sets, textures)
        elif tool == "material_regression_compare":
            process_regression(path, payload, regressions, materials)
        elif tool == "graph_diff_refactor":
            process_graph_diff(path, payload, graph_diffs, materials)
        elif tool == "graph_refactor_apply":
            process_graph_refactor_apply(path, payload, graph_refactor_applies, materials)
        elif tool == "shader_permutation_report":
            process_permutation_report(path, payload, permutations)
        elif tool == "material_function_linter":
            process_function_linter(path, payload, functions)

    material_list = material_rows(materials)
    texture_list = texture_rows(textures)
    collisions = parameter_collisions(parameter_index)
    max_items = args.max_items
    hotlists = {
        "materials_by_score": sorted_top(material_list, limit=max_items),
    }
    hotlists["materials_by_instructions"] = material_metric_hotlist(material_list, "metrics", "instructions", max_items)
    hotlists["materials_by_samplers"] = material_metric_hotlist(material_list, "metrics", "samplers", max_items)
    hotlists["materials_by_static_switches"] = material_metric_hotlist(material_list, "parameters", "static_switch_parameters", max_items)
    hotlists["materials_by_dead_nodes"] = material_metric_hotlist(material_list, "metrics", "dead_nodes", max_items)
    hotlists["textures_by_score"] = sorted_top(texture_list, limit=max_items)
    hotlists["textures_by_size"] = sorted(
        texture_list,
        key=lambda row: (-(metric_float(row.get("width")) * metric_float(row.get("height"))), str(row.get("texture") or "")),
    )[:max_items]
    hotlists["texture_sets_by_score"] = sorted_top(texture_sets, limit=max_items)
    hotlists["permutation_groups"] = sorted_top(permutations, limit=max_items)
    hotlists["parameter_name_collisions"] = collisions[:max_items]
    hotlists["failed_regressions"] = sorted_top([row for row in regressions if row.get("passed") is False], limit=max_items)
    hotlists["graph_diffs_requiring_review"] = sorted_top([row for row in graph_diffs if row.get("requires_review")], limit=max_items)
    hotlists["graph_refactor_applies_needing_review"] = sorted_top(
        [row for row in graph_refactor_applies if not row.get("ready_for_acceptance")],
        limit=max_items,
    )
    hotlists["material_functions_by_score"] = sorted_top(functions, limit=max_items)
    hotlists["suspicious_master_candidates"] = suspicious_master_candidates(material_list, args)

    graph_apply_failures = [
        row
        for row in graph_refactor_applies
        if row.get("regression_status") == "failed"
        or metric_int(row.get("operation_failures")) > 0
        or row.get("preview_shaded_ok") is False
        or metric_int(row.get("after_domain_errors")) > 0
    ]
    summary = {
        "report_count": sum(tool_counts.values()),
        "invalid_report_count": len(invalid_reports),
        "tool_counts": dict(sorted(tool_counts.items())),
        "material_count": len(material_list),
        "texture_count": len(texture_list),
        "texture_set_count": len(texture_sets),
        "failed_regression_count": len([row for row in regressions if row.get("passed") is False]),
        "graph_diff_review_count": len([row for row in graph_diffs if row.get("requires_review")]),
        "graph_refactor_apply_count": len(graph_refactor_applies),
        "graph_refactor_apply_review_count": len([row for row in graph_refactor_applies if not row.get("ready_for_acceptance")]),
        "graph_refactor_apply_failed_count": len(graph_apply_failures),
        "permutation_group_count": len(permutations),
        "parameter_collision_count": len(collisions),
        "high_risk_material_count": len([row for row in material_list if metric_int(row.get("risk_score")) >= args.high_risk_score]),
        "high_risk_texture_count": len([row for row in texture_list if metric_int(row.get("risk_score")) >= args.high_risk_score]),
        "high_risk_texture_set_count": len(
            [
                row
                for row in texture_sets
                if row.get("passed") is False or metric_int(row.get("risk_score")) >= args.high_risk_score
            ]
        ),
    }

    recommendations = build_recommendations(summary, hotlists)
    report = {
        "tool": "project_material_health",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "project_root": str(ctx.project_root),
        "report_roots": [str(root) for root in roots],
        "options": {
            "instruction_budget": args.instruction_budget,
            "sampler_budget": args.sampler_budget,
            "texture_max_dimension": args.texture_max_dimension,
            "max_items": args.max_items,
        },
        "summary": summary,
        "hotlists": hotlists,
        "recommendations": recommendations,
        "invalid_reports": invalid_reports[:max_items],
        "gate": {
            "passed": summary["high_risk_material_count"] == 0
            and summary["high_risk_texture_count"] == 0
            and summary["high_risk_texture_set_count"] == 0
            and summary["failed_regression_count"] == 0
            and summary["graph_refactor_apply_failed_count"] == 0
            and summary["invalid_report_count"] == 0,
            "requires_triage": bool(
                summary["high_risk_material_count"]
                or summary["high_risk_texture_count"]
                or summary["high_risk_texture_set_count"]
                or summary["failed_regression_count"]
                or summary["graph_diff_review_count"]
                or summary["graph_refactor_apply_review_count"]
                or summary["invalid_report_count"]
            ),
        },
    }
    out = Path(args.out) if args.out else ctx.material_root / "project-health" / "project-material-health.json"
    return report, out


def build_recommendations(summary: dict[str, Any], hotlists: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    if summary.get("failed_regression_count"):
        recommendations.append("Triage failed material regressions first; run graph_diff_refactor for failures that do not already have an explanation.")
    if summary.get("graph_diff_review_count"):
        recommendations.append("Review graph diffs requiring attention before accepting any new visual baselines.")
    if summary.get("graph_refactor_apply_failed_count"):
        recommendations.append("Reject or repair failed graph-refactor candidates; keep the original material untouched and use the recorded backup/candidate paths.")
    elif summary.get("graph_refactor_apply_review_count"):
        recommendations.append("Review graph-refactor apply candidates and add regression baselines before promoting any candidate material.")
    if hotlists.get("materials_by_instructions"):
        top = hotlists["materials_by_instructions"][0]
        if metric_int((top.get("metrics") or {}).get("instructions")):
            recommendations.append(f"Start shader-cost review with `{top.get('material_path')}`; it has the highest observed instruction count.")
    if hotlists.get("materials_by_static_switches") and metric_int((hotlists["materials_by_static_switches"][0].get("parameters") or {}).get("static_switch_parameters")):
        recommendations.append("Review static switch usage and permutation groups before adding more material instances.")
    if summary.get("high_risk_texture_count") or summary.get("high_risk_texture_set_count") or hotlists.get("texture_sets_by_score"):
        recommendations.append("Use texture_set_pipeline and texture_import_fix batch specs to reduce texture-set and import-setting risks.")
    if summary.get("parameter_collision_count"):
        recommendations.append("Inspect parameter name collisions, especially mixed-type names, before standardizing master material controls.")
    if not recommendations:
        recommendations.append("No major project-level material health blockers were found in the supplied evidence.")
    return recommendations


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    gate = report.get("gate") or {}
    hotlists = report.get("hotlists") or {}
    lines = [
        "# Project Material Health",
        "",
        f"- Passed: `{gate.get('passed')}`",
        f"- Requires triage: `{gate.get('requires_triage')}`",
        f"- Reports scanned: `{summary.get('report_count')}`",
        f"- Materials: `{summary.get('material_count')}`",
        f"- Textures: `{summary.get('texture_count')}`",
        f"- Texture sets: `{summary.get('texture_set_count')}`",
        f"- High-risk texture sets: `{summary.get('high_risk_texture_set_count')}`",
        f"- Failed regressions: `{summary.get('failed_regression_count')}`",
        f"- Graph diffs requiring review: `{summary.get('graph_diff_review_count')}`",
        f"- Graph refactor applies needing review: `{summary.get('graph_refactor_apply_review_count')}`",
        f"- Parameter collisions: `{summary.get('parameter_collision_count')}`",
        "",
        "## Material Hotlist",
        "",
    ]
    materials = hotlists.get("materials_by_score") or []
    if materials:
        for item in materials[:10]:
            metrics = item.get("metrics") or {}
            lines.append(
                f"- score=`{item.get('risk_score')}` `{item.get('material_path')}` "
                f"instr=`{metrics.get('instructions')}` samplers=`{metrics.get('samplers')}` "
                f"dead=`{metrics.get('dead_nodes')}` stale=`{metrics.get('stale_overrides')}`"
            )
            reasons = item.get("top_reasons") or []
            if reasons:
                lines.append(f"  Top reason: {reasons[0].get('category')} - {reasons[0].get('message')}")
    else:
        lines.append("- No material audit evidence found.")

    lines.extend(["", "## Texture Hotlist", ""])
    textures = hotlists.get("textures_by_score") or []
    if textures:
        for item in textures[:10]:
            lines.append(
                f"- score=`{item.get('risk_score')}` `{item.get('texture')}` role=`{item.get('role')}` "
                f"size=`{item.get('width')}x{item.get('height')}`"
            )
    else:
        lines.append("- No texture health evidence found.")

    lines.extend(["", "## Texture Set Hotlist", ""])
    texture_sets = hotlists.get("texture_sets_by_score") or []
    if texture_sets:
        for item in texture_sets[:10]:
            counts = item.get("counts") or {}
            lines.append(
                f"- score=`{item.get('risk_score')}` `{item.get('effect')}/{item.get('layer')}` "
                f"passed=`{item.get('passed')}` ready=`{item.get('ready_for_import')}` "
                f"errors=`{counts.get('errors', 0)}` warnings=`{counts.get('warnings', 0)}`"
            )
    else:
        lines.append("- No texture-set evidence found.")

    lines.extend(["", "## Regressions, Diffs, And Refactor Applies", ""])
    regressions = hotlists.get("failed_regressions") or []
    if regressions:
        for item in regressions[:8]:
            lines.append(f"- failed regression score=`{item.get('risk_score')}` `{item.get('effect')}/{item.get('layer')}` label=`{item.get('label')}`")
    else:
        lines.append("- No failed regression evidence.")
    graph_diffs = hotlists.get("graph_diffs_requiring_review") or []
    for item in graph_diffs[:8]:
        lines.append(f"- graph diff review score=`{item.get('risk_score')}` `{item.get('effect')}/{item.get('layer')}` label=`{item.get('label')}`")
    applies = hotlists.get("graph_refactor_applies_needing_review") or []
    for item in applies[:8]:
        lines.append(
            f"- graph apply review score=`{item.get('risk_score')}` `{item.get('effect')}/{item.get('layer')}` "
            f"label=`{item.get('label')}` ready=`{item.get('ready_for_acceptance')}` "
            f"regression=`{item.get('regression_status')}` skipped=`{item.get('operation_skipped')}` "
            f"blocked=`{item.get('blocked_operations')}` failed=`{item.get('operation_failures')}` "
            f"candidate=`{item.get('candidate_path')}`"
        )

    lines.extend(["", "## Permutations And Parameters", ""])
    permutations = hotlists.get("permutation_groups") or []
    if permutations:
        for item in permutations[:8]:
            lines.append(f"- permutation score=`{item.get('risk_score')}` base=`{item.get('base_path')}` instances=`{item.get('instance_count')}` switches=`{item.get('switch_count')}`")
    else:
        lines.append("- No permutation groups with evidence.")
    collisions = hotlists.get("parameter_name_collisions") or []
    for item in collisions[:8]:
        lines.append(f"- parameter `{item.get('name')}` occurrences=`{item.get('occurrences')}` materials=`{item.get('material_count')}` types=`{', '.join(item.get('types') or [])}`")
    masters = hotlists.get("suspicious_master_candidates") or []
    for item in masters[:8]:
        lines.append(
            f"- suspicious master score=`{item.get('master_candidate_score')}` `{item.get('material_path')}` "
            f"reasons=`{', '.join(item.get('master_candidate_reasons') or [])}`"
        )

    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command_scan(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 1 if args.strict and not report["gate"]["passed"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build project-level material health hotlists from existing material delivery evidence.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan report roots and build project-level material health heatmaps.")
    scan.add_argument("--root", default="auto")
    scan.add_argument("--report-root", action="append", default=[], help="JSON report root or file. Defaults to .codex/session/material-delivery.")
    scan.add_argument("--instruction-budget", type=int, default=220)
    scan.add_argument("--sampler-budget", type=int, default=12)
    scan.add_argument("--texture-max-dimension", type=int, default=2048)
    scan.add_argument("--master-expression-threshold", type=int, default=120)
    scan.add_argument("--master-switch-threshold", type=int, default=6)
    scan.add_argument("--master-texture-param-threshold", type=int, default=8)
    scan.add_argument("--high-risk-score", type=int, default=80)
    scan.add_argument("--max-items", type=int, default=20)
    scan.add_argument("--out")
    scan.add_argument("--markdown", action="store_true")
    scan.add_argument("--strict", action="store_true")
    scan.set_defaults(func=command_scan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
