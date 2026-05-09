from __future__ import annotations

import argparse
import textwrap

from .bridge import BridgeClient
from .core import resolve_root_context


def split_target(target_path: str) -> tuple[str, str]:
    normalized = target_path.rsplit(".", 1)[0]
    package_path, asset_name = normalized.rsplit("/", 1)
    return package_path, asset_name


def duplicate_asset_script(source_path: str, target_path: str) -> str:
    package_path, asset_name = split_target(target_path)
    return textwrap.dedent(
        f"""
        import json
        import unreal

        source = unreal.load_asset({source_path!r})
        if source is None:
            raise RuntimeError(f"Unable to load source asset: {source_path}")
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        duplicated = tools.duplicate_asset({asset_name!r}, {package_path!r}, source)
        ok = duplicated is not None
        if ok:
            unreal.EditorAssetLibrary.save_asset({target_path!r}, False)
        print(json.dumps({{"success": ok, "target_path": {target_path!r}}}, ensure_ascii=False))
        """
    ).strip()


def move_asset_script(source_path: str, target_path: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal
        ok = unreal.EditorAssetLibrary.rename_asset({source_path!r}, {target_path!r})
        print(json.dumps({{"success": bool(ok), "target_path": {target_path!r}}}, ensure_ascii=False))
        """
    ).strip()


def create_material_instance_script(parent_path: str, target_path: str) -> str:
    package_path, asset_name = split_target(target_path)
    return textwrap.dedent(
        f"""
        import json
        import unreal

        tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialInstanceConstantFactoryNew()
        created = tools.create_asset({asset_name!r}, {package_path!r}, unreal.MaterialInstanceConstant, factory)
        if created is None:
            raise RuntimeError(f"Unable to create material instance: {target_path}")
        parent = unreal.load_asset({parent_path!r})
        if parent is None:
            raise RuntimeError(f"Unable to load parent material: {parent_path}")
        created.set_editor_property("parent", parent)
        unreal.EditorAssetLibrary.save_asset({target_path!r}, False)
        print(json.dumps({{"success": True, "target_path": {target_path!r}, "parent": {parent_path!r}}}, ensure_ascii=False))
        """
    ).strip()


def save_assets_script(asset_paths: list[str]) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        results = {{}}
        for asset_path in {asset_paths!r}:
            results[asset_path] = bool(unreal.EditorAssetLibrary.save_asset(asset_path, False))
        print(json.dumps({{"success": True, "results": results}}, ensure_ascii=False))
        """
    ).strip()


def set_niagara_system_props_script(system_path: str, effect_type_path: str, fixed_bounds: str, warmup_tick_count: int | None, warmup_tick_delta: float | None) -> str:
    effect_block = ""
    if effect_type_path:
        effect_block = textwrap.dedent(
            f"""
            effect_type = unreal.load_asset({effect_type_path!r})
            if effect_type is None:
                raise RuntimeError(f"Unable to load effect type: {effect_type_path}")
            system = unreal.load_asset({system_path!r})
            if system is None:
                raise RuntimeError(f"Unable to load Niagara system: {system_path}")
            try:
                system.set_editor_property("effect_type", effect_type)
            except Exception:
                pass
            """
        )
    property_calls: list[str] = []
    if fixed_bounds:
        property_calls.append(
            f"results['FixedBounds'] = bool(PROP.set_u_property_from_export_text({system_path!r}, 'FixedBounds', {fixed_bounds!r}, True))"
        )
    if warmup_tick_count is not None:
        property_calls.append(
            f"results['WarmupTickCount'] = bool(PROP.set_u_property_from_export_text({system_path!r}, 'WarmupTickCount', {str(warmup_tick_count)!r}, True))"
        )
    if warmup_tick_delta is not None:
        property_calls.append(
            f"results['WarmupTickDelta'] = bool(PROP.set_u_property_from_export_text({system_path!r}, 'WarmupTickDelta', {str(warmup_tick_delta)!r}, True))"
        )
    return textwrap.dedent(
        f"""
        import json
        import unreal

        PROP = unreal.UnrealBridgePropertyLibrary
        results = {{}}
        {effect_block}
        {'; '.join(property_calls) if property_calls else "results['noop'] = True"}
        unreal.EditorAssetLibrary.save_asset({system_path!r}, False)
        print(json.dumps({{"success": True, "results": results}}, ensure_ascii=False))
        """
    ).strip()


def run_bridge(args: argparse.Namespace, script_text: str) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    print(client.exec_json(script_text))
    return 0


def duplicate_command(args: argparse.Namespace) -> int:
    return run_bridge(args, duplicate_asset_script(args.source, args.target))


def move_command(args: argparse.Namespace) -> int:
    return run_bridge(args, move_asset_script(args.source, args.target))


def create_mi_command(args: argparse.Namespace) -> int:
    return run_bridge(args, create_material_instance_script(args.parent, args.target))


def save_command(args: argparse.Namespace) -> int:
    return run_bridge(args, save_assets_script(args.asset))


def duplicate_system_command(args: argparse.Namespace) -> int:
    return run_bridge(args, duplicate_asset_script(args.template, args.target))


def duplicate_emitter_command(args: argparse.Namespace) -> int:
    return run_bridge(args, duplicate_asset_script(args.template, args.target))


def set_system_command(args: argparse.Namespace) -> int:
    return run_bridge(
        args,
        set_niagara_system_props_script(args.system_path, args.effect_type_path, args.fixed_bounds, args.warmup_tick_count, args.warmup_tick_delta),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="First-pass write-side Unreal helpers for VFX asset creation and repair.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--timeout", type=int, default=180)
    subparsers = parser.add_subparsers(dest="command", required=True)

    duplicate = subparsers.add_parser("duplicate-asset")
    duplicate.add_argument("source")
    duplicate.add_argument("target")
    duplicate.set_defaults(func=duplicate_command)

    move = subparsers.add_parser("move-asset")
    move.add_argument("source")
    move.add_argument("target")
    move.set_defaults(func=move_command)

    create_mi = subparsers.add_parser("create-material-instance")
    create_mi.add_argument("parent")
    create_mi.add_argument("target")
    create_mi.set_defaults(func=create_mi_command)

    save_assets = subparsers.add_parser("save-assets")
    save_assets.add_argument("asset", nargs="+")
    save_assets.set_defaults(func=save_command)

    duplicate_system = subparsers.add_parser("duplicate-niagara-system")
    duplicate_system.add_argument("template")
    duplicate_system.add_argument("target")
    duplicate_system.set_defaults(func=duplicate_system_command)

    duplicate_emitter = subparsers.add_parser("duplicate-niagara-emitter")
    duplicate_emitter.add_argument("template")
    duplicate_emitter.add_argument("target")
    duplicate_emitter.set_defaults(func=duplicate_emitter_command)

    set_system = subparsers.add_parser("set-niagara-system-props")
    set_system.add_argument("system_path")
    set_system.add_argument("--effect-type-path", default="")
    set_system.add_argument("--fixed-bounds", default="")
    set_system.add_argument("--warmup-tick-count", type=int)
    set_system.add_argument("--warmup-tick-delta", type=float)
    set_system.set_defaults(func=set_system_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
