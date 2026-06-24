from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from .core import normalize_cli_global_args, resolve_root_context, utc_now_iso, write_text
from .effect_state import acceptance_default, approvals_default, load_effect_record, save_effect_record
from .reference_cache import find_entry, load_index


VALID_STATUS = ("pending", "approved", "revise", "rejected", "historical")


def current_anchor_lock(ctx, effect: str) -> dict[str, Any]:
    payload = load_effect_record(ctx, "reference-acceptance", effect, acceptance_default(effect))
    return payload.get("anchor_lock", {})


def create_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    index = load_index(ctx)
    entry = find_entry(index, args.reference_id)
    payload = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    anchor_lock = current_anchor_lock(ctx, args.effect)
    if not str(anchor_lock.get("entry_id", "") or "").strip():
        raise SystemExit("Preview approval gate failed: no locked anchor.")
    if not bool(anchor_lock.get("scope_confirmed", False)):
        raise SystemExit("Preview approval gate failed: locked anchor scope is not confirmed.")
    if entry["id"] != anchor_lock.get("entry_id"):
        raise SystemExit(
            f"Preview approval gate failed: requested reference `{entry['id']}` is not the locked anchor `{anchor_lock.get('entry_id', '')}`."
        )
    review = {
        "id": uuid.uuid4().hex[:12],
        "layer_name": args.layer,
        "reference_id": entry["id"],
        "reference_path": entry["cached_path"],
        "reference_scope": args.reference_scope,
        "preview_path": str(Path(args.preview_path).resolve()),
        "preview_kind": args.preview_kind,
        "final_systems": args.final_system,
        "final_materials": args.final_material,
        "preset": args.preset,
        "status": "pending",
        "notes": args.notes,
        "differences": [],
        "anchor_revision": int(anchor_lock.get("revision", 0) or 0),
        "historical_reason": "",
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


def invalidate_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    changed = 0
    current_revision = int(current_anchor_lock(ctx, args.effect).get("revision", 0) or 0)
    for review in payload["reviews"]:
        if args.layer and review.get("layer_name") != args.layer:
            continue
        if review.get("status") == "historical":
            continue
        if args.anchor_revision_only and int(review.get("anchor_revision", 0) or 0) == current_revision:
            continue
        review["status"] = "historical"
        review["historical_reason"] = args.reason or "anchor switched or approval context invalidated"
        review["updated_at"] = utc_now_iso()
        changed += 1
    path = save_effect_record(ctx, "preview-approvals", args.effect, payload)
    print({"path": str(path), "changed": changed, "current_anchor_revision": current_revision})
    return 0


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
                f"- Anchor revision: `{review.get('anchor_revision', 0)}`",
                f"- Kind: `{review['preview_kind']}`",
                f"- Preset: `{review['preset'] or 'none'}`",
                f"- Final systems: `{', '.join(review.get('final_systems', [])) or 'unset'}`",
                f"- Final materials: `{', '.join(review.get('final_materials', [])) or 'unset'}`",
                f"- Reference scope: `{review.get('reference_scope', '') or 'unset'}`",
                f"- Notes: {review['notes'] or 'none'}",
                f"- Historical reason: {review.get('historical_reason', '') or 'none'}",
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
    create.add_argument("--final-system", action="append", default=[], help="Final Niagara system this preview was rendered from.")
    create.add_argument("--final-material", action="append", default=[], help="Final material route this preview used.")
    create.add_argument("--preset", default="")
    create.add_argument("--notes", default="")
    create.add_argument("--reference-scope", default="")
    create.set_defaults(func=create_command)

    decide = subparsers.add_parser("decide")
    decide.add_argument("--effect", required=True)
    decide.add_argument("--review-id", required=True)
    decide.add_argument("--status", required=True, choices=VALID_STATUS)
    decide.add_argument("--difference", action="append", default=[])
    decide.add_argument("--notes", default="")
    decide.set_defaults(func=decide_command)

    invalidate = subparsers.add_parser("invalidate")
    invalidate.add_argument("--effect", required=True)
    invalidate.add_argument("--layer", default="")
    invalidate.add_argument("--reason", default="anchor switched or approval context invalidated")
    invalidate.add_argument("--anchor-revision-only", action="store_true")
    invalidate.set_defaults(func=invalidate_command)

    show = subparsers.add_parser("show")
    show.add_argument("--effect", required=True)
    show.set_defaults(func=show_command)

    export_md = subparsers.add_parser("export-md")
    export_md.add_argument("--effect", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=export_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"create", "decide", "invalidate", "show", "export-md"},
        global_opts_with_value={"--root"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
