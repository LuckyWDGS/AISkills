from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import resolve_root_context, utc_now_iso, write_text
from .effect_state import acceptance_default, load_effect_record, save_effect_record
from .reference_cache import find_entry, load_index


VALID_STATUS = ("candidate", "approved", "rejected", "hold")
VALID_AUTHORITY = ("authoritative", "style", "runtime", "debug")


def upsert_review(payload: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    for index, existing in enumerate(payload["reviews"]):
        if existing["entry_id"] == review["entry_id"]:
            payload["reviews"][index] = review
            return review
    payload["reviews"].append(review)
    return review


def review_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    index = load_index(ctx)
    entry = find_entry(index, args.entry_id)
    effect = args.effect or entry["effect"]
    payload = load_effect_record(ctx, "reference-acceptance", effect, acceptance_default(effect))
    review = {
        "entry_id": entry["id"],
        "label": entry["label"],
        "cached_path": entry["cached_path"],
        "source_status": entry["status"],
        "status": args.status,
        "authority": args.authority,
        "anchor_role": args.anchor_role,
        "clarity_score": args.clarity_score,
        "notes": args.notes,
        "locked_anchor": bool(args.lock_anchor),
        "updated_at": utc_now_iso(),
    }
    upsert_review(payload, review)
    if args.lock_anchor:
        payload["anchor_lock"] = {
            "entry_id": entry["id"],
            "updated_at": utc_now_iso(),
            "notes": args.lock_notes or args.notes,
        }
        for item in payload["reviews"]:
            item["locked_anchor"] = item["entry_id"] == entry["id"]
    if args.status == "rejected" and payload["anchor_lock"]["entry_id"] == entry["id"]:
        payload["anchor_lock"] = {"entry_id": "", "updated_at": utc_now_iso(), "notes": "auto-cleared after rejection"}
        review["locked_anchor"] = False
    path = save_effect_record(ctx, "reference-acceptance", effect, payload)
    print(path)
    return 0


def lock_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "reference-acceptance", args.effect, acceptance_default(args.effect))
    found = False
    for review in payload["reviews"]:
        review["locked_anchor"] = review["entry_id"] == args.entry_id
        if review["locked_anchor"]:
            found = True
    if not found:
        raise SystemExit(f"Entry id is not reviewed for effect {args.effect}: {args.entry_id}")
    payload["anchor_lock"] = {"entry_id": args.entry_id, "updated_at": utc_now_iso(), "notes": args.notes}
    path = save_effect_record(ctx, "reference-acceptance", args.effect, payload)
    print(path)
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "reference-acceptance", args.effect, acceptance_default(args.effect))
    print(payload)
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "reference-acceptance", args.effect, acceptance_default(args.effect))
    target = Path(args.out) if args.out else Path(ctx.vfx_root / "reference-acceptance" / f"{args.effect}-acceptance.md")
    lines = [
        f"# Reference Acceptance: {args.effect}",
        "",
        f"- Locked anchor: `{payload['anchor_lock']['entry_id'] or 'unset'}`",
        f"- Lock notes: {payload['anchor_lock']['notes'] or 'none'}",
        "",
    ]
    for review in payload["reviews"]:
        lines.append(
            f"- `{review['entry_id']}` `{review['label']}` status=`{review['status']}` authority=`{review['authority']}` clarity=`{review['clarity_score']}` locked=`{review['locked_anchor']}`"
        )
    write_text(target, "\n".join(lines).rstrip() + "\n")
    print(target)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve, reject, and lock authoritative reference anchors.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review")
    review.add_argument("entry_id")
    review.add_argument("--effect")
    review.add_argument("--status", default="candidate", choices=VALID_STATUS)
    review.add_argument("--authority", default="authoritative", choices=VALID_AUTHORITY)
    review.add_argument("--anchor-role", default="design-reference")
    review.add_argument("--clarity-score", type=int, default=85)
    review.add_argument("--notes", default="")
    review.add_argument("--lock-anchor", action="store_true")
    review.add_argument("--lock-notes", default="")
    review.set_defaults(func=review_command)

    lock = subparsers.add_parser("lock")
    lock.add_argument("--effect", required=True)
    lock.add_argument("--entry-id", required=True)
    lock.add_argument("--notes", default="")
    lock.set_defaults(func=lock_command)

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
