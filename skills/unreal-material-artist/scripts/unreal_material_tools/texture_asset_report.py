from __future__ import annotations

import argparse
import json
import struct
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


def collect_paths(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            found.extend(item for item in path.rglob("*") if item.suffix.lower() in IMAGE_EXTENSIONS)
        elif path.exists():
            found.append(path)
        else:
            found.append(path)
    return sorted(found)


def png_header(path: Path) -> dict[str, Any] | None:
    with path.open("rb") as handle:
        header = handle.read(33)
    if not header.startswith(b"\x89PNG\r\n\x1a\n") or header[12:16] != b"IHDR":
        return None
    width, height, bit_depth, color_type = struct.unpack(">IIBB", header[16:26])
    return {
        "format": "PNG",
        "width": width,
        "height": height,
        "mode": f"png_color_type_{color_type}",
        "has_alpha": color_type in {4, 6},
        "bit_depth": bit_depth,
        "metadata_source": "png_header",
    }


def image_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "warnings": ["file does not exist"]}
    try:
        from PIL import Image, ImageStat  # type: ignore

        with Image.open(path) as image:
            mode = image.mode
            has_alpha = "A" in mode or mode in {"LA", "PA"}
            stats: dict[str, Any] = {}
            try:
                stat = ImageStat.Stat(image.convert("RGBA"))
                stats = {
                    "channel_min": [round(pair[0], 3) for pair in stat.extrema],
                    "channel_max": [round(pair[1], 3) for pair in stat.extrema],
                    "channel_mean": [round(v, 3) for v in stat.mean],
                }
            except Exception:
                stats = {}
            return {
                "path": str(path),
                "exists": True,
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": mode,
                "has_alpha": has_alpha,
                "metadata_source": "pillow",
                "stats": stats,
            }
    except Exception:
        if path.suffix.lower() == ".png":
            header = png_header(path)
            if header:
                return {"path": str(path), "exists": True, **header}
        return {
            "path": str(path),
            "exists": True,
            "format": path.suffix.lower().lstrip(".") or "unknown",
            "width": None,
            "height": None,
            "mode": "unknown",
            "has_alpha": None,
            "metadata_source": "extension_only",
        }


def analyze_texture(info: dict[str, Any], role: str, grid: tuple[int, int] | None) -> dict[str, Any]:
    warnings: list[str] = list(info.get("warnings") or [])
    width = info.get("width")
    height = info.get("height")
    if not info.get("exists"):
        return {**info, "role": role, "warnings": warnings}

    if isinstance(width, int) and isinstance(height, int):
        info["power_of_two"] = is_power_of_two(width) and is_power_of_two(height)
        info["square"] = width == height
        info["megapixels"] = round((width * height) / 1_000_000, 3)
        info["recommended_power_of_two"] = {
            "width": next_power_of_two(width),
            "height": next_power_of_two(height),
        }
        if not info["power_of_two"]:
            warnings.append(
                "non-power-of-two textures may not stream or mip as expected in UE; "
                f"consider {info['recommended_power_of_two']['width']}x{info['recommended_power_of_two']['height']}"
            )
        if width > 2048 or height > 2048:
            warnings.append("large texture; confirm memory budget and intended screen coverage")
        if role in {"flipbook", "atlas"}:
            if not grid:
                warnings.append("flipbook/atlas role should provide --grid COLSxROWS")
            else:
                cols, rows = grid
                integral = width % cols == 0 and height % rows == 0
                cell_w = width // cols if integral else None
                cell_h = height // rows if integral else None
                info["grid"] = {
                    "cols": cols,
                    "rows": rows,
                    "integral_cells": integral,
                    "cell_width": cell_w,
                    "cell_height": cell_h,
                    "cell_power_of_two": bool(cell_w and cell_h and is_power_of_two(cell_w) and is_power_of_two(cell_h)),
                }
                if not integral:
                    warnings.append("image dimensions are not evenly divisible by the requested grid")
                elif cell_w != cell_h:
                    warnings.append("atlas cells are not square; confirm SubUV expectations")
                elif not info["grid"]["cell_power_of_two"]:
                    warnings.append("atlas cells are not power-of-two; prefer 32/64/128/256-sized cells when possible")
        if role in {"sprite", "mask", "flipbook", "atlas"} and info.get("has_alpha") is False:
            warnings.append("role usually needs alpha or clean black-background extraction")
        if role in {"mask", "packed", "flow", "normal"}:
            warnings.append("technical/data texture: import with sRGB disabled and validate channels")
    else:
        warnings.append("could not read dimensions; install Pillow or use PNG for stronger checks")

    return {**info, "role": role, "warnings": warnings}


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Texture Asset Report", ""]
    for item in report["textures"]:
        lines.extend(
            [
                f"## {Path(item['path']).name}",
                "",
                f"- Path: `{item['path']}`",
                f"- Role: `{item.get('role')}`",
                f"- Format: `{item.get('format')}`",
                f"- Size: `{item.get('width')}x{item.get('height')}`",
                f"- Alpha: `{item.get('has_alpha')}`",
                f"- Power of two: `{item.get('power_of_two')}`",
                f"- Recommended POT: `{item.get('recommended_power_of_two', {}).get('width')}x{item.get('recommended_power_of_two', {}).get('height')}`",
                "",
                "Warnings:",
            ]
        )
        warnings = item.get("warnings") or []
        if warnings:
            lines.extend(f"- {warning}" for warning in warnings)
        else:
            lines.append("- No first-pass warnings.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    grid = parse_grid(args.grid)
    paths = collect_paths(args.paths)
    textures = [analyze_texture(image_info(path), args.role, grid) for path in paths]
    report = {
        "tool": "texture_asset_report",
        "role": args.role,
        "grid": args.grid,
        "textures": textures,
    }
    effect = slugify(args.effect or "texture-assets")
    out = Path(args.out) if args.out else default_report_path(ctx, "textures", effect, "texture-asset-report", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect generated texture files for UE material readiness.")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect")
    parser.add_argument("--role", default="sprite", choices=["sprite", "mask", "packed", "normal", "flow", "flipbook", "atlas", "albedo", "ramp", "noise"])
    parser.add_argument("--grid", help="Atlas or flipbook grid, such as 4x4 or 8x8.")
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
