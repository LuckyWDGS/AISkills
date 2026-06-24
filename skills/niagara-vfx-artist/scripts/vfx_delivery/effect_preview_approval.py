from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from .core import normalize_cli_global_args, resolve_root_context, utc_now_iso, write_text
from .effect_state import effect_preview_approvals_default, load_effect_record, save_effect_record


VALID_STATUS = ("pending", "approved", "revise", "rejected", "historical")


def normalize_text(value: str) -> str:
    return str(value or "").strip()


def build_context(
    *,
    system_path: str,
    material_path: str,
    renderer_path: str,
    grid: str,
    playback_seconds: float | None,
    preview_kind: str,
    carrier: str,
) -> dict[str, Any]:
    return {
        "system_path": normalize_text(system_path),
        "material_path": normalize_text(material_path),
        "renderer_path": normalize_text(renderer_path),
        "grid": normalize_text(grid),
        "playback_seconds": None if playback_seconds is None else round(float(playback_seconds), 6),
        "preview_kind": normalize_text(preview_kind),
        "carrier": normalize_text(carrier),
    }


def context_key(context: dict[str, Any]) -> str:
    payload = json.dumps(context, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def create_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "effect-preview-approvals", args.effect, effect_preview_approvals_default(args.effect))
    context = build_context(
        system_path=args.system_path,
        material_path=args.material_path,
        renderer_path=args.renderer_path,
        grid=args.grid,
        playback_seconds=args.playback_seconds,
        preview_kind=args.preview_kind,
        carrier=args.carrier,
    )
    review = {
        "id": uuid.uuid4().hex[:12],
        "context_key": context_key(context),
        "context": context,
        "preview_path": str(Path(args.preview_path).resolve()),
        "preset": args.preset,
        "status": "pending",
        "notes": args.notes,
        "differences": [],
        "historical_reason": "",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    payload["reviews"].append(review)
    path = save_effect_record(ctx, "effect-preview-approvals", args.effect, payload)
    print(json.dumps({"path": str(path), "review_id": review["id"], "context_key": review["context_key"]}, ensure_ascii=False))
    return 0


def decide_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "effect-preview-approvals", args.effect, effect_preview_approvals_default(args.effect))
    for review in payload["reviews"]:
        if review["id"] == args.review_id:
            review["status"] = args.status
            review["notes"] = args.notes or review["notes"]
            review["differences"] = args.difference
            review["updated_at"] = utc_now_iso()
            path = save_effect_record(ctx, "effect-preview-approvals", args.effect, payload)
            print(path)
            return 0
    raise SystemExit(f"Unknown review id: {args.review_id}")


def invalidate_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "effect-preview-approvals", args.effect, effect_preview_approvals_default(args.effect))
    changed = 0
    target_key = normalize_text(args.context_key)
    for review in payload["reviews"]:
        if target_key and review.get("context_key") != target_key:
            continue
        if review.get("status") == "historical":
            continue
        review["status"] = "historical"
        review["historical_reason"] = args.reason
        review["updated_at"] = utc_now_iso()
        changed += 1
    path = save_effect_record(ctx, "effect-preview-approvals", args.effect, payload)
    print(json.dumps({"path": str(path), "changed": changed}, ensure_ascii=False))
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "effect-preview-approvals", args.effect, effect_preview_approvals_default(args.effect))
    print(payload)
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "effect-preview-approvals", args.effect, effect_preview_approvals_default(args.effect))
    target = Path(args.out) if args.out else Path(ctx.vfx_root / "effect-preview-approvals" / f"{args.effect}-effect-preview-approval.md")
    lines = [f"# Effect Preview Approval: {args.effect}", ""]
    for review in payload["reviews"]:
        context = review.get("context") or {}
        lines.extend(
            [
                f"## {review['id']}",
                "",
                f"- Status: `{review['status']}`",
                f"- Context key: `{review.get('context_key', '')}`",
                f"- System: `{context.get('system_path', '') or 'unset'}`",
                f"- Material: `{context.get('material_path', '') or 'unset'}`",
                f"- Renderer: `{context.get('renderer_path', '') or 'unset'}`",
                f"- Grid: `{context.get('grid', '') or 'unset'}`",
                f"- Playback seconds: `{context.get('playback_seconds')}`",
                f"- Kind: `{context.get('preview_kind', '') or 'unset'}`",
                f"- Carrier: `{context.get('carrier', '') or 'unset'}`",
                f"- Preset: `{review.get('preset', '') or 'none'}`",
                f"- Notes: {review.get('notes', '') or 'none'}",
                f"- Historical reason: {review.get('historical_reason', '') or 'none'}",
                f"- Differences: {', '.join(review.get('differences', [])) or 'none'}",
                f"- Preview: {review['preview_path']}",
                "",
            ]
        )
    write_text(target, "\n".join(lines).rstrip() + "\n")
    print(target)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track approval of controlled final effect previews.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--effect", required=True)
    create.add_argument("--preview-path", required=True)
    create.add_argument("--system-path", required=True)
    create.add_argument("--material-path", required=True)
    create.add_argument("--renderer-path", default="")
    create.add_argument("--grid", required=True)
    create.add_argument("--playback-seconds", type=float)
    create.add_argument("--preview-kind", default="still")
    create.add_argument("--carrier", default="sprite")
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

    invalidate = subparsers.add_parser("invalidate")
    invalidate.add_argument("--effect", required=True)
    invalidate.add_argument("--context-key", default="")
    invalidate.add_argument("--reason", default="preview context invalidated")
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
