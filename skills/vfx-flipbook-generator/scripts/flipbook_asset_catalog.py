from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


STATUS_RANK = {"ready": 3, "conditional": 2, "blocked": 1, "unknown": 0}
READY_RE = re.compile(r"^# UE Flipbook Readiness:\s*(?P<status>\w+)\s*$", re.IGNORECASE)
FIELD_RE = re.compile(r"^-\s*(?P<key>[^:]+):\s*(?P<value>.+?)\s*$")
FINDING_RE = re.compile(r"^-\s*`(?P<severity>[^`]+)`\s*`(?P<code>[^`]+)`:\s*(?P<message>.+)$")


@dataclass(slots=True)
class ReadinessInfo:
    path: str
    status: str
    mode: str | None = None
    size: str | None = None
    grid: str | None = None
    frames: int | None = None
    cell: str | None = None
    alpha_varies: bool | None = None
    likely_black_luma_sheet: bool | None = None
    findings: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class AssetEntry:
    name: str
    primary_path: str
    role: str
    usage: str | None
    effect_name: str | None
    grid: str | None
    cells: int | None
    size: str | None
    alpha_path: str | None
    preview_path: str | None
    manifest_path: str | None
    readiness_status: str
    alpha_readiness_status: str | None
    warnings: list[str]
    material_hint: str
    niagara_hint: str
    import_hint: str
    recommendation: str


@dataclass(slots=True)
class Catalog:
    generated_utc: str
    root: str
    entries: list[AssetEntry]
    counts: dict[str, int]


def clean_code_value(value: str) -> str:
    text = value.strip()
    if text.startswith("`") and text.endswith("`"):
        return text[1:-1]
    return text


def parse_bool(value: str) -> bool | None:
    text = clean_code_value(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def parse_int_code(value: str) -> int | None:
    text = clean_code_value(value)
    try:
        return int(text)
    except ValueError:
        return None


def parse_readiness(path: Path) -> ReadinessInfo:
    text = path.read_text(encoding="utf-8")
    status = "unknown"
    atlas = ""
    fields: dict[str, str] = {}
    findings: list[dict[str, str]] = []

    for line in text.splitlines():
        ready_match = READY_RE.match(line)
        if ready_match:
            status = ready_match.group("status").lower()
            continue
        finding_match = FINDING_RE.match(line)
        if finding_match:
            findings.append(finding_match.groupdict())
            continue
        field_match = FIELD_RE.match(line)
        if field_match:
            key = field_match.group("key").strip().lower()
            value = clean_code_value(field_match.group("value"))
            fields[key] = value
            if key == "atlas":
                atlas = value
            continue

    return ReadinessInfo(
        path=atlas or str(path.with_name(path.name.replace("_readiness.md", ".png")).resolve()),
        status=status,
        mode=fields.get("mode"),
        size=fields.get("size"),
        grid=fields.get("grid"),
        frames=parse_int_code(fields["frames"]) if "frames" in fields else None,
        cell=fields.get("cell"),
        alpha_varies=parse_bool(fields["alpha varies"]) if "alpha varies" in fields else None,
        likely_black_luma_sheet=parse_bool(fields["likely black luma sheet"]) if "likely black luma sheet" in fields else None,
        findings=findings,
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse JSON manifest: {path}\n{exc}") from exc


def path_key(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).lower()


def existing_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.exists():
        return path.resolve()
    return None


def inspect_size(path: Path) -> str | None:
    try:
        with Image.open(path) as image:
            return f"{image.width}x{image.height}"
    except OSError:
        return None


def manifest_grid(manifest: dict[str, Any]) -> tuple[str | None, int | None]:
    grid = manifest.get("grid") or {}
    columns = grid.get("columns")
    rows = grid.get("rows")
    cells = grid.get("cells")
    if columns and rows:
        return f"{columns}x{rows}", int(cells) if cells is not None else int(columns) * int(rows)
    ue_notes = manifest.get("ue_notes") or {}
    columns = ue_notes.get("sub_uv_columns")
    rows = ue_notes.get("sub_uv_rows")
    if columns and rows:
        return f"{columns}x{rows}", int(columns) * int(rows)
    return None, None


def manifest_outputs(manifest: dict[str, Any]) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for key, value in (manifest.get("outputs") or {}).items():
        path = existing_path(value)
        if path:
            outputs[key] = path
    atlas_path = existing_path((manifest.get("atlas") or {}).get("path"))
    if atlas_path:
        outputs.setdefault("atlas_path", atlas_path)
    return outputs


def choose_primary(outputs: dict[str, Path]) -> Path | None:
    preferred = (
        "rgb_preview_atlas",
        "rgba_channel_atlas",
        "black_preview_atlas",
        "atlas_path",
        "rgba_channel_texture",
        "black_preview",
    )
    for key in preferred:
        if key in outputs:
            return outputs[key]
    return next(iter(outputs.values()), None)


def choose_alpha(outputs: dict[str, Path], primary: Path | None) -> Path | None:
    preferred = ("rgba_alpha_atlas", "rgba_channel_atlas", "rgba_channel_texture")
    for key in preferred:
        path = outputs.get(key)
        if path and path != primary:
            return path
    for key, path in outputs.items():
        lowered = key.lower()
        if "alpha" in lowered and "debug" not in lowered and path != primary:
            return path
    return None


def choose_preview(outputs: dict[str, Path], primary: Path | None) -> Path | None:
    for key in ("black_preview_atlas", "black_preview", "rgb_preview_atlas"):
        path = outputs.get(key)
        if path and path != primary:
            return path
    return None


def role_for_path(path: Path, manifest: dict[str, Any] | None = None) -> str:
    name = path.name.lower()
    if "alpha_debug" in name or "debug" in name:
        return "debug"
    if manifest and "channel_texture" in json.dumps(manifest.get("outputs", {})).lower():
        return "channel-texture"
    if "_alpha_" in name or name.endswith("_alpha.png"):
        return "alpha-support"
    if "preview" in name:
        return "preview"
    return "atlas"


def warning_codes(readiness: ReadinessInfo | None) -> list[str]:
    if not readiness:
        return []
    return [finding["code"] for finding in readiness.findings if finding.get("severity") in {"warn", "fail"}]


def unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def route_is_random(usage: str | None, readiness: ReadinessInfo | None) -> bool:
    text = f"{usage or ''} {readiness.mode if readiness else ''}".lower()
    return "random" in text or "random-sheet" in text


def material_hint(readiness: ReadinessInfo | None, alpha_path: str | None) -> str:
    if readiness and readiness.alpha_varies:
        return "Unlit Translucent/Additive: RGB -> Emissive, A -> Opacity, multiply ParticleColor."
    if readiness and readiness.likely_black_luma_sheet:
        return "Unlit Additive or luma-opacity route; black background should disappear additively."
    if alpha_path:
        return "Prefer the paired alpha PNG for Translucent/Additive opacity."
    return "Define opacity route before UE import; alpha/luma policy is not obvious."


def niagara_hint(grid: str | None, cells: int | None, usage: str | None, readiness: ReadinessInfo | None) -> str:
    if not grid:
        return "Not a SubUV atlas; use as a regular texture or ribbon/beam channel."
    frame_count = readiness.frames if readiness and readiness.frames is not None else cells
    end_frame = (frame_count or 1) - 1
    unused_note = ""
    if cells and frame_count and frame_count < cells:
        unused_note = f"; play only frames 0..{end_frame} and leave cells {frame_count}..{cells - 1} unused"
    if route_is_random(usage, readiness):
        return f"Sprite Renderer Sub Image Size {grid}; randomize SubImageIndex 0..{end_frame}{unused_note}; keep Sub UV Blending off unless tested."
    return f"Sprite Renderer Sub Image Size {grid}; SubUV Animation Start 0 / End {end_frame}{unused_note}; enable blending for soft continuous effects."


def import_hint(readiness: ReadinessInfo | None, role: str) -> str:
    if role == "channel-texture":
        return "Clamp sampler; use linear/mask settings if alpha-only, or sRGB only when RGB color is intentional."
    if readiness and readiness.alpha_varies:
        return "Use this RGBA texture, or the paired alpha PNG when present, for Translucent/Additive opacity; keep mips and verify fine-line readability at 1024/512/256/128."
    if readiness and readiness.likely_black_luma_sheet:
        return "Black luma/additive sheet; RGB color can stay sRGB, mask-only luma route should be linear/no-sRGB."
    return "Set compression/sRGB intentionally; do not rely on UE surface-texture defaults."


def recommendation_for(primary: ReadinessInfo | None, alpha: ReadinessInfo | None, role: str, name: str) -> str:
    statuses = [primary.status if primary else "unknown", alpha.status if alpha else None]
    if role in {"debug", "preview"}:
        return "support-only"
    if statuses[0] == "ready" and (statuses[1] in {None, "ready"}):
        return "recommended" if "softreadable" in name.lower() or "softfalloff" in name.lower() else "usable"
    if statuses[0] == "conditional" or statuses[1] == "conditional":
        return "conditional"
    if statuses[0] == "blocked" or statuses[1] == "blocked":
        return "blocked"
    return "needs-review"


def size_pixels(value: str | None) -> int:
    if not value:
        return 0
    match = re.search(r"(?P<width>\d+)x(?P<height>\d+)", value)
    if not match:
        return 0
    return int(match.group("width")) * int(match.group("height"))


def recommendation_rank(value: str) -> int:
    return {
        "recommended": 0,
        "usable": 1,
        "conditional": 2,
        "needs-review": 3,
        "support-only": 4,
        "blocked": 5,
    }.get(value, 6)


def build_entries(root: Path, *, include_orphans: bool = False) -> list[AssetEntry]:
    manifest_paths = sorted(root.rglob("*_manifest.json"))
    readiness_paths = sorted(root.rglob("*_readiness.md"))
    readiness_by_path: dict[str, ReadinessInfo] = {}
    readiness_by_stem: dict[str, ReadinessInfo] = {}
    for readiness_path in readiness_paths:
        info = parse_readiness(readiness_path)
        readiness_by_path[path_key(info.path)] = info
        readiness_by_stem[readiness_path.name.replace("_readiness.md", "")] = info

    covered: set[str] = set()
    entries: list[AssetEntry] = []
    for manifest_path in manifest_paths:
        manifest = load_json(manifest_path)
        outputs = manifest_outputs(manifest)
        primary = choose_primary(outputs)
        if not primary:
            continue
        alpha = choose_alpha(outputs, primary)
        preview = choose_preview(outputs, primary)
        covered.update(path_key(path) for path in outputs.values())

        primary_readiness = readiness_by_path.get(path_key(primary)) or readiness_by_stem.get(primary.stem)
        alpha_readiness = None
        if alpha:
            alpha_readiness = readiness_by_path.get(path_key(alpha)) or readiness_by_stem.get(alpha.stem)
        grid, cells = manifest_grid(manifest)
        size = (primary_readiness.size if primary_readiness else None) or inspect_size(primary)
        role = role_for_path(primary, manifest)
        warnings = unique_values(warning_codes(primary_readiness) + warning_codes(alpha_readiness))
        recommendation = recommendation_for(primary_readiness, alpha_readiness, role, primary.name)

        entries.append(
            AssetEntry(
                name=manifest.get("effect_name") or primary.stem,
                primary_path=str(primary),
                role=role,
                usage=manifest.get("usage"),
                effect_name=manifest.get("effect_name"),
                grid=grid,
                cells=cells,
                size=size,
                alpha_path=str(alpha) if alpha else None,
                preview_path=str(preview) if preview else None,
                manifest_path=str(manifest_path.resolve()),
                readiness_status=primary_readiness.status if primary_readiness else "unknown",
                alpha_readiness_status=alpha_readiness.status if alpha_readiness else None,
                warnings=warnings,
                material_hint=material_hint(primary_readiness, str(alpha) if alpha else None),
                niagara_hint=niagara_hint(grid, cells, manifest.get("usage"), primary_readiness),
                import_hint=import_hint(primary_readiness, role),
                recommendation=recommendation,
            )
        )

    for readiness in readiness_by_path.values():
        atlas_path = Path(readiness.path)
        if path_key(atlas_path) in covered or not atlas_path.exists():
            continue
        if not include_orphans and readiness.status == "unknown":
            continue
        role = role_for_path(atlas_path)
        grid_match = re.search(r"(\d+x\d+)", readiness.grid or "")
        grid = grid_match.group(1) if grid_match else None
        cells = None
        if grid:
            columns, rows = (int(part) for part in grid.split("x"))
            cells = columns * rows
        entries.append(
            AssetEntry(
                name=atlas_path.stem,
                primary_path=str(atlas_path.resolve()),
                role=role,
                usage=None,
                effect_name=None,
                grid=grid,
                cells=cells,
                size=readiness.size or inspect_size(atlas_path),
                alpha_path=None,
                preview_path=None,
                manifest_path=None,
                readiness_status=readiness.status,
                alpha_readiness_status=None,
                warnings=warning_codes(readiness),
                material_hint=material_hint(readiness, None),
                niagara_hint=niagara_hint(grid, cells, None, readiness),
                import_hint=import_hint(readiness, role),
                recommendation=recommendation_for(readiness, None, role, atlas_path.name),
            )
        )

    if include_orphans:
        for png_path in sorted(root.rglob("*.png")):
            key = path_key(png_path)
            if key in covered or any(path_key(entry.primary_path) == key for entry in entries):
                continue
            entries.append(
                AssetEntry(
                    name=png_path.stem,
                    primary_path=str(png_path.resolve()),
                    role=role_for_path(png_path),
                    usage=None,
                    effect_name=None,
                    grid=None,
                    cells=None,
                    size=inspect_size(png_path),
                    alpha_path=None,
                    preview_path=None,
                    manifest_path=None,
                    readiness_status="unknown",
                    alpha_readiness_status=None,
                    warnings=[],
                    material_hint="No manifest/readiness report found; run ue_flipbook_readiness.py before UE delivery.",
                    niagara_hint="No SubUV contract found.",
                    import_hint="Needs review.",
                    recommendation="needs-review",
                )
            )

    entries.sort(
        key=lambda entry: (
            -STATUS_RANK.get(entry.readiness_status, 0),
            recommendation_rank(entry.recommendation),
            -size_pixels(entry.size),
            entry.name,
        )
    )
    return entries


def build_catalog(root: Path, *, include_orphans: bool = False) -> Catalog:
    entries = build_entries(root, include_orphans=include_orphans)
    counts = {"ready": 0, "conditional": 0, "blocked": 0, "unknown": 0}
    for entry in entries:
        counts[entry.readiness_status if entry.readiness_status in counts else "unknown"] += 1
    return Catalog(
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        root=str(root.resolve()),
        entries=entries,
        counts=counts,
    )


def short_path(path: str | None, root: Path) -> str:
    if not path:
        return ""
    value = Path(path)
    try:
        return str(value.relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(value)


def markdown_table_row(values: list[str]) -> str:
    escaped = [value.replace("\n", " ").replace("|", "\\|") for value in values]
    return "| " + " | ".join(escaped) + " |"


def catalog_to_markdown(catalog: Catalog) -> str:
    root = Path(catalog.root)
    lines = [
        "# Flipbook Asset Catalog",
        "",
        f"- Generated UTC: `{catalog.generated_utc}`",
        f"- Root: `{catalog.root}`",
        f"- Entries: `{len(catalog.entries)}`",
        f"- Status counts: ready `{catalog.counts['ready']}`, conditional `{catalog.counts['conditional']}`, blocked `{catalog.counts['blocked']}`, unknown `{catalog.counts['unknown']}`",
        "",
        "## UE / Niagara Defaults",
        "",
        "- Random sheets: set Sprite Renderer `Sub Image Size` to the atlas grid, randomize `SubImageIndex`, and keep `Sub UV Blending` off unless the hard icon transitions have been tested.",
        "- Continuous flipbooks: use SubUV Animation `Start Frame = 0`, `End Frame = frame_count - 1`, and enable SubUV blending only for soft smoke/fire-like interpolation.",
        "- Production atlas source size: prefer `2048x2048` or `4096x4096` power-of-two assets when the target platform budget permits; treat `1024x1024` as preview, mobile-only, or an intentional low-budget derivative.",
        "- Black luma sheets: use Unlit Additive or derive opacity from luminance; alpha-support PNGs are safer for Translucent/Additive opacity.",
        "- Ultra-fine blueprint/constellation lines: verify mip readability at smaller sizes such as `512`, `256`, and `128`; avoid relying on screen Bloom on standalone/mobile targets.",
        "- UE import should explicitly choose sRGB/compression/mips based on whether the texture is visible emissive color or a mask/data channel.",
        "",
        "## Recommended Ready Assets",
        "",
    ]
    recommended = [entry for entry in catalog.entries if entry.recommendation == "recommended"]
    if recommended:
        lines.extend(
            [
                markdown_table_row(["Name", "Status", "Grid", "Size", "Primary", "Alpha", "Niagara"]),
                markdown_table_row(["---", "---", "---", "---", "---", "---", "---"]),
            ]
        )
        for entry in recommended:
            lines.append(
                markdown_table_row(
                    [
                        entry.name,
                        entry.readiness_status,
                        entry.grid or "",
                        entry.size or "",
                        short_path(entry.primary_path, root),
                        short_path(entry.alpha_path, root),
                        entry.niagara_hint,
                    ]
                )
            )
    else:
        lines.append("_No ready recommended assets found._")

    lines.extend(
        [
            "",
            "## All Catalog Entries",
            "",
            markdown_table_row(["Use", "Name", "Role", "Status", "Alpha", "Grid", "Size", "Warnings", "Primary"]),
            markdown_table_row(["---", "---", "---", "---", "---", "---", "---", "---", "---"]),
        ]
    )
    for entry in catalog.entries:
        alpha_status = entry.alpha_readiness_status or ""
        lines.append(
            markdown_table_row(
                [
                    entry.recommendation,
                    entry.name,
                    entry.role,
                    entry.readiness_status,
                    alpha_status,
                    entry.grid or "",
                    entry.size or "",
                    ", ".join(entry.warnings),
                    short_path(entry.primary_path, root),
                ]
            )
        )

    lines.extend(
        [
            "",
            "## Per-Asset Handoff Notes",
            "",
        ]
    )
    for entry in catalog.entries:
        if entry.recommendation not in {"recommended", "usable", "conditional"}:
            continue
        lines.extend(
            [
                f"### {entry.name}",
                "",
                f"- Primary: `{short_path(entry.primary_path, root)}`",
                f"- Alpha: `{short_path(entry.alpha_path, root)}`" if entry.alpha_path else "- Alpha: _none_",
                f"- Readiness: `{entry.readiness_status}`" + (f" / alpha `{entry.alpha_readiness_status}`" if entry.alpha_readiness_status else ""),
                f"- Material: {entry.material_hint}",
                f"- Niagara: {entry.niagara_hint}",
                f"- Import: {entry.import_hint}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Markdown/JSON catalog for flipbook atlases, manifests, and UE readiness reports.")
    parser.add_argument("root", help="Folder containing atlas PNGs, *_manifest.json files, and *_readiness.md reports.")
    parser.add_argument("--out", help="Markdown output path. Defaults to stdout.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--include-orphans", action="store_true", help="Also include PNG files without manifests or readiness reports.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Catalog root does not exist: {root}")
    catalog = build_catalog(root, include_orphans=args.include_orphans)
    markdown = catalog_to_markdown(catalog)
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if args.json_out:
        json_path = Path(args.json_out).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(asdict(catalog), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
