from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import (
    _as_list,
    _text,
    evidence_rows,
    load_json,
    package_report_paths,
    resolve_path,
    rows_by_tool,
    severity_counts,
)


TEXTURE_TOOLS = {
    "material_contract",
    "delivery_packager",
    "texture_set_pipeline",
    "texture_asset_report",
    "texture_import_audit",
    "texture_import_fix",
    "texture_import_fix_batch",
    "channel_packer",
    "material_source_provenance",
}


def normalize_key(value: Any) -> str:
    text = _text(value).replace("\\", "/").lower()
    return "".join(ch for ch in text if ch.isalnum() or ch in {"/", "_", ".", "-"})


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def contract_path_from_package(package: dict[str, Any], package_path: Path, explicit: str = "") -> Path | None:
    if explicit:
        return resolve_path(explicit, base=Path.cwd())
    source = package.get("source") if isinstance(package.get("source"), dict) else {}
    if source.get("contract_path"):
        return resolve_path(str(source["contract_path"]), base=package_path.parent)
    return None


def collect_rows(args: argparse.Namespace, package: dict[str, Any], package_path: Path | None, contract_path: Path | None) -> list[dict[str, Any]]:
    paths = package_report_paths(package, package_path=package_path) if package and package_path else []
    if package_path:
        paths.append(package_path)
    if contract_path:
        paths.append(contract_path)
    for values in (
        args.texture_set_report,
        args.texture_asset_report,
        args.import_audit_report,
        args.import_fix_report,
        args.channel_packer_report,
        args.provenance_report,
    ):
        for value in values:
            paths.append(resolve_path(value, base=Path.cwd()))
    return evidence_rows(paths)


def record_key(item: dict[str, Any]) -> str:
    for key in ("asset_path", "texture_path", "file_path", "original_file", "name", "slot"):
        value = item.get(key)
        if value:
            return normalize_key(value)
    return normalize_key(json.dumps(item, sort_keys=True, ensure_ascii=False))


def empty_record(seed: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": _text(seed.get("slot")),
        "role": _text(seed.get("role")),
        "name": _text(seed.get("name")),
        "file_path": _text(first_present(seed, "file_path", "file", "path")),
        "asset_path": _text(first_present(seed, "asset_path", "texture_path", "asset")),
        "source_kind": _text(first_present(seed, "source_kind", "source_type", "provenance_kind")),
        "source_prompt": _text(first_present(seed, "source_prompt", "generation_prompt", "prompt")),
        "original_file": _text(first_present(seed, "original_file", "source_file", "original_path")),
        "source_url": _text(first_present(seed, "source_url", "url")),
        "license": _text(first_present(seed, "license", "rights", "usage_rights")),
        "reuse_notes": _text(first_present(seed, "reuse_notes", "note", "notes")),
        "import_settings": {},
        "fix_records": [],
        "packed_sources": [],
        "asset_reports": [],
        "reports": [],
        "findings": [],
        "sources": [],
    }


def merge_scalar(target: dict[str, Any], key: str, value: Any) -> None:
    if target.get(key) in (None, "", []) and value not in (None, "", []):
        target[key] = value


def merge_record(records: dict[str, dict[str, Any]], seed: dict[str, Any], *, source_tool: str, source_path: str, source_section: str) -> dict[str, Any]:
    key = record_key(seed)
    record = records.setdefault(key, empty_record(seed))
    for field in ("slot", "role", "name", "file_path", "asset_path", "source_kind", "source_prompt", "original_file", "source_url", "license", "reuse_notes"):
        if field in {"file_path", "asset_path"}:
            value = _text(first_present(seed, field, field.replace("_path", ""), "path"))
        elif field == "source_kind":
            value = first_present(seed, "source_kind", "source_type", "provenance_kind")
        else:
            value = first_present(seed, field)
        merge_scalar(record, field, value)
    report_ref = {"tool": source_tool, "path": source_path, "section": source_section}
    if report_ref not in record["reports"]:
        record["reports"].append(report_ref)
    record["sources"].append({"tool": source_tool, "path": source_path, "section": source_section, "raw": seed})
    return record


def load_source_manifest(path_text: str) -> list[dict[str, Any]]:
    if not path_text:
        return []
    payload = load_json(Path(path_text))
    textures = payload.get("textures") if isinstance(payload.get("textures"), (list, dict)) else payload.get("items")
    if isinstance(textures, dict):
        result = []
        for key, value in textures.items():
            if isinstance(value, dict):
                result.append({"slot": key, **value})
            else:
                result.append({"slot": key, "file_path": str(value)})
        return result
    if isinstance(textures, list):
        return [item for item in textures if isinstance(item, dict)]
    return []


def merge_source_manifest(records: dict[str, dict[str, Any]], manifest_rows: list[dict[str, Any]], source_path: str) -> None:
    for item in manifest_rows:
        if item.get("source") and not item.get("source_kind"):
            item = {**item, "source_kind": item.get("source")}
        merge_record(records, item, source_tool="source_manifest", source_path=source_path, source_section="textures")


def collect_contract_textures(records: dict[str, dict[str, Any]], payload: dict[str, Any], *, tool: str, path: str) -> None:
    for section in ("textures", "texture_requirements", "texture_set"):
        for item in _as_list(payload.get(section)):
            if isinstance(item, dict):
                if item.get("source") and not item.get("source_kind"):
                    item = {**item, "source_kind": item.get("source")}
                merge_record(records, item, source_tool=tool, source_path=path, source_section=section)


def collect_texture_set(records: dict[str, dict[str, Any]], payload: dict[str, Any], *, path: str) -> None:
    slots = payload.get("slots") if isinstance(payload.get("slots"), dict) else {}
    for slot, item in slots.items():
        if isinstance(item, dict):
            record = merge_record(records, {"slot": slot, **item}, source_tool="texture_set_pipeline", source_path=path, source_section=f"slots.{slot}")
            expected = item.get("expected_import") if isinstance(item.get("expected_import"), dict) else {}
            if expected and not record["import_settings"]:
                record["import_settings"] = {"expected": expected}
            import_audit = item.get("import_audit") if isinstance(item.get("import_audit"), dict) else {}
            if import_audit:
                record["import_settings"]["audit"] = import_audit
    source_channels = payload.get("source_channels") if isinstance(payload.get("source_channels"), dict) else {}
    for slot, item in source_channels.items():
        if isinstance(item, dict):
            merge_record(records, {"slot": slot, "role": "source_channel", **item}, source_tool="texture_set_pipeline", source_path=path, source_section=f"source_channels.{slot}")
    pack = ((payload.get("fix_plan") or {}).get("pack_rma") if isinstance(payload.get("fix_plan"), dict) else {}) or {}
    if isinstance(pack, dict) and pack.get("output_path"):
        record = merge_record(
            records,
            {
                "slot": "rma",
                "role": "packed",
                "file_path": pack.get("output_path"),
                "source_kind": "channel_packed",
                "reuse_notes": f"Packed via texture_set_pipeline {payload.get('packed_convention') or ''}".strip(),
            },
            source_tool="texture_set_pipeline",
            source_path=path,
            source_section="fix_plan.pack_rma",
        )
        for channel, source in (pack.get("sources") or {}).items():
            if source:
                record["packed_sources"].append({"channel": channel, "source": source, "semantics": (pack.get("channel_semantics") or {}).get(channel)})


def collect_texture_asset_report(records: dict[str, dict[str, Any]], payload: dict[str, Any], *, path: str) -> None:
    for item in payload.get("textures") or []:
        if not isinstance(item, dict):
            continue
        record = merge_record(records, {"file_path": item.get("path"), "role": item.get("role") or payload.get("role"), **item}, source_tool="texture_asset_report", source_path=path, source_section="textures")
        record["asset_reports"].append(item)


def import_settings_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "srgb": item.get("srgb"),
        "compression_settings": item.get("compression_settings"),
        "lod_group": item.get("lod_group"),
        "num_mips": item.get("num_mips"),
        "pixel_format": item.get("pixel_format"),
        "resource_size_bytes": item.get("resource_size_bytes"),
        "width": item.get("width"),
        "height": item.get("height"),
    }


def collect_import_report(records: dict[str, dict[str, Any]], payload: dict[str, Any], *, tool: str, path: str) -> None:
    if tool == "texture_import_audit":
        for item in payload.get("textures") or []:
            if isinstance(item, dict):
                record = merge_record(records, item, source_tool=tool, source_path=path, source_section="textures")
                record["import_settings"]["audit"] = import_settings_from_item(item)
    elif tool == "texture_import_fix":
        after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
        seed = {"asset_path": payload.get("texture_path") or after.get("asset_path"), "role": payload.get("role"), **after}
        record = merge_record(records, seed, source_tool=tool, source_path=path, source_section="after")
        record["fix_records"].append(
            {
                "path": path,
                "apply": payload.get("apply"),
                "planned_changes": payload.get("planned_changes") or {},
                "apply_error": payload.get("apply_error"),
            }
        )
        record["import_settings"]["after_fix"] = import_settings_from_item(after)
    elif tool == "texture_import_fix_batch":
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                collect_import_report(records, item, tool="texture_import_fix", path=path)


def collect_channel_packer(records: dict[str, dict[str, Any]], payload: dict[str, Any], *, path: str) -> None:
    if not payload.get("output_png"):
        return
    record = merge_record(
        records,
        {
            "slot": "packed",
            "role": "packed",
            "file_path": payload.get("output_png"),
            "source_kind": "channel_packed",
        },
        source_tool="channel_packer",
        source_path=path,
        source_section="output_png",
    )
    for channel, source in (payload.get("sources") or {}).items():
        if isinstance(source, dict) and source.get("path"):
            record["packed_sources"].append({"channel": channel.upper(), "source": source.get("path"), "source_channel": source.get("channel")})


def collect_existing_provenance(records: dict[str, dict[str, Any]], payload: dict[str, Any], *, path: str) -> None:
    for item in payload.get("textures") or []:
        if isinstance(item, dict):
            record = merge_record(records, item, source_tool="material_source_provenance", source_path=path, source_section="textures")
            for field in ("import_settings", "fix_records", "packed_sources", "asset_reports"):
                value = item.get(field)
                if value:
                    if isinstance(record[field], list):
                        record[field].extend(value if isinstance(value, list) else [value])
                    elif isinstance(value, dict):
                        record[field].update(value)


def collect_records(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = row.get("payload") or {}
        tool = str(row.get("tool") or "")
        path = str(row.get("path") or "")
        if not isinstance(payload, dict):
            continue
        if tool in {"material_contract", "delivery_packager", "reference_to_material_plan"}:
            collect_contract_textures(records, payload, tool=tool, path=path)
        if tool == "texture_set_pipeline":
            collect_texture_set(records, payload, path=path)
        if tool == "texture_asset_report":
            collect_texture_asset_report(records, payload, path=path)
        if tool in {"texture_import_audit", "texture_import_fix", "texture_import_fix_batch"}:
            collect_import_report(records, payload, tool=tool, path=path)
        if tool == "channel_packer":
            collect_channel_packer(records, payload, path=path)
        if tool == "material_source_provenance":
            collect_existing_provenance(records, payload, path=path)
    return records


def has_provenance(record: dict[str, Any]) -> bool:
    return any(_text(record.get(key)) for key in ("source_kind", "source_prompt", "original_file", "source_url", "license", "reuse_notes"))


def is_generated(record: dict[str, Any]) -> bool:
    text = " ".join(_text(record.get(key)).lower() for key in ("source_kind", "reuse_notes", "source_url"))
    return any(token in text for token in ("generated", "ai", "cm-imagegen", "imagegen", "prompt"))


def local_file_missing(path_text: str) -> bool:
    if not path_text:
        return False
    if path_text.startswith("/Game") or "://" in path_text:
        return False
    path = Path(path_text)
    return path.suffix != "" and not path.exists()


def evaluate_record(record: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not (record.get("name") or record.get("file_path") or record.get("asset_path")):
        add("error", "missing_identifier", "Texture record has no name, file_path, or asset_path.")
    if not record.get("slot") and not record.get("role"):
        add("warning", "missing_slot_or_role", "Texture provenance lacks a slot or role.")
    if not has_provenance(record):
        add("error" if args.require_complete else "warning", "missing_source_provenance", "No source kind, prompt, original file, URL, license, or reuse notes are recorded.")
    if is_generated(record) and not record.get("source_prompt"):
        add("error" if args.require_complete else "warning", "generated_prompt_missing", "Generated texture lacks its source prompt.")
    if args.require_license and not record.get("license"):
        add("error" if args.require_complete else "warning", "license_missing", "Texture lacks license/usage-rights metadata.")
    if record.get("asset_path") and not record.get("import_settings"):
        add("error" if args.require_complete else "warning", "import_settings_missing", "UE asset texture lacks import settings evidence.")
    if record.get("source_kind") == "channel_packed" and not record.get("packed_sources"):
        add("error" if args.require_complete else "warning", "packed_sources_missing", "Packed texture lacks source-channel provenance.")
    if local_file_missing(_text(record.get("file_path"))):
        add("warning", "source_file_missing_on_disk", f"File path does not exist now: {record.get('file_path')}")
    return findings


def finalize_records(records: dict[str, dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    result = []
    for key, record in sorted(records.items()):
        record["id"] = key
        record["findings"] = evaluate_record(record, args)
        counts = severity_counts(record["findings"])
        record["reuse_eligibility"] = {
            "ready": counts["errors"] == 0 and counts["warnings"] == 0,
            "errors": counts["errors"],
            "warnings": counts["warnings"],
            "has_provenance": has_provenance(record),
            "has_import_settings": bool(record.get("import_settings")) or not record.get("asset_path"),
        }
        result.append(record)
    return result


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package_path = resolve_path(args.package, base=Path.cwd()) if args.package else None
    package = load_json(package_path) if package_path else {}
    contract_path = contract_path_from_package(package, package_path or Path.cwd(), args.contract)
    rows = collect_rows(args, package, package_path, contract_path)
    records = collect_records(rows)
    if args.source_manifest:
        merge_source_manifest(records, load_source_manifest(args.source_manifest), str(resolve_path(args.source_manifest, base=Path.cwd())))
    textures = finalize_records(records, args)
    all_findings: list[dict[str, Any]] = []
    for texture in textures:
        label = texture.get("asset_path") or texture.get("file_path") or texture.get("name") or texture.get("slot")
        for finding in texture.get("findings") or []:
            all_findings.append({"texture": label, **finding})
    counts = severity_counts(all_findings)
    passed = counts["errors"] == 0 and not (args.fail_on_warning and counts["warnings"])
    effect = args.effect or package.get("effect") or ""
    layer = args.layer or package.get("layer") or ""
    report = {
        "tool": "material_source_provenance",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "material_path": args.material_path or package.get("material_path") or "",
        "textures": textures,
        "summary": {
            **counts,
            "texture_count": len(textures),
            "reuse_ready_count": sum(1 for item in textures if (item.get("reuse_eligibility") or {}).get("ready")),
        },
        "gate": {
            "passed": passed,
            "provenance_complete": counts["errors"] == 0 and counts["warnings"] == 0,
            "requires_triage": bool(counts["errors"] or counts["warnings"]),
            "require_complete": bool(args.require_complete),
        },
        "evidence": {
            "package": str(package_path or ""),
            "contract": str(contract_path or ""),
            "source_manifest": str(resolve_path(args.source_manifest, base=Path.cwd())) if args.source_manifest else "",
            "texture_set_reports": [row["path"] for row in rows_by_tool(rows, "texture_set_pipeline")],
            "texture_asset_reports": [row["path"] for row in rows_by_tool(rows, "texture_asset_report")],
            "import_reports": [row["path"] for row in rows if row.get("tool") in {"texture_import_audit", "texture_import_fix", "texture_import_fix_batch"}],
            "channel_packer_reports": [row["path"] for row in rows_by_tool(rows, "channel_packer")],
            "all_reports": [row["path"] for row in rows],
        },
        "findings": all_findings,
        "next_actions": next_actions(all_findings),
    }
    stem = slugify(effect or layer or args.material_path or "material-source")
    out = Path(args.out) if args.out else default_report_path(ctx, "source-provenance", stem, "material-source-provenance", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {str(item.get("rule") or "") for item in findings if item.get("severity") in {"error", "warning"}}
    actions: list[str] = []
    if "missing_source_provenance" in rules:
        actions.append("Add source_kind, original_file/source_url, prompt, license, or reuse notes for every texture.")
    if "generated_prompt_missing" in rules:
        actions.append("Record the image-generation prompt and provider route for generated textures.")
    if "import_settings_missing" in rules:
        actions.append("Attach texture_import_audit.py or texture_import_fix.py evidence for UE texture assets.")
    if "packed_sources_missing" in rules:
        actions.append("Record source-channel paths and channel semantics for packed RMA/ORM/Mask textures.")
    if "license_missing" in rules:
        actions.append("Record license/usage-rights metadata before marking the texture reusable.")
    if not actions:
        actions.append("Texture provenance is complete enough for reuse review.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    gate = report.get("gate") or {}
    lines = [
        f"# Material Source Provenance: {report.get('effect') or report.get('material_path')}",
        "",
        f"- Passed: `{gate.get('passed')}`",
        f"- Provenance complete: `{gate.get('provenance_complete')}`",
        f"- Textures: `{summary.get('texture_count')}`",
        f"- Reuse ready: `{summary.get('reuse_ready_count')}`",
        f"- Errors: `{summary.get('errors', 0)}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Textures",
        "",
        "| Texture | Slot | Role | Source | Prompt | Import | Packed Sources | Ready |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for item in report.get("textures") or []:
        label = item.get("asset_path") or item.get("file_path") or item.get("name") or item.get("slot")
        lines.append(
            f"| `{label}` | `{item.get('slot') or ''}` | `{item.get('role') or ''}` | `{item.get('source_kind') or 'missing'}` | "
            f"`{bool(item.get('source_prompt'))}` | `{bool(item.get('import_settings'))}` | {len(item.get('packed_sources') or [])} | "
            f"`{(item.get('reuse_eligibility') or {}).get('ready')}` |"
        )
    lines.extend(["", "## Findings", ""])
    if report.get("findings"):
        for finding in report["findings"]:
            lines.append(f"- [{finding.get('severity')}] `{finding.get('texture')}` `{finding.get('rule')}` {finding.get('message')}")
    else:
        lines.append("- No provenance findings.")
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
    if args.require_complete and not (report.get("gate") or {}).get("provenance_complete"):
        print(f"Material source provenance is incomplete: {out}", file=sys.stderr)
        return 2
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a texture provenance manifest for material delivery: sources, prompts, originals, import settings, fix records, packed-channel origins, and reuse readiness.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--package", default="", help="delivery_packager.py JSON report.")
    parser.add_argument("--contract", default="", help="material_contract.py JSON report.")
    parser.add_argument("--source-manifest", default="", help="Optional JSON manifest with textures/source metadata.")
    parser.add_argument("--texture-set-report", action="append", default=[])
    parser.add_argument("--texture-asset-report", action="append", default=[])
    parser.add_argument("--import-audit-report", action="append", default=[])
    parser.add_argument("--import-fix-report", action="append", default=[])
    parser.add_argument("--channel-packer-report", action="append", default=[])
    parser.add_argument("--provenance-report", action="append", default=[])
    parser.add_argument("--require-license", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (
        args.package
        or args.contract
        or args.source_manifest
        or args.texture_set_report
        or args.texture_asset_report
        or args.import_audit_report
        or args.import_fix_report
        or args.channel_packer_report
        or args.provenance_report
    ):
        parser.error("Provide package/contract, a source manifest, or at least one texture/provenance report.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
