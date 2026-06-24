from __future__ import annotations

import argparse
from pathlib import Path

from .core import normalize_cli_global_args, resolve_root_context, write_text
from .effect_state import integration_default, load_effect_record, save_effect_record
from .reference_gate import assert_anchor_ready
from .visual_layer_map import load_map


def infer_user_params(layer_name: str, carrier: str) -> list[str]:
    params = ["User.Intensity", "User.ColorTint", "User.LifetimeScale"]
    carrier_key = carrier.lower()
    if "ribbon" in carrier_key or "trail" in carrier_key:
        params.extend(["User.SourceTransform", "User.TrailWidth", "User.SpawnBurstScale"])
    if "mesh" in carrier_key:
        params.extend(["User.MeshScale", "User.FadeScale"])
    if any(token in layer_name for token in ("翼", "翅", "wing", "left", "right", "左右")):
        params.append("User.LeftRightSide")
    return sorted(dict.fromkeys(params))


def generate_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    assert_anchor_ready(ctx, args.effect)
    layer_map = load_map(ctx, args.effect)
    payload = load_effect_record(ctx, "integration-plans", args.effect, integration_default(args.effect))
    payload["owner"] = args.owner
    payload["attachment_mode"] = args.attachment_mode
    payload["source_space"] = args.source_space
    payload["sockets"] = args.socket
    payload["notifies"] = args.notify or [f"FX_{args.effect}_{layer['name']}_Peak" for layer in layer_map["layers"]]
    params = []
    for layer in layer_map["layers"]:
        params.extend(infer_user_params(layer["name"], layer["ue_carrier"].get("primary", "")))
    payload["user_parameters"] = sorted(dict.fromkeys(params))
    payload["runtime_contract"] = [
        f"{layer['name']}: owner={args.owner} carrier={layer['ue_carrier'].get('primary', '') or 'unset'}"
        for layer in layer_map["layers"]
    ]
    payload["notes"] = args.notes
    path = save_effect_record(ctx, "integration-plans", args.effect, payload)
    print(path)
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "integration-plans", args.effect, integration_default(args.effect))
    target = Path(args.out) if args.out else Path(ctx.vfx_root / "integration-plans" / f"{args.effect}-integration-plan.md")
    lines = [
        f"# Integration Plan: {args.effect}",
        "",
        f"- Owner: `{payload['owner']}`",
        f"- Attachment mode: `{payload['attachment_mode']}`",
        f"- Source space: `{payload['source_space']}`",
        f"- Sockets: {', '.join(payload['sockets']) or 'none'}",
        f"- Notifies: {', '.join(payload['notifies']) or 'none'}",
        "",
        "## User Parameters",
        "",
    ]
    for item in payload["user_parameters"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Runtime Contract", ""])
    for item in payload["runtime_contract"]:
        lines.append(f"- {item}")
    write_text(target, "\n".join(lines).rstrip() + "\n")
    print(target)
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    print(load_effect_record(ctx, "integration-plans", args.effect, integration_default(args.effect)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the gameplay/animation hookup plan for an effect.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--effect", required=True)
    generate.add_argument("--owner", default="animation_notify")
    generate.add_argument("--attachment-mode", default="socket")
    generate.add_argument("--source-space", default="component")
    generate.add_argument("--socket", action="append", default=[])
    generate.add_argument("--notify", action="append", default=[])
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
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"generate", "export-md", "show"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
