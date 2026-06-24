from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .core import normalize_cli_global_args, read_jsonl, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .effect_state import (
    acceptance_default,
    approvals_default,
    asset_plan_default,
    effect_preview_approvals_default,
    effect_folder,
    integration_default,
    load_effect_record,
)
from .effect_contracts import effect_type_contract, effect_type_names
from .tuning_log import log_path
from .visual_layer_map import load_map


def asset_reference_variants(path: str) -> set[str]:
    clean = str(path or "").strip().strip("'\"")
    if not clean:
        return set()
    match = re.search(r"'([^']+)'", clean)
    if match:
        clean = match.group(1)
    variants = {clean}
    leaf = clean.rsplit("/", 1)[-1]
    if "." in leaf:
        variants.add(clean.rsplit(".", 1)[0])
    else:
        variants.add(f"{clean}.{leaf}")
    return {item for item in variants if item}


def asset_reference_matches(candidate: str, required: str) -> bool:
    return bool(asset_reference_variants(candidate) & asset_reference_variants(required))


def load_live_asset_reports(ctx, effect: str) -> list[dict[str, Any]]:
    folder = ctx.vfx_root / "live-asset-verify"
    if not folder.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in folder.rglob("*.json"):
        try:
            payload = __import__("json").loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        report_effect = str(payload.get("effect", "") or "")
        if effect and report_effect != effect:
            continue
        payload["_source_path"] = str(path)
        reports.append(payload)
    return reports


def load_niagara_audit_reports(ctx, final_systems: list[str]) -> list[dict[str, Any]]:
    if not final_systems:
        return []
    folder = ctx.vfx_root / "audits" / "niagara"
    if not folder.exists():
        return []
    wanted = set(final_systems)
    latest_by_system: dict[str, tuple[float, dict[str, Any]]] = {}
    for path in folder.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        system_path = str(payload.get("system_path", "") or "")
        if wanted and system_path not in wanted:
            continue
        payload["_source_path"] = str(path)
        mtime = path.stat().st_mtime
        existing = latest_by_system.get(system_path)
        if existing is None or mtime > existing[0]:
            latest_by_system[system_path] = (mtime, payload)
    return [item[1] for item in latest_by_system.values()]


def find_latest_delivery_index(ctx, effect: str) -> Path | None:
    folder = ctx.vfx_root / "delivery"
    if not folder.exists():
        return None
    exact = folder / slugify(effect) / "delivery-index.json"
    candidates: list[Path] = []
    if exact.exists():
        candidates.append(exact)
    for path in folder.rglob("delivery-index.json"):
        if path not in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if str(payload.get("effect_name", "") or "") == effect:
                candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]


def load_delivery_payload(path: str | Path) -> dict[str, Any]:
    payload_path = Path(path)
    if not payload_path.exists():
        raise FileNotFoundError(f"Delivery payload not found: {payload_path}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Delivery payload is not an object: {payload_path}")
    return payload


def load_material_delivery_reports(ctx) -> list[dict[str, Any]]:
    folder = ctx.session_root / "material-delivery" / "deliveries"
    if not folder.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in folder.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_source_path"] = str(path)
        reports.append(payload)
    return reports


def match_material_delivery_reports(final_materials: list[str], reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for material_path in final_materials:
        candidates = [
            report for report in reports
            if (((report.get("asset") or {}).get("ue_asset_path") or "") == material_path)
        ]
        candidates.sort(key=lambda item: str(item.get("generated_utc") or ""), reverse=True)
        chosen = candidates[0] if candidates else None
        asset = (chosen or {}).get("asset") or {}
        delivery = (chosen or {}).get("delivery_summary") or {}
        matched.append(
            {
                "requested_material_path": material_path,
                "has_delivery_report": bool(chosen),
                "delivery_report_path": (chosen or {}).get("_source_path", ""),
                "approved_for_reuse": bool(delivery.get("approved_for_reuse")) if chosen else False,
                "category": asset.get("category", ""),
                "role": asset.get("role", ""),
                "material_domain": asset.get("material_domain", ""),
                "warnings": int(delivery.get("warnings") or 0) if chosen else 0,
                "errors": int(delivery.get("errors") or 0) if chosen else 0,
                "generated_utc": (chosen or {}).get("generated_utc", ""),
            }
        )
    return matched


def load_material_integration_probe_reports(ctx, effect: str, explicit_paths: list[str] | None = None) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    seen: set[str] = set()
    candidates: list[Path] = []
    for raw_path in explicit_paths or []:
        path = Path(raw_path)
        if path.exists():
            candidates.append(path)
    if not explicit_paths:
        folder = ctx.vfx_root / "material-integration-probe"
        exact = folder / slugify(effect)
        if exact.exists():
            candidates.extend(exact.rglob("*.json"))
        if folder.exists():
            candidates.extend(path for path in folder.rglob("*.json") if path not in candidates)
    for path in candidates:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("tool", "") or "") != "niagara_material_integration_probe":
            continue
        report_effect = str(payload.get("effect", "") or "")
        if effect and report_effect and report_effect != effect and path.parent.name != slugify(effect):
            continue
        payload["_source_path"] = str(path)
        reports.append(payload)
    return sorted(reports, key=lambda item: str(item.get("generated_utc") or ""), reverse=True)


def material_integration_report_system_path(report: dict[str, Any]) -> str:
    return str(report.get("system_path", "") or "")


def material_integration_report_material_path(report: dict[str, Any]) -> str:
    expectations = report.get("expectations") if isinstance(report.get("expectations"), dict) else {}
    return str(expectations.get("material_path") or report.get("material_path") or "")


def material_integration_report_summary(report: dict[str, Any]) -> dict[str, int]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "errors": int(summary.get("errors") or 0),
        "warnings": int(summary.get("warnings") or 0),
        "info": int(summary.get("info") or 0),
        "ok": int(summary.get("ok") or 0),
    }


def material_integration_report_matches(report: dict[str, Any], *, system_path: str, material_path: str) -> bool:
    report_system = material_integration_report_system_path(report)
    report_material = material_integration_report_material_path(report)
    return asset_reference_matches(report_system, system_path) and asset_reference_matches(report_material, material_path)


def material_integration_report_passed(report: dict[str, Any], *, allow_warnings: bool = False) -> bool:
    gate = report.get("gate") if isinstance(report.get("gate"), dict) else {}
    summary = material_integration_report_summary(report)
    if not gate.get("real_system_checked"):
        return False
    if bool(gate.get("material_preview_is_system_proof")):
        return False
    if not gate.get("integration_ready"):
        return False
    if summary["errors"] > 0:
        return False
    if not allow_warnings and (summary["warnings"] > 0 or gate.get("requires_triage")):
        return False
    return True


def material_integration_probe_index_entry(report: dict[str, Any], *, allow_warnings: bool = False) -> dict[str, Any]:
    summary = material_integration_report_summary(report)
    gate = report.get("gate") if isinstance(report.get("gate"), dict) else {}
    return {
        "source_path": report.get("_source_path", ""),
        "effect": report.get("effect", ""),
        "system_path": material_integration_report_system_path(report),
        "material_path": material_integration_report_material_path(report),
        "integration_ready": bool(gate.get("integration_ready")),
        "real_system_checked": bool(gate.get("real_system_checked")),
        "material_preview_is_system_proof": bool(gate.get("material_preview_is_system_proof")),
        "requires_triage": bool(gate.get("requires_triage")),
        "passed": material_integration_report_passed(report, allow_warnings=allow_warnings),
        "summary": summary,
    }


def live_asset_report_passed(report: dict[str, Any]) -> bool:
    source_policy = str(report.get("source_policy") or "required")
    source_ok = True
    if source_policy in {"generated", "required"}:
        source_ok = bool(report.get("local_file_exists"))
    return bool(
        source_ok
        and report.get("texture_asset_exists")
        and report.get("material_references_target_texture")
        and report.get("renderer_references_material")
    )


def live_asset_report_identifiers(report: dict[str, Any]) -> set[str]:
    values = {
        str(report.get("local_file", "") or ""),
        str(report.get("texture_asset_path", "") or ""),
    }
    texture_asset_path = str(report.get("texture_asset_path", "") or "")
    if texture_asset_path and "." not in texture_asset_path.rsplit("/", 1)[-1]:
        asset_name = texture_asset_path.rsplit("/", 1)[-1]
        values.add(f"{texture_asset_path}.{asset_name}")
    return {value for value in values if value}


def niagara_audit_warning_count(report: dict[str, Any]) -> int:
    return len(report.get("warnings", []) or [])


def niagara_audit_system_path(report: dict[str, Any]) -> str:
    return str(report.get("system_path", "") or "")


def renderer_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def niagara_audit_renderer_classes(report: dict[str, Any]) -> list[str]:
    classes: list[str] = []
    for emitter in report.get("emitters", []) or []:
        parsed = emitter.get("parsed") or {}
        classes.extend(str(item) for item in parsed.get("renderer_classes", []) or [])
    return sorted(dict.fromkeys(classes))


def niagara_audit_renderer_materials(report: dict[str, Any]) -> list[str]:
    materials: list[str] = []
    for emitter in report.get("emitters", []) or []:
        parsed = emitter.get("parsed") or {}
        materials.extend(str(item) for item in parsed.get("renderer_materials", []) or [])
    return sorted(dict.fromkeys(materials))


def niagara_emitter_roles(emitter: dict[str, Any]) -> set[str]:
    parsed = emitter.get("parsed") or {}
    roles = {str(emitter.get("role", "") or "")}
    roles.update(str(item) for item in emitter.get("roles", []) or [])
    capabilities = {str(item) for item in emitter.get("capabilities", []) or []}
    roles.update(item for item in capabilities if item.endswith("-receiver") or item == "source")
    renderer_blob = " ".join(str(item) for item in parsed.get("renderer_classes", []) or [])
    if "Ribbon" in renderer_blob:
        roles.add("trail-receiver")
    function_blob = " ".join(str(item) for item in parsed.get("function_names", []) or []).lower()
    data_interface_blob = " ".join(str(item) for item in parsed.get("data_interface_classes", []) or []).lower()
    if (
        parsed.get("data_interface_bindings")
        or "particleread" in data_interface_blob
        or "sampleparticlesfromotheremitter" in function_blob
        or "spawnparticlesfromotheremitter" in function_blob
        or "attribute-reader" in capabilities
        or "inter-emitter-data-flow" in capabilities
    ):
        roles.add("attribute-reader-receiver")
    name_blob = " ".join([str(emitter.get("name", "") or ""), str(emitter.get("id_name", "") or "")]).lower()
    if any(token in name_blob for token in ("source", "leader", "seed", "driver", "upstream")):
        roles.add("source")
    if any(token in name_blob for token in ("receiver", "trail", "follow", "secondary", "downstream")):
        roles.add("receiver")
    return {role for role in roles if role}


def niagara_audit_roles(report: dict[str, Any]) -> set[str]:
    roles: set[str] = set()
    for emitter in report.get("emitters", []) or []:
        roles.update(niagara_emitter_roles(emitter))
    return roles


def niagara_audit_has_attribute_reader_flow(report: dict[str, Any]) -> bool:
    for emitter in report.get("emitters", []) or []:
        capabilities = {str(item) for item in emitter.get("capabilities", []) or []}
        if "attribute-reader" in capabilities or "inter-emitter-data-flow" in capabilities:
            return True
        parsed = emitter.get("parsed") or {}
        if parsed.get("data_interface_bindings"):
            return True
        blob = " ".join(
            [
                " ".join(str(item) for item in parsed.get("data_interface_classes", []) or []),
                " ".join(str(item) for item in parsed.get("function_names", []) or []),
                str(emitter.get("role", "")),
                " ".join(str(item) for item in emitter.get("roles", []) or []),
                " ".join(capabilities),
            ]
        ).lower()
        if "particleread" in blob or "sampleparticlesfromotheremitter" in blob or "spawnparticlesfromotheremitter" in blob:
            return True
    return False


def niagara_audit_has_bounds(report: dict[str, Any]) -> bool:
    system_bounds = ((report.get("system_properties") or {}).get("FixedBounds") or {}).get("text", "")
    if str(system_bounds or "").strip():
        return True
    for emitter in report.get("emitters", []) or []:
        parsed = emitter.get("parsed") or {}
        if str(parsed.get("fixed_bounds", "") or "").strip():
            return True
    return False


def niagara_audit_test_emitters(report: dict[str, Any]) -> list[str]:
    offenders: list[str] = []
    for emitter in report.get("emitters", []) or []:
        name = str(emitter.get("name", "") or "")
        emitter_path = str(emitter.get("emitter_path", "") or "")
        path_leaf = emitter_path.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
        blob = " ".join([name, str(emitter.get("id_name", "") or ""), path_leaf]).lower()
        compact = renderer_token(blob)
        word_hit = bool(re.search(r"(^|[^a-z0-9])(test|debug|tmp)([^a-z0-9]|$)", blob))
        compact_hit = any(token in compact for token in ("codexrenderertest", "renderertest", "testemitter", "emittertest"))
        if word_hit or compact_hit:
            offenders.append(name or str(emitter.get("emitter_path", "") or "unnamed-emitter"))
    return offenders


def make_niagara_contract(args: argparse.Namespace) -> dict[str, Any]:
    preset: dict[str, Any] = {}
    effect_type = str(getattr(args, "effect_type_contract", "") or "")
    if effect_type:
        preset = effect_type_contract(effect_type)
    return {
        "effect_type": effect_type,
        "effect_type_label": preset.get("label", ""),
        "expected_roles": list(preset.get("expected_roles", []) or []),
        "visual_required": list(preset.get("visual_required", []) or []),
        "required_renderers": [
            *list(preset.get("required_renderers", []) or []),
            *list(getattr(args, "require_niagara_renderer", []) or []),
        ],
        "required_materials": list(getattr(args, "require_niagara_material", []) or []),
        "require_attribute_reader_data_flow": bool(
            preset.get("require_attribute_reader_data_flow")
            or getattr(args, "require_attribute_reader_data_flow", False)
        ),
        "require_bounds": bool(preset.get("require_bounds") or getattr(args, "require_niagara_bounds", False)),
        "forbid_test_emitters": bool(preset.get("forbid_test_emitters") or getattr(args, "forbid_test_emitter", False)),
    }


def niagara_contract_enabled(contract: dict[str, Any] | None) -> bool:
    if not contract:
        return False
    return bool(
        contract.get("expected_roles")
        or contract.get("required_renderers")
        or contract.get("required_materials")
        or contract.get("require_attribute_reader_data_flow")
        or contract.get("require_bounds")
        or contract.get("forbid_test_emitters")
    )


def evaluate_niagara_contract(niagara_audit_reports: list[dict[str, Any]], contract: dict[str, Any] | None) -> list[str]:
    if not niagara_contract_enabled(contract):
        return []
    contract = contract or {}
    violations: list[str] = []
    all_materials: list[str] = []
    for report in niagara_audit_reports:
        system_path = niagara_audit_system_path(report) or "unknown-system"
        renderer_classes = niagara_audit_renderer_classes(report)
        renderer_tokens = [renderer_token(item) for item in renderer_classes]
        roles = niagara_audit_roles(report)
        for expected_role in contract.get("expected_roles", []) or []:
            if expected_role and expected_role not in roles:
                violations.append(f"System `{system_path}` is missing expected emitter role `{expected_role}` for `{contract.get('effect_type')}`.")
        for required in contract.get("required_renderers", []) or []:
            required_token = renderer_token(required)
            if required_token and not any(required_token in item or item in required_token for item in renderer_tokens):
                violations.append(f"System `{system_path}` is missing required renderer `{required}`.")
        if contract.get("require_attribute_reader_data_flow") and not niagara_audit_has_attribute_reader_flow(report):
            violations.append(f"System `{system_path}` is missing Attribute Reader / inter-emitter data flow evidence.")
        if contract.get("require_bounds") and not niagara_audit_has_bounds(report):
            violations.append(f"System `{system_path}` is missing FixedBounds evidence.")
        if contract.get("forbid_test_emitters"):
            offenders = niagara_audit_test_emitters(report)
            if offenders:
                violations.append(f"System `{system_path}` still contains test/debug emitter(s): {', '.join(offenders)}.")
        all_materials.extend(niagara_audit_renderer_materials(report))
    for required_material in contract.get("required_materials", []) or []:
        if not any(asset_reference_matches(candidate, required_material) for candidate in all_materials):
            violations.append(f"No audited Niagara renderer is bound to required material `{required_material}`.")
    return sorted(dict.fromkeys(violations))


def load_visual_diff_reports(ctx, effect: str) -> list[dict[str, Any]]:
    folder = ctx.vfx_root / "diff-qa" / slugify(effect)
    if not folder.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in folder.rglob("diff-report.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_source_path"] = str(path)
        reports.append(payload)
    return reports


def load_design_compare_reports(ctx, effect: str) -> list[dict[str, Any]]:
    folder = ctx.vfx_root / "design-compare" / slugify(effect)
    if not folder.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in folder.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_source_path"] = str(path)
        reports.append(payload)
    return reports


def evaluate_visual_quality(
    *,
    diff_reports: list[dict[str, Any]],
    compare_reports: list[dict[str, Any]],
    max_mean_diff: float,
    max_edge_mean_diff: float,
    max_mask_delta: float,
    required_criteria: list[str],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    passed_diff_count = 0
    for report in diff_reports:
        metrics = report.get("metrics") or {}
        mean_diff = float(metrics.get("mean_diff", 9999.0) or 9999.0)
        edge_diff = float(metrics.get("edge_mean_diff", 9999.0) or 9999.0)
        mask_delta = float(metrics.get("mask_delta", 1.0) or 1.0)
        report_path = report.get("_source_path", "")
        if mean_diff > max_mean_diff:
            failures.append(f"Visual diff `{report_path}` mean_diff {mean_diff} exceeds {max_mean_diff}.")
        if edge_diff > max_edge_mean_diff:
            failures.append(f"Visual diff `{report_path}` edge_mean_diff {edge_diff} exceeds {max_edge_mean_diff}.")
        if mask_delta > max_mask_delta:
            failures.append(f"Visual diff `{report_path}` mask_delta {mask_delta} exceeds {max_mask_delta}.")
        if mean_diff <= max_mean_diff and edge_diff <= max_edge_mean_diff and mask_delta <= max_mask_delta:
            passed_diff_count += 1
    criteria_seen: set[str] = set()
    for report in compare_reports:
        report_path = report.get("_source_path", "")
        for item in report.get("criteria", []) or []:
            name = str(item.get("name", "") or "")
            status = str(item.get("status", "pending") or "pending")
            criteria_seen.add(name)
            if status in {"fail", "needs-tuning", "pending"}:
                failures.append(f"Design compare `{report_path}` criterion `{name}` is `{status}`.")
    missing_required = [name for name in required_criteria if name not in criteria_seen]
    for name in missing_required:
        failures.append(f"Required visual criterion `{name}` has no design-compare record.")
    return failures, {
        "diff_report_count": len(diff_reports),
        "passed_diff_count": passed_diff_count,
        "design_compare_count": len(compare_reports),
        "required_criteria": required_criteria,
        "criteria_seen": sorted(criteria_seen),
        "thresholds": {
            "max_mean_diff": max_mean_diff,
            "max_edge_mean_diff": max_edge_mean_diff,
            "max_mask_delta": max_mask_delta,
        },
    }


def review_asset_values(review: dict[str, Any], plural_key: str, singular_keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    plural_value = review.get(plural_key)
    if isinstance(plural_value, list):
        values.extend(str(item) for item in plural_value if str(item or "").strip())
    elif plural_value:
        values.append(str(plural_value))
    for key in singular_keys:
        value = review.get(key)
        if value:
            values.append(str(value))
    return sorted(dict.fromkeys(values))


def preview_covers_required_assets(review_values: list[str], required_values: list[str]) -> bool:
    if not required_values:
        return True
    if not review_values:
        return False
    return all(any(asset_reference_matches(candidate, required) for candidate in review_values) for required in required_values)


def preview_matches_delivery_context(
    review: dict[str, Any],
    *,
    anchor_revision: int,
    final_systems: list[str],
    final_materials: list[str],
) -> bool:
    if int(review.get("anchor_revision", 0) or 0) != int(anchor_revision or 0):
        return False
    review_systems = review_asset_values(review, "final_systems", ("final_system", "system_path"))
    review_materials = review_asset_values(review, "final_materials", ("final_material", "material_path"))
    return preview_covers_required_assets(review_systems, final_systems) and preview_covers_required_assets(review_materials, final_materials)


def effect_preview_matches_delivery_context(
    review: dict[str, Any],
    *,
    final_systems: list[str],
    final_materials: list[str],
) -> bool:
    context = review.get("context") if isinstance(review.get("context"), dict) else {}
    review_systems = review_asset_values(context, "final_systems", ("final_system", "system_path"))
    review_materials = review_asset_values(context, "final_materials", ("final_material", "material_path"))
    if not review_systems:
        review_systems = review_asset_values(review, "final_systems", ("final_system", "system_path"))
    if not review_materials:
        review_materials = review_asset_values(review, "final_materials", ("final_material", "material_path"))
    return preview_covers_required_assets(review_systems, final_systems) and preview_covers_required_assets(review_materials, final_materials)


def status_entry(
    status: str,
    label: str,
    detail: str,
    *,
    action_needed: str,
    count: int = 0,
    required: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    entry = {
        "status": status,
        "label": label,
        "detail": detail,
        "action_needed": action_needed,
        "count": count,
        "required": required,
    }
    entry.update(extra)
    return entry


def material_integration_probe_coverage(
    reports: list[dict[str, Any]],
    *,
    final_systems: list[str],
    final_materials: list[str],
    allow_warnings: bool = False,
) -> dict[str, Any]:
    matched_reports: list[dict[str, Any]] = []
    passing_reports: list[dict[str, Any]] = []
    failing_reports: list[dict[str, Any]] = []
    for report in reports:
        matches_route = any(
            material_integration_report_matches(report, system_path=system_path, material_path=material_path)
            for system_path in final_systems
            for material_path in final_materials
        )
        if not matches_route:
            continue
        matched_reports.append(report)
        if material_integration_report_passed(report, allow_warnings=allow_warnings):
            passing_reports.append(report)
        else:
            failing_reports.append(report)
    missing_systems = [
        system_path for system_path in final_systems
        if not any(
            material_integration_report_matches(report, system_path=system_path, material_path=material_path)
            and material_integration_report_passed(report, allow_warnings=allow_warnings)
            for report in reports
            for material_path in final_materials
        )
    ]
    missing_materials = [
        material_path for material_path in final_materials
        if not any(
            material_integration_report_matches(report, system_path=system_path, material_path=material_path)
            and material_integration_report_passed(report, allow_warnings=allow_warnings)
            for report in reports
            for system_path in final_systems
        )
    ]
    return {
        "matched_count": len(matched_reports),
        "passing_count": len(passing_reports),
        "failing_count": len(failing_reports),
        "missing_systems": missing_systems,
        "missing_materials": missing_materials,
        "matched_reports": [material_integration_probe_index_entry(item, allow_warnings=allow_warnings) for item in matched_reports],
    }


def build_delivery_health(
    *,
    effect: str,
    acceptance: dict[str, Any],
    approved_previews: list[dict[str, Any]],
    approved_effect_previews: list[dict[str, Any]],
    live_reports: list[dict[str, Any]],
    final_material_delivery: list[dict[str, Any]],
    niagara_audit_reports: list[dict[str, Any]],
    material_integration_probe_reports: list[dict[str, Any]] | None = None,
    active_assets: list[str],
    final_materials: list[str],
    final_systems: list[str],
    niagara_contract: dict[str, Any] | None = None,
    visual_diff_reports: list[dict[str, Any]] | None = None,
    design_compare_reports: list[dict[str, Any]] | None = None,
    require_visual_qa: bool = False,
    allow_material_integration_warnings: bool = False,
    visual_thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    anchor = acceptance.get("anchor_lock", {})
    anchor_id = str(anchor.get("entry_id", "") or "")
    anchor_scope = str(anchor.get("implementation_scope", "") or "")
    anchor_cache = str(anchor.get("cached_path", "") or "")
    scope_confirmed = bool(anchor.get("scope_confirmed", False))
    no_action = "No action needed."

    if not anchor_id:
        anchor_status = status_entry(
            "missing",
            "Anchor Approval",
            "No locked implementation anchor.",
            action_needed=f"Cache/review the intended reference, then run `reference_acceptance.py lock --effect {effect} --entry-id <id> --implementation-scope <scope> --scope-confirmed`.",
            required=True,
        )
    elif not scope_confirmed or not anchor_scope:
        anchor_status = status_entry(
            "blocked",
            "Anchor Approval",
            f"Anchor `{anchor_id}` is locked but scope is not confirmed.",
            action_needed=f"Re-lock `{anchor_id}` with `--implementation-scope <scope> --scope-confirmed` before implementation delivery.",
            required=True,
        )
    elif not anchor_cache or not Path(anchor_cache).exists():
        anchor_status = status_entry(
            "blocked",
            "Anchor Approval",
            f"Anchor `{anchor_id}` has no durable local cache.",
            action_needed="Re-cache the anchor with `reference_cache.py`, then re-lock the cached entry before packaging.",
            required=True,
        )
    else:
        anchor_status = status_entry(
            "pass",
            "Anchor Approval",
            f"`{anchor_id}` / `{anchor_scope}`",
            action_needed=no_action,
            count=1,
            required=True,
        )

    current_anchor_revision = int(anchor.get("revision", 0) or 0)
    matching_previews = []
    if anchor_id and current_anchor_revision > 0:
        matching_previews = [
            item for item in approved_previews
            if preview_matches_delivery_context(
                item,
                anchor_revision=current_anchor_revision,
                final_systems=final_systems,
                final_materials=final_materials,
            )
        ]
    if matching_previews:
        preview_status = status_entry(
            "pass",
            "Preview Approval",
            f"{len(matching_previews)} approved preview(s) match current anchor/final assets.",
            action_needed=no_action,
            count=len(matching_previews),
            required=True,
            matching_count=len(matching_previews),
            approved_count=len(approved_previews),
        )
    elif approved_previews and anchor_id and current_anchor_revision > 0:
        preview_status = status_entry(
            "risk",
            "Preview Approval",
            "Approved preview(s) exist, but none match the current anchor revision and final system/material binding.",
            action_needed=f"Capture a controlled preview from the current final system/material and register it with `preview_approval.py create --effect {effect} --final-system <system> --final-material <material>`.",
            count=0,
            required=True,
            matching_count=0,
            approved_count=len(approved_previews),
        )
    elif approved_previews:
        preview_status = status_entry(
            "missing",
            "Preview Approval",
            "Approved preview(s) exist, but there is no current locked anchor revision to bind them to.",
            action_needed=f"Lock the current anchor with `reference_acceptance.py lock --effect {effect}`, then create a preview from the current final system/material.",
            count=0,
            required=True,
            matching_count=0,
            approved_count=len(approved_previews),
        )
    else:
        preview_status = status_entry(
            "missing",
            "Preview Approval",
            "No approved preview recorded.",
            action_needed=f"Create and review a controlled preview, then run `preview_approval.py decide --effect {effect} --review-id <id> --status approved`.",
            required=True,
        )

    matching_effect_previews = []
    if final_systems:
        matching_effect_previews = [
            item
            for item in approved_effect_previews
            if effect_preview_matches_delivery_context(
                item,
                final_systems=final_systems,
                final_materials=final_materials,
            )
        ]
    if matching_effect_previews:
        effect_preview_status = status_entry(
            "pass",
            "Effect Preview Approval",
            f"{len(matching_effect_previews)} approved final effect preview(s) match the current final system/material route.",
            action_needed=no_action,
            count=len(matching_effect_previews),
            required=True,
            matching_count=len(matching_effect_previews),
            approved_count=len(approved_effect_previews),
        )
    elif final_systems and approved_effect_previews:
        effect_preview_status = status_entry(
            "risk",
            "Effect Preview Approval",
            "Approved final effect preview(s) exist, but none match the current final system/material route.",
            action_needed=(
                f"Capture a fresh controlled final effect preview for `{effect}`, register it with "
                f"`effect_preview_approval.py create --effect {effect} --preview-path <png> --system-path <system> --material-path <material> --grid <cols>x<rows>`, "
                f"then approve it with `effect_preview_approval.py decide --effect {effect} --review-id <id> --status approved`."
            ),
            count=0,
            required=True,
            matching_count=0,
            approved_count=len(approved_effect_previews),
        )
    elif final_systems:
        effect_preview_status = status_entry(
            "missing",
            "Effect Preview Approval",
            "No approved final effect preview recorded for the current final route.",
            action_needed=(
                f"Capture a controlled final effect preview for `{effect}`, create a review with "
                f"`effect_preview_approval.py create --effect {effect} --preview-path <png> --system-path <system> --material-path <material> --grid <cols>x<rows>`, "
                f"then approve it with `effect_preview_approval.py decide --effect {effect} --review-id <id> --status approved`."
            ),
            required=True,
        )
    else:
        effect_preview_status = status_entry(
            "not_applicable",
            "Effect Preview Approval",
            "No final Niagara systems specified.",
            action_needed="No action unless this package has final effect/system assets that require controlled final preview approval.",
            required=False,
        )

    passed_live = [item for item in live_reports if live_asset_report_passed(item)]
    if active_assets:
        verified_identifiers = set().union(*(live_asset_report_identifiers(item) for item in passed_live)) if passed_live else set()
        missing_assets = [asset for asset in active_assets if asset not in verified_identifiers]
        if missing_assets:
            live_status = status_entry(
                "risk",
                "Live Asset Verify",
                f"{len(active_assets) - len(missing_assets)}/{len(active_assets)} active asset(s) have passing live verify.",
                action_needed=f"Run `live_asset_verify.py --effect {effect}` for each missing active texture; use `--source-policy ue-only` for UE-native or hand-authored assets without a local source file.",
                count=len(passed_live),
                required=True,
            )
        else:
            live_status = status_entry(
                "pass",
                "Live Asset Verify",
                f"All {len(active_assets)} active asset(s) have passing live verify.",
                action_needed=no_action,
                count=len(passed_live),
                required=True,
            )
    elif live_reports:
        live_status = status_entry(
            "pass" if passed_live else "risk",
            "Live Asset Verify",
            f"{len(passed_live)}/{len(live_reports)} live verify report(s) pass.",
            action_needed=no_action if passed_live else f"Re-run failing `live_asset_verify.py --effect {effect}` checks after fixing UE import/material/renderer references.",
            count=len(passed_live),
            required=False,
        )
    else:
        live_status = status_entry(
            "not_applicable",
            "Live Asset Verify",
            "No active texture assets specified.",
            action_needed="No action unless this package includes generated or live-bound texture assets.",
            required=False,
        )

    approved_materials = [item for item in final_material_delivery if item.get("approved_for_reuse")]
    if final_materials:
        missing_reports = [item for item in final_material_delivery if not item.get("has_delivery_report")]
        unapproved_reports = [
            item for item in final_material_delivery
            if item.get("has_delivery_report") and not item.get("approved_for_reuse")
        ]
        if missing_reports:
            material_status = status_entry(
                "risk",
                "Material Delivery Approval",
                f"{len(missing_reports)} final material(s) missing material delivery report.",
                action_needed="Generate or approve the missing material delivery report from `unreal-material-artist`, then rerun `delivery_package.py`.",
                count=len(approved_materials),
                required=True,
            )
        elif unapproved_reports:
            material_status = status_entry(
                "risk",
                "Material Delivery Approval",
                f"{len(unapproved_reports)} final material report(s) are not approved.",
                action_needed="Fix material preview/report warnings, promote or approve the material, then rerun `delivery_package.py`.",
                count=len(approved_materials),
                required=True,
            )
        else:
            material_status = status_entry(
                "pass",
                "Material Delivery Approval",
                f"All {len(final_materials)} final material(s) approved for reuse.",
                action_needed=no_action,
                count=len(approved_materials),
                required=True,
            )
    else:
        material_status = status_entry(
            "not_applicable",
            "Material Delivery Approval",
            "No final materials specified.",
            action_needed="No action unless this package has final material assets.",
            required=False,
        )

    material_integration_probe_reports = material_integration_probe_reports or []
    if final_systems and final_materials:
        probe_coverage = material_integration_probe_coverage(
            material_integration_probe_reports,
            final_systems=final_systems,
            final_materials=final_materials,
            allow_warnings=allow_material_integration_warnings,
        )
        missing_systems = probe_coverage["missing_systems"]
        missing_materials = probe_coverage["missing_materials"]
        if not material_integration_probe_reports:
            material_integration_status = status_entry(
                "missing",
                "Material Integration Probe",
                "No Niagara material integration probe report found for the final system/material route.",
                action_needed=(
                    f"Run `niagara_material_integration_probe.py --system-path <system> --material-delivery-package <material-package> "
                    f"--material-path <material> --strict-unknown --fail-on-warning --markdown`, then rerun `delivery_package.py --effect {effect}`."
                ),
                required=True,
                **probe_coverage,
            )
        elif missing_systems or missing_materials:
            status = "risk" if probe_coverage["matched_count"] else "missing"
            detail = (
                f"{probe_coverage['matched_count']} matching probe report(s) exist, but none pass the strict material integration gate."
                if probe_coverage["matched_count"] and not probe_coverage["passing_count"]
                else f"{probe_coverage['passing_count']} passing probe report(s); coverage is missing for current final system/material route."
            )
            action = (
                "Fix the failing `niagara_material_integration_probe.py` warning/error evidence, or rerun delivery with `--allow-material-integration-warnings` only for an intentional tolerant check."
                if probe_coverage["matched_count"] and not probe_coverage["passing_count"]
                else "Run or refresh `niagara_material_integration_probe.py` for every final Niagara system and final material pair that must ship together."
            )
            material_integration_status = status_entry(
                status,
                "Material Integration Probe",
                detail,
                action_needed=action,
                required=True,
                **probe_coverage,
            )
        else:
            material_integration_status = status_entry(
                "pass",
                "Material Integration Probe",
                f"{probe_coverage['passing_count']} passing probe report(s) cover the final system/material route.",
                action_needed=no_action,
                count=probe_coverage["passing_count"],
                required=True,
                **probe_coverage,
            )
    elif material_integration_probe_reports:
        passing_count = sum(
            1 for item in material_integration_probe_reports
            if material_integration_report_passed(item, allow_warnings=allow_material_integration_warnings)
        )
        material_integration_status = status_entry(
            "pass" if passing_count else "risk",
            "Material Integration Probe",
            f"{passing_count}/{len(material_integration_probe_reports)} material integration probe report(s) pass, but no complete final system/material route was provided.",
            action_needed=no_action if passing_count else "Review failing `niagara_material_integration_probe.py` report(s) or rerun the probe for the intended final route.",
            count=passing_count,
            required=False,
            matched_count=0,
            passing_count=passing_count,
            failing_count=len(material_integration_probe_reports) - passing_count,
            missing_systems=[],
            missing_materials=[],
            matched_reports=[
                material_integration_probe_index_entry(item, allow_warnings=allow_material_integration_warnings)
                for item in material_integration_probe_reports
            ],
        )
    else:
        material_integration_status = status_entry(
            "not_applicable",
            "Material Integration Probe",
            "No final system/material route specified for material integration proof.",
            action_needed="No action unless this package has both final Niagara systems and final material assets.",
            required=False,
            matched_count=0,
            passing_count=0,
            failing_count=0,
            missing_systems=[],
            missing_materials=[],
            matched_reports=[],
        )

    if final_systems:
        audited_systems = {niagara_audit_system_path(item) for item in niagara_audit_reports}
        missing_audits = [system for system in final_systems if system not in audited_systems]
        warning_reports = [item for item in niagara_audit_reports if niagara_audit_warning_count(item) > 0]
        contract_violations = evaluate_niagara_contract(niagara_audit_reports, niagara_contract)
        if missing_audits:
            niagara_status = status_entry(
                "risk",
                "Niagara Structural Audit",
                f"{len(missing_audits)} final system(s) missing Niagara audit.",
                action_needed=f"Run `niagara_audit.py <system> --root <root>` for each final system, then rerun `delivery_package.py --effect {effect}`.",
                count=len(niagara_audit_reports),
                required=True,
                contract=niagara_contract or {},
                violations=[],
            )
        elif warning_reports:
            niagara_status = status_entry(
                "risk",
                "Niagara Structural Audit",
                f"{len(warning_reports)} Niagara audit report(s) contain warnings.",
                action_needed="Fix renderer/material/data-flow warnings or regenerate the audit after repair before final packaging.",
                count=len(niagara_audit_reports),
                required=True,
                contract=niagara_contract or {},
                violations=[],
            )
        elif contract_violations:
            niagara_status = status_entry(
                "risk",
                "Niagara Structural Audit",
                f"{len(contract_violations)} Niagara structural contract violation(s).",
                action_needed="Fix the Niagara renderer/material/data-flow/bounds/test-emitter contract, regenerate `niagara_audit.py`, then rerun `delivery_package.py`.",
                count=len(niagara_audit_reports),
                required=True,
                contract=niagara_contract or {},
                violations=contract_violations,
            )
        else:
            niagara_status = status_entry(
                "pass",
                "Niagara Structural Audit",
                f"All {len(final_systems)} final system(s) have warning-free Niagara audits and satisfy the requested structural contract.",
                action_needed=no_action,
                count=len(niagara_audit_reports),
                required=True,
                contract=niagara_contract or {},
                violations=[],
            )
    else:
        niagara_status = status_entry(
            "not_applicable",
            "Niagara Structural Audit",
            "No final Niagara systems specified.",
            action_needed="No action unless this package has final Niagara system assets.",
            required=False,
            contract=niagara_contract or {},
            violations=[],
        )

    visual_diff_reports = visual_diff_reports or []
    design_compare_reports = design_compare_reports or []
    visual_thresholds = visual_thresholds or {}
    visual_required = list((niagara_contract or {}).get("visual_required", []) or [])
    visual_failures, visual_summary = evaluate_visual_quality(
        diff_reports=visual_diff_reports,
        compare_reports=design_compare_reports,
        max_mean_diff=float(visual_thresholds.get("max_mean_diff", 64.0)),
        max_edge_mean_diff=float(visual_thresholds.get("max_edge_mean_diff", 48.0)),
        max_mask_delta=float(visual_thresholds.get("max_mask_delta", 0.35)),
        required_criteria=visual_required if require_visual_qa else [],
    )
    if require_visual_qa:
        if not visual_diff_reports and not design_compare_reports:
            visual_status = status_entry(
                "missing",
                "Visual Quality",
                "No visual diff or design-compare reports found.",
                action_needed=f"Run `visual_diff_qa.py` and `design_compare_checklist.py` for `{effect}`, then rerun delivery packaging.",
                required=True,
                summary=visual_summary,
                violations=[],
            )
        elif visual_failures:
            visual_status = status_entry(
                "risk",
                "Visual Quality",
                f"{len(visual_failures)} visual QA issue(s).",
                action_needed="Fix the visual mismatch, regenerate controlled preview/diff/checklist, then rerun delivery packaging.",
                required=True,
                summary=visual_summary,
                violations=visual_failures,
            )
        else:
            visual_status = status_entry(
                "pass",
                "Visual Quality",
                "Visual diff and design-compare records satisfy the required thresholds.",
                action_needed=no_action,
                required=True,
                summary=visual_summary,
                violations=[],
            )
    elif visual_diff_reports or design_compare_reports:
        visual_status = status_entry(
            "pass" if not visual_failures else "risk",
            "Visual Quality",
            f"{visual_summary['diff_report_count']} visual diff report(s), {visual_summary['design_compare_count']} design-compare report(s).",
            action_needed=no_action if not visual_failures else "Review visual QA reports; use `--require-visual-qa` when visual proof should be a hard gate.",
            required=False,
            summary=visual_summary,
            violations=visual_failures,
        )
    else:
        visual_status = status_entry(
            "not_applicable",
            "Visual Quality",
            "No visual QA required for this package.",
            action_needed="Use `--require-visual-qa` for final design-fidelity delivery.",
            required=False,
            summary=visual_summary,
            violations=[],
        )

    checks = {
        "anchor_approval": anchor_status,
        "preview_approval": preview_status,
        "effect_preview_approval": effect_preview_status,
        "live_asset_verify": live_status,
        "niagara_structural_audit": niagara_status,
        "visual_quality": visual_status,
        "material_delivery_approval": material_status,
        "material_integration_probe": material_integration_status,
    }
    required = [item for item in checks.values() if item["required"]]
    if any(item["status"] == "blocked" for item in required):
        overall = "blocked"
    elif any(item["status"] == "risk" for item in required):
        overall = "risk"
    elif any(item["status"] == "missing" for item in required):
        overall = "incomplete"
    else:
        overall = "ready"
    return {"overall": overall, "checks": checks}


def build_manifest(ctx, effect: str, args: argparse.Namespace) -> dict[str, Any]:
    acceptance = load_effect_record(ctx, "reference-acceptance", effect, acceptance_default(effect))
    approvals = load_effect_record(ctx, "preview-approvals", effect, approvals_default(effect))
    effect_preview_approvals = load_effect_record(ctx, "effect-preview-approvals", effect, effect_preview_approvals_default(effect))
    asset_plan = load_effect_record(ctx, "asset-plans", effect, asset_plan_default(effect))
    integration = load_effect_record(ctx, "integration-plans", effect, integration_default(effect))
    tuning_entries = read_jsonl(log_path(ctx, effect))
    layer_map = load_map(ctx, effect)
    live_reports = load_live_asset_reports(ctx, effect)
    niagara_audit_reports = load_niagara_audit_reports(ctx, args.final_system)
    material_delivery_reports = load_material_delivery_reports(ctx)
    material_integration_probe_reports = load_material_integration_probe_reports(ctx, effect, args.material_integration_probe)
    approved_previews = [item for item in approvals["reviews"] if item["status"] == "approved"]
    approved_effect_previews = [item for item in effect_preview_approvals["reviews"] if item["status"] == "approved"]
    niagara_contract = make_niagara_contract(args)
    visual_diff_reports = load_visual_diff_reports(ctx, effect)
    design_compare_reports = load_design_compare_reports(ctx, effect)
    risks = list(args.risk)
    unverified_assets: list[str] = []
    if args.asset:
        verified_paths = {
            identifier
            for item in live_reports
            if live_asset_report_passed(item)
            for identifier in live_asset_report_identifiers(item)
        }
        for asset in args.asset:
            if asset not in verified_paths:
                risks.append(f"Asset `{asset}` has no passing live asset verification record.")
                unverified_assets.append(asset)
    final_material_delivery = match_material_delivery_reports(args.final_material, material_delivery_reports)
    missing_material_delivery = []
    unapproved_material_delivery = []
    for item in final_material_delivery:
        if not item["has_delivery_report"]:
            missing_material_delivery.append(item["requested_material_path"])
            risks.append(f"Final material `{item['requested_material_path']}` has no material delivery report.")
        elif not item["approved_for_reuse"]:
            unapproved_material_delivery.append(item["requested_material_path"])
            risks.append(f"Final material `{item['requested_material_path']}` has a material delivery report but is not approved for reuse.")
    delivery_health = build_delivery_health(
        effect=effect,
        acceptance=acceptance,
        approved_previews=approved_previews,
        approved_effect_previews=approved_effect_previews,
        live_reports=live_reports,
        final_material_delivery=final_material_delivery,
        niagara_audit_reports=niagara_audit_reports,
        material_integration_probe_reports=material_integration_probe_reports,
        active_assets=args.asset,
        final_materials=args.final_material,
        final_systems=args.final_system,
        niagara_contract=niagara_contract,
        visual_diff_reports=visual_diff_reports,
        design_compare_reports=design_compare_reports,
        require_visual_qa=args.require_visual_qa,
        allow_material_integration_warnings=args.allow_material_integration_warnings,
        visual_thresholds={
            "max_mean_diff": args.max_visual_mean_diff,
            "max_edge_mean_diff": args.max_visual_edge_mean_diff,
            "max_mask_delta": args.max_visual_mask_delta,
        },
    )
    return {
        "version": 1,
        "effect_name": effect,
        "delivery_health": delivery_health,
        "approved_anchor": acceptance["anchor_lock"]["entry_id"],
        "approved_previews": approved_previews,
        "approved_effect_previews": approved_effect_previews,
        "layer_count": len(layer_map["layers"]),
        "active_assets": args.asset,
        "final_systems": args.final_system,
        "final_materials": args.final_material,
        "niagara_contract": niagara_contract,
        "material_integration_probes": [
            material_integration_probe_index_entry(item, allow_warnings=args.allow_material_integration_warnings)
            for item in material_integration_probe_reports
        ],
        "visual_quality_reports": {
            "diff_reports": [
                {
                    "source_path": item.get("_source_path", ""),
                    "layer_name": item.get("layer_name", ""),
                    "preview_path": item.get("preview_path", ""),
                    "metrics": item.get("metrics", {}),
                }
                for item in visual_diff_reports
            ],
            "design_compare_reports": [
                {
                    "source_path": item.get("_source_path", ""),
                    "layer_name": item.get("layer_name", ""),
                    "criteria": item.get("criteria", []),
                }
                for item in design_compare_reports
            ],
        },
        "low_end_note": args.low_end_note,
        "risks": risks,
        "unverified_assets": unverified_assets,
        "final_material_delivery": final_material_delivery,
        "missing_material_delivery": missing_material_delivery,
        "unapproved_material_delivery": unapproved_material_delivery,
        "notes": args.notes,
        "supporting_records": {
            "layer_map_effect": effect,
            "asset_plan_present": bool(asset_plan.get("assets")),
            "integration_present": bool(integration.get("runtime_contract")),
            "tuning_entry_count": len(tuning_entries),
            "live_asset_verify_count": len(live_reports),
            "niagara_audit_report_count": len(niagara_audit_reports),
            "material_delivery_report_count": len(material_delivery_reports),
            "material_integration_probe_count": len(material_integration_probe_reports),
            "effect_preview_approval_count": len(approved_effect_previews),
        },
        "delivery_index": build_delivery_index(
            effect=effect,
            delivery_health=delivery_health,
            acceptance=acceptance,
            approved_previews=approved_previews,
            approved_effect_previews=approved_effect_previews,
            live_reports=live_reports,
            final_material_delivery=final_material_delivery,
            niagara_audit_reports=niagara_audit_reports,
            material_integration_probe_reports=material_integration_probe_reports,
            manifest_path="",
            summary_path="",
            final_systems=args.final_system,
            final_materials=args.final_material,
            niagara_contract=niagara_contract,
            allow_material_integration_warnings=args.allow_material_integration_warnings,
            visual_quality_reports={
                "diff_reports": visual_diff_reports,
                "design_compare_reports": design_compare_reports,
            },
        ),
    }


def build_delivery_index(
    *,
    effect: str,
    delivery_health: dict[str, Any],
    acceptance: dict[str, Any],
    approved_previews: list[dict[str, Any]],
    approved_effect_previews: list[dict[str, Any]],
    live_reports: list[dict[str, Any]],
    final_material_delivery: list[dict[str, Any]],
    niagara_audit_reports: list[dict[str, Any]],
    manifest_path: str,
    summary_path: str,
    final_systems: list[str],
    final_materials: list[str],
    niagara_contract: dict[str, Any] | None = None,
    material_integration_probe_reports: list[dict[str, Any]] | None = None,
    allow_material_integration_warnings: bool = False,
    visual_quality_reports: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    anchor = acceptance.get("anchor_lock", {})
    anchor_revision = int(anchor.get("revision", 0) or 0)
    return {
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect_name": effect,
        "overall": delivery_health.get("overall", "unknown"),
        "health": delivery_health,
        "anchor": {
            "entry_id": anchor.get("entry_id", ""),
            "implementation_scope": anchor.get("implementation_scope", ""),
            "cached_path": anchor.get("cached_path", ""),
            "revision": int(anchor.get("revision", 0) or 0),
        },
        "preview_approvals": [
            {
                "id": item.get("id", ""),
                "layer_name": item.get("layer_name", ""),
                "preview_path": item.get("preview_path", ""),
                "preview_kind": item.get("preview_kind", ""),
                "anchor_revision": int(item.get("anchor_revision", 0) or 0),
                "final_systems": review_asset_values(item, "final_systems", ("final_system", "system_path")),
                "final_materials": review_asset_values(item, "final_materials", ("final_material", "material_path")),
                "matches_delivery_context": preview_matches_delivery_context(
                    item,
                    anchor_revision=anchor_revision,
                    final_systems=final_systems,
                    final_materials=final_materials,
                ),
            }
            for item in approved_previews
        ],
        "effect_preview_approvals": [
            {
                "id": item.get("id", ""),
                "preview_path": item.get("preview_path", ""),
                "preset": item.get("preset", ""),
                "context": item.get("context", {}),
                "matches_delivery_context": effect_preview_matches_delivery_context(
                    item,
                    final_systems=final_systems,
                    final_materials=final_materials,
                ),
            }
            for item in approved_effect_previews
        ],
        "live_asset_verify": [
            {
                "source_path": item.get("_source_path", ""),
                "passed": live_asset_report_passed(item),
                "source_policy": item.get("source_policy", "required"),
                "local_file": item.get("local_file", ""),
                "texture_asset_path": item.get("texture_asset_path", ""),
                "material_path": item.get("material_path", ""),
                "renderer_path": item.get("renderer_path", ""),
            }
            for item in live_reports
        ],
        "niagara_audits": [
            {
                "source_path": item.get("_source_path", ""),
                "system_path": item.get("system_path", ""),
                "warning_count": niagara_audit_warning_count(item),
                "emitter_count": len(item.get("emitters", []) or []),
                "renderer_classes": niagara_audit_renderer_classes(item),
                "renderer_materials": niagara_audit_renderer_materials(item),
                "roles": sorted(niagara_audit_roles(item)),
                "has_attribute_reader_data_flow": niagara_audit_has_attribute_reader_flow(item),
                "has_bounds": niagara_audit_has_bounds(item),
                "test_emitters": niagara_audit_test_emitters(item),
            }
            for item in niagara_audit_reports
        ],
        "niagara_contract": niagara_contract or {},
        "niagara_contract_violations": ((delivery_health.get("checks") or {}).get("niagara_structural_audit") or {}).get("violations", []),
        "material_integration_probes": [
            material_integration_probe_index_entry(item, allow_warnings=allow_material_integration_warnings)
            for item in material_integration_probe_reports or []
        ],
        "material_integration_probe_coverage": ((delivery_health.get("checks") or {}).get("material_integration_probe") or {}),
        "visual_quality": {
            "summary": ((delivery_health.get("checks") or {}).get("visual_quality") or {}).get("summary", {}),
            "violations": ((delivery_health.get("checks") or {}).get("visual_quality") or {}).get("violations", []),
            "diff_report_count": len((visual_quality_reports or {}).get("diff_reports", [])),
            "design_compare_count": len((visual_quality_reports or {}).get("design_compare_reports", [])),
        },
        "material_delivery": final_material_delivery,
        "final_systems": final_systems,
        "final_materials": final_materials,
        "outputs": {
            "manifest": manifest_path,
            "summary": summary_path,
        },
    }


def health_badge(status: str) -> str:
    return {
        "pass": "PASS",
        "ready": "READY",
        "risk": "RISK",
        "missing": "MISSING",
        "not_applicable": "N/A",
        "blocked": "BLOCKED",
        "incomplete": "INCOMPLETE",
    }.get(status, str(status or "UNKNOWN").upper())


def delivery_payload_health(payload: dict[str, Any]) -> dict[str, Any]:
    if "health" in payload and isinstance(payload["health"], dict):
        return payload["health"]
    if "delivery_health" in payload and isinstance(payload["delivery_health"], dict):
        return payload["delivery_health"]
    return {"overall": "unknown", "checks": {}}


def delivery_payload_output_path(payload: dict[str, Any]) -> str:
    outputs = payload.get("outputs") or {}
    return str(outputs.get("summary") or outputs.get("manifest") or "")


def check_delivery_payload(payload: dict[str, Any], *, require_ready: bool) -> int:
    health = delivery_payload_health(payload)
    overall = str(health.get("overall", "unknown") or "unknown")
    print(f"Delivery health: {health_badge(overall)}")
    for key, item in (health.get("checks") or {}).items():
        label = item.get("label", key)
        status = health_badge(str(item.get("status", "unknown") or "unknown"))
        action = item.get("action_needed", "")
        print(f"- {label}: {status} - {item.get('detail', '')}")
        for violation in item.get("violations", [])[:5]:
            print(f"  Violation: {violation}")
        if action and action != "No action needed.":
            print(f"  Action: {action}")
    if require_ready and overall != "ready":
        output_path = delivery_payload_output_path(payload)
        suffix = f": {output_path}" if output_path else ""
        print(f"Delivery health is `{overall}`, not `ready`{suffix}", file=sys.stderr)
        return 2
    return 0


def update_delivery_index_outputs(index: dict[str, Any], *, manifest_path: Path, summary_path: Path) -> dict[str, Any]:
    clone = json.loads(json.dumps(index, ensure_ascii=False))
    clone.setdefault("outputs", {})
    clone["outputs"]["manifest"] = str(manifest_path)
    clone["outputs"]["summary"] = str(summary_path)
    return clone


def render_markdown(manifest: dict[str, Any]) -> str:
    health = manifest.get("delivery_health") or {}
    checks = health.get("checks") or {}
    lines = [
        f"# Delivery Package: {manifest['effect_name']}",
        "",
        "## Delivery Health",
        "",
        f"Overall: `{health_badge(str(health.get('overall', 'unknown')))}`",
        "",
        "| Gate | Status | Detail | Action Needed |",
        "| --- | --- | --- | --- |",
    ]
    for key in (
        "anchor_approval",
        "preview_approval",
        "effect_preview_approval",
        "live_asset_verify",
        "niagara_structural_audit",
        "material_integration_probe",
        "visual_quality",
        "material_delivery_approval",
    ):
        item = checks.get(key) or {}
        detail = item.get("detail", "No detail.")
        violations = item.get("violations") or []
        if violations:
            detail = f"{detail} Violations: {'; '.join(violations[:3])}"
        lines.append(
            f"| {item.get('label', key)} | `{health_badge(str(item.get('status', 'unknown')))}` | {detail} | {item.get('action_needed', 'No action recorded.')} |"
        )
    lines.extend(
        [
            "",
            "## Package Facts",
            "",
        ]
    )
    lines.extend([
        f"- Approved anchor: `{manifest['approved_anchor'] or 'unset'}`",
        f"- Approved previews: `{len(manifest['approved_previews'])}`",
        f"- Approved effect previews: `{len(manifest.get('approved_effect_previews', []))}`",
        f"- Layer count: `{manifest['layer_count']}`",
        f"- Final systems: {', '.join(manifest['final_systems']) or 'none'}",
        f"- Final materials: {', '.join(manifest['final_materials']) or 'none'}",
        f"- Active assets: {', '.join(manifest['active_assets']) or 'none'}",
        f"- Low-end note: {manifest['low_end_note'] or 'none'}",
        "",
        "## Risks",
        "",
    ])
    for item in manifest["risks"]:
        lines.append(f"- {item}")
    if not manifest["risks"]:
        lines.append("- none")
    lines.extend(["", "## Unverified Assets", ""])
    for item in manifest.get("unverified_assets", []):
        lines.append(f"- `{item}`")
    if not manifest.get("unverified_assets"):
        lines.append("- none")
    lines.extend(["", "## Final Material Delivery", ""])
    for item in manifest.get("final_material_delivery", []):
        lines.append(f"- Material: `{item['requested_material_path']}`")
        lines.append(f"Status: `{'approved' if item.get('approved_for_reuse') else 'missing-or-not-approved'}`")
        lines.append(f"Delivery report: `{item.get('delivery_report_path') or 'none'}`")
        lines.append(f"Domain: `{item.get('material_domain') or 'unknown'}`")
        lines.append(f"Category/Role: `{item.get('category') or 'unknown'}` / `{item.get('role') or 'unknown'}`")
        lines.append(f"Gate warnings/errors: `{item.get('warnings', 0)}` / `{item.get('errors', 0)}`")
    if not manifest.get("final_material_delivery"):
        lines.append("- none")
    lines.extend(["", "## Material Integration Probes", ""])
    for item in manifest.get("material_integration_probes", []):
        lines.append(f"- System: `{item.get('system_path') or 'unknown'}`")
        lines.append(f"Material: `{item.get('material_path') or 'unknown'}`")
        lines.append(f"Status: `{'passed' if item.get('passed') else 'not-passed'}`")
        lines.append(f"Report: `{item.get('source_path') or 'none'}`")
        summary = item.get("summary") or {}
        lines.append(f"Errors/warnings: `{summary.get('errors', 0)}` / `{summary.get('warnings', 0)}`")
    if not manifest.get("material_integration_probes"):
        lines.append("- none")
    lines.extend(["", "## Visual Quality Reports", ""])
    visual_reports = manifest.get("visual_quality_reports") or {}
    lines.append(f"- Diff reports: `{len(visual_reports.get('diff_reports', []))}`")
    lines.append(f"- Design compare reports: `{len(visual_reports.get('design_compare_reports', []))}`")
    return "\n".join(lines).rstrip() + "\n"


def package_command(args: argparse.Namespace) -> int:
    if not args.effect:
        raise SystemExit("Packaging requires --effect.")
    ctx = resolve_root_context(args.root)
    manifest = build_manifest(ctx, args.effect, args)
    folder = effect_folder(ctx, "delivery", args.effect)
    manifest_path = folder / "manifest.json"
    summary_path = folder / "summary.md"
    index_path = folder / "delivery-index.json"
    manifest["delivery_index"] = update_delivery_index_outputs(
        manifest.get("delivery_index", {}),
        manifest_path=manifest_path,
        summary_path=summary_path,
    )
    save_json(manifest_path, manifest)
    save_json(index_path, manifest["delivery_index"])
    write_text(summary_path, render_markdown(manifest))
    print(manifest_path)
    if args.require_ready and manifest.get("delivery_health", {}).get("overall") != "ready":
        print(
            f"Delivery health is `{manifest.get('delivery_health', {}).get('overall', 'unknown')}`, not `ready`: {summary_path}",
            file=sys.stderr,
        )
        return 2
    return 0


def check_command(args: argparse.Namespace) -> int:
    if bool(args.manifest) == bool(args.index):
        raise SystemExit("Provide exactly one of --manifest or --index.")
    payload_path = Path(args.manifest or args.index)
    payload = load_delivery_payload(payload_path)
    return check_delivery_payload(payload, require_ready=args.require_ready)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assemble a delivery manifest from the effect's closed-loop records.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command")
    check = subparsers.add_parser("check", description="Check an existing delivery manifest or index without regenerating it.")
    check.add_argument("--manifest", default="")
    check.add_argument("--index", default="")
    check.add_argument("--require-ready", action="store_true")
    check.set_defaults(func=check_command)
    parser.add_argument("--effect", default="")
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--final-system", action="append", default=[])
    parser.add_argument("--final-material", action="append", default=[])
    parser.add_argument("--material-integration-probe", action="append", default=[], help="Explicit niagara_material_integration_probe.py JSON report. When omitted, reports are auto-discovered by effect.")
    parser.add_argument("--allow-material-integration-warnings", action="store_true", help="Allow probe reports with warnings to satisfy the Material Integration Probe gate.")
    parser.add_argument("--effect-type-contract", choices=effect_type_names(), default="", help="Apply a built-in effect-type structural/visual contract.")
    parser.add_argument("--require-niagara-renderer", action="append", default=[], help="Require an audited renderer class/token, for example RibbonRendererProperties or Ribbon.")
    parser.add_argument("--require-niagara-material", action="append", default=[], help="Require an audited Niagara renderer material binding.")
    parser.add_argument("--require-attribute-reader-data-flow", action="store_true", help="Require Attribute Reader / inter-emitter data-flow evidence in Niagara audit.")
    parser.add_argument("--require-niagara-bounds", action="store_true", help="Require FixedBounds evidence in Niagara audit.")
    parser.add_argument("--forbid-test-emitter", action="store_true", help="Reject audited final systems that still contain test/debug emitter names.")
    parser.add_argument("--require-visual-qa", action="store_true", help="Require visual diff/design-compare records to pass before delivery can be ready.")
    parser.add_argument("--max-visual-mean-diff", type=float, default=64.0)
    parser.add_argument("--max-visual-edge-mean-diff", type=float, default=48.0)
    parser.add_argument("--max-visual-mask-delta", type=float, default=0.35)
    parser.add_argument("--low-end-note", default="")
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--require-ready", action="store_true")
    parser.set_defaults(func=package_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"check"},
        global_opts_with_value={"--root"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
