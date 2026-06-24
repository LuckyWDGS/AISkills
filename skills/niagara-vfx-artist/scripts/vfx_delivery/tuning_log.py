from __future__ import annotations

import argparse
from pathlib import Path

from .core import append_jsonl, default_report_path, read_jsonl, resolve_root_context, utc_now_iso, write_text


def log_path(ctx, effect: str) -> Path:
    return ctx.vfx_root / "tuning-logs" / f"{effect}.jsonl"


def add_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    entry = {
        "timestamp": utc_now_iso(),
        "effect": args.effect,
        "layer": args.layer,
        "asset_type": args.asset_type,
        "asset_path": args.asset_path,
        "parameter": args.parameter,
        "old_value": args.old_value,
        "new_value": args.new_value,
        "reason": args.reason,
        "visual_gap": args.visual_gap,
        "result": args.result,
    }
    append_jsonl(log_path(ctx, args.effect), entry)
    print(log_path(ctx, args.effect))
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    entries = read_jsonl(log_path(ctx, args.effect))
    lines = [f"# Parameter Tuning Log: {args.effect}", ""]
    for entry in entries:
        lines.append(
            f"- [{entry['timestamp']}] `{entry['asset_type']}` `{entry['parameter']}` `{entry['old_value']}` -> `{entry['new_value']}` | gap: {entry['visual_gap']} | reason: {entry['reason']} | result: {entry['result']}"
        )
    out_path = Path(args.out) if args.out else default_report_path(ctx, "tuning-logs", args.effect, "tuning-log", ".md")
    write_text(out_path, "\n".join(lines).rstrip() + "\n")
    print(out_path)
    return 0


def list_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    for entry in read_jsonl(log_path(ctx, args.effect)):
        print(entry)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record parameter tuning decisions and the visual gap they address.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add")
    add.add_argument("--effect", required=True)
    add.add_argument("--layer", default="")
    add.add_argument("--asset-type", required=True)
    add.add_argument("--asset-path", required=True)
    add.add_argument("--parameter", required=True)
    add.add_argument("--old-value", default="")
    add.add_argument("--new-value", required=True)
    add.add_argument("--reason", required=True)
    add.add_argument("--visual-gap", required=True)
    add.add_argument("--result", default="")
    add.set_defaults(func=add_command)

    export = subparsers.add_parser("export-md")
    export.add_argument("--effect", required=True)
    export.add_argument("--out")
    export.set_defaults(func=export_command)

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--effect", required=True)
    list_cmd.set_defaults(func=list_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
