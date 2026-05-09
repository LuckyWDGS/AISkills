from __future__ import annotations

import argparse
import shutil
import uuid
from pathlib import Path
from typing import Any

from .core import (
    RootContext,
    ensure_dir,
    load_json,
    relative_or_absolute,
    resolve_root_context,
    save_json,
    sha256_file,
    slugify,
    utc_now_iso,
)
from .image_ops import crop_image, image_size, upscale_image


INDEX_NAME = "index.json"
VALID_STATUSES = ("active", "rejected", "debug")


def cache_root(ctx: RootContext) -> Path:
    return ensure_dir(ctx.vfx_root / "reference-cache")


def index_path(ctx: RootContext) -> Path:
    return cache_root(ctx) / INDEX_NAME


def load_index(ctx: RootContext) -> dict[str, Any]:
    return load_json(index_path(ctx), {"version": 1, "entries": []})


def save_index(ctx: RootContext, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    save_json(index_path(ctx), payload)


def find_entry(payload: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for entry in payload["entries"]:
        if entry["id"] == entry_id:
            return entry
    raise SystemExit(f"Unknown reference entry id: {entry_id}")


def next_target(ctx: RootContext, effect: str, status: str, label: str, suffix: str) -> Path:
    folder = ensure_dir(cache_root(ctx) / status / slugify(effect))
    base = slugify(label)
    candidate = folder / f"{base}{suffix}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = folder / f"{base}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise SystemExit("Unable to allocate a unique cache path")


def register_file(
    ctx: RootContext,
    source: Path,
    effect: str,
    label: str,
    status: str,
    kind: str,
    notes: str,
    derived_from: str | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise SystemExit(f"status must be one of: {', '.join(VALID_STATUSES)}")
    source = source.resolve()
    if not source.exists():
        raise SystemExit(f"Source file does not exist: {source}")
    target = next_target(ctx, effect, status, label, source.suffix.lower())
    shutil.copy2(source, target)
    width, height = image_size(target)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "effect": effect,
        "label": label,
        "status": status,
        "kind": kind,
        "notes": notes,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "source_path": str(source),
        "cached_path": str(target),
        "sha256": sha256_file(target),
        "size": {"width": width, "height": height},
        "derived_from": derived_from,
    }
    payload = load_index(ctx)
    payload["entries"].append(entry)
    save_index(ctx, payload)
    return entry


def register_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    entry = register_file(
        ctx=ctx,
        source=Path(args.source),
        effect=args.effect,
        label=args.label or Path(args.source).stem,
        status=args.status,
        kind=args.kind,
        notes=args.notes,
    )
    print_json_entry(ctx, entry)
    return 0


def crop_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_index(ctx)
    source_entry = find_entry(payload, args.entry_id)
    source_path = Path(source_entry["cached_path"])
    label = args.label or f"{source_entry['label']}-crop"
    target = next_target(ctx, source_entry["effect"], args.status, label, source_path.suffix.lower())
    width, height = crop_image(source_path, target, (args.left, args.top, args.right, args.bottom))
    entry = {
        "id": uuid.uuid4().hex[:12],
        "effect": source_entry["effect"],
        "label": label,
        "status": args.status,
        "kind": "crop",
        "notes": args.notes,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "source_path": str(source_path),
        "cached_path": str(target),
        "sha256": sha256_file(target),
        "size": {"width": width, "height": height},
        "derived_from": source_entry["id"],
        "crop_box": {"left": args.left, "top": args.top, "right": args.right, "bottom": args.bottom},
    }
    payload["entries"].append(entry)
    save_index(ctx, payload)
    print_json_entry(ctx, entry)
    return 0


def hq_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_index(ctx)
    source_entry = find_entry(payload, args.entry_id)
    source_path = Path(source_entry["cached_path"])
    label = args.label or f"{source_entry['label']}-hq-{args.scale:g}x"
    target = next_target(ctx, source_entry["effect"], args.status, label, source_path.suffix.lower())
    width, height = upscale_image(source_path, target, args.scale, args.sharpen)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "effect": source_entry["effect"],
        "label": label,
        "status": args.status,
        "kind": "hq",
        "notes": args.notes,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "source_path": str(source_path),
        "cached_path": str(target),
        "sha256": sha256_file(target),
        "size": {"width": width, "height": height},
        "derived_from": source_entry["id"],
        "hq": {"scale": args.scale, "sharpen": args.sharpen},
    }
    payload["entries"].append(entry)
    save_index(ctx, payload)
    print_json_entry(ctx, entry)
    return 0


def set_status_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_index(ctx)
    entry = find_entry(payload, args.entry_id)
    source_path = Path(entry["cached_path"])
    target = next_target(ctx, entry["effect"], args.status, entry["label"], source_path.suffix.lower())
    shutil.move(str(source_path), str(target))
    entry["status"] = args.status
    entry["cached_path"] = str(target)
    entry["updated_at"] = utc_now_iso()
    save_index(ctx, payload)
    print_json_entry(ctx, entry)
    return 0


def list_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_index(ctx)
    rows = payload["entries"]
    if args.effect:
        rows = [entry for entry in rows if entry["effect"] == args.effect]
    if args.status:
        rows = [entry for entry in rows if entry["status"] == args.status]
    for entry in rows:
        print_json_entry(ctx, entry)
    return 0


def print_json_entry(ctx: RootContext, entry: dict[str, Any]) -> None:
    serializable = dict(entry)
    serializable["cached_path"] = relative_or_absolute(Path(entry["cached_path"]), ctx.project_root)
    print(serializable)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cache, classify, crop, and HQ-copy VFX reference images.")
    parser.add_argument("--root", default="auto", help="Project root. Default: auto-detect.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register", help="Copy a reference image into the managed cache.")
    register.add_argument("source")
    register.add_argument("--effect", required=True)
    register.add_argument("--label")
    register.add_argument("--status", default="active", choices=VALID_STATUSES)
    register.add_argument("--kind", default="design-reference")
    register.add_argument("--notes", default="")
    register.set_defaults(func=register_command)

    crop = subparsers.add_parser("crop", help="Create a derived crop from a cached reference.")
    crop.add_argument("entry_id")
    crop.add_argument("--left", type=int, required=True)
    crop.add_argument("--top", type=int, required=True)
    crop.add_argument("--right", type=int, required=True)
    crop.add_argument("--bottom", type=int, required=True)
    crop.add_argument("--label")
    crop.add_argument("--status", default="active", choices=VALID_STATUSES)
    crop.add_argument("--notes", default="")
    crop.set_defaults(func=crop_command)

    hq = subparsers.add_parser("hq", help="Generate a larger clarity copy from a cached reference.")
    hq.add_argument("entry_id")
    hq.add_argument("--scale", type=float, default=2.0)
    hq.add_argument("--sharpen", type=float, default=1.0)
    hq.add_argument("--label")
    hq.add_argument("--status", default="active", choices=VALID_STATUSES)
    hq.add_argument("--notes", default="")
    hq.set_defaults(func=hq_command)

    move = subparsers.add_parser("set-status", help="Move a cached reference between active/rejected/debug.")
    move.add_argument("entry_id")
    move.add_argument("--status", required=True, choices=VALID_STATUSES)
    move.set_defaults(func=set_status_command)

    list_cmd = subparsers.add_parser("list", help="List cached references.")
    list_cmd.add_argument("--effect")
    list_cmd.add_argument("--status", choices=VALID_STATUSES)
    list_cmd.set_defaults(func=list_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
