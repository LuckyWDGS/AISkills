from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import (
    RootContext,
    default_report_path,
    load_json,
    normalize_cli_global_args,
    resolve_root_context,
    save_json,
    set_dotted_field,
    slugify,
    utc_now_iso,
    write_text,
)
from .reference_gate import assert_anchor_ready


def map_path(ctx: RootContext, effect: str) -> Path:
    return ctx.vfx_root / "layer-maps" / f"{slugify(effect)}.json"


def load_map(ctx: RootContext, effect: str) -> dict[str, Any]:
    return load_json(
        map_path(ctx, effect),
        {
            "version": 1,
            "effect_name": effect,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "anchor_reference_id": "",
            "style_reference_ids": [],
            "notes": "",
            "layers": [],
        },
    )


def save_map(ctx: RootContext, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    save_json(map_path(ctx, payload["effect_name"]), payload)


def default_layer(name: str, order: int) -> dict[str, Any]:
    return {
        "name": name,
        "order": order,
        "evidence": {
            "reference_id": "",
            "region": "",
            "silhouette": "",
            "brightness": "",
            "color": "",
            "motion_cue": "",
            "occlusion": "",
            "consistency": "",
            "notes": "",
        },
        "ue_carrier": {
            "primary": "",
            "alternates": [],
            "rationale": "",
        },
        "material": {
            "asset_paths": [],
            "logic": "",
            "parameters": [],
        },
        "niagara": {
            "system": "",
            "emitters": [],
            "renderer": "",
            "bindings": "",
            "lifecycle": "",
        },
        "textures": [],
        "self_test": [],
    }


def parse_kv_list(items: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        output[key] = value
    return output


def find_layer(payload: dict[str, Any], layer_name: str) -> dict[str, Any]:
    for layer in payload["layers"]:
        if layer["name"] == layer_name:
            return layer
    raise SystemExit(f"Unknown layer: {layer_name}")


def init_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_map(ctx, args.effect)
    payload["anchor_reference_id"] = args.anchor_reference_id or payload["anchor_reference_id"]
    if args.style_reference_id:
        payload["style_reference_ids"] = list(dict.fromkeys(args.style_reference_id))
    if args.notes:
        payload["notes"] = args.notes
    save_map(ctx, payload)
    print(map_path(ctx, args.effect))
    return 0


def add_layer_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    assert_anchor_ready(ctx, args.effect)
    payload = load_map(ctx, args.effect)
    if any(layer["name"] == args.name for layer in payload["layers"]):
        raise SystemExit(f"Layer already exists: {args.name}")
    layer = default_layer(args.name, args.order if args.order is not None else len(payload["layers"]) + 1)
    for key, value in parse_kv_list(args.field).items():
        set_dotted_field(layer, key, value)
    if args.texture:
        layer["textures"] = [{"name": item.split(":", 1)[0], "usage": item.split(":", 1)[1] if ":" in item else ""} for item in args.texture]
    if args.self_test:
        layer["self_test"] = [{"name": f"check-{index+1}", "check": value} for index, value in enumerate(args.self_test)]
    payload["layers"].append(layer)
    payload["layers"].sort(key=lambda entry: entry["order"])
    save_map(ctx, payload)
    print(layer["name"])
    return 0


def update_layer_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    assert_anchor_ready(ctx, args.effect)
    payload = load_map(ctx, args.effect)
    layer = find_layer(payload, args.layer)
    for key, value in parse_kv_list(args.field).items():
        set_dotted_field(layer, key, value)
    if args.texture:
        layer["textures"] = [{"name": item.split(":", 1)[0], "usage": item.split(":", 1)[1] if ":" in item else ""} for item in args.texture]
    if args.self_test:
        layer["self_test"] = [{"name": f"check-{index+1}", "check": value} for index, value in enumerate(args.self_test)]
    save_map(ctx, payload)
    print(layer["name"])
    return 0


def export_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['effect_name']} Visual Layer Map",
        "",
        f"- Anchor reference: `{payload['anchor_reference_id'] or 'unset'}`",
        f"- Style references: `{', '.join(payload['style_reference_ids']) or 'none'}`",
        f"- Notes: {payload['notes'] or 'none'}",
        "",
    ]
    for layer in sorted(payload["layers"], key=lambda item: item["order"]):
        lines.extend(
            [
                f"## {layer['order']}. {layer['name']}",
                "",
                f"- Visual evidence: {layer['evidence'].get('region') or 'unset'}",
                f"- Motion cue: {layer['evidence'].get('motion_cue') or 'unset'}",
                f"- UE carrier: {layer['ue_carrier'].get('primary') or 'unset'}",
                f"- Material: {layer['material'].get('logic') or 'unset'}",
                f"- Niagara: {layer['niagara'].get('renderer') or layer['niagara'].get('system') or 'unset'}",
                f"- Textures: {', '.join(item['name'] for item in layer.get('textures', [])) or 'none'}",
                f"- Self-test: {', '.join(item['check'] for item in layer.get('self_test', [])) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_map(ctx, args.effect)
    target = Path(args.out) if args.out else default_report_path(ctx, "layer-maps", args.effect, "visual-layer-map", ".md")
    write_text(target, export_markdown(payload))
    print(target)
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_map(ctx, args.effect)
    print(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain the visual evidence -> UE carrier -> asset map for a VFX effect.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init")
    init_cmd.add_argument("--effect", required=True)
    init_cmd.add_argument("--anchor-reference-id")
    init_cmd.add_argument("--style-reference-id", action="append", default=[])
    init_cmd.add_argument("--notes", default="")
    init_cmd.set_defaults(func=init_command)

    add_cmd = subparsers.add_parser("add-layer")
    add_cmd.add_argument("--effect", required=True)
    add_cmd.add_argument("--name", required=True)
    add_cmd.add_argument("--order", type=int)
    add_cmd.add_argument("--field", action="append", default=[])
    add_cmd.add_argument("--texture", action="append", default=[])
    add_cmd.add_argument("--self-test", action="append", default=[])
    add_cmd.set_defaults(func=add_layer_command)

    update_cmd = subparsers.add_parser("update-layer")
    update_cmd.add_argument("--effect", required=True)
    update_cmd.add_argument("--layer", required=True)
    update_cmd.add_argument("--field", action="append", default=[])
    update_cmd.add_argument("--texture", action="append", default=[])
    update_cmd.add_argument("--self-test", action="append", default=[])
    update_cmd.set_defaults(func=update_layer_command)

    export_cmd = subparsers.add_parser("export-md")
    export_cmd.add_argument("--effect", required=True)
    export_cmd.add_argument("--out")
    export_cmd.set_defaults(func=export_command)

    show_cmd = subparsers.add_parser("show")
    show_cmd.add_argument("--effect", required=True)
    show_cmd.set_defaults(func=show_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"init", "add-layer", "update-layer", "export-md", "show"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
