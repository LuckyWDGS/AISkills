from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from .core import resolve_root_context, slugify, write_text
from .effect_state import asset_plan_default, load_effect_record, save_effect_record
from .visual_layer_map import load_map


def asset_token(text: str) -> str:
    token = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_")
    return token or "Layer"


def platform_budget(platform: str) -> dict[str, Any]:
    key = platform.lower()
    if key in {"android", "ios", "mobile"}:
        return {"max_emitters_per_system": 4, "max_texture_size": 1024, "max_material_instructions": 90, "target_particle_budget": 120}
    if key in {"cinematic", "film"}:
        return {"max_emitters_per_system": 12, "max_texture_size": 4096, "max_material_instructions": 320, "target_particle_budget": 600}
    return {"max_emitters_per_system": 8, "max_texture_size": 2048, "max_material_instructions": 180, "target_particle_budget": 260}


def infer_layer_assets(effect: str, prefix: str, layer: dict[str, Any]) -> dict[str, Any]:
    layer_token = asset_token(layer["name"])
    carrier = str(layer["ue_carrier"].get("primary", "")).lower()
    textures = [
        {
            "name": item["name"],
            "usage": item.get("usage", ""),
        }
        for item in layer.get("textures", [])
    ]
    if not textures:
        textures = [{"name": f"T_{prefix}_{layer_token}_Mask", "usage": "generated-from-layer-preview"}]

    material_master = f"MFX_{prefix}_{layer_token}"
    material_instance = f"MI_{prefix}_{layer_token}"
    if "ribbon" in carrier or "trail" in carrier:
        emitters = [f"NE_{prefix}_{layer_token}_Source", f"NE_{prefix}_{layer_token}_Trail"]
        renderers = ["Ribbon"]
    elif "mesh" in carrier:
        emitters = [f"NE_{prefix}_{layer_token}_Afterimage"]
        renderers = ["Mesh"]
    elif "sprite" in carrier or "atlas" in carrier or "flipbook" in carrier:
        emitters = [f"NE_{prefix}_{layer_token}_Sprite"]
        renderers = ["Sprite"]
    else:
        emitters = [f"NE_{prefix}_{layer_token}_Main"]
        renderers = ["Sprite"]
    return {
        "layer_name": layer["name"],
        "carrier": layer["ue_carrier"].get("primary", ""),
        "textures": textures,
        "materials": [{"master": material_master, "instance": material_instance}],
        "emitters": emitters,
        "renderers": renderers,
    }


def generate_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    layer_map = load_map(ctx, args.effect)
    prefix = args.prefix or asset_token(args.effect)
    payload = load_effect_record(ctx, "asset-plans", args.effect, asset_plan_default(args.effect))
    payload["platform"] = args.platform
    payload["naming"] = {
        "prefix": prefix,
        "system_name": f"NS_{prefix}",
        "folder_root": args.folder_root or f"/Game/VFX/{prefix}",
    }
    payload["budgets"] = platform_budget(args.platform)
    payload["assets"] = {
        "layers": [infer_layer_assets(args.effect, prefix, layer) for layer in layer_map["layers"]],
        "low_end_variant_required": args.include_low_end or args.platform.lower() in {"android", "ios", "mobile"},
    }
    payload["notes"] = args.notes
    path = save_effect_record(ctx, "asset-plans", args.effect, payload)
    print(path)
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "asset-plans", args.effect, asset_plan_default(args.effect))
    target = Path(args.out) if args.out else Path(ctx.vfx_root / "asset-plans" / f"{args.effect}-asset-plan.md")
    lines = [
        f"# Asset Plan: {args.effect}",
        "",
        f"- Platform: `{payload['platform']}`",
        f"- Folder root: `{payload['naming'].get('folder_root', '')}`",
        f"- System name: `{payload['naming'].get('system_name', '')}`",
        "",
        "## Budgets",
        "",
    ]
    for key, value in payload.get("budgets", {}).items():
        lines.append(f"- `{key}` = `{value}`")
    lines.extend(["", "## Layer Assets", ""])
    for layer in payload.get("assets", {}).get("layers", []):
        lines.append(
            f"- `{layer['layer_name']}` carrier=`{layer['carrier']}` emitters=`{', '.join(layer['emitters'])}` materials=`{', '.join(item['instance'] for item in layer['materials'])}` textures=`{', '.join(item['name'] for item in layer['textures'])}`"
        )
    write_text(target, "\n".join(lines).rstrip() + "\n")
    print(target)
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    print(load_effect_record(ctx, "asset-plans", args.effect, asset_plan_default(args.effect)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a minimum viable asset plan from the visual layer map.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--effect", required=True)
    generate.add_argument("--platform", default="PC")
    generate.add_argument("--prefix", default="")
    generate.add_argument("--folder-root", default="")
    generate.add_argument("--include-low-end", action="store_true")
    generate.add_argument("--notes", default="")
    generate.set_defaults(func=generate_command)

    export_md = subparsers.add_parser("export-md")
    export_md.add_argument("--effect", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=export_command)

    show = subparsers.add_parser("show")
    show.add_argument("--effect", required=True)
    show.set_defaults(func=show_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
