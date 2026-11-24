from __future__ import annotations

import argparse
import json
from pathlib import Path

from .control_common import find_control, load_control_presets, load_control_schema, save_control_presets
from .core import normalize_cli_global_args, write_text


def parse_value(item: str) -> tuple[str, str]:
    if "=" not in item:
        raise SystemExit(f"Expected CONTROL=VALUE_JSON, got: {item}")
    control_id, value = item.split("=", 1)
    return control_id.strip(), value.strip()


def command_set(args: argparse.Namespace) -> int:
    schema = load_control_schema(args.schema)
    effect = str(schema.get("effect_name") or args.effect or "Effect")
    ctx = args._ctx
    payload = load_control_presets(ctx, effect)
    presets = payload.get("presets") or []
    existing = next((item for item in presets if item.get("name") == args.name), None)
    if existing is None:
        existing = {"name": args.name, "values": {}, "notes": "", "schema_path": str(Path(args.schema).resolve())}
        presets.append(existing)
    for row in args.value:
        control_selector, value_json = parse_value(row)
        control = find_control(schema, control_selector)
        existing["values"][control["id"]] = value_json
    if args.note:
        existing["notes"] = args.note
    existing["schema_path"] = str(Path(args.schema).resolve())
    payload["presets"] = presets
    out = save_control_presets(ctx, effect, payload)
    print(out)
    return 0


def command_show(args: argparse.Namespace) -> int:
    payload = load_control_presets(args._ctx, args.effect)
    if args.name:
        preset = next((item for item in payload.get("presets") or [] if item.get("name") == args.name), None)
        if preset is None:
            raise SystemExit(f"Unknown preset `{args.name}`.")
        print(json.dumps(preset, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_export(args: argparse.Namespace) -> int:
    payload = load_control_presets(args._ctx, args.effect)
    out = Path(args.out) if args.out else args._ctx.vfx_root / "control-presets" / f"{args.effect}-control-presets.md"
    lines = [f"# Control Presets: {args.effect}", ""]
    for preset in payload.get("presets") or []:
        lines.extend([f"## {preset.get('name', '')}", "", f"- Notes: {preset.get('notes', '') or 'none'}", ""])
        for key, value in sorted((preset.get("values") or {}).items()):
            lines.append(f"- `{key}` = `{value}`")
        lines.append("")
    write_text(out, "\n".join(lines).rstrip() + "\n")
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Save reusable runtime control presets against an effect control schema.")
    parser.add_argument("--root", default="auto")
    sub = parser.add_subparsers(dest="command", required=True)

    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("--effect", default="")
    set_cmd.add_argument("--schema", required=True)
    set_cmd.add_argument("--name", required=True)
    set_cmd.add_argument("--value", action="append", default=[])
    set_cmd.add_argument("--note", default="")
    set_cmd.set_defaults(func=command_set)

    show = sub.add_parser("show")
    show.add_argument("--effect", required=True)
    show.add_argument("--name", default="")
    show.set_defaults(func=command_show)

    export_md = sub.add_parser("export-md")
    export_md.add_argument("--effect", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=command_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    from .control_common import resolve_root

    argv = normalize_cli_global_args(argv, known_subcommands={"set", "show", "export-md"})
    parser = build_parser()
    args = parser.parse_args(argv)
    args._ctx = resolve_root(args.root)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
