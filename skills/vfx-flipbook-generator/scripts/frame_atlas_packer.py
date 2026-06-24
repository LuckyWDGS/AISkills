from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


def parse_grid(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("*", "x").replace("×", "x")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("grid must look like 8x8")
    try:
        columns = int(parts[0])
        rows = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("grid must contain integer columns and rows") from exc
    if columns <= 0 or rows <= 0:
        raise argparse.ArgumentTypeError("grid columns and rows must be positive")
    return columns, rows


def parse_size(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("*", "x").replace("×", "x")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must look like 256x256")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must contain integer width and height") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size width and height must be positive")
    return width, height


def parse_background(value: str) -> tuple[int, int, int, int]:
    if value.lower() == "transparent":
        return (0, 0, 0, 0)
    if value.startswith("#"):
        text = value[1:]
        if len(text) == 6:
            text += "ff"
        if len(text) != 8:
            raise argparse.ArgumentTypeError("background hex must be #RRGGBB or #RRGGBBAA")
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4, 6))  # type: ignore[return-value]
    parts = [part.strip() for part in value.split(",")]
    if len(parts) not in {3, 4}:
        raise argparse.ArgumentTypeError("background must be transparent, #RRGGBB, #RRGGBBAA, or r,g,b[,a]")
    channels = [int(part) for part in parts]
    if len(channels) == 3:
        channels.append(255)
    if any(channel < 0 or channel > 255 for channel in channels):
        raise argparse.ArgumentTypeError("background channels must be 0-255")
    return tuple(channels)  # type: ignore[return-value]


def nearest_power_of_two(value: int) -> int:
    lower = 1 << (value.bit_length() - 1)
    if lower == value:
        return value
    upper = lower << 1
    return lower if value - lower <= upper - value else upper


def ceil_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def atlas_size_for_mode(raw_size: tuple[int, int], mode: str) -> tuple[int, int]:
    if mode == "raw":
        return raw_size
    if mode == "nearest-power-of-two":
        return nearest_power_of_two(raw_size[0]), nearest_power_of_two(raw_size[1])
    if mode == "pad-to-power-of-two":
        return ceil_power_of_two(raw_size[0]), ceil_power_of_two(raw_size[1])
    raise ValueError(f"Unknown atlas size mode: {mode}")


def normalize_image(source: Path, cell_size: tuple[int, int], fit: str, background: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        if fit == "stretch":
            return image.resize(cell_size, Image.Resampling.LANCZOS)
        if fit == "cover":
            return ImageOps.fit(image, cell_size, method=Image.Resampling.LANCZOS)
        contained = ImageOps.contain(image, cell_size, method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", cell_size, background)
        x = (cell_size[0] - contained.width) // 2
        y = (cell_size[1] - contained.height) // 2
        canvas.alpha_composite(contained, (x, y))
        return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack a folder of frame PNGs into a flipbook atlas.")
    parser.add_argument("frames_dir", help="Folder containing frame images.")
    parser.add_argument("--pattern", default="*.png", help="Glob pattern inside frames_dir. Default: *.png")
    parser.add_argument("--grid", required=True, type=parse_grid, help="Grid such as 12x12.")
    parser.add_argument("--cell-size", required=True, type=parse_size, help="Cell size such as 256x256.")
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    parser.add_argument("--background", default="transparent")
    parser.add_argument("--atlas-size-mode", choices=("nearest-power-of-two", "pad-to-power-of-two", "raw"), default="nearest-power-of-two")
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument("--atlas-name", default="flipbook_atlas.png")
    parser.add_argument("--effect", default="", help="Optional effect name for manifest readability.")
    args = parser.parse_args()

    frames_dir = Path(args.frames_dir).expanduser().resolve()
    if not frames_dir.exists():
        raise SystemExit(f"Frames folder does not exist: {frames_dir}")

    frame_paths = sorted(path for path in frames_dir.glob(args.pattern) if path.is_file())
    if not frame_paths:
        raise SystemExit(f"No frames matched pattern '{args.pattern}' in {frames_dir}")

    columns, rows = args.grid
    cells = columns * rows
    frame_paths = frame_paths[:cells]
    background = parse_background(args.background)
    cell_size = args.cell_size
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    atlas_path = out_dir / args.atlas_name

    raw_size = (columns * cell_size[0], rows * cell_size[1])
    final_size = atlas_size_for_mode(raw_size, args.atlas_size_mode)
    grid_divides_final = final_size[0] % columns == 0 and final_size[1] % rows == 0
    final_cell_size = (
        {"width": final_size[0] // columns, "height": final_size[1] // rows}
        if grid_divides_final
        else None
    )
    atlas = Image.new("RGBA", raw_size, background)
    for index, frame_path in enumerate(frame_paths):
        normalized = normalize_image(frame_path, cell_size, args.fit, background)
        x = (index % columns) * cell_size[0]
        y = (index // columns) * cell_size[1]
        atlas.alpha_composite(normalized, (x, y))

    if args.atlas_size_mode == "nearest-power-of-two" and final_size != raw_size:
        atlas = atlas.resize(final_size, Image.Resampling.LANCZOS)
    elif args.atlas_size_mode == "pad-to-power-of-two" and final_size != raw_size:
        padded = Image.new("RGBA", final_size, background)
        padded.alpha_composite(atlas, (0, 0))
        atlas = padded
    atlas.save(atlas_path)

    manifest = {
        "tool": "frame_atlas_packer",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "effect_name": args.effect,
        "frames_dir": str(frames_dir),
        "matched_pattern": args.pattern,
        "input_frame_count": len(frame_paths),
        "grid": {
            "columns": columns,
            "rows": rows,
            "cells": cells,
            "cell_width": cell_size[0],
            "cell_height": cell_size[1],
            "fit": args.fit,
            "background": args.background,
        },
        "atlas": {
            "path": str(atlas_path),
            "width": final_size[0],
            "height": final_size[1],
            "raw_width": raw_size[0],
            "raw_height": raw_size[1],
            "size_mode": args.atlas_size_mode,
            "power_of_two": is_power_of_two(final_size[0]) and is_power_of_two(final_size[1]),
            "grid_divides_atlas": grid_divides_final,
            "cell_width_exact": final_cell_size["width"] if final_cell_size else None,
            "cell_height_exact": final_cell_size["height"] if final_cell_size else None,
            "snap_method": (
                "none"
                if final_size == raw_size
                else ("scale" if args.atlas_size_mode == "nearest-power-of-two" else "pad")
            ),
            "snapped_from": None if final_size == raw_size else {"width": raw_size[0], "height": raw_size[1]},
        },
        "ue_notes": {
            "sub_uv_columns": columns,
            "sub_uv_rows": rows,
            "first_frame": 0,
            "last_frame": max(0, len(frame_paths) - 1),
            "blank_cells": max(0, cells - len(frame_paths)),
            "frame_order": "row-major-left-to-right-top-to-bottom",
            "grid_divides_atlas": grid_divides_final,
            "sub_uv_direct_ready": grid_divides_final
            and is_power_of_two(final_size[0])
            and is_power_of_two(final_size[1]),
            "sub_uv_risk": None
            if grid_divides_final
            else "atlas dimensions do not divide evenly by grid; direct UE SubUV can jitter or sample offset",
            "recommended_end_frame": max(0, len(frame_paths) - 1),
        },
        "frame_files": [path.name for path in frame_paths],
    }
    manifest_path = out_dir / "flipbook-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = [
        f"# Flipbook Atlas: {args.effect or atlas_path.stem}",
        "",
        f"- Frames dir: `{frames_dir}`",
        f"- Frames used: `{len(frame_paths)}`",
        f"- Grid: `{columns}x{rows}` ({cells} cells)",
        f"- Cell: `{cell_size[0]}x{cell_size[1]}`",
        f"- Atlas: `{atlas_path}` (`{final_size[0]}x{final_size[1]}`)",
    ]
    if final_size != raw_size:
        summary[-1] += f" snapped from `{raw_size[0]}x{raw_size[1]}` via `{manifest['atlas']['snap_method']}`"
    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
