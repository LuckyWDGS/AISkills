from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter


@dataclass(slots=True)
class ResizeResult:
    target_size: str
    primary_path: str
    alpha_path: str | None
    manifest_path: str


def parse_grid(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("*", "x").replace("x", "x").replace("×", "x")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("grid must look like 4x4")
    try:
        columns = int(parts[0])
        rows = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("grid must contain integer columns and rows") from exc
    if columns <= 0 or rows <= 0:
        raise argparse.ArgumentTypeError("grid columns and rows must be positive")
    return columns, rows


def parse_target_size(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("*", "x").replace("×", "x")
    if "x" in normalized:
        parts = normalized.split("x")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("target size must look like 2048 or 2048x2048")
        try:
            width = int(parts[0])
            height = int(parts[1])
        except ValueError as exc:
            raise argparse.ArgumentTypeError("target size must contain integers") from exc
    else:
        try:
            width = int(normalized)
            height = width
        except ValueError as exc:
            raise argparse.ArgumentTypeError("target size must contain integers") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("target dimensions must be positive")
    if not is_power_of_two(width) or not is_power_of_two(height):
        raise argparse.ArgumentTypeError("target dimensions must be powers of two")
    return width, height


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def load_manifest(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse manifest: {path}\n{exc}") from exc


def infer_source_manifest(primary: Path) -> Path | None:
    candidate = primary.with_name(primary.stem + "_manifest.json")
    return candidate if candidate.exists() else None


def size_label(size: tuple[int, int]) -> str:
    width, height = size
    if width == height and width % 1024 == 0:
        return f"{width // 1024}k"
    return f"{width}x{height}"


def output_name(source: Path, target_size: tuple[int, int]) -> str:
    width, height = target_size
    replacement = str(width) if width == height else f"{width}x{height}"
    stem = source.stem
    match = re.search(r"_(\d{3,5})(?=$)", stem)
    if match:
        stem = stem[: match.start()] + f"_{replacement}"
    else:
        stem = f"{stem}_{replacement}"
    return f"{stem}{source.suffix}"


def find_output_key(manifest: dict[str, Any], source: Path, fallback: str) -> str:
    outputs = manifest.get("outputs") or {}
    source_resolved = str(source.resolve()).lower()
    for key, value in outputs.items():
        if isinstance(value, str) and str(Path(value).expanduser().resolve()).lower() == source_resolved:
            return key
    return fallback


def resize_image(
    source: Path,
    output: Path,
    target_size: tuple[int, int],
    *,
    unsharp_percent: int = 0,
) -> tuple[int, int]:
    with Image.open(source) as opened:
        source_size = opened.size
        mode = "RGBA" if "A" in opened.getbands() else "RGB"
        image = opened.convert(mode)
        resized = image.resize(target_size, Image.Resampling.LANCZOS)
        if unsharp_percent > 0:
            resized = resized.filter(ImageFilter.UnsharpMask(radius=1.0, percent=unsharp_percent, threshold=2))
        output.parent.mkdir(parents=True, exist_ok=True)
        resized.save(output)
    return source_size


def resize_atlas_pair(
    primary: Path,
    *,
    alpha: Path | None,
    source_manifest: Path | None,
    grid: tuple[int, int],
    targets: list[tuple[int, int]],
    out_dir: Path,
    effect_name: str | None = None,
    unsharp_percent: int = 0,
) -> list[ResizeResult]:
    manifest = load_manifest(source_manifest)
    columns, rows = grid
    results: list[ResizeResult] = []

    for target_size in targets:
        width, height = target_size
        if width % columns != 0 or height % rows != 0:
            raise SystemExit(f"Target {width}x{height} does not divide cleanly by grid {columns}x{rows}.")

        primary_out = out_dir / output_name(primary, target_size)
        alpha_out = out_dir / output_name(alpha, target_size) if alpha else None
        source_size = resize_image(primary, primary_out, target_size, unsharp_percent=unsharp_percent)
        if alpha and alpha_out:
            resize_image(alpha, alpha_out, target_size, unsharp_percent=unsharp_percent)

        target_label = size_label(target_size)
        base_effect = effect_name or manifest.get("effect_name") or primary.stem
        target_effect_name = f"{base_effect}_{target_label}"
        primary_key = find_output_key(manifest, primary, "rgb_preview_atlas")
        outputs: dict[str, str] = {primary_key: str(primary_out.resolve())}
        if alpha and alpha_out:
            alpha_key = find_output_key(manifest, alpha, "rgba_alpha_atlas")
            outputs[alpha_key] = str(alpha_out.resolve())

        new_manifest: dict[str, Any] = {
            "tool": "flipbook_atlas_resizer",
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_atlas": str(primary.resolve()),
            "source_alpha": str(alpha.resolve()) if alpha else None,
            "source_manifest": str(source_manifest.resolve()) if source_manifest else None,
            "source_size": {"width": source_size[0], "height": source_size[1]},
            "effect_name": target_effect_name,
            "usage": manifest.get("usage", "VFX flipbook atlas derivative"),
            "resolution_policy": (
                "High-resolution power-of-two derivative for final delivery/downscale workflows; "
                "prefer native 2K/4K generation when the image provider supports it."
            ),
            "outputs": outputs,
            "grid": {
                "columns": columns,
                "rows": rows,
                "cells": columns * rows,
                "cell_width": width // columns,
                "cell_height": height // rows,
            },
            "atlas": {
                "path": str(primary_out.resolve()),
                "width": width,
                "height": height,
                "source_width": source_size[0],
                "source_height": source_size[1],
                "power_of_two": True,
                "grid_divides_atlas": True,
                "cell_width_exact": width // columns,
                "cell_height_exact": height // rows,
            },
            "ue_notes": {
                **(manifest.get("ue_notes") or {}),
                "sub_uv_columns": columns,
                "sub_uv_rows": rows,
                "first_frame": 0,
                "last_frame": columns * rows - 1,
                "high_resolution_delivery": (
                    f"Use this {width}x{height} atlas as the source and downscale as needed; "
                    "do not upscale a 1024 preview as the only final asset when native 2K/4K generation is available."
                ),
            },
        }
        for key in ("style_contract", "shape_contract", "falloff_contract"):
            if key in manifest:
                new_manifest[key] = manifest[key]

        manifest_path = primary_out.with_name(primary_out.stem + "_manifest.json")
        manifest_path.write_text(json.dumps(new_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(
            ResizeResult(
                target_size=f"{width}x{height}",
                primary_path=str(primary_out.resolve()),
                alpha_path=str(alpha_out.resolve()) if alpha_out else None,
                manifest_path=str(manifest_path.resolve()),
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Resize a flipbook atlas and optional alpha atlas to 2K/4K power-of-two delivery sizes.")
    parser.add_argument("primary", help="Primary atlas PNG.")
    parser.add_argument("--alpha-path", help="Optional paired alpha/support PNG.")
    parser.add_argument("--source-manifest", help="Optional source manifest. Defaults to <primary>_manifest.json when present.")
    parser.add_argument("--grid", required=True, type=parse_grid, help="Atlas grid, e.g. 4x4.")
    parser.add_argument("--targets", nargs="+", default=["2048", "4096"], type=parse_target_size, help="Target sizes, e.g. 2048 4096 or 2048x2048.")
    parser.add_argument("--out-dir", required=True, help="Output folder.")
    parser.add_argument("--effect-name", help="Override effect_name base for generated manifests.")
    parser.add_argument("--unsharp-percent", type=int, default=0, help="Optional post-resize UnsharpMask percent. Default keeps pure resize.")
    args = parser.parse_args()

    primary = Path(args.primary).expanduser().resolve()
    if not primary.exists():
        raise SystemExit(f"Primary atlas does not exist: {primary}")
    alpha = Path(args.alpha_path).expanduser().resolve() if args.alpha_path else None
    if alpha and not alpha.exists():
        raise SystemExit(f"Alpha atlas does not exist: {alpha}")
    source_manifest = Path(args.source_manifest).expanduser().resolve() if args.source_manifest else infer_source_manifest(primary)
    if source_manifest and not source_manifest.exists():
        raise SystemExit(f"Source manifest does not exist: {source_manifest}")
    out_dir = Path(args.out_dir).expanduser().resolve()
    results = resize_atlas_pair(
        primary,
        alpha=alpha,
        source_manifest=source_manifest,
        grid=args.grid,
        targets=args.targets,
        out_dir=out_dir,
        effect_name=args.effect_name,
        unsharp_percent=max(0, args.unsharp_percent),
    )
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
