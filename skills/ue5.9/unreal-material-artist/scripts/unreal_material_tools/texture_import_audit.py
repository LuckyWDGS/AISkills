"""Audit Unreal texture import settings for material readiness through Epic's built-in MCP.

One ProgrammaticToolset script reads each texture's asset-registry tags (format,
dimensions, sRGB, compression, LOD group, mip generation, alpha) and its size.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, run_tool_script


# Report contract; bump when a consumer-visible field changes. Version 1 was the UnrealBridge-era report.
SCHEMA_VERSION = "texture_import_audit/2"
COVERAGE_GAPS = [
    "MCP exposes no mip count or resource size: mips are judged from MipGenSettings "
    "(TMGS_NoMipmaps = one mip) and --max-resource-bytes is not checked.",
]


ROLE_CHOICES = [
    "albedo",
    "emissive",
    "sprite",
    "mask",
    "packed",
    "normal",
    "flow",
    "flipbook",
    "atlas",
    "ui",
    "ramp",
    "noise",
]


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


def asset_package_path(path: str) -> str:
    head, _, leaf = path.rpartition("/")
    return f"{head}/{leaf.split('.', 1)[0]}" if head else path


def build_collect_script(texture_paths: list[str]) -> str:
    """ProgrammaticToolset script; missing textures are reported, not fatal."""
    return textwrap.dedent(
        """
        import json

        PATHS = __PATHS__
        A = "editor_toolset.toolsets.asset.AssetTools."
        T = "editor_toolset.toolsets.texture.TextureTools."

        def call(tool, **args):
            return json.loads(json.dumps(execute_tool(tool, json.dumps(args))["returnValue"]))

        def run():
            rows = []
            for path in PATHS:
                if not call(A + "exists", path=path):
                    rows.append({"asset_path": path, "found": False})
                    continue
                leaf = path.rsplit("/", 1)[-1]
                size = call(T + "get_size", texture={"refPath": path + "." + leaf})
                rows.append({"asset_path": path, "found": True, "size": size,
                             "tags": call(A + "get_asset_tags", asset_path=path)})
            return {"textures": rows}
        """
    ).strip().replace("__PATHS__", json.dumps(texture_paths))


def _flag(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def texture_info(row: dict[str, Any]) -> dict[str, Any]:
    """One collected row in the report's texture shape."""
    if not row.get("found"):
        return {"asset_path": row["asset_path"], "found": False}
    tags = row.get("tags") or {}
    size = row.get("size") or {}
    mip_gen = str(tags.get("MipGenSettings") or "")
    return {
        "asset_path": row["asset_path"],
        "found": True,
        "width": int(size.get("x") or 0),
        "height": int(size.get("y") or 0),
        "num_mips": 1 if mip_gen == "TMGS_NoMipmaps" else None,
        "mip_gen_settings": mip_gen,
        "pixel_format": str(tags.get("Format") or ""),
        "compression_settings": str(tags.get("CompressionSettings") or ""),
        "lod_group": str(tags.get("LODGroup") or ""),
        "srgb": _flag(tags.get("SRGB")),
        "never_stream": _flag(tags.get("NeverStream")),
        "has_alpha": _flag(tags.get("HasAlphaChannel")),
        "virtual_texture_streaming": _flag(tags.get("VirtualTextureStreaming")),
        "resource_size_bytes": None,
    }


def collect(skill_root: Path, texture_paths: list[str], *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
            project: str | None = None) -> list[dict[str, Any]]:
    paths = [asset_package_path(path) for path in texture_paths]
    raw = run_tool_script(skill_root, build_collect_script(paths), url=url, timeout=timeout, project=project)
    return [texture_info(row) for row in raw["textures"]]


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def next_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def analyze_texture(
    info: dict[str, Any],
    role: str,
    grid: tuple[int, int] | None,
    max_dimension: int,
    max_bytes: int | None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not info.get("found"):
        add("error", "missing_asset", "Texture asset was not found in Unreal.")
        return {**info, "role": role, "findings": findings}

    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    compression = str(info.get("compression_settings") or "")
    lod_group = str(info.get("lod_group") or "")
    srgb = bool(info.get("srgb"))
    num_mips = info.get("num_mips")  # None: mips generated, count unknown over MCP
    has_mips = num_mips is None or int(num_mips) > 1
    resource_size = int(info.get("resource_size_bytes") or 0)

    info["power_of_two"] = is_power_of_two(width) and is_power_of_two(height)
    info["megabytes"] = round(resource_size / (1024 * 1024), 3) if resource_size else 0.0
    info["recommended_power_of_two"] = {
        "width": next_power_of_two(width) if width > 0 else None,
        "height": next_power_of_two(height) if height > 0 else None,
    }

    if width <= 0 or height <= 0:
        add("error", "invalid_size", "Texture dimensions are invalid.")
    if width > max_dimension or height > max_dimension:
        add("warning", "oversized", f"Texture exceeds the configured max dimension of {max_dimension}.")
    if max_bytes is not None and resource_size > max_bytes:
        add("warning", "resource_budget", "Texture resource size exceeds the configured byte budget.")
    if role != "ui" and not info["power_of_two"]:
        add(
            "warning",
            "non_power_of_two",
            "Texture is not power-of-two; confirm streaming and mip expectations. "
            f"Typical recommendation: {info['recommended_power_of_two']['width']}x{info['recommended_power_of_two']['height']}.",
        )
    if role in {"mask", "packed", "flow", "normal", "ramp"} and srgb:
        add("warning", "srgb_enabled", f"{role} textures should usually import with sRGB disabled.")
    if role in {"albedo", "emissive", "sprite", "ui"} and not srgb:
        add("warning", "srgb_disabled", f"{role} textures usually expect sRGB enabled unless they are pure data.")
    if role == "normal" and compression.lower() != "tc_normalmap":
        add("warning", "normal_compression", "Normal maps should usually use TC_Normalmap compression.")
    if role in {"mask", "packed"} and compression.lower() == "tc_default":
        add("warning", "data_compression", "Mask/packed textures often want mask- or grayscale-style compression, not TC_Default.")
    if role == "ui" and "ui" not in lod_group.lower():
        add("warning", "ui_lod_group", "UI textures usually belong to a UI LOD group.")
    if role == "ui" and has_mips:
        add("info", "ui_mips", "UI textures often disable mips unless scaling behavior needs them.")
    if role in {"flipbook", "atlas"}:
        if not grid:
            add("warning", "missing_grid", "Flipbook/atlas audit should provide --grid COLSxROWS.")
        else:
            cols, rows = grid
            if width % cols != 0 or height % rows != 0:
                add("error", "grid_divisibility", "Texture dimensions are not evenly divisible by the requested grid.")
            else:
                cell_w = width // cols
                cell_h = height // rows
                info["grid"] = {
                    "cols": cols,
                    "rows": rows,
                    "cell_width": cell_w,
                    "cell_height": cell_h,
                    "cell_power_of_two": is_power_of_two(cell_w) and is_power_of_two(cell_h),
                }
                if cell_w != cell_h:
                    add("warning", "cell_shape", "Atlas cells are not square; confirm SubUV expectations.")
                if not info["grid"]["cell_power_of_two"]:
                    add("warning", "cell_power_of_two", "Atlas cell size is not power-of-two; prefer 32/64/128/256-sized cells when possible.")

    if role in {"sprite", "flipbook", "atlas"} and not has_mips:
        add("info", "mip_count", "Texture has one mip; confirm that close-only usage makes this acceptable.")

    return {**info, "role": role, "findings": findings}


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Texture Import Audit", ""]
    for item in report["textures"]:
        lines.extend(
            [
                f"## {item.get('asset_path', '')}",
                "",
                f"- Role: `{item.get('role')}`",
                f"- Found: `{item.get('found')}`",
                f"- Size: `{item.get('width')}x{item.get('height')}`",
                f"- Mip generation: `{item.get('mip_gen_settings')}`",
                f"- Pixel format: `{item.get('pixel_format')}`",
                f"- Compression: `{item.get('compression_settings')}`",
                f"- LOD group: `{item.get('lod_group')}`",
                f"- sRGB: `{item.get('srgb')}`",
                f"- Power of two: `{item.get('power_of_two')}`",
                f"- Recommended POT: `{item.get('recommended_power_of_two', {}).get('width')}x{item.get('recommended_power_of_two', {}).get('height')}`",
                f"- Never stream: `{item.get('never_stream')}`",
                "",
                "Findings:",
            ]
        )
        findings = item.get("findings") or []
        if findings:
            lines.extend(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}" for finding in findings)
        else:
            lines.append("- No first-pass findings.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_report(textures: list[dict[str, Any]], *, role: str, grid_text: str | None, max_dimension: int,
                 max_resource_bytes: int | None) -> dict[str, Any]:
    grid = parse_grid(grid_text)
    return {
        "tool": "texture_import_audit",
        "schema_version": SCHEMA_VERSION,
        "transport": "epic-mcp ProgrammaticToolset",
        "role": role,
        "grid": grid_text,
        "textures": [analyze_texture(dict(item), role, grid, max_dimension, max_resource_bytes) for item in textures],
        "coverage_gaps": COVERAGE_GAPS,
    }


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    textures = collect(ctx.skill_root, args.texture_paths, url=args.mcp_url, timeout=args.timeout, project=args.project)
    report = build_report(textures, role=args.role, grid_text=args.grid, max_dimension=args.max_dimension,
                          max_resource_bytes=args.max_resource_bytes)
    effect = slugify(args.effect or args.role or "textures")
    stem = slugify("-".join(args.texture_paths[:2]))
    out = Path(args.out) if args.out else default_report_path(ctx, "imports", effect, f"texture-import-audit-{stem}", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Unreal texture import settings for material readiness.")
    parser.add_argument("texture_paths", nargs="+")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--role", default="sprite", choices=ROLE_CHOICES)
    parser.add_argument("--grid")
    parser.add_argument("--max-dimension", type=int, default=2048)
    parser.add_argument("--max-resource-bytes", type=int)
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
