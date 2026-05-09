from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat

from .core import load_json, resolve_root_context, save_json, utc_now_iso
from .effect_state import effect_folder, evidence_default, load_effect_record, save_effect_record
from .image_ops import crop_image
from .reference_cache import find_entry, load_index
from .visual_layer_map import find_layer, load_map, save_map


def iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    left = max(box_a[0], box_b[0])
    top = max(box_a[1], box_b[1])
    right = min(box_a[2], box_b[2])
    bottom = min(box_a[3], box_b[3])
    if right <= left or bottom <= top:
        return 0.0
    inter = (right - left) * (bottom - top)
    area_a = max(1, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    area_b = max(1, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
    return inter / float(area_a + area_b - inter)


def suggest_hotspots(image_path: Path, count: int, window_scale: float) -> list[dict[str, Any]]:
    with Image.open(image_path) as image:
        rgba = image.convert("RGBA")
        gray = rgba.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        alpha = rgba.getchannel("A")
        width, height = rgba.size
        win_w = max(48, int(width * window_scale))
        win_h = max(48, int(height * window_scale))
        step_x = max(16, win_w // 3)
        step_y = max(16, win_h // 3)
        scored: list[dict[str, Any]] = []
        for top in range(0, max(1, height - win_h + 1), step_y):
            for left in range(0, max(1, width - win_w + 1), step_x):
                box = (left, top, min(width, left + win_w), min(height, top + win_h))
                gray_stat = ImageStat.Stat(gray.crop(box))
                edge_stat = ImageStat.Stat(edges.crop(box))
                alpha_stat = ImageStat.Stat(alpha.crop(box))
                alpha_cov = alpha_stat.mean[0] / 255.0
                score = gray_stat.stddev[0] * 0.9 + edge_stat.mean[0] * 1.6 + alpha_cov * 40.0
                scored.append({"box": box, "score": round(score, 3), "alpha_coverage": round(alpha_cov, 4)})
        scored.sort(key=lambda item: item["score"], reverse=True)
        chosen: list[dict[str, Any]] = []
        for item in scored:
            if len(chosen) >= count:
                break
            if any(iou(item["box"], existing["box"]) > 0.45 for existing in chosen):
                continue
            chosen.append(item)
        return chosen


def suggestion_report_path(ctx, effect: str, entry_id: str) -> Path:
    return effect_folder(ctx, "layer-evidence", effect) / "suggestions" / f"{entry_id}.json"


def suggest_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    index = load_index(ctx)
    entry = find_entry(index, args.entry_id)
    suggestions = suggest_hotspots(Path(entry["cached_path"]), args.count, args.window_scale)
    report = {
        "effect_name": entry["effect"],
        "entry_id": entry["id"],
        "cached_path": entry["cached_path"],
        "generated_at": utc_now_iso(),
        "window_scale": args.window_scale,
        "suggestions": suggestions,
    }
    target = Path(args.out) if args.out else suggestion_report_path(ctx, entry["effect"], entry["id"])
    save_json(target, report)
    payload = load_effect_record(ctx, "layer-evidence", entry["effect"], evidence_default(entry["effect"]))
    payload["suggestions"].append(report)
    save_effect_record(ctx, "layer-evidence", entry["effect"], payload)
    print(target)
    return 0


def parse_box(box_text: str) -> tuple[int, int, int, int]:
    parts = [int(item.strip()) for item in box_text.split(",")]
    if len(parts) != 4:
        raise SystemExit("Box format must be left,top,right,bottom")
    return parts[0], parts[1], parts[2], parts[3]


def attach_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    index = load_index(ctx)
    entry = find_entry(index, args.entry_id)
    effect = args.effect or entry["effect"]
    box = parse_box(args.box) if args.box else None
    if args.suggestion_index is not None:
        report = load_effect_record(ctx, "layer-evidence", effect, evidence_default(effect))
        if not report["suggestions"]:
            suggestion_payload = load_json(suggestion_report_path(ctx, effect, entry["id"]), {"suggestions": []})
            suggestions = suggestion_payload["suggestions"]
        else:
            suggestions = [item for item in report["suggestions"] if item["entry_id"] == entry["id"]][-1]["suggestions"]
        try:
            box = tuple(suggestions[args.suggestion_index]["box"])  # type: ignore[assignment]
        except Exception as exc:
            raise SystemExit(f"Suggestion index is invalid: {args.suggestion_index}") from exc
    if box is None:
        raise SystemExit("Provide --box or --suggestion-index")

    effect_record = load_effect_record(ctx, "layer-evidence", effect, evidence_default(effect))
    crops_dir = effect_folder(ctx, "layer-evidence", effect) / "crops"
    crop_path = crops_dir / f"{args.layer}-{uuid.uuid4().hex[:8]}.png"
    crop_image(Path(entry["cached_path"]), crop_path, box)
    attachment = {
        "id": uuid.uuid4().hex[:12],
        "entry_id": entry["id"],
        "effect_name": effect,
        "layer_name": args.layer,
        "box": list(box),
        "crop_path": str(crop_path),
        "silhouette": args.silhouette,
        "residue": args.residue,
        "spacing": args.spacing,
        "motion_cue": args.motion_cue,
        "notes": args.notes,
        "created_at": utc_now_iso(),
    }
    effect_record["attachments"].append(attachment)
    save_effect_record(ctx, "layer-evidence", effect, effect_record)

    layer_map = load_map(ctx, effect)
    layer = find_layer(layer_map, args.layer)
    layer["evidence"]["reference_id"] = entry["id"]
    layer["evidence"]["region"] = ",".join(str(item) for item in box)
    layer["evidence"]["silhouette"] = args.silhouette or layer["evidence"].get("silhouette", "")
    layer["evidence"]["motion_cue"] = args.motion_cue or layer["evidence"].get("motion_cue", "")
    layer["evidence"]["notes"] = args.notes or layer["evidence"].get("notes", "")
    layer["evidence"]["crop_path"] = str(crop_path)
    layer["evidence"]["residue"] = args.residue
    layer["evidence"]["spacing"] = args.spacing
    save_map(ctx, layer_map)
    print(crop_path)
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "layer-evidence", args.effect, evidence_default(args.effect))
    print(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Suggest and attach visible evidence crops for effect layers.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest = subparsers.add_parser("suggest")
    suggest.add_argument("entry_id")
    suggest.add_argument("--count", type=int, default=6)
    suggest.add_argument("--window-scale", type=float, default=0.35)
    suggest.add_argument("--out")
    suggest.set_defaults(func=suggest_command)

    attach = subparsers.add_parser("attach")
    attach.add_argument("entry_id")
    attach.add_argument("--effect")
    attach.add_argument("--layer", required=True)
    attach.add_argument("--box")
    attach.add_argument("--suggestion-index", type=int)
    attach.add_argument("--silhouette", default="")
    attach.add_argument("--residue", default="")
    attach.add_argument("--spacing", default="")
    attach.add_argument("--motion-cue", default="")
    attach.add_argument("--notes", default="")
    attach.set_defaults(func=attach_command)

    show = subparsers.add_parser("show")
    show.add_argument("--effect", required=True)
    show.set_defaults(func=show_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
