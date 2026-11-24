from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp", ".exr"}


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def next_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def require_pillow() -> Any:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("flipbook_normalizer.py requires Pillow (PIL).") from exc
    return Image


def parse_grid(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    normalized = value.lower().replace(" ", "")
    if "x" not in normalized:
        raise argparse.ArgumentTypeError("Grid must look like 4x4 or 8x8.")
    left, right = normalized.split("x", 1)
    cols, rows = int(left), int(right)
    if cols <= 0 or rows <= 0:
        raise argparse.ArgumentTypeError("Grid dimensions must be positive.")
    return cols, rows


def collect_frame_paths(inputs: list[str]) -> list[Path]:
    frames: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_dir():
            frames.extend(item for item in sorted(path.iterdir()) if item.suffix.lower() in IMAGE_EXTENSIONS)
        elif path.exists():
            frames.append(path)
    return sorted(frames)


def split_atlas(image: Any, grid: tuple[int, int], image_module: Any) -> list[Any]:
    cols, rows = grid
    cell_w = image.width // cols
    cell_h = image.height // rows
    frames = []
    for row in range(rows):
        for col in range(cols):
            box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
            frames.append(image.crop(box))
    return frames


def content_bbox(image: Any, background_mode: str, threshold: int) -> tuple[int, int, int, int] | None:
    rgba = image.convert("RGBA")
    if background_mode == "alpha":
        alpha = rgba.getchannel("A")
        mask = alpha.point(lambda px: 255 if px > threshold else 0)
        return mask.getbbox()
    luminance = rgba.convert("L")
    mask = luminance.point(lambda px: 255 if px > threshold else 0)
    return mask.getbbox()


def normalize_frames(
    frames: list[Any],
    image_module: Any,
    cell_size: int,
    padding: int,
    background_mode: str,
    threshold: int,
    normalize_scale: bool,
) -> tuple[list[Any], list[dict[str, Any]]]:
    cropped: list[tuple[Any, tuple[int, int, int, int] | None]] = []
    long_edges: list[int] = []
    for frame in frames:
        bbox = content_bbox(frame, background_mode, threshold)
        crop = frame.crop(bbox) if bbox else image_module.new("RGBA", (1, 1), color=(0, 0, 0, 0))
        cropped.append((crop, bbox))
        if bbox:
            long_edges.append(max(crop.width, crop.height))

    target_edge = statistics.median(long_edges) if long_edges else 1
    content_limit = max(1, cell_size - 2 * padding)

    normalized: list[Any] = []
    manifest: list[dict[str, Any]] = []
    for index, (crop, bbox) in enumerate(cropped):
        result = image_module.new("RGBA", (cell_size, cell_size), color=(0, 0, 0, 0))
        scale = 1.0
        if bbox:
            if normalize_scale and max(crop.width, crop.height) > 0:
                scale = target_edge / max(crop.width, crop.height)
            resized_w = max(1, round(crop.width * scale))
            resized_h = max(1, round(crop.height * scale))
            if resized_w > content_limit or resized_h > content_limit:
                fit = min(content_limit / resized_w, content_limit / resized_h)
                resized_w = max(1, round(resized_w * fit))
                resized_h = max(1, round(resized_h * fit))
                scale *= fit
            if resized_w != crop.width or resized_h != crop.height:
                crop = crop.resize((resized_w, resized_h), image_module.Resampling.LANCZOS)
            x = (cell_size - crop.width) // 2
            y = (cell_size - crop.height) // 2
            result.alpha_composite(crop, (x, y))
        normalized.append(result)
        manifest.append(
            {
                "frame_index": index,
                "bbox": bbox,
                "scale_applied": round(scale, 6),
                "output_size": [cell_size, cell_size],
            }
        )
    return normalized, manifest


def compose_atlas(frames: list[Any], grid: tuple[int, int], cell_size: int, image_module: Any) -> Any:
    cols, rows = grid
    atlas = image_module.new("RGBA", (cols * cell_size, rows * cell_size), color=(0, 0, 0, 0))
    for index, frame in enumerate(frames):
        row = index // cols
        col = index % cols
        atlas.alpha_composite(frame, (col * cell_size, row * cell_size))
    return atlas


def promote_atlas_to_power_of_two(atlas: Any, image_module: Any) -> tuple[Any, dict[str, int] | None]:
    target_w = next_power_of_two(atlas.width)
    target_h = next_power_of_two(atlas.height)
    if target_w == atlas.width and target_h == atlas.height:
        return atlas, None
    padded = image_module.new("RGBA", (target_w, target_h), color=(0, 0, 0, 0))
    padded.alpha_composite(atlas, (0, 0))
    return padded, {"width": target_w, "height": target_h}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Flipbook Normalizer",
        "",
        f"- Frame count: `{report['frame_count']}`",
        f"- Output grid: `{report['output_grid']}`",
        f"- Cell size: `{report['cell_size']}`",
        f"- Atlas: `{report['atlas_png']}`",
        f"- Atlas size: `{report['atlas_width']}x{report['atlas_height']}`",
        f"- Atlas power of two: `{report['atlas_power_of_two']}`",
    ]
    if report.get("recommended_atlas_power_of_two"):
        rec = report["recommended_atlas_power_of_two"]
        lines.append(f"- Recommended POT atlas: `{rec['width']}x{rec['height']}`")
    if report.get("atlas_padded_to"):
        pad = report["atlas_padded_to"]
        lines.append(f"- Padded atlas size: `{pad['width']}x{pad['height']}`")
    if report.get("frames_dir"):
        lines.append(f"- Normalized frames: `{report['frames_dir']}`")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    image_module = require_pillow()
    ctx = resolve_root_context(args.root)
    source_grid = parse_grid(args.source_grid)
    output_grid = parse_grid(args.grid)

    input_paths = collect_frame_paths(args.inputs)
    frames: list[Any] = []
    source_desc: list[str] = []
    if len(input_paths) == 1 and source_grid:
        atlas_path = input_paths[0]
        atlas_image = image_module.open(atlas_path).convert("RGBA")
        frames = split_atlas(atlas_image, source_grid, image_module)
        source_desc.append(str(atlas_path))
    else:
        frames = [image_module.open(path).convert("RGBA") for path in input_paths]
        source_desc = [str(path) for path in input_paths]

    if not frames:
        raise SystemExit("No input frames were found.")

    if output_grid is None:
        cols = math.ceil(math.sqrt(len(frames)))
        rows = math.ceil(len(frames) / cols)
        output_grid = (cols, rows)

    normalized, manifest = normalize_frames(
        frames,
        image_module,
        args.cell_size,
        args.padding,
        args.background_mode,
        args.threshold,
        args.normalize_scale,
    )
    atlas = compose_atlas(normalized, output_grid, args.cell_size, image_module)
    atlas_power_of_two = is_power_of_two(atlas.width) and is_power_of_two(atlas.height)
    recommended_pot = {"width": next_power_of_two(atlas.width), "height": next_power_of_two(atlas.height)}
    padded_to = None
    if args.pow2_atlas:
        atlas, padded_to = promote_atlas_to_power_of_two(atlas, image_module)

    effect = slugify(args.effect or "flipbook")
    atlas_out = Path(args.out) if args.out else default_report_path(ctx, "flipbooks", effect, "flipbook-normalized", ".png")
    atlas_out.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(atlas_out)

    frames_dir = None
    if args.frames_dir:
        frames_dir = Path(args.frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(normalized):
            frame.save(frames_dir / f"{index:04d}.png")

    report = {
        "tool": "flipbook_normalizer",
        "sources": source_desc,
        "source_grid": args.source_grid,
        "output_grid": f"{output_grid[0]}x{output_grid[1]}",
        "frame_count": len(normalized),
        "cell_size": args.cell_size,
        "padding": args.padding,
        "background_mode": args.background_mode,
        "normalize_scale": args.normalize_scale,
        "atlas_width": atlas.width,
        "atlas_height": atlas.height,
        "atlas_power_of_two": is_power_of_two(atlas.width) and is_power_of_two(atlas.height),
        "recommended_atlas_power_of_two": None if atlas_power_of_two else recommended_pot,
        "atlas_padded_to": padded_to,
        "atlas_png": str(atlas_out),
        "frames_dir": str(frames_dir) if frames_dir else None,
        "frames": manifest,
    }
    json_out = atlas_out.with_suffix(".json")
    save_json(json_out, report)
    if args.markdown:
        write_text(atlas_out.with_suffix(".md"), render_markdown(report))
    print(json_out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize flipbook frames or a source atlas into a clean centered atlas.")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect")
    parser.add_argument("--source-grid", help="Split a single source atlas using COLSxROWS before normalization.")
    parser.add_argument("--grid", help="Output atlas grid such as 8x8; auto-squares by default.")
    parser.add_argument("--cell-size", type=int, default=256)
    parser.add_argument("--padding", type=int, default=8)
    parser.add_argument("--background-mode", choices=["alpha", "black"], default="alpha")
    parser.add_argument("--threshold", type=int, default=8)
    parser.add_argument("--normalize-scale", action="store_true")
    parser.add_argument("--pow2-atlas", action="store_true", help="Pad the final atlas canvas up to power-of-two dimensions.")
    parser.add_argument("--frames-dir")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
