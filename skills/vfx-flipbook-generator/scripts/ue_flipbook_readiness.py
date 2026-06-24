from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat


SUPPORTED_EXTENSIONS = {".png", ".tga", ".exr", ".hdr", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp"}
ALPHA_POLICIES = {"auto", "true-alpha", "luma", "additive", "opaque"}


@dataclass(slots=True)
class Finding:
    severity: str
    code: str
    message: str


@dataclass(slots=True)
class ReadinessReport:
    status: str
    atlas_path: str
    mode: str
    width: int
    height: int
    columns: int
    rows: int
    cells: int
    frame_count: int
    cell_width: int | None
    cell_height: int | None
    extension: str
    power_of_two: bool
    grid_divides_atlas: bool
    has_alpha_channel: bool
    alpha_varies: bool
    alpha_policy: str
    likely_black_luma_sheet: bool
    blank_used_cells: int | None
    border_contact_cells: int | None
    findings: list[Finding]


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


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def load_manifest(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    if not path.exists():
        raise SystemExit(f"Manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def infer_manifest_path(atlas_path: Path) -> Path | None:
    candidate = atlas_path.parent / "flipbook-manifest.json"
    return candidate if candidate.exists() else None


def manifest_grid(manifest: dict[str, Any]) -> tuple[int, int] | None:
    grid = manifest.get("grid") or {}
    if "columns" in grid and "rows" in grid:
        return int(grid["columns"]), int(grid["rows"])
    ue_notes = manifest.get("ue_notes") or {}
    if "sub_uv_columns" in ue_notes and "sub_uv_rows" in ue_notes:
        return int(ue_notes["sub_uv_columns"]), int(ue_notes["sub_uv_rows"])
    return None


def manifest_frame_count(manifest: dict[str, Any]) -> int | None:
    for path in (("sampling", "frame_count"), ("grid", "input_frame_count")):
        cursor: Any = manifest
        for key in path:
            if not isinstance(cursor, dict) or key not in cursor:
                cursor = None
                break
            cursor = cursor[key]
        if cursor is not None:
            return int(cursor)
    ue_notes = manifest.get("ue_notes") or {}
    if "last_frame" in ue_notes:
        return int(ue_notes["last_frame"]) + 1
    return None


def mean_luma(image: Image.Image) -> float:
    return float(ImageStat.Stat(image.convert("L")).mean[0])


def border_luma(image: Image.Image) -> float:
    if image.width <= 2 or image.height <= 2:
        return mean_luma(image)
    strips = [
        image.crop((0, 0, image.width, 1)),
        image.crop((0, image.height - 1, image.width, image.height)),
        image.crop((0, 0, 1, image.height)),
        image.crop((image.width - 1, 0, image.width, image.height)),
    ]
    values = [mean_luma(strip) for strip in strips]
    return sum(values) / len(values)


def alpha_mean(image: Image.Image) -> float:
    return float(ImageStat.Stat(image.getchannel("A")).mean[0])


def evaluate_cells(
    image: Image.Image,
    columns: int,
    rows: int,
    frame_count: int,
    *,
    alpha_varies: bool,
    likely_black_luma_sheet: bool,
) -> tuple[int, int]:
    cell_width = image.width // columns
    cell_height = image.height // rows
    blank = 0
    border_contact = 0
    used = min(frame_count, columns * rows)
    for index in range(used):
        column = index % columns
        row = index // columns
        cell = image.crop(
            (
                column * cell_width,
                row * cell_height,
                (column + 1) * cell_width,
                (row + 1) * cell_height,
            )
        )
        luma = mean_luma(cell)
        alpha = alpha_mean(cell)
        if alpha_varies:
            if alpha < 2.0:
                blank += 1
            if border_luma(cell.getchannel("A")) > 12.0:
                border_contact += 1
        elif likely_black_luma_sheet:
            if luma < 2.0:
                blank += 1
            if border_luma(cell) > 12.0:
                border_contact += 1
    return blank, border_contact


def infer_luma_sheet(image: Image.Image, alpha_varies: bool) -> bool:
    if alpha_varies:
        return False
    rgba = image.convert("RGBA")
    width, height = rgba.size
    samples = [
        rgba.crop((0, 0, max(1, width // 16), max(1, height // 16))),
        rgba.crop((width - max(1, width // 16), 0, width, max(1, height // 16))),
        rgba.crop((0, height - max(1, height // 16), max(1, width // 16), height)),
        rgba.crop((width - max(1, width // 16), height - max(1, height // 16), width, height)),
    ]
    corner_luma = sum(mean_luma(sample) for sample in samples) / len(samples)
    full_luma = mean_luma(rgba)
    return corner_luma < 8.0 and full_luma > 1.0


def add(finding_list: list[Finding], severity: str, code: str, message: str) -> None:
    finding_list.append(Finding(severity=severity, code=code, message=message))


def build_report(
    atlas_path: Path,
    *,
    columns: int,
    rows: int,
    frame_count: int | None,
    mode: str,
    alpha_policy: str,
    max_texture_size: int,
) -> ReadinessReport:
    findings: list[Finding] = []
    extension = atlas_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        add(findings, "fail", "unsupported_extension", f"Unreal import may not support `{extension}` as a texture source.")

    with Image.open(atlas_path) as opened:
        original_mode = opened.mode
        bands = opened.getbands()
        rgba = opened.convert("RGBA")

    width, height = rgba.size
    cells = columns * rows
    frames = frame_count if frame_count is not None else cells
    power_of_two = is_power_of_two(width) and is_power_of_two(height)
    grid_divides = width % columns == 0 and height % rows == 0
    cell_width = width // columns if grid_divides else None
    cell_height = height // rows if grid_divides else None
    has_alpha_channel = "A" in bands
    alpha_min, alpha_max = rgba.getchannel("A").getextrema()
    alpha_varies = bool(has_alpha_channel and alpha_min < 255)
    likely_black_luma_sheet = infer_luma_sheet(rgba, alpha_varies)

    if not power_of_two:
        add(findings, "fail", "non_power_of_two", "Atlas width and height should be power-of-two for default UE/Niagara texture delivery.")
    if width > max_texture_size or height > max_texture_size:
        add(findings, "warn", "texture_budget", f"Atlas exceeds the configured `{max_texture_size}` max texture budget on at least one axis.")
    if not grid_divides:
        add(
            findings,
            "fail",
            "grid_not_divisible",
            "Atlas dimensions must divide evenly by columns and rows for direct SubUV/Flipbook sampling.",
        )
    if frames > cells:
        add(findings, "fail", "too_many_frames", f"Frame count `{frames}` exceeds grid cells `{cells}`.")
    if frames < cells:
        add(findings, "warn", "unused_cells", f"`{cells - frames}` grid cells are unused; make sure Niagara end frame is `{max(0, frames - 1)}`.")
    if columns <= 1 and rows <= 1 and mode in {"niagara", "both"}:
        add(findings, "warn", "single_cell", "A single-cell texture can be used by Niagara sprites, but it is not a SubUV animation.")
    if power_of_two and (not is_power_of_two(columns) or not is_power_of_two(rows)):
        add(
            findings,
            "warn" if grid_divides else "fail",
            "non_power_of_two_grid",
            "Power-of-two atlases only divide cleanly into power-of-two row/column counts; prefer 4x4, 8x8, 16x8, or 16x16 for UE SubUV.",
        )

    if alpha_policy not in ALPHA_POLICIES:
        raise SystemExit(f"Unknown alpha policy: {alpha_policy}")
    if alpha_policy == "true-alpha" and not alpha_varies:
        add(findings, "fail", "missing_true_alpha", "The requested true-alpha route needs a varying alpha channel.")
    elif alpha_policy == "auto" and not alpha_varies:
        if likely_black_luma_sheet:
            add(
                findings,
                "warn",
                "luma_opacity_required",
                "Atlas has no useful alpha but looks like a black-background luma sheet; material must derive opacity from luminance or use Additive.",
            )
        else:
            add(findings, "fail", "missing_opacity_route", "Atlas has no useful alpha and does not look like a clean black luma sheet.")
    elif alpha_policy == "luma" and not likely_black_luma_sheet and not alpha_varies:
        add(findings, "warn", "weak_luma_sheet", "Luma route was requested, but the atlas does not look like a clean black-background mask.")

    blank_used_cells: int | None = None
    border_contact_cells: int | None = None
    if grid_divides:
        blank_used_cells, border_contact_cells = evaluate_cells(
            rgba,
            columns,
            rows,
            frames,
            alpha_varies=alpha_varies,
            likely_black_luma_sheet=likely_black_luma_sheet or alpha_policy == "luma",
        )
        if blank_used_cells >= min(frames, cells):
            add(findings, "fail", "all_used_cells_blank", "All used cells appear blank under the selected opacity route.")
        elif blank_used_cells:
            add(findings, "warn", "blank_used_cells", f"`{blank_used_cells}` used cells appear nearly blank; verify this is intentional birth/fade timing.")
        if border_contact_cells:
            add(findings, "warn", "cell_edge_contact", f"`{border_contact_cells}` used cells have opacity/luma on cell borders; check for crop or missing gutter.")

    if alpha_varies and original_mode not in {"RGBA", "LA", "PA"}:
        add(findings, "note", "converted_alpha", f"Image mode `{original_mode}` was converted to RGBA for analysis.")
    if mode in {"niagara", "both"} and not any(f.code == "grid_not_divisible" for f in findings):
        add(findings, "note", "niagara_contract", f"Set Sprite Renderer Sub Image Size to `{columns}x{rows}` and SubUV end frame to `{max(0, frames - 1)}`.")
    if mode in {"material", "both"}:
        add(findings, "note", "material_contract", "Material must expose the atlas texture, correct row/column count, opacity route, ParticleColor tint/alpha, and blend mode.")

    status = "ready"
    if any(f.severity == "fail" for f in findings):
        status = "blocked"
    elif any(f.severity == "warn" for f in findings):
        status = "conditional"

    return ReadinessReport(
        status=status,
        atlas_path=str(atlas_path.resolve()),
        mode=mode,
        width=width,
        height=height,
        columns=columns,
        rows=rows,
        cells=cells,
        frame_count=frames,
        cell_width=cell_width,
        cell_height=cell_height,
        extension=extension,
        power_of_two=power_of_two,
        grid_divides_atlas=grid_divides,
        has_alpha_channel=has_alpha_channel,
        alpha_varies=alpha_varies,
        alpha_policy=alpha_policy,
        likely_black_luma_sheet=likely_black_luma_sheet,
        blank_used_cells=blank_used_cells,
        border_contact_cells=border_contact_cells,
        findings=findings,
    )


def report_to_markdown(report: ReadinessReport) -> str:
    lines = [
        f"# UE Flipbook Readiness: {report.status}",
        "",
        f"- Atlas: `{report.atlas_path}`",
        f"- Mode: `{report.mode}`",
        f"- Size: `{report.width}x{report.height}`",
        f"- Grid: `{report.columns}x{report.rows}` ({report.cells} cells)",
        f"- Frames: `{report.frame_count}`",
        f"- Cell: `{report.cell_width}x{report.cell_height}`" if report.cell_width else "- Cell: `not evenly divisible`",
        f"- Power of two: `{report.power_of_two}`",
        f"- Grid divides atlas: `{report.grid_divides_atlas}`",
        f"- Alpha varies: `{report.alpha_varies}`",
        f"- Likely black luma sheet: `{report.likely_black_luma_sheet}`",
        "",
        "## Findings",
    ]
    for finding in report.findings:
        lines.append(f"- `{finding.severity}` `{finding.code}`: {finding.message}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a flipbook atlas is directly usable by UE materials and Niagara SubUV.")
    parser.add_argument("atlas", help="Atlas image path.")
    parser.add_argument("--manifest", help="Optional flipbook-manifest.json. Defaults to a sibling manifest when present.")
    parser.add_argument("--grid", type=parse_grid, help="Grid such as 8x8. Defaults to manifest grid when available.")
    parser.add_argument("--frames", type=int, help="Used frame count. Defaults to manifest frame count or grid cells.")
    parser.add_argument("--mode", choices=("material", "niagara", "both", "random-sheet"), default="both")
    parser.add_argument("--alpha-policy", choices=sorted(ALPHA_POLICIES), default="auto")
    parser.add_argument("--max-texture-size", type=int, default=4096)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--out", help="Optional report path. Extension controls nothing; content follows --json.")
    args = parser.parse_args()

    atlas_path = Path(args.atlas).expanduser().resolve()
    if not atlas_path.exists():
        raise SystemExit(f"Atlas does not exist: {atlas_path}")
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else infer_manifest_path(atlas_path)
    manifest = load_manifest(manifest_path)
    grid = args.grid or manifest_grid(manifest)
    if grid is None:
        raise SystemExit("Grid is required. Pass --grid or provide a manifest with grid columns/rows.")
    frames = args.frames if args.frames is not None else manifest_frame_count(manifest)
    report = build_report(
        atlas_path,
        columns=grid[0],
        rows=grid[1],
        frame_count=frames,
        mode=args.mode,
        alpha_policy=args.alpha_policy,
        max_texture_size=args.max_texture_size,
    )
    payload = json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n"
    output = payload if args.json else report_to_markdown(report)
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
