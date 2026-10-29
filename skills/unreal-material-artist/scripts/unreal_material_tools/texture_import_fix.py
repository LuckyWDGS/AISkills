"""Apply safe role-based Unreal texture import fixes through Epic's built-in MCP.

Plan, validate, then run: the texture audit's live reads become a reviewable
JSONL plan for ``builtin_mcp.py batch``. Each texture gets one
``ObjectTools.set_properties`` step with a readback ``expect`` and a save of that
package only. Without ``--apply`` nothing is written; ``--from-plan`` runs a
previously reviewed plan. Reports keep the ``texture_import_fix`` /
``texture_import_fix_batch`` shape that provenance, texture-set and health tools read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, builtin_mcp, connect
from .texture_import_audit import analyze_texture, asset_package_path, collect, parse_grid


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "texture_import_fix/2"
ROLE_CHOICES = ["albedo", "emissive", "mask", "packed", "normal", "flow", "ui", "flipbook", "atlas", "sprite"]
FLAVOR_CHOICES = ["color", "mask", "data"]
# Report field -> UTexture property name as ObjectTools reads and writes it.
PROPERTY_NAMES = {"srgb": "sRGB", "compression_settings": "compressionSettings",
                  "lod_group": "lODGroup", "never_stream": "neverStream"}

ROLE_PROFILES = {
    "albedo": {"srgb": True, "compression_settings": "TC_Default", "lod_group": "TEXTUREGROUP_World", "never_stream": False},
    "emissive": {"srgb": True, "compression_settings": "TC_Default", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
    "mask": {"srgb": False, "compression_settings": "TC_Masks", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
    "packed": {"srgb": False, "compression_settings": "TC_Masks", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
    "normal": {"srgb": False, "compression_settings": "TC_Normalmap", "lod_group": "TEXTUREGROUP_WorldNormalMap", "never_stream": False},
    "flow": {"srgb": False, "compression_settings": "TC_VectorDisplacementmap", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
    "ui": {"srgb": True, "compression_settings": "TC_Default", "lod_group": "TEXTUREGROUP_UI", "never_stream": True},
}
# Roles whose data type depends on content (flipbook/atlas/sprite) take the flavor profile.
FLAVOR_PROFILES = {
    "color": {"srgb": True, "compression_settings": "TC_Default", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
    "mask": {"srgb": False, "compression_settings": "TC_Masks", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
    "data": {"srgb": False, "compression_settings": "TC_VectorDisplacementmap", "lod_group": "TEXTUREGROUP_Effects", "never_stream": False},
}


def role_profile(role: str, flavor: str) -> dict[str, Any]:
    return dict(ROLE_PROFILES.get(role) or FLAVOR_PROFILES[flavor])


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    # Older specs spell enums Python-style (TC_MASKS, TEXTUREGROUP_WORLD_NORMAL_MAP).
    return str(left).replace("_", "").lower() == str(right).replace("_", "").lower()


def diff_profile(info: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in profile.items() if not _same(info.get(key), value)}


def object_ref(path: str) -> dict[str, str]:
    package = asset_package_path(path)
    return {"refPath": f"{package}.{package.rsplit('/', 1)[-1]}"}


def build_plan(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batch steps for every item with planned changes. Pure: no editor access."""
    steps: list[dict[str, Any]] = []
    for item in items:
        changes = item.get("planned_changes") or {}
        if not changes:
            continue
        package = asset_package_path(item["texture_path"])
        leaf = package.rsplit("/", 1)[-1]
        values = {PROPERTY_NAMES[key]: value for key, value in changes.items()}
        steps.append({
            "label": f"{leaf}: import settings", "texture": package, "kind": "set",
            "toolset": "ObjectTools", "tool": "set_properties",
            "args": {"instance": object_ref(package), "values": json.dumps(values)},
            "readback": {"toolset": "ObjectTools", "tool": "get_properties",
                         "args": {"instance": object_ref(package), "properties": sorted(values)}},
            "expect": values,
        })
        steps.append({
            "label": f"{leaf}: save", "texture": package, "kind": "save",
            "toolset": "AssetTools", "tool": "save_assets", "args": {"asset_paths": [package]},
            "readback": {"toolset": "AssetTools", "tool": "is_dirty", "args": {"asset_path": package}},
            "expect": False,
        })
    return steps


def write_plan(path: Path, steps: list[dict[str, Any]]) -> None:
    lines = ["# texture_import_fix plan: one builtin_mcp batch step per line; review before --apply"]
    lines += [json.dumps(step, ensure_ascii=False) for step in steps]
    write_text(path, "\n".join(lines) + "\n")


def resolve_items(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str, bool]:
    """(items, effect, batch_mode) from --batch-spec or the single-texture arguments."""
    if args.batch_spec:
        spec = json.loads(Path(args.batch_spec).read_text(encoding="utf-8-sig"))
        defaults = spec.get("defaults") or {}
        if not spec.get("items"):
            raise SystemExit("Batch spec must include a non-empty 'items' array.")
        items = [{
            "texture_path": item.get("texture_path") or "",
            "role": item.get("role") or defaults.get("role") or args.role or "",
            "flavor": item.get("flavor") or defaults.get("flavor") or args.flavor,
            "grid": item.get("grid") or defaults.get("grid") or args.grid,
            "max_dimension": int(item.get("max_dimension") or defaults.get("max_dimension") or args.max_dimension),
            "max_resource_bytes": item.get("max_resource_bytes", defaults.get("max_resource_bytes", args.max_resource_bytes)),
        } for item in spec["items"]]
        return items, slugify(args.effect or spec.get("effect") or "texture-fix-batch"), True
    if not args.texture_path or not args.role:
        raise SystemExit("Single-asset mode requires texture_path and --role.")
    item = {"texture_path": args.texture_path, "role": args.role, "flavor": args.flavor, "grid": args.grid,
            "max_dimension": args.max_dimension, "max_resource_bytes": args.max_resource_bytes}
    return [item], slugify(args.effect or args.role or "texture-fix"), False


def item_reports(items: list[dict[str, Any]], before: dict[str, dict[str, Any]],
                 after: dict[str, dict[str, Any]], batch: dict[str, Any] | None, apply: bool) -> list[dict[str, Any]]:
    errors = {}
    for row in (batch or {}).get("results", []):
        if row.get("status") not in ("ok", None):
            errors.setdefault(row.get("label", "").split(":", 1)[0], row.get("error") or row["status"])
    reports = []
    for item in items:
        path = item["texture_path"]
        if not path or not item["role"]:
            reports.append({"tool": "texture_import_fix", "texture_path": path, "role": item["role"], "flavor": item["flavor"],
                            "apply": apply, "target_profile": {}, "planned_changes": {}, "apply_result": None,
                            "apply_error": "Batch item is missing texture_path or role.",
                            "before": {"findings": []}, "after": {"findings": []}})
            continue
        grid = parse_grid(item["grid"])
        package = asset_package_path(path)
        before_row = analyze_texture(dict(before[package]), item["role"], grid, item["max_dimension"], item["max_resource_bytes"])
        after_info = after.get(package, before[package])
        leaf = package.rsplit("/", 1)[-1]
        reports.append({
            "tool": "texture_import_fix",
            "schema_version": SCHEMA_VERSION,
            "texture_path": path,
            "role": item["role"],
            "flavor": item["flavor"],
            "apply": apply,
            "target_profile": item["target_profile"],
            "planned_changes": item["planned_changes"],
            "apply_result": {"route": "epic-mcp batch"} if apply and item["planned_changes"] and leaf not in errors else None,
            "apply_error": errors.get(leaf) if apply else None,
            "before": before_row,
            "after": analyze_texture(dict(after_info), item["role"], grid, item["max_dimension"], item["max_resource_bytes"]),
        })
    return reports


def render_markdown(report: dict[str, Any]) -> str:
    if report.get("tool") == "texture_import_fix_batch":
        lines = [
            f"# Texture Import Fix Batch: {report['effect']}",
            "",
            f"- Status: `{report['status']}`",
            f"- Plan: `{report['plan']}`",
            f"- Item count: `{len(report['items'])}`",
            f"- Error count: `{report['summary']['errors']}`",
            f"- Warning count: `{report['summary']['warnings']}`",
            "",
        ]
        lines += [f"- Problem: {problem}" for problem in report.get("problems") or []]
        for item in report["items"]:
            lines.extend([
                f"## {item['texture_path']}", "",
                f"- Role: `{item['role']}`",
                f"- Flavor: `{item['flavor']}`",
                f"- Apply error: `{item.get('apply_error')}`",
                f"- Planned changes: `{json.dumps(item.get('planned_changes') or {})}`",
                "",
            ])
        return "\n".join(lines).rstrip() + "\n"

    lines = [
        f"# Texture Import Fix: {report['texture_path']}",
        "",
        f"- Role: `{report['role']}`",
        f"- Flavor: `{report['flavor']}`",
        f"- Status: `{report.get('status')}`",
        "",
        "## Planned Changes",
        "",
    ]
    changes = report.get("planned_changes") or {}
    lines += [f"- `{key}` -> `{value}`" for key, value in changes.items()] or ["- No property changes needed."]
    lines.extend(["", "## Findings After Fix", ""])
    findings = report["after"].get("findings") or []
    lines += [f"- [{f['severity']}] `{f['rule']}` {f['message']}" for f in findings] or ["- No first-pass findings."]
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    module = builtin_mcp(ctx.skill_root)
    items, effect, batch_mode = resolve_items(args)
    if batch_mode:
        out = Path(args.out) if args.out else default_report_path(ctx, "import-fixes", effect, "texture-import-fix-batch", ".json")
    else:
        out = Path(args.out) if args.out else default_report_path(
            ctx, "import-fixes", effect, f"texture-import-fix-{slugify(items[0]['texture_path'])}", ".json")
    plan_path = Path(args.from_plan) if args.from_plan else out.with_name(out.stem + "-plan.jsonl")
    paths = [item["texture_path"] for item in items if item["texture_path"] and item["role"]]
    before = {row["asset_path"]: row for row in collect(ctx.skill_root, paths, url=args.mcp_url,
                                                        timeout=args.timeout, project=args.project)} if paths else {}
    problems: list[str] = []
    for item in items:
        info = before.get(asset_package_path(item["texture_path"])) if item["texture_path"] else None
        item["target_profile"] = role_profile(item["role"], item["flavor"]) if item["role"] else {}
        item["planned_changes"] = diff_profile(info, item["target_profile"]) if info and info.get("found") else {}
        if item["texture_path"] and info is not None and not info.get("found"):
            problems.append(f"{item['texture_path']}: texture not found")

    batch = None
    after: dict[str, dict[str, Any]] = {}
    client = connect(ctx.skill_root, url=args.mcp_url, timeout=args.timeout, project=args.project)
    try:
        if not args.from_plan:
            write_plan(plan_path, build_plan(items))
        entries = module.load_batch(plan_path)
        if client.pie_running():
            problems.append("Play-In-Editor is running; stop PIE and run again.")
        if problems:
            status = "blocked"
        elif not entries:
            status = "no_changes"
        else:
            validation = module.run_batch(client, entries, dry_run=True)
            problems = validation["problems"]
            if problems:
                status = "blocked"
            elif not args.apply:
                status = "planned"
            else:
                batch = module.run_batch(client, entries)
                status = "applied" if batch["ok"] else "failed"
                if batch.get("left_dirty"):
                    problems.append(f"left unsaved after the batch: {', '.join(batch['left_dirty'])}")
                    status = "applied_with_side_effects" if batch["ok"] else status
    finally:
        client.close()
    if batch:
        after = {row["asset_path"]: row for row in collect(ctx.skill_root, paths, url=args.mcp_url,
                                                           timeout=args.timeout, project=args.project)}

    reports = item_reports(items, before, after, batch, bool(args.apply))
    common = {"status": status, "plan": str(plan_path.resolve()), "problems": problems,
              "transport": "epic-mcp batch", "batch": batch}
    if batch_mode:
        report = {
            "tool": "texture_import_fix_batch",
            "schema_version": SCHEMA_VERSION,
            "effect": effect,
            "apply": bool(args.apply),
            **common,
            "items": reports,
            "summary": {
                "errors": sum(1 for item in reports if item.get("apply_error")) + len(problems),
                "warnings": sum(1 for item in reports for finding in item["after"].get("findings") or []
                                if str(finding.get("severity") or "").lower() == "warning"),
            },
        }
    else:
        report = {**reports[0], **common}
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0 if status in ("planned", "applied", "no_changes") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan, validate and (with --apply) fix Unreal texture import settings through Epic MCP.")
    parser.add_argument("texture_path", nargs="?")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project", help="Refuse to run unless the MCP endpoint is served by this project.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--role", choices=ROLE_CHOICES)
    parser.add_argument("--flavor", choices=FLAVOR_CHOICES, default="color")
    parser.add_argument("--batch-spec")
    parser.add_argument("--from-plan", help="Run a previously generated, reviewed JSONL plan (still needs the spec/role for reports).")
    parser.add_argument("--grid")
    parser.add_argument("--max-dimension", type=int, default=2048)
    parser.add_argument("--max-resource-bytes", type=int)
    parser.add_argument("--apply", action="store_true", help="Run the plan; without it nothing is written.")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
