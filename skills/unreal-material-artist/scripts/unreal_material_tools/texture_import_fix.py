from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient, BridgeError
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .texture_import_audit import analyze_texture, build_ue_script, parse_grid


ROLE_CHOICES = ["albedo", "emissive", "mask", "packed", "normal", "flow", "ui", "flipbook", "atlas", "sprite"]
FLAVOR_CHOICES = ["color", "mask", "data"]


def role_profile(role: str, flavor: str) -> dict[str, Any]:
    base_profiles = {
        "albedo": {
            "srgb": True,
            "compression_settings": "TC_DEFAULT",
            "lod_group": "TEXTUREGROUP_WORLD",
            "never_stream": False,
        },
        "emissive": {
            "srgb": True,
            "compression_settings": "TC_DEFAULT",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
        "mask": {
            "srgb": False,
            "compression_settings": "TC_MASKS",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
        "packed": {
            "srgb": False,
            "compression_settings": "TC_MASKS",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
        "normal": {
            "srgb": False,
            "compression_settings": "TC_NORMALMAP",
            "lod_group": "TEXTUREGROUP_WORLD_NORMAL_MAP",
            "never_stream": False,
        },
        "flow": {
            "srgb": False,
            "compression_settings": "TC_VECTOR_DISPLACEMENTMAP",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
        "ui": {
            "srgb": True,
            "compression_settings": "TC_DEFAULT",
            "lod_group": "TEXTUREGROUP_UI",
            "never_stream": True,
        },
    }
    if role in base_profiles:
        return base_profiles[role]

    flavor_profiles = {
        "color": {
            "srgb": True,
            "compression_settings": "TC_DEFAULT",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
        "mask": {
            "srgb": False,
            "compression_settings": "TC_MASKS",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
        "data": {
            "srgb": False,
            "compression_settings": "TC_VECTOR_DISPLACEMENTMAP",
            "lod_group": "TEXTUREGROUP_EFFECTS",
            "never_stream": False,
        },
    }
    return flavor_profiles[flavor]


def diff_profile(info: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    current = {
        "srgb": bool(info.get("srgb")),
        "compression_settings": str(info.get("compression_settings") or ""),
        "lod_group": str(info.get("lod_group") or ""),
        "never_stream": bool(info.get("never_stream")),
    }
    changes: dict[str, Any] = {}
    for key, value in profile.items():
        if current.get(key) != value:
            changes[key] = value
    return changes


def build_apply_script(texture_path: str, changes: dict[str, Any]) -> str:
    payload = json.dumps(changes, ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import json
        import unreal

        TR = unreal.UnrealBridgeToolsetRegistryLibrary
        asset_path = {texture_path!r}
        changes = json.loads({payload!r})
        tex = unreal.EditorAssetLibrary.load_asset(asset_path)
        if not tex:
            raise RuntimeError(f"Could not load texture: {{asset_path}}")

        def enum_value(enum_type, name):
            if hasattr(enum_type, name):
                return getattr(enum_type, name)
            for attr in dir(enum_type):
                if attr.upper() == str(name).upper():
                    return getattr(enum_type, attr)
            raise RuntimeError(f"Enum value {{name}} not found on {{enum_type}}")

        if "srgb" in changes:
            tex.set_editor_property("srgb", bool(changes["srgb"]))
        if "never_stream" in changes:
            tex.set_editor_property("never_stream", bool(changes["never_stream"]))
        if "compression_settings" in changes:
            tex.set_editor_property("compression_settings", enum_value(unreal.TextureCompressionSettings, changes["compression_settings"]))
        if "lod_group" in changes:
            tex.set_editor_property("lod_group", enum_value(unreal.TextureGroup, changes["lod_group"]))

        tex.set_editor_property("defer_compression", False)
        save = TR.execute_qualified_tool(
            'toolset_registry.toolsets.core.asset.AssetTools.save_assets',
            json.dumps({{'asset_paths': [asset_path]}}, ensure_ascii=False),
            True,
        )
        print(json.dumps({{"success": bool(save.success), "save_error": save.error, "changes": changes}}, ensure_ascii=False))
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    if report.get("tool") == "texture_import_fix_batch":
        lines = [
            f"# Texture Import Fix Batch: {report['effect']}",
            "",
            f"- Apply mode: `{report['apply']}`",
            f"- Item count: `{len(report['items'])}`",
            f"- Error count: `{report['summary']['errors']}`",
            f"- Warning count: `{report['summary']['warnings']}`",
            "",
        ]
        for item in report["items"]:
            lines.extend(
                [
                    f"## {item['texture_path']}",
                    "",
                    f"- Role: `{item['role']}`",
                    f"- Flavor: `{item['flavor']}`",
                    f"- Apply error: `{item.get('apply_error')}`",
                    f"- Planned changes: `{len(item.get('planned_changes') or {})}`",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    lines = [
        f"# Texture Import Fix: {report['texture_path']}",
        "",
        f"- Role: `{report['role']}`",
        f"- Flavor: `{report['flavor']}`",
        f"- Apply mode: `{report['apply']}`",
        "",
        "## Planned Changes",
        "",
    ]
    changes = report.get("planned_changes") or {}
    if changes:
        for key, value in changes.items():
            lines.append(f"- `{key}` -> `{value}`")
    else:
        lines.append("- No property changes needed.")
    lines.extend(["", "## Findings After Fix", ""])
    findings = report["after"].get("findings") or []
    if findings:
        for finding in findings:
            lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
    else:
        lines.append("- No first-pass findings.")
    return "\n".join(lines).rstrip() + "\n"


def run_fix(
    *,
    client: BridgeClient,
    texture_path: str,
    role: str,
    flavor: str,
    grid_text: str | None,
    max_dimension: int,
    max_resource_bytes: int | None,
    apply: bool,
) -> dict[str, Any]:
    before_raw = client.exec_json(build_ue_script([texture_path]))
    before_info = before_raw["textures"][0]
    grid = parse_grid(grid_text)
    before = analyze_texture(before_info, role, grid, max_dimension, max_resource_bytes)
    profile = role_profile(role, flavor)
    changes = diff_profile(before_info, profile)
    apply_result = None
    apply_error = None
    if apply and changes:
        try:
            apply_result = client.exec_json(build_apply_script(texture_path, changes))
        except BridgeError as exc:
            apply_error = str(exc)

    after_raw = client.exec_json(build_ue_script([texture_path]))
    after_info = after_raw["textures"][0]
    after = analyze_texture(after_info, role, grid, max_dimension, max_resource_bytes)
    return {
        "tool": "texture_import_fix",
        "texture_path": texture_path,
        "role": role,
        "flavor": flavor,
        "apply": apply,
        "target_profile": profile,
        "planned_changes": changes,
        "apply_result": apply_result,
        "apply_error": apply_error,
        "before": before,
        "after": after,
    }


def load_batch_spec(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()

    if args.batch_spec:
        spec = load_batch_spec(args.batch_spec)
        defaults = spec.get("defaults") or {}
        items = spec.get("items") or []
        if not items:
            raise SystemExit("Batch spec must include a non-empty 'items' array.")

        reports: list[dict[str, Any]] = []
        item_errors = 0
        item_warnings = 0
        for item in items:
            texture_path = item.get("texture_path")
            role = item.get("role") or defaults.get("role") or args.role
            if not texture_path or not role:
                reports.append(
                    {
                        "tool": "texture_import_fix",
                        "texture_path": texture_path or "",
                        "role": role or "",
                        "flavor": item.get("flavor") or defaults.get("flavor") or args.flavor,
                        "apply": args.apply,
                        "target_profile": {},
                        "planned_changes": {},
                        "apply_result": None,
                        "apply_error": "Batch item is missing texture_path or role.",
                        "before": {"findings": []},
                        "after": {"findings": []},
                    }
                )
                item_errors += 1
                continue

            report = run_fix(
                client=client,
                texture_path=texture_path,
                role=role,
                flavor=item.get("flavor") or defaults.get("flavor") or args.flavor,
                grid_text=item.get("grid") or defaults.get("grid") or args.grid,
                max_dimension=int(item.get("max_dimension") or defaults.get("max_dimension") or args.max_dimension),
                max_resource_bytes=item.get("max_resource_bytes", defaults.get("max_resource_bytes", args.max_resource_bytes)),
                apply=args.apply,
            )
            reports.append(report)
            if report.get("apply_error"):
                item_errors += 1
            item_warnings += sum(
                1
                for finding in report["after"].get("findings") or []
                if str(finding.get("severity") or "").lower() == "warning"
            )

        effect = slugify(args.effect or spec.get("effect") or "texture-fix-batch")
        batch_report = {
            "tool": "texture_import_fix_batch",
            "effect": effect,
            "apply": args.apply,
            "items": reports,
            "summary": {
                "errors": item_errors,
                "warnings": item_warnings,
            },
        }
        out = Path(args.out) if args.out else default_report_path(ctx, "import-fixes", effect, "texture-import-fix-batch", ".json")
        save_json(out, batch_report)
        if args.markdown:
            write_text(out.with_suffix(".md"), render_markdown(batch_report))
        print(out)
        return 1 if item_errors else 0

    if not args.texture_path or not args.role:
        raise SystemExit("Single-asset mode requires texture_path and --role.")

    report = run_fix(
        client=client,
        texture_path=args.texture_path,
        role=args.role,
        flavor=args.flavor,
        grid_text=args.grid,
        max_dimension=args.max_dimension,
        max_resource_bytes=args.max_resource_bytes,
        apply=args.apply,
    )
    effect = slugify(args.effect or args.role or "texture-fix")
    stem = slugify(args.texture_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "import-fixes", effect, f"texture-import-fix-{stem}", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply safe role-based Unreal texture import fixes.")
    parser.add_argument("texture_path", nargs="?")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--role", choices=ROLE_CHOICES)
    parser.add_argument("--flavor", choices=FLAVOR_CHOICES, default="color")
    parser.add_argument("--batch-spec")
    parser.add_argument("--grid")
    parser.add_argument("--max-dimension", type=int, default=2048)
    parser.add_argument("--max-resource-bytes", type=int)
    parser.add_argument("--apply", action="store_true")
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
