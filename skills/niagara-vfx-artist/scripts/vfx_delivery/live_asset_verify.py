from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, normalize_cli_global_args_no_subcommand, resolve_root_context, save_json, write_text


def build_ue_script(texture_asset_path: str, material_path: str, renderer_path: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        MAT = unreal.UnrealBridgeMaterialLibrary
        PROP = unreal.UnrealBridgePropertyLibrary

        def load_exists(path):
            try:
                return bool(EAL.does_asset_exist(path))
            except Exception:
                return False

        payload = {{
            "texture_asset_path": {texture_asset_path!r},
            "material_path": {material_path!r},
            "renderer_path": {renderer_path!r},
            "texture_asset_exists": load_exists({texture_asset_path!r}) if {bool(texture_asset_path)!r} else False,
            "material_exists": load_exists({material_path!r}) if {bool(material_path)!r} else False,
            "renderer_exists": False,
            "material_texture_parameters": [],
            "material_effective_texture_parameters": [],
            "renderer_material_path": "",
        }}

        if {bool(renderer_path)!r}:
            try:
                text, ok = PROP.get_u_property_as_export_text({renderer_path!r}, "Material")
                payload["renderer_exists"] = bool(ok)
                payload["renderer_material_path"] = text
            except Exception:
                pass

        if payload["material_exists"]:
            try:
                info = MAT.get_material_instance_parameters({material_path!r})
                for p in info.parameters:
                    if p.param_type == "Texture":
                        payload["material_texture_parameters"].append({{
                            "name": p.name,
                            "value": p.value,
                            "matches_target": bool({texture_asset_path!r}) and str(p.value).split(".")[0] == {texture_asset_path!r},
                        }})
            except Exception:
                pass
            try:
                mat_info = MAT.get_material_info({material_path!r})
                for p in mat_info.texture_parameters:
                    payload["material_effective_texture_parameters"].append({{
                        "name": p.name,
                        "value": p.value,
                        "matches_target": bool({texture_asset_path!r}) and str(p.value).split(".")[0] == {texture_asset_path!r},
                    }})
            except Exception:
                pass

        payload["material_references_target_texture"] = any(item["matches_target"] for item in payload["material_texture_parameters"]) or any(
            item["matches_target"] for item in payload["material_effective_texture_parameters"]
        )
        payload["renderer_references_material"] = bool(payload["renderer_material_path"]) and {material_path!r} in payload["renderer_material_path"]
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Live Asset Verify: {report.get('texture_asset_path') or report.get('local_file')}",
        "",
        f"- Source policy: `{report.get('source_policy', 'required')}`",
        f"- Verification passed: `{report.get('verification_passed')}`",
        f"- Local file exists: `{report.get('local_file_exists')}`",
        f"- Texture asset exists: `{report.get('texture_asset_exists')}`",
        f"- Material exists: `{report.get('material_exists')}`",
        f"- Renderer exists: `{report.get('renderer_exists')}`",
        f"- Material references target texture: `{report.get('material_references_target_texture')}`",
        f"- Renderer references material: `{report.get('renderer_references_material')}`",
        "",
        "## Material Texture Parameters",
        "",
    ]
    params = report.get("material_texture_parameters", [])
    if not params:
        lines.append("- none")
    else:
        for item in params:
            lines.append(f"- `{item['name']}` -> `{item['value']}` match=`{item['matches_target']}`")
    lines.extend(["", "## Effective Material Texture Parameters", ""])
    effective = report.get("material_effective_texture_parameters", [])
    if not effective:
        lines.append("- none")
    else:
        for item in effective:
            lines.append(f"- `{item['name']}` -> `{item['value']}` match=`{item['matches_target']}`")
    return "\n".join(lines).rstrip() + "\n"


def verification_passed(report: dict[str, Any]) -> bool:
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


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    local_file = Path(args.local_file).resolve() if args.local_file else None
    local_file_exists = bool(local_file and local_file.exists())

    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.texture_asset_path, args.material_path, args.renderer_path))

    report = {
        "tool": "live_asset_verify",
        "effect": args.effect or "",
        "source_policy": args.source_policy,
        "local_file": str(local_file) if local_file else "",
        "local_file_exists": local_file_exists,
        **raw,
    }
    report["verification_passed"] = verification_passed(report)
    out = Path(args.out) if args.out else default_report_path(ctx, "live-asset-verify", args.effect or "shared", "live-asset-verify", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify that a generated texture is imported into UE and referenced by the live material/renderer route.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--local-file", default="")
    parser.add_argument(
        "--source-policy",
        default="required",
        choices=("generated", "required", "ue-only"),
        help="Whether a local source file is required. Use ue-only for hand-authored or UE-native assets.",
    )
    parser.add_argument("--texture-asset-path", required=True)
    parser.add_argument("--material-path", required=True)
    parser.add_argument("--renderer-path", default="")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args_no_subcommand(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
