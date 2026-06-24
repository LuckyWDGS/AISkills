from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import normalize_cli_global_args_no_subcommand, resolve_root_context, save_json, utc_now_iso
from .delivery_package import check_delivery_payload, find_latest_delivery_index, load_delivery_payload
from .effect_state import effect_folder
from .promote_naming import PROMOTE_POLICY_CHOICES, resolve_promote_details


def resolve_index(ctx, args: argparse.Namespace) -> Path:
    if args.index:
        return Path(args.index)
    if not args.effect:
        raise SystemExit("Provide --index or --effect.")
    path = find_latest_delivery_index(ctx, args.effect)
    if path is None:
        raise SystemExit(f"No delivery-index.json found for effect `{args.effect}`.")
    return path


def package_path(asset_path: str) -> str:
    clean = str(asset_path or "").strip().strip("'\"")
    if "." in clean.rsplit("/", 1)[-1]:
        return clean.rsplit(".", 1)[0]
    return clean


def object_path(asset_path: str) -> str:
    pkg = package_path(asset_path)
    if not pkg:
        return ""
    name = pkg.rsplit("/", 1)[-1]
    return f"{pkg}.{name}"


def promote_target_for(source: str, promote_root: str) -> str:
    source_pkg = package_path(source)
    name = source_pkg.rsplit("/", 1)[-1]
    return object_path(f"{promote_root.rstrip('/')}/{name}")


def parse_promote_maps(items: list[str]) -> list[dict[str, str]]:
    mappings: list[dict[str, str]] = []
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Expected --promote-map Source=Target, got: {item}")
        source, target = item.split("=", 1)
        mappings.append({"source": object_path(source), "target": object_path(target)})
    return mappings


def default_promote_maps(payload: dict[str, Any], promote_root: str) -> list[dict[str, str]]:
    if not promote_root:
        return []
    mappings: list[dict[str, str]] = []
    for source in [*payload.get("final_systems", []), *payload.get("final_materials", [])]:
        mappings.append({"source": object_path(source), "target": promote_target_for(source, promote_root)})
    return mappings


def promote_script(mappings: list[dict[str, str]], mode: str, save_assets: bool) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mappings = {json.dumps(mappings, ensure_ascii=False)!r}
        mappings = json.loads(mappings)
        mode = {mode!r}
        results = []

        def package_path(path):
            path = (path or "").split(".", 1)[0]
            return path

        def split_target(path):
            pkg = package_path(path)
            folder, name = pkg.rsplit("/", 1)
            return folder, name

        for item in mappings:
            source = package_path(item.get("source", ""))
            target = package_path(item.get("target", ""))
            row = {{"source": source, "target": target, "mode": mode, "success": False, "error": ""}}
            try:
                if not EAL.does_asset_exist(source):
                    row["error"] = "source asset missing"
                elif EAL.does_asset_exist(target):
                    row["error"] = "target asset already exists"
                elif mode == "duplicate":
                    folder, name = split_target(target)
                    asset = unreal.load_asset(source)
                    created = tools.duplicate_asset(name, folder, asset)
                    row["success"] = created is not None
                else:
                    row["success"] = bool(EAL.rename_asset(source, target))
                if row["success"] and {save_assets!r}:
                    EAL.save_asset(target, False)
            except Exception as exc:
                row["error"] = str(exc)
            results.append(row)
        print(json.dumps({{"success": all(item["success"] for item in results), "results": results}}, ensure_ascii=False))
        """
    ).strip()


def run_promote(ctx, args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    promote_details = resolve_promote_details(
        effect=str(payload.get("effect_name") or args.effect or ""),
        explicit_root=args.promote_root,
        promote_policy=args.promote_policy,
        promote_base=args.promote_base,
        promote_group=args.promote_group,
        promote_effect_name=args.promote_effect_name,
        promote_studio=args.promote_studio,
        promote_project_name=args.promote_project_name,
        promote_effect_family=args.promote_effect_family,
    )
    resolved_promote_root = str(promote_details.get("promote_root") or "")
    if resolved_promote_root and not resolved_promote_root.startswith("/Game/VFX/") and resolved_promote_root != "/Game/VFX":
        raise SystemExit(f"Promote root must stay under /Game/VFX for formal production promotion. Got: {resolved_promote_root}")
    mappings = [*default_promote_maps(payload, resolved_promote_root), *parse_promote_maps(args.promote_map)]
    if not mappings:
        return {
            "enabled": False,
            "success": True,
            "results": [],
            "reason": "no promote mappings",
            "naming": promote_details,
            "promote_root": resolved_promote_root,
        }
    if args.dry_run_promote:
        return {
            "enabled": True,
            "dry_run": True,
            "success": True,
            "results": mappings,
            "naming": promote_details,
            "promote_root": resolved_promote_root,
        }
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    result = client.exec_json(promote_script(mappings, args.promote_mode, args.save_promoted_assets), no_preflight=True)
    return {
        "enabled": True,
        "naming": promote_details,
        "promote_root": resolved_promote_root,
        **result,
    }


def build_finalize_record(index_path: Path, payload: dict[str, Any], notes: str, promote_result: dict[str, Any] | None = None) -> dict[str, Any]:
    outputs = payload.get("outputs") or {}
    promoted_assets = {
        "systems": payload.get("final_systems", []),
        "materials": payload.get("final_materials", []),
    }
    if promote_result and promote_result.get("enabled") and promote_result.get("success"):
        targets = [item.get("target", "") for item in promote_result.get("results", []) if item.get("target")]
        promoted_assets = {
            "systems": [target for target in targets if "/NS_" in target or "/Niagara/" in target],
            "materials": [target for target in targets if "/M_" in target or "/MI_" in target or "/Materials/" in target],
        }
    return {
        "tool": "delivery_finalize",
        "generated_utc": utc_now_iso(),
        "effect_name": payload.get("effect_name", ""),
        "source_index": str(index_path),
        "source_manifest": outputs.get("manifest", ""),
        "source_summary": outputs.get("summary", ""),
        "overall": payload.get("overall", ""),
        "final_systems": payload.get("final_systems", []),
        "final_materials": payload.get("final_materials", []),
        "promoted_assets": promoted_assets,
        "ue_promote": promote_result or {"enabled": False, "success": True, "results": []},
        "notes": notes,
    }


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    index_path = resolve_index(ctx, args)
    payload = load_delivery_payload(index_path)
    code = check_delivery_payload(payload, require_ready=True)
    if code != 0:
        return code
    promote_result = {"enabled": False, "success": True, "results": []}
    if args.promote_assets:
        promote_result = run_promote(ctx, args, payload)
        if not promote_result.get("success"):
            out = Path(args.out) if args.out else effect_folder(ctx, "finalized", str(payload.get("effect_name") or args.effect or index_path.parent.name)) / "finalize-failed-promote.json"
            save_json(out, {
                "tool": "delivery_finalize",
                "generated_utc": utc_now_iso(),
                "effect_name": payload.get("effect_name", ""),
                "source_index": str(index_path),
                "overall": payload.get("overall", ""),
                "ue_promote": promote_result,
                "notes": args.notes,
            })
            print(out)
            return 2
    effect = str(payload.get("effect_name") or args.effect or index_path.parent.name)
    out = Path(args.out) if args.out else effect_folder(ctx, "finalized", effect) / "finalize.json"
    record = build_finalize_record(index_path, payload, args.notes, promote_result)
    save_json(out, record)
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finalize a VFX delivery package only after delivery-index health is ready.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--index", default="")
    parser.add_argument("--effect", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--promote-assets", action="store_true", help="Promote UE assets after the delivery index is ready.")
    parser.add_argument("--promote-root", default="", help="Target UE folder for all final systems/materials, for example /Game/VFX/Final/MyEffect.")
    parser.add_argument("--promote-policy", choices=PROMOTE_POLICY_CHOICES, default="manual-root")
    parser.add_argument("--promote-base", default="/Game/VFX")
    parser.add_argument("--promote-group", default="Final")
    parser.add_argument("--promote-studio", default="Studio")
    parser.add_argument("--promote-project-name", default="Project")
    parser.add_argument("--promote-effect-family", default="Shared")
    parser.add_argument("--promote-effect-name", default="")
    parser.add_argument("--promote-map", action="append", default=[], help="Explicit Source=Target UE asset mapping; can be repeated.")
    parser.add_argument("--promote-mode", choices=("move", "duplicate"), default="move")
    parser.add_argument("--dry-run-promote", action="store_true")
    parser.add_argument("--save-promoted-assets", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args_no_subcommand(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
