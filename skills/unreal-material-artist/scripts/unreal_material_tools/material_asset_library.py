from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .core import load_json, save_json, slugify, utc_now_iso, write_text
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
    "decal",
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
    "decal": "albedo",
    "other": "sprite",
}


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
    return load_json(
        catalog_file(),
        {
            "version": 1,
            "updated_utc": utc_now_iso(),
            "stages": list(STAGES),
            "categories": list(CATEGORIES),
            "assets": [],
        },
    )


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


def stage_abs_path(record: dict[str, Any]) -> Path:
    return skill_root() / record["library_relpath"]


def move_record_asset(record: dict[str, Any], new_stage: str, new_category: str) -> None:
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
        lines.extend(
            [
                f"## {record['name']}",
                "",
                f"- ID: `{record['id']}`",
                f"- Stage: `{record['stage']}`",
                f"- Category: `{record['category']}`",
                f"- Role: `{record['role']}`",
                f"- Path: `{record['library_relpath']}`",
                f"- Size: `{record.get('width')}x{record.get('height')}`",
                f"- POT: `{record.get('power_of_two')}`",
                f"- Tags: {', '.join(record.get('tags') or []) or 'none'}",
            ]
        )
        if record.get("notes"):
            lines.append(f"- Notes: {record['notes']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
    target["updated_utc"] = utc_now_iso()
    save_catalog(catalog)
    print(json.dumps(target, ensure_ascii=False, indent=2))
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
        target["updated_utc"] = utc_now_iso()
        save_catalog(catalog)
        decision["applied"] = True
        decision["new_stage"] = "approved"

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
    payload = {
        "library_root": str(library_root()),
        "catalog": str(catalog_file()),
        "total_assets": len(catalog["assets"]),
        "by_stage": summary,
        "by_category": categories,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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

    promote = sub.add_parser("promote", help="Move an indexed asset between stages/categories after review.")
    promote.add_argument("asset_id")
    promote.add_argument("--stage", required=True, choices=STAGES)
    promote.add_argument("--category", choices=CATEGORIES)
    promote.add_argument("--tags")
    promote.add_argument("--notes")
    promote.add_argument("--qa-status")
    promote.add_argument("--report-path", action="append")
    promote.set_defaults(func=command_promote)

    auto = sub.add_parser("auto-promote", help="Promote a candidate asset when reports and self-review pass.")
    auto.add_argument("asset_id")
    auto.add_argument("--report-path", action="append")
    auto.add_argument("--self-review", choices=["approved", "rejected"], required=True)
    auto.add_argument("--allow-warnings", action="store_true")
    auto.add_argument("--notes")
    auto.add_argument("--apply", action="store_true")
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
