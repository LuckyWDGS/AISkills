from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, load_json, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .texture_asset_report import analyze_texture, image_info, is_power_of_two, parse_grid, render_markdown as render_texture_report_markdown


STAGES = ("approved", "candidates", "rejected")
CATEGORIES = (
    "noise",
    "mask",
    "distortion",
    "flipbook",
    "atlas",
    "ramp",
    "packed",
    "surface",
    "foliage",
    "decal",
    "post_process",
    "other",
)
TEXTURE_REPORT_ROLE_BY_CATEGORY = {
    "noise": "noise",
    "mask": "mask",
    "distortion": "flow",
    "flipbook": "flipbook",
    "atlas": "atlas",
    "ramp": "ramp",
    "packed": "packed",
    "surface": "albedo",
    "foliage": "foliage",
    "decal": "albedo",
    "other": "sprite",
}


def _merge_unique(existing: list[str] | None, canonical: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for item in list(existing or []) + list(canonical):
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _append_unique(items: list[str] | None, value: str) -> list[str]:
    result = list(items or [])
    if value not in result:
        result.append(value)
    return result


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def library_root() -> Path:
    return skill_root() / "assets" / "library"


def catalog_file() -> Path:
    return library_root() / "catalog" / "material-asset-catalog.json"


def catalog_reports_root() -> Path:
    return library_root() / "catalog" / "reports"


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def infer_audit_role(category: str, explicit_role: str | None) -> str:
    if explicit_role:
        return explicit_role.strip().lower()
    return TEXTURE_REPORT_ROLE_BY_CATEGORY.get(category, "sprite")


def ensure_library_layout() -> None:
    root = library_root()
    (root / "catalog").mkdir(parents=True, exist_ok=True)
    catalog_reports_root().mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        (root / stage).mkdir(parents=True, exist_ok=True)
    if not catalog_file().exists():
        save_json(
            catalog_file(),
            {
                "version": 1,
                "updated_utc": utc_now_iso(),
                "stages": list(STAGES),
                "categories": list(CATEGORIES),
                "assets": [],
            },
        )


def load_catalog() -> dict[str, Any]:
    ensure_library_layout()
    catalog = load_json(
        catalog_file(),
        {
            "version": 1,
            "updated_utc": utc_now_iso(),
            "stages": list(STAGES),
            "categories": list(CATEGORIES),
            "assets": [],
        },
    )
    changed = False
    merged_stages = _merge_unique(catalog.get("stages"), STAGES)
    if catalog.get("stages") != merged_stages:
        catalog["stages"] = merged_stages
        changed = True
    else:
        catalog["stages"] = merged_stages
    merged_categories = _merge_unique(catalog.get("categories"), CATEGORIES)
    if catalog.get("categories") != merged_categories:
        catalog["categories"] = merged_categories
        changed = True
    else:
        catalog["categories"] = merged_categories
    if "assets" not in catalog or not isinstance(catalog["assets"], list):
        catalog["assets"] = []
        changed = True
    for record in catalog["assets"]:
        if not isinstance(record, dict):
            continue
        if "asset_kind" not in record:
            record["asset_kind"] = "texture"
            changed = True
        if record.get("asset_kind") == "material":
            if "storage_mode" not in record:
                record["storage_mode"] = "external-ue-asset"
                changed = True
        else:
            if "storage_mode" not in record:
                record["storage_mode"] = "library-file"
                changed = True
    if catalog.get("version") != 1:
        catalog["version"] = 1
        changed = True
    if changed or catalog.get("stages") != list(catalog.get("stages")) or catalog.get("categories") != list(catalog.get("categories")):
        save_catalog(catalog)
    return catalog


def save_catalog(catalog: dict[str, Any]) -> None:
    catalog["updated_utc"] = utc_now_iso()
    save_json(catalog_file(), catalog)


def normalize_stage(stage: str) -> str:
    lowered = stage.strip().lower()
    if lowered not in STAGES:
        raise SystemExit(f"Unknown stage '{stage}'. Expected one of {STAGES}.")
    return lowered


def normalize_category(category: str) -> str:
    lowered = category.strip().lower()
    if lowered not in CATEGORIES:
        raise SystemExit(f"Unknown category '{category}'. Expected one of {CATEGORIES}.")
    return lowered


def make_dest_path(stage: str, category: str, source: Path, name: str | None) -> Path:
    base_name = slugify(name or source.stem)
    candidate = library_root() / stage / category / f"{base_name}{source.suffix.lower()}"
    if not candidate.exists():
        return candidate
    return library_root() / stage / category / f"{base_name}-{uuid.uuid4().hex[:8]}{source.suffix.lower()}"


def write_library_texture_report(asset_id: str, stored_path: Path, audit_role: str, grid: str | None) -> str:
    parsed_grid = parse_grid(grid)
    report = {
        "tool": "texture_asset_report",
        "role": audit_role,
        "grid": grid,
        "textures": [analyze_texture(image_info(stored_path), audit_role, parsed_grid)],
    }
    out = catalog_reports_root() / f"{slugify(asset_id)}-texture-asset-report.json"
    save_json(out, report)
    write_text(out.with_suffix(".md"), render_texture_report_markdown(report))
    return str(out)


def build_record(
    *,
    asset_id: str,
    stage: str,
    category: str,
    role: str,
    source_kind: str,
    original_source: str,
    stored_path: Path,
    name: str,
    tags: list[str],
    notes: str,
    qa_status: str,
    seamless: bool,
    grid: str | None,
    audit_role: str,
    info: dict[str, Any],
    source_report_paths: list[str],
    report_paths: list[str],
) -> dict[str, Any]:
    width = info.get("width")
    height = info.get("height")
    return {
        "asset_kind": "texture",
        "storage_mode": "library-file",
        "id": asset_id,
        "name": name,
        "stage": stage,
        "category": category,
        "role": role,
        "source_kind": source_kind,
        "original_source": original_source,
        "library_relpath": str(stored_path.relative_to(skill_root())).replace("\\", "/"),
        "file_name": stored_path.name,
        "tags": tags,
        "notes": notes,
        "qa_status": qa_status,
        "seamless": seamless,
        "grid": grid,
        "audit_role": audit_role,
        "width": width,
        "height": height,
        "power_of_two": bool(isinstance(width, int) and isinstance(height, int) and is_power_of_two(width) and is_power_of_two(height)),
        "has_alpha": info.get("has_alpha"),
        "source_report_paths": source_report_paths,
        "report_paths": report_paths,
        "created_utc": utc_now_iso(),
        "updated_utc": utc_now_iso(),
    }


def build_material_record(
    *,
    asset_id: str,
    stage: str,
    category: str,
    role: str,
    ue_asset_path: str,
    name: str,
    tags: list[str],
    notes: str,
    qa_status: str,
    source_kind: str,
    source_material_path: str,
    report_paths: list[str],
    material_info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "asset_kind": "material",
        "storage_mode": "external-ue-asset",
        "id": asset_id,
        "name": name,
        "stage": stage,
        "category": category,
        "role": role,
        "ue_asset_path": ue_asset_path,
        "source_kind": source_kind,
        "original_source": source_material_path,
        "source_material_path": source_material_path,
        "library_relpath": "",
        "file_name": "",
        "tags": tags,
        "notes": notes,
        "qa_status": qa_status,
        "material_domain": material_info.get("material_domain", ""),
        "blend_mode": material_info.get("blend_mode", ""),
        "shading_models": list(material_info.get("shading_models") or []),
        "num_expressions": material_info.get("num_expressions"),
        "source_report_paths": [],
        "report_paths": report_paths,
        "created_utc": utc_now_iso(),
        "updated_utc": utc_now_iso(),
    }


def stage_abs_path(record: dict[str, Any]) -> Path:
    return skill_root() / record["library_relpath"]


def move_record_asset(record: dict[str, Any], new_stage: str, new_category: str) -> None:
    if record.get("asset_kind") == "material" or record.get("storage_mode") == "external-ue-asset":
        record["stage"] = new_stage
        record["category"] = new_category
        return
    old_abs = stage_abs_path(record)
    new_abs = make_dest_path(new_stage, new_category, old_abs, record["name"])
    new_abs.parent.mkdir(parents=True, exist_ok=True)
    if old_abs.exists() and old_abs.resolve() != new_abs.resolve():
        shutil.move(str(old_abs), new_abs)
    record["stage"] = new_stage
    record["category"] = new_category
    record["library_relpath"] = str(new_abs.relative_to(skill_root())).replace("\\", "/")


def summarize_texture_asset_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    warnings = 0
    errors = 0
    for texture in payload.get("textures") or []:
        warnings += len(texture.get("warnings") or [])
        if not texture.get("exists", True):
            errors += 1
    return {
        "kind": "texture_asset_report",
        "path": str(path),
        "warnings": warnings,
        "errors": errors,
        "ok": warnings == 0 and errors == 0,
    }


def summarize_texture_import_audit(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    warnings = 0
    errors = 0
    infos = 0
    for texture in payload.get("textures") or []:
        for finding in texture.get("findings") or []:
            severity = str(finding.get("severity") or "").lower()
            if severity == "error":
                errors += 1
            elif severity == "warning":
                warnings += 1
            else:
                infos += 1
    return {
        "kind": "texture_import_audit",
        "path": str(path),
        "warnings": warnings,
        "errors": errors,
        "infos": infos,
        "ok": warnings == 0 and errors == 0,
    }


def load_gate_summary(path_text: str) -> dict[str, Any]:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Review report does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    tool = payload.get("tool")
    if tool == "texture_asset_report":
        return summarize_texture_asset_report(path)
    if tool == "texture_import_audit":
        return summarize_texture_import_audit(path)
    if tool == "material_preview":
        outputs = payload.get("outputs") or {}
        contract_scan = payload.get("contract_scan") or {}
        warnings = 0
        errors = 0
        for finding in contract_scan.get("findings") or []:
            sev = str(finding.get("severity") or "").lower()
            if sev == "error":
                errors += 1
            elif sev == "warning":
                warnings += 1
        for gate_name in ("decal_gate", "post_process_gate"):
            for finding in (contract_scan.get(gate_name) or {}).get("findings") or []:
                sev = str(finding.get("severity") or "").lower()
                if sev == "error":
                    errors += 1
                elif sev == "warning":
                    warnings += 1
        if outputs.get("shaded_ok") is False:
            errors += 1
        return {
            "kind": "material_preview",
            "path": str(path),
            "warnings": warnings,
            "errors": errors,
            "ok": errors == 0,
        }
    if tool == "material_domain_rebuilder":
        warnings = len(payload.get("skipped_nodes") or []) + len(payload.get("skipped_connections") or []) + len(payload.get("skipped_outputs") or [])
        errors = 0
        if not (payload.get("create") or {}).get("success"):
            errors += 1
        if not (payload.get("compile") or {}).get("success"):
            errors += 1
        if not (payload.get("save") or {}).get("success"):
            errors += 1
        return {
            "kind": "material_domain_rebuilder",
            "path": str(path),
            "warnings": warnings,
            "errors": errors,
            "ok": errors == 0,
        }
    raise SystemExit(f"Unsupported review report type '{tool}' in {path}")


def record_matches(record: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.stage and record.get("stage") != args.stage:
        return False
    if args.category and record.get("category") != args.category:
        return False
    if args.role and record.get("role") != args.role:
        return False
    if args.seamless and not record.get("seamless"):
        return False
    if args.power_of_two and not record.get("power_of_two"):
        return False
    if args.grid and record.get("grid") != args.grid:
        return False
    if args.tag:
        record_tags = {tag.lower() for tag in record.get("tags") or []}
        wanted = {tag.lower() for tag in args.tag}
        if not wanted.issubset(record_tags):
            return False
    if args.query:
        haystack = " ".join(
            [
                str(record.get("name", "")),
                str(record.get("category", "")),
                str(record.get("role", "")),
                str(record.get("ue_asset_path", "")),
                str(record.get("material_domain", "")),
                " ".join(record.get("tags") or []),
                str(record.get("notes", "")),
            ]
        ).lower()
        terms = [term.lower() for term in args.query]
        if not all(term in haystack for term in terms):
            return False
    return True


def render_search_markdown(records: list[dict[str, Any]]) -> str:
    lines = ["# Material Asset Library Search", ""]
    if not records:
        lines.append("- No matching reusable assets found.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        asset_kind = record.get("asset_kind", "texture")
        lines.extend(
            [
                f"## {record['name']}",
                "",
                f"- ID: `{record['id']}`",
                f"- Kind: `{asset_kind}`",
                f"- Stage: `{record['stage']}`",
                f"- Category: `{record['category']}`",
                f"- Role: `{record['role']}`",
                f"- Tags: {', '.join(record.get('tags') or []) or 'none'}",
            ]
        )
        if asset_kind == "material":
            lines.append(f"- UE Asset: `{record.get('ue_asset_path', '')}`")
            lines.append(f"- Domain: `{record.get('material_domain', '')}`")
            lines.append(f"- Blend: `{record.get('blend_mode', '')}`")
            lines.append(f"- Expressions: `{record.get('num_expressions')}`")
        else:
            lines.append(f"- Path: `{record['library_relpath']}`")
            lines.append(f"- Size: `{record.get('width')}x{record.get('height')}`")
            lines.append(f"- POT: `{record.get('power_of_two')}`")
        if record.get("notes"):
            lines.append(f"- Notes: {record['notes']}")
        delivery_reports = list(record.get("delivery_report_paths") or [])
        if delivery_reports:
            lines.append(f"- Delivery reports: `{len(delivery_reports)}`")
            lines.append(f"- Latest delivery report: `{delivery_reports[-1]}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_report_payload(path_text: str) -> dict[str, Any] | None:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        payload["_source_path"] = str(path)
        return payload
    return None


def _extract_recovery_details(record: dict[str, Any], report_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    for payload in report_payloads:
        if payload.get("tool") == "material_preview":
            rebuilt = ((payload.get("contract_scan") or {}).get("rebuilt_from")) or {}
            if rebuilt:
                outputs = payload.get("outputs") or {}
                options = payload.get("options") or {}
                return {
                    "source_material_path": rebuilt.get("source_material_path") or record.get("source_material_path", ""),
                    "target_material_ref": rebuilt.get("target_material_ref") or record.get("ue_asset_path", ""),
                    "target_domain": rebuilt.get("target_domain") or record.get("material_domain", ""),
                    "preview_carrier": options.get("carrier"),
                    "preview_route": options.get("preview_route"),
                    "preview_png": outputs.get("shaded_png"),
                    "compile_success": ((rebuilt.get("compile") or {}).get("success")),
                    "save_success": ((rebuilt.get("save") or {}).get("success")),
                    "create_reused_existing": ((rebuilt.get("create") or {}).get("reused_existing")),
                }
    for payload in report_payloads:
        if payload.get("tool") == "material_domain_rebuilder":
            return {
                "source_material_path": payload.get("source_material_path") or record.get("source_material_path", ""),
                "target_material_ref": payload.get("target_material_ref") or record.get("ue_asset_path", ""),
                "target_domain": payload.get("target_domain") or record.get("material_domain", ""),
                "preview_carrier": "",
                "preview_route": "",
                "preview_png": "",
                "compile_success": ((payload.get("compile") or {}).get("success")),
                "save_success": ((payload.get("save") or {}).get("success")),
                "create_reused_existing": ((payload.get("create") or {}).get("reused_existing")),
            }
    return {
        "source_material_path": record.get("source_material_path", ""),
        "target_material_ref": record.get("ue_asset_path", ""),
        "target_domain": record.get("material_domain", ""),
        "preview_carrier": "",
        "preview_route": "",
        "preview_png": "",
        "compile_success": None,
        "save_success": None,
        "create_reused_existing": None,
    }


def build_delivery_report(
    *,
    record: dict[str, Any],
    route: str,
    gate_report_paths: list[str],
    gate_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    report_payloads = [payload for payload in (_load_report_payload(path) for path in gate_report_paths) if payload]
    recovery = _extract_recovery_details(record, report_payloads)
    review_gate = dict(record.get("review_gate") or {})
    preview_pngs = [
        str(((payload.get("outputs") or {}).get("shaded_png") or "")).strip()
        for payload in report_payloads
        if payload.get("tool") == "material_preview"
    ]
    preview_pngs = [item for item in preview_pngs if item]
    return {
        "tool": "material_delivery_report",
        "generated_utc": utc_now_iso(),
        "delivery_route": route,
        "asset": {
            "asset_id": record.get("id"),
            "asset_kind": record.get("asset_kind"),
            "name": record.get("name"),
            "stage": record.get("stage"),
            "category": record.get("category"),
            "role": record.get("role"),
            "qa_status": record.get("qa_status"),
            "ue_asset_path": record.get("ue_asset_path", ""),
            "material_domain": record.get("material_domain", ""),
            "blend_mode": record.get("blend_mode", ""),
            "shading_models": list(record.get("shading_models") or []),
            "num_expressions": record.get("num_expressions"),
            "source_kind": record.get("source_kind", ""),
            "source_material_path": record.get("source_material_path", ""),
            "notes": record.get("notes", ""),
        },
        "delivery_summary": {
            "approved_for_reuse": record.get("stage") == "approved" and record.get("qa_status") == "approved",
            "report_gate_passed": all((item.get("errors") or 0) == 0 for item in gate_summaries),
            "warnings": sum(int(item.get("warnings") or 0) for item in gate_summaries),
            "errors": sum(int(item.get("errors") or 0) for item in gate_summaries),
            "report_count": len(gate_summaries),
        },
        "recovery": recovery,
        "approval_gate": {
            "review_gate": review_gate,
            "report_summaries": gate_summaries,
        },
        "linked_reports": {
            "gate_report_paths": gate_report_paths,
            "preview_pngs": preview_pngs,
        },
    }


def render_delivery_markdown(report: dict[str, Any]) -> str:
    asset = report.get("asset") or {}
    delivery = report.get("delivery_summary") or {}
    recovery = report.get("recovery") or {}
    review_gate = ((report.get("approval_gate") or {}).get("review_gate")) or {}
    lines = [
        f"# Material Delivery Report: {asset.get('name') or asset.get('asset_id')}",
        "",
        f"- Asset ID: `{asset.get('asset_id')}`",
        f"- Route: `{report.get('delivery_route')}`",
        f"- Approved for reuse: `{delivery.get('approved_for_reuse')}`",
        f"- Stage: `{asset.get('stage')}`",
        f"- Category: `{asset.get('category')}`",
        f"- Role: `{asset.get('role')}`",
        f"- UE Asset: `{asset.get('ue_asset_path')}`",
        f"- Domain: `{asset.get('material_domain')}`",
        f"- Blend: `{asset.get('blend_mode')}`",
        f"- Shading Models: `{', '.join(asset.get('shading_models') or []) or 'none'}`",
        f"- Expressions: `{asset.get('num_expressions')}`",
        f"- Source Kind: `{asset.get('source_kind')}`",
        f"- Source Material: `{asset.get('source_material_path')}`",
        f"- Gate Errors: `{delivery.get('errors')}`",
        f"- Gate Warnings: `{delivery.get('warnings')}`",
    ]
    if recovery.get("target_domain"):
        lines.extend(
            [
                "",
                "Recovery Summary:",
                f"- Target Domain: `{recovery.get('target_domain')}`",
                f"- Preview Carrier: `{recovery.get('preview_carrier') or 'n/a'}`",
                f"- Preview Route: `{recovery.get('preview_route') or 'n/a'}`",
                f"- Preview PNG: `{recovery.get('preview_png') or 'n/a'}`",
                f"- Compile Success: `{recovery.get('compile_success')}`",
                f"- Save Success: `{recovery.get('save_success')}`",
            ]
        )
    if review_gate:
        lines.extend(
            [
                "",
                "Review Gate:",
                f"- Reviewed UTC: `{review_gate.get('reviewed_utc')}`",
                f"- Self Review: `{review_gate.get('self_review')}`",
                f"- Allow Warnings: `{review_gate.get('allow_warnings')}`",
                f"- Errors: `{review_gate.get('errors')}`",
                f"- Warnings: `{review_gate.get('warnings')}`",
            ]
        )
    gate_report_paths = list(((report.get("linked_reports") or {}).get("gate_report_paths")) or [])
    if gate_report_paths:
        lines.extend(["", "Gate Reports:"])
        for path in gate_report_paths:
            lines.append(f"- `{path}`")
    return "\n".join(lines).rstrip() + "\n"


def write_delivery_report_for_record(
    *,
    record: dict[str, Any],
    route: str,
    gate_report_paths: list[str],
    gate_summaries: list[dict[str, Any]],
    root: str | None = None,
    out: str | None = None,
) -> str:
    ctx = resolve_root_context(root)
    effect = slugify(record.get("name") or record.get("ue_asset_path") or record.get("id") or "material")
    out_path = Path(out) if out else default_report_path(ctx, "deliveries", effect, f"{record.get('id')}-delivery-report", ".json")
    report = build_delivery_report(
        record=record,
        route=route,
        gate_report_paths=gate_report_paths,
        gate_summaries=gate_summaries,
    )
    save_json(out_path, report)
    write_text(out_path.with_suffix(".md"), render_delivery_markdown(report))
    return str(out_path)


def upsert_material_record(
    *,
    ue_asset_path: str,
    stage: str,
    category: str,
    role: str,
    name: str | None,
    tags: list[str],
    notes: str,
    qa_status: str,
    source_kind: str,
    source_material_path: str,
    report_paths: list[str],
    material_info: dict[str, Any],
) -> dict[str, Any]:
    catalog = load_catalog()
    existing = next(
        (
            record
            for record in catalog["assets"]
            if record.get("asset_kind") == "material" and record.get("ue_asset_path") == ue_asset_path
        ),
        None,
    )
    if existing is None:
        record = build_material_record(
            asset_id=uuid.uuid4().hex[:12],
            stage=normalize_stage(stage),
            category=normalize_category(category),
            role=role,
            ue_asset_path=ue_asset_path,
            name=name or ue_asset_path.rsplit("/", 1)[-1].split(".", 1)[0],
            tags=tags,
            notes=notes,
            qa_status=qa_status,
            source_kind=source_kind,
            source_material_path=source_material_path,
            report_paths=report_paths,
            material_info=material_info,
        )
        catalog["assets"].append(record)
    else:
        record = existing
        record["stage"] = normalize_stage(stage)
        record["category"] = normalize_category(category)
        record["role"] = role
        record["name"] = name or record.get("name") or ue_asset_path.rsplit("/", 1)[-1].split(".", 1)[0]
        record["tags"] = tags
        record["notes"] = notes
        record["qa_status"] = qa_status
        record["source_kind"] = source_kind
        record["original_source"] = source_material_path
        record["source_material_path"] = source_material_path
        record["material_domain"] = material_info.get("material_domain", "")
        record["blend_mode"] = material_info.get("blend_mode", "")
        record["shading_models"] = list(material_info.get("shading_models") or [])
        record["num_expressions"] = material_info.get("num_expressions")
        existing_reports = list(record.get("report_paths") or [])
        for item in report_paths:
            if item not in existing_reports:
                existing_reports.append(item)
        record["report_paths"] = existing_reports
        record["updated_utc"] = utc_now_iso()
    save_catalog(catalog)
    return record


def command_search(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    records = [record for record in catalog["assets"] if record_matches(record, args)]
    records = records[: args.max_results]
    if args.markdown:
        out = Path(args.out) if args.out else library_root() / "catalog" / "last-search.md"
        write_text(out, render_search_markdown(records))
        print(out)
    else:
        print(json.dumps({"results": records}, ensure_ascii=False, indent=2))
    return 0


def command_register(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Source file does not exist: {source}")

    stage = normalize_stage(args.stage)
    category = normalize_category(args.category)
    role = args.role.strip().lower()
    audit_role = infer_audit_role(category, getattr(args, "audit_role", None))
    dest = make_dest_path(stage, category, source, args.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if args.move:
        shutil.move(str(source), dest)
    else:
        shutil.copy2(source, dest)

    info = image_info(dest)
    asset_id = uuid.uuid4().hex[:12]
    library_report = write_library_texture_report(asset_id, dest, audit_role, args.grid)
    record = build_record(
        asset_id=asset_id,
        stage=stage,
        category=category,
        role=role,
        source_kind=args.source_kind,
        original_source=str(source),
        stored_path=dest,
        name=args.name or dest.stem,
        tags=split_csv(args.tags),
        notes=args.notes,
        qa_status=args.qa_status,
        seamless=args.seamless,
        grid=args.grid,
        audit_role=audit_role,
        info=info,
        source_report_paths=args.report_path or [],
        report_paths=[library_report],
    )
    catalog["assets"].append(record)
    save_catalog(catalog)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def command_promote(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    target = next((record for record in catalog["assets"] if record["id"] == args.asset_id), None)
    if target is None:
        raise SystemExit(f"Unknown asset id: {args.asset_id}")

    new_stage = normalize_stage(args.stage)
    new_category = normalize_category(args.category or target["category"])
    move_record_asset(target, new_stage, new_category)
    if args.tags:
        target["tags"] = split_csv(args.tags)
    if args.notes:
        target["notes"] = args.notes
    if args.qa_status:
        target["qa_status"] = args.qa_status
    if args.report_path:
        existing = list(target.get("report_paths") or [])
        for item in args.report_path:
            if item not in existing:
                existing.append(item)
        target["report_paths"] = existing
    delivery_report_path = None
    if new_stage == "approved" and target.get("asset_kind") == "material":
        gate_report_paths = list(args.report_path or target.get("report_paths") or [])
        gate_summaries = [load_gate_summary(path) for path in gate_report_paths] if gate_report_paths else []
        delivery_report_path = write_delivery_report_for_record(
            record=target,
            route="promote",
            gate_report_paths=gate_report_paths,
            gate_summaries=gate_summaries,
            root=getattr(args, "root", None),
            out=getattr(args, "delivery_out", None),
        )
        target["delivery_report_paths"] = _append_unique(target.get("delivery_report_paths"), delivery_report_path)
    target["updated_utc"] = utc_now_iso()
    save_catalog(catalog)
    payload: dict[str, Any] = {"record": target}
    if delivery_report_path:
        payload["delivery_report_path"] = delivery_report_path
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_auto_promote(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    target = next((record for record in catalog["assets"] if record["id"] == args.asset_id), None)
    if target is None:
        raise SystemExit(f"Unknown asset id: {args.asset_id}")
    if target["stage"] != "candidates":
        raise SystemExit("Auto promote gate only applies to candidate assets.")

    if args.self_review != "approved":
        decision = {
            "asset_id": args.asset_id,
            "decision": "rejected",
            "reason": "self_review_not_approved",
            "self_review": args.self_review,
            "applied": False,
        }
        print(json.dumps(decision, ensure_ascii=False, indent=2))
        return 1

    report_paths = list(args.report_path or target.get("report_paths") or [])
    if not report_paths:
        raise SystemExit("Auto promote needs report paths or a record with report_paths.")
    summaries = [load_gate_summary(path) for path in report_paths]
    errors = sum(int(item.get("errors") or 0) for item in summaries)
    warnings = sum(int(item.get("warnings") or 0) for item in summaries)
    passed = errors == 0 and (warnings == 0 or args.allow_warnings)

    decision = {
        "asset_id": args.asset_id,
        "decision": "approved" if passed else "blocked",
        "self_review": args.self_review,
        "allow_warnings": args.allow_warnings,
        "errors": errors,
        "warnings": warnings,
        "reports": summaries,
        "applied": False,
    }

    if passed and args.apply:
        move_record_asset(target, "approved", target["category"])
        target["qa_status"] = "approved"
        if args.notes:
            target["notes"] = args.notes
        existing = list(target.get("report_paths") or [])
        for item in report_paths:
            if item not in existing:
                existing.append(item)
        target["report_paths"] = existing
        target["review_gate"] = {
            "reviewed_utc": utc_now_iso(),
            "self_review": args.self_review,
            "allow_warnings": args.allow_warnings,
            "errors": errors,
            "warnings": warnings,
        }
        delivery_report_path = write_delivery_report_for_record(
            record=target,
            route="auto-promote",
            gate_report_paths=report_paths,
            gate_summaries=summaries,
            root=getattr(args, "root", None),
            out=getattr(args, "delivery_out", None),
        )
        target["delivery_report_paths"] = _append_unique(target.get("delivery_report_paths"), delivery_report_path)
        target["updated_utc"] = utc_now_iso()
        save_catalog(catalog)
        decision["applied"] = True
        decision["new_stage"] = "approved"
        decision["delivery_report_path"] = delivery_report_path

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def command_status(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    summary = {
        stage: sum(1 for record in catalog["assets"] if record.get("stage") == stage)
        for stage in STAGES
    }
    categories = {
        category: sum(1 for record in catalog["assets"] if record.get("category") == category)
        for category in CATEGORIES
    }
    kinds = {}
    for record in catalog["assets"]:
        kind = str(record.get("asset_kind") or "texture")
        kinds[kind] = kinds.get(kind, 0) + 1
    payload = {
        "library_root": str(library_root()),
        "catalog": str(catalog_file()),
        "total_assets": len(catalog["assets"]),
        "by_stage": summary,
        "by_category": categories,
        "by_asset_kind": kinds,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_register_material(args: argparse.Namespace) -> int:
    stage = normalize_stage(args.stage)
    category = normalize_category(args.category)
    role = args.role.strip().lower()
    client = BridgeClient(skill_root(), project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    script = (
        "import json\n"
        "import unreal\n"
        f"info = unreal.UnrealBridgeMaterialLibrary.get_material_info({args.material_path!r})\n"
        "print(json.dumps({\n"
        "  'found': info.found,\n"
        "  'path': info.path,\n"
        "  'material_domain': info.material_domain,\n"
        "  'blend_mode': info.blend_mode,\n"
        "  'shading_models': list(info.shading_models),\n"
        "  'num_expressions': info.num_expressions,\n"
        "}, ensure_ascii=False))\n"
    )
    material_info = client.exec_json(script)
    if not material_info.get("found"):
        raise SystemExit(f"Material asset not found in Unreal: {args.material_path}")
    record = upsert_material_record(
        ue_asset_path=args.material_path,
        stage=stage,
        category=category,
        role=role,
        name=args.name,
        tags=split_csv(args.tags),
        notes=args.notes,
        qa_status=args.qa_status,
        source_kind=args.source_kind,
        source_material_path=args.source_material_path or args.material_path,
        report_paths=args.report_path or [],
        material_info=material_info,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search, register, and promote reusable material texture assets.")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search the reusable material asset library.")
    search.add_argument("--stage", default="approved", choices=STAGES)
    search.add_argument("--category", choices=CATEGORIES)
    search.add_argument("--role")
    search.add_argument("--tag", action="append")
    search.add_argument("--query", action="append")
    search.add_argument("--seamless", action="store_true")
    search.add_argument("--power-of-two", action="store_true")
    search.add_argument("--grid")
    search.add_argument("--max-results", type=int, default=20)
    search.add_argument("--out")
    search.add_argument("--markdown", action="store_true")
    search.set_defaults(func=command_search)

    register = sub.add_parser("register", help="Copy or move an asset into the reusable library and index it.")
    register.add_argument("source")
    register.add_argument("--stage", default="candidates", choices=STAGES)
    register.add_argument("--category", required=True, choices=CATEGORIES)
    register.add_argument("--role", required=True)
    register.add_argument("--name")
    register.add_argument("--tags")
    register.add_argument("--notes", default="")
    register.add_argument("--qa-status", default="candidate")
    register.add_argument("--source-kind", default="generated")
    register.add_argument("--seamless", action="store_true")
    register.add_argument("--grid")
    register.add_argument("--audit-role")
    register.add_argument("--report-path", action="append")
    register.add_argument("--move", action="store_true")
    register.set_defaults(func=command_register)

    register_material = sub.add_parser("register-material", help="Register an Unreal material asset as a candidate/approved/rejected reusable material asset.")
    register_material.add_argument("material_path")
    register_material.add_argument("--stage", default="candidates", choices=STAGES)
    register_material.add_argument("--category", required=True, choices=CATEGORIES)
    register_material.add_argument("--role", required=True)
    register_material.add_argument("--name")
    register_material.add_argument("--tags")
    register_material.add_argument("--notes", default="")
    register_material.add_argument("--qa-status", default="candidate")
    register_material.add_argument("--source-kind", default="rebuilt")
    register_material.add_argument("--source-material-path")
    register_material.add_argument("--report-path", action="append")
    register_material.add_argument("--project")
    register_material.add_argument("--endpoint")
    register_material.add_argument("--timeout", type=int, default=180)
    register_material.set_defaults(func=command_register_material)

    promote = sub.add_parser("promote", help="Move an indexed asset between stages/categories after review.")
    promote.add_argument("asset_id")
    promote.add_argument("--stage", required=True, choices=STAGES)
    promote.add_argument("--category", choices=CATEGORIES)
    promote.add_argument("--tags")
    promote.add_argument("--notes")
    promote.add_argument("--qa-status")
    promote.add_argument("--report-path", action="append")
    promote.add_argument("--root", default="auto")
    promote.add_argument("--delivery-out")
    promote.set_defaults(func=command_promote)

    auto = sub.add_parser("auto-promote", help="Promote a candidate asset when reports and self-review pass.")
    auto.add_argument("asset_id")
    auto.add_argument("--report-path", action="append")
    auto.add_argument("--self-review", choices=["approved", "rejected"], required=True)
    auto.add_argument("--allow-warnings", action="store_true")
    auto.add_argument("--notes")
    auto.add_argument("--apply", action="store_true")
    auto.add_argument("--root", default="auto")
    auto.add_argument("--delivery-out")
    auto.set_defaults(func=command_auto_promote)

    status = sub.add_parser("status", help="Show library counts by stage and category.")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
