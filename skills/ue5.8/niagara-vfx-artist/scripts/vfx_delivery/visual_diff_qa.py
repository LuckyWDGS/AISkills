from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from .core import default_report_path, ensure_dir, resolve_root_context, save_json, slugify
from .reference_cache import find_entry, load_index


def load_reference_path(ctx, reference_id: str | None, reference_path: str | None) -> Path:
    if reference_id:
        entry = find_entry(load_index(ctx), reference_id)
        return Path(entry["cached_path"])
    if reference_path:
        return Path(reference_path).resolve()
    raise SystemExit("Provide --reference-id or --reference-path")


def build_mask(gray: Image.Image, threshold: int) -> Image.Image:
    return gray.point(lambda value: 255 if value >= threshold else 0)


def centroid(mask: Image.Image) -> tuple[float, float]:
    width, height = mask.size
    data = list(mask.getdata())
    total = 0
    sum_x = 0
    sum_y = 0
    for index, value in enumerate(data):
        if value:
            x = index % width
            y = index // width
            total += value
            sum_x += x * value
            sum_y += y * value
    if total == 0:
        return 0.0, 0.0
    return round(sum_x / total, 3), round(sum_y / total, 3)


def compare_images(reference_path: Path, preview_path: Path, threshold: int) -> dict[str, Any]:
    with Image.open(reference_path) as reference_image, Image.open(preview_path) as preview_image:
        ref = reference_image.convert("RGBA")
        prev = preview_image.convert("RGBA").resize(ref.size, Image.Resampling.LANCZOS)
        ref_gray = ref.convert("L")
        prev_gray = prev.convert("L")
        diff = ImageChops.difference(ref_gray, prev_gray)
        ref_edges = ImageOps.autocontrast(ref_gray.filter(ImageFilter.FIND_EDGES))
        prev_edges = ImageOps.autocontrast(prev_gray.filter(ImageFilter.FIND_EDGES))
        diff_edges = ImageChops.difference(ref_edges, prev_edges)
        ref_mask = build_mask(ref_gray, threshold)
        prev_mask = build_mask(prev_gray, threshold)
        diff_mask = ImageChops.difference(ref_mask, prev_mask)

        diff_stat = ImageStat.Stat(diff)
        edge_stat = ImageStat.Stat(diff_edges)
        ref_mask_stat = ImageStat.Stat(ref_mask)
        prev_mask_stat = ImageStat.Stat(prev_mask)
        diff_mask_stat = ImageStat.Stat(diff_mask)

        return {
            "size": {"width": ref.width, "height": ref.height},
            "mean_diff": round(diff_stat.mean[0], 4),
            "rms_diff": round(diff_stat.rms[0], 4),
            "edge_mean_diff": round(edge_stat.mean[0], 4),
            "reference_coverage": round(ref_mask_stat.mean[0] / 255.0, 4),
            "preview_coverage": round(prev_mask_stat.mean[0] / 255.0, 4),
            "mask_delta": round(diff_mask_stat.mean[0] / 255.0, 4),
            "reference_centroid": centroid(ref_mask),
            "preview_centroid": centroid(prev_mask),
            "ref_image": ref,
            "prev_image": prev,
            "diff_image": diff,
            "diff_edges": diff_edges,
        }


def save_outputs(target_dir: Path, result: dict[str, Any]) -> dict[str, str]:
    ensure_dir(target_dir)
    heat = Image.merge("RGB", (result["diff_image"], Image.new("L", result["diff_image"].size, 0), Image.new("L", result["diff_image"].size, 0)))
    composite = Image.new("RGB", (result["ref_image"].width * 3, result["ref_image"].height))
    composite.paste(result["ref_image"].convert("RGB"), (0, 0))
    composite.paste(result["prev_image"].convert("RGB"), (result["ref_image"].width, 0))
    composite.paste(heat, (result["ref_image"].width * 2, 0))

    heat_path = target_dir / "diff-heat.png"
    edge_path = target_dir / "diff-edges.png"
    composite_path = target_dir / "diff-composite.png"
    heat.save(heat_path)
    result["diff_edges"].save(edge_path)
    composite.save(composite_path)
    return {"heat_path": str(heat_path), "edge_path": str(edge_path), "composite_path": str(composite_path)}


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    reference_path = load_reference_path(ctx, args.reference_id, args.reference_path)
    preview_path = Path(args.preview_path).resolve()
    result = compare_images(reference_path, preview_path, args.threshold)
    if args.out_dir:
        output_dir = Path(args.out_dir)
    else:
        output_dir = ensure_dir(ctx.vfx_root / "diff-qa" / slugify(args.effect or str(reference_path.stem)) / slugify(args.layer or preview_path.stem))
    files = save_outputs(output_dir, result)
    payload = {
        "effect_name": args.effect,
        "layer_name": args.layer,
        "reference_path": str(reference_path),
        "preview_path": str(preview_path),
        "threshold": args.threshold,
        "metrics": {key: value for key, value in result.items() if key not in {"ref_image", "prev_image", "diff_image", "diff_edges"}},
        "outputs": files,
    }
    save_json(output_dir / "diff-report.json", payload)
    print(output_dir / "diff-report.json")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a first-pass visual diff between a reference and a preview capture.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--reference-id")
    parser.add_argument("--reference-path")
    parser.add_argument("--preview-path", required=True)
    parser.add_argument("--threshold", type=int, default=96)
    parser.add_argument("--out-dir")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
