from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import normalize_cli_global_args, read_jsonl, resolve_root_context, utc_now_iso, write_text
from .effect_state import acceptance_default, approvals_default, load_effect_record, save_effect_record
from .reference_gate import assert_anchor_ready, is_anchor_changed
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


def invalidate_preview_approvals(ctx, effect: str, new_revision: int, reason: str) -> int:
    payload = load_effect_record(ctx, "preview-approvals", effect, approvals_default(effect))
    changed = 0
    for review in payload["reviews"]:
        if int(review.get("anchor_revision", 0) or 0) >= new_revision:
            continue
        if review.get("status") == "historical":
            continue
        review["status"] = "historical"
        review["historical_reason"] = reason
        review["updated_at"] = utc_now_iso()
        changed += 1
    if changed:
        save_effect_record(ctx, "preview-approvals", effect, payload)
    return changed


def invalidate_gap_diagnoses(ctx, effect: str, reason: str) -> int:
    path = ctx.vfx_root / "gap-diagnosis" / f"{effect}.jsonl"
    entries = read_jsonl(path)
    changed = 0
    for entry in entries:
        if entry.get("status") in {"historical", "invalidated-by-anchor-switch"}:
            continue
        entry["status"] = "invalidated-by-anchor-switch"
        entry["status_note"] = reason
        entry["updated_at"] = utc_now_iso()
        changed += 1
    if changed:
        path.write_text(
            "\n".join(__import__("json").dumps(entry, ensure_ascii=False) for entry in entries) + "\n",
            encoding="utf-8",
        )
    return changed


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
        "implementation_scope": args.implementation_scope,
        "scope_confirmed": bool(args.scope_confirmed),
        "updated_at": utc_now_iso(),
    }
    upsert_review(payload, review)
    if args.lock_anchor:
        if not args.implementation_scope.strip():
            raise SystemExit("Locking an anchor requires --implementation-scope.")
        if not args.scope_confirmed:
            raise SystemExit("Locking an anchor requires --scope-confirmed.")
        if not Path(entry["cached_path"]).exists():
            raise SystemExit(f"Cannot lock anchor because cached file is missing: {entry['cached_path']}")
        anchor_changed = is_anchor_changed(payload["anchor_lock"], entry["id"], args.implementation_scope)
        next_revision = int(payload["anchor_lock"].get("revision", 0) or 0) + (1 if anchor_changed else 0)
        payload["anchor_lock"] = {
            "entry_id": entry["id"],
            "updated_at": utc_now_iso(),
            "notes": args.lock_notes or args.notes,
            "implementation_scope": args.implementation_scope,
            "scope_confirmed": True,
            "authority": args.authority,
            "clarity_score": args.clarity_score,
            "cached_path": entry["cached_path"],
            "revision": next_revision,
        }
        if anchor_changed:
            invalidate_preview_approvals(ctx, effect, next_revision, "anchor switched and older preview approvals are now historical")
            invalidate_gap_diagnoses(ctx, effect, "anchor switched and earlier diagnoses must be revalidated")
        for item in payload["reviews"]:
            item["locked_anchor"] = item["entry_id"] == entry["id"]
            if item["locked_anchor"]:
                item["implementation_scope"] = args.implementation_scope
                item["scope_confirmed"] = True
    if args.status == "rejected" and payload["anchor_lock"]["entry_id"] == entry["id"]:
        payload["anchor_lock"] = {
            "entry_id": "",
            "updated_at": utc_now_iso(),
            "notes": "auto-cleared after rejection",
            "implementation_scope": "",
            "scope_confirmed": False,
            "authority": "",
            "clarity_score": 0,
            "cached_path": "",
            "revision": int(payload["anchor_lock"].get("revision", 0) or 0),
        }
        review["locked_anchor"] = False
    path = save_effect_record(ctx, "reference-acceptance", effect, payload)
    print(path)
    return 0


def lock_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "reference-acceptance", args.effect, acceptance_default(args.effect))
    found = False
    locked_review: dict[str, Any] | None = None
    for review in payload["reviews"]:
        review["locked_anchor"] = review["entry_id"] == args.entry_id
        if review["locked_anchor"]:
            found = True
            locked_review = review
    if not found:
        raise SystemExit(f"Entry id is not reviewed for effect {args.effect}: {args.entry_id}")
    if not args.implementation_scope.strip():
        raise SystemExit("Locking an anchor requires --implementation-scope.")
    if not args.scope_confirmed:
        raise SystemExit("Locking an anchor requires --scope-confirmed.")
    if locked_review is None:
        raise SystemExit("Internal error: locked review missing.")
    cached_path = str(locked_review.get("cached_path", "") or "")
    if not cached_path or not Path(cached_path).exists():
        raise SystemExit("Locked anchor must have a locally cached file.")
    anchor_changed = is_anchor_changed(payload["anchor_lock"], args.entry_id, args.implementation_scope)
    payload["anchor_lock"] = {
        "entry_id": args.entry_id,
        "updated_at": utc_now_iso(),
        "notes": args.notes,
        "implementation_scope": args.implementation_scope,
        "scope_confirmed": True,
        "authority": locked_review.get("authority", ""),
        "clarity_score": int(locked_review.get("clarity_score", 0) or 0),
        "cached_path": cached_path,
        "revision": int(payload["anchor_lock"].get("revision", 0) or 0) + (1 if anchor_changed else 0),
    }
    if anchor_changed:
        invalidate_preview_approvals(
            ctx,
            args.effect,
            int(payload["anchor_lock"].get("revision", 0) or 0),
            "anchor switched and older preview approvals are now historical",
        )
        invalidate_gap_diagnoses(ctx, args.effect, "anchor switched and earlier diagnoses must be revalidated")
    locked_review["implementation_scope"] = args.implementation_scope
    locked_review["scope_confirmed"] = True
    path = save_effect_record(ctx, "reference-acceptance", args.effect, payload)
    print(path)
    return 0


def assert_ready_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    lock = assert_anchor_ready(ctx, args.effect, args.require_entry_id, args.require_scope)
    entry_id = str(lock.get("entry_id", "") or "")
    cached_path = str(lock.get("cached_path", "") or "")
    print(
        {
            "effect": args.effect,
            "ready": True,
            "entry_id": entry_id,
            "implementation_scope": lock.get("implementation_scope", ""),
            "cached_path": cached_path,
            "revision": int(lock.get("revision", 0) or 0),
        }
    )
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
        f"- Implementation scope: `{payload['anchor_lock'].get('implementation_scope', '') or 'unset'}`",
        f"- Scope confirmed: `{payload['anchor_lock'].get('scope_confirmed', False)}`",
        f"- Anchor revision: `{payload['anchor_lock'].get('revision', 0)}`",
        "",
    ]
    for review in payload["reviews"]:
        lines.append(
            f"- `{review['entry_id']}` `{review['label']}` status=`{review['status']}` authority=`{review['authority']}` clarity=`{review['clarity_score']}` locked=`{review['locked_anchor']}` scope=`{review.get('implementation_scope', '') or 'unset'}` scope_confirmed=`{review.get('scope_confirmed', False)}`"
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
    review.add_argument("--implementation-scope", default="")
    review.add_argument("--scope-confirmed", action="store_true")
    review.add_argument("--lock-anchor", action="store_true")
    review.add_argument("--lock-notes", default="")
    review.set_defaults(func=review_command)

    lock = subparsers.add_parser("lock")
    lock.add_argument("--effect", required=True)
    lock.add_argument("--entry-id", required=True)
    lock.add_argument("--notes", default="")
    lock.add_argument("--implementation-scope", required=True)
    lock.add_argument("--scope-confirmed", action="store_true")
    lock.set_defaults(func=lock_command)

    assert_ready = subparsers.add_parser("assert-ready")
    assert_ready.add_argument("--effect", required=True)
    assert_ready.add_argument("--require-entry-id", default="")
    assert_ready.add_argument("--require-scope", default="")
    assert_ready.set_defaults(func=assert_ready_command)

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
        known_subcommands={"review", "lock", "assert-ready", "show", "export-md"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
