from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from .core import resolve_root_context, utc_now_iso, write_text
from .effect_state import approvals_default, load_effect_record, save_effect_record
from .reference_cache import find_entry, load_index


VALID_STATUS = ("pending", "approved", "revise", "rejected")


def create_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    index = load_index(ctx)
    entry = find_entry(index, args.reference_id)
    payload = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    review = {
        "id": uuid.uuid4().hex[:12],
        "layer_name": args.layer,
        "reference_id": entry["id"],
        "reference_path": entry["cached_path"],
        "preview_path": str(Path(args.preview_path).resolve()),
        "preview_kind": args.preview_kind,
        "preset": args.preset,
        "status": "pending",
        "notes": args.notes,
        "differences": [],
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    payload["reviews"].append(review)
    path = save_effect_record(ctx, "preview-approvals", args.effect, payload)
    print(path)
    return 0


def decide_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    for review in payload["reviews"]:
        if review["id"] == args.review_id:
            review["status"] = args.status
            review["notes"] = args.notes or review["notes"]
            review["differences"] = args.difference
            review["updated_at"] = utc_now_iso()
            path = save_effect_record(ctx, "preview-approvals", args.effect, payload)
            print(path)
            return 0
    raise SystemExit(f"Unknown review id: {args.review_id}")


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    print(payload)
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    target = Path(args.out) if args.out else Path(ctx.vfx_root / "preview-approvals" / f"{args.effect}-preview-approval.md")
    lines = [f"# Preview Approval: {args.effect}", ""]
    for review in payload["reviews"]:
        lines.extend(
            [
                f"## {review['layer_name']} / {review['id']}",
                "",
                f"- Status: `{review['status']}`",
                f"- Kind: `{review['preview_kind']}`",
                f"- Preset: `{review['preset'] or 'none'}`",
                f"- Notes: {review['notes'] or 'none'}",
                f"- Differences: {', '.join(review['differences']) or 'none'}",
                f"- Reference: {review['reference_path']}",
                f"- Preview: {review['preview_path']}",
                "",
            ]
        )
    write_text(target, "\n".join(lines).rstrip() + "\n")
    print(target)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track preview approval before implementation proceeds.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--effect", required=True)
    create.add_argument("--layer", required=True)
    create.add_argument("--reference-id", required=True)
    create.add_argument("--preview-path", required=True)
    create.add_argument("--preview-kind", default="still")
    create.add_argument("--preset", default="")
    create.add_argument("--notes", default="")
    create.set_defaults(func=create_command)

    decide = subparsers.add_parser("decide")
    decide.add_argument("--effect", required=True)
    decide.add_argument("--review-id", required=True)
    decide.add_argument("--status", required=True, choices=VALID_STATUS)
    decide.add_argument("--difference", action="append", default=[])
    decide.add_argument("--notes", default="")
    decide.set_defaults(func=decide_command)

    show = subparsers.add_parser("show")
    show.add_argument("--effect", required=True)
    show.set_defaults(func=show_command)

    export_md = subparsers.add_parser("export-md")
    export_md.add_argument("--effect", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=export_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
