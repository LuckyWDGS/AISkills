"""Story page table as data: load, validate and scaffold `story_manifest.json`.

The manifest is the single source for compose_bubbles.py and qa_preview.py.
Paths are relative to the manifest file; boxes and points are relative
coordinates (0-1) so they survive resolution changes.

Usage:
  python story_manifest.py init --base-dir base --pages-dir pages --out story_manifest.json
  python story_manifest.py validate --manifest story_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "wechat-story-manifest/1"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
BUBBLE_SHAPES = ("round", "ellipse", "rect")
BUBBLE_KINDS = ("speech", "thought", "caption", "offscreen")
DEFAULTS = {
    "reading_width_px": 390,
    "max_pages": 20,
    "min_reading_font_px": 13,
    "max_reading_font_px": 18,
    "min_contrast": 4.5,
    "fill_alpha": 160,
}


class ManifestError(ValueError):
    pass


@dataclass
class Bubble:
    text: str
    box: tuple[float, float, float, float]
    speaker: str = ""
    kind: str = "speech"
    shape: str = "round"
    tail: tuple[float, float] | None = None
    font_px: int | None = None
    fill_alpha: int | None = None
    fill: str = "#FFFFFF"
    text_color: str = "#111111"
    outline: str = "#222222"
    index: int = 0


@dataclass
class Region:
    label: str
    box: tuple[float, float, float, float]
    avoid: bool = False


@dataclass
class Page:
    id: str
    image: Path
    base: Path | None
    bubbles: list[Bubble] = field(default_factory=list)
    review_regions: list[Region] = field(default_factory=list)
    note: str = ""


@dataclass
class Manifest:
    path: Path
    root: Path
    title: str
    settings: dict
    watermark_zones: list[tuple[float, float, float, float]]
    font: str | None
    pages: list[Page]
    raw: dict

    def setting(self, name: str):
        return self.settings.get(name, DEFAULTS[name])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _box(value, where: str) -> tuple[float, float, float, float]:
    if not (isinstance(value, (list, tuple)) and len(value) == 4 and all(isinstance(v, (int, float)) for v in value)):
        raise ManifestError(f"{where}: box must be [x, y, w, h] in 0-1 relative units")
    x, y, w, h = (float(v) for v in value)
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.0001 or y + h > 1.0001:
        raise ManifestError(f"{where}: box {value} must lie inside the page (0-1) with positive size")
    return x, y, w, h


def _point(value, where: str) -> tuple[float, float]:
    if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value)):
        raise ManifestError(f"{where}: tail must be [x, y] in 0-1 relative units")
    x, y = float(value[0]), float(value[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ManifestError(f"{where}: tail {value} must lie inside the page")
    return x, y


def parse_manifest(data: dict, path: Path) -> Manifest:
    if data.get("schema") != SCHEMA:
        raise ManifestError(f"schema must be {SCHEMA!r}")
    root = path.parent
    pages_raw = data.get("pages")
    if not isinstance(pages_raw, list) or not pages_raw:
        raise ManifestError("pages must be a non-empty list")
    seen = set()
    pages = []
    for p_index, raw in enumerate(pages_raw):
        where = f"pages[{p_index}]"
        page_id = str(raw.get("id") or "").strip()
        if not page_id:
            raise ManifestError(f"{where}: id is required")
        if page_id in seen:
            raise ManifestError(f"{where}: duplicate id {page_id!r}")
        seen.add(page_id)
        if not raw.get("image"):
            raise ManifestError(f"{where} ({page_id}): image (final page path) is required")
        bubbles = []
        for b_index, b in enumerate(raw.get("bubbles") or []):
            bw = f"{page_id}.bubbles[{b_index}]"
            text = str(b.get("text") or "").strip()
            if not text:
                raise ManifestError(f"{bw}: text is required")
            kind = b.get("kind", "speech")
            if kind not in BUBBLE_KINDS:
                raise ManifestError(f"{bw}: kind must be one of {BUBBLE_KINDS}")
            shape = b.get("shape", "rect" if kind == "caption" else "round")
            if shape not in BUBBLE_SHAPES:
                raise ManifestError(f"{bw}: shape must be one of {BUBBLE_SHAPES}")
            tail = _point(b["tail"], bw) if b.get("tail") is not None else None
            if kind in ("speech", "offscreen") and tail is None and not b.get("no_tail"):
                raise ManifestError(f"{bw}: speech bubbles need a tail point toward the speaker (or no_tail: true)")
            if kind == "speech" and not str(b.get("speaker") or "").strip():
                raise ManifestError(f"{bw}: speaker is required for speech bubbles")
            alpha = b.get("fill_alpha")
            if alpha is not None and not (0 <= int(alpha) <= 255):
                raise ManifestError(f"{bw}: fill_alpha must be 0-255")
            bubbles.append(
                Bubble(
                    text=text,
                    box=_box(b.get("box"), bw),
                    speaker=str(b.get("speaker") or ""),
                    kind=kind,
                    shape=shape,
                    tail=tail,
                    font_px=int(b["font_px"]) if b.get("font_px") else None,
                    fill_alpha=int(alpha) if alpha is not None else None,
                    fill=b.get("fill", "#FFFFFF"),
                    text_color=b.get("text_color", "#111111"),
                    outline=b.get("outline", "#222222"),
                    index=b_index,
                )
            )
        regions = [
            Region(str(r.get("label") or f"region{r_index}"), _box(r.get("box"), f"{page_id}.review_regions[{r_index}]"),
                   bool(r.get("avoid")))
            for r_index, r in enumerate(raw.get("review_regions") or [])
        ]
        pages.append(
            Page(
                id=page_id,
                image=(root / raw["image"]).resolve(),
                base=(root / raw["base"]).resolve() if raw.get("base") else None,
                bubbles=bubbles,
                review_regions=regions,
                note=str(raw.get("note") or ""),
            )
        )
    zones = [_box(z, f"watermark_zones[{i}]") for i, z in enumerate(data.get("watermark_zones") or [])]
    settings = dict(data.get("settings") or {})
    unknown = set(settings) - set(DEFAULTS)
    if unknown:
        raise ManifestError(f"settings: unknown keys {sorted(unknown)}; allowed {sorted(DEFAULTS)}")
    return Manifest(path=path.resolve(), root=root.resolve(), title=str(data.get("title") or ""), settings=settings,
                    watermark_zones=zones, font=data.get("font"), pages=pages, raw=data)


def load_manifest(path: str | Path) -> Manifest:
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc
    return parse_manifest(data, path)


def box_px(box, size: tuple[int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = box
    width, height = size
    return round(x * width), round(y * height), round((x + w) * width), round((y + h) * height)


def boxes_overlap(a, b) -> float:
    """Overlap area as a fraction of box a (relative coordinates)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return (ix * iy) / (aw * ah) if aw * ah else 0.0


def init_manifest(args) -> int:
    out = Path(args.out)
    if out.exists() and not args.force:
        raise ManifestError(f"{out} exists; pass --force to overwrite")
    root = out.parent.resolve()
    base_dir = Path(args.base_dir).resolve() if args.base_dir else None
    pages_dir = Path(args.pages_dir).resolve()
    source = base_dir or pages_dir
    images = sorted(p for p in source.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise ManifestError(f"no images found in {source}")

    def rel(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    pages = []
    for image in images:
        entry = {"id": image.stem, "image": rel(pages_dir / f"{image.stem}.png"), "bubbles": [], "review_regions": []}
        if base_dir:
            entry["base"] = rel(image)
        pages.append(entry)
    data = {"schema": SCHEMA, "title": args.title or "", "settings": dict(DEFAULTS), "watermark_zones": [], "pages": pages}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "manifest": str(out.resolve()), "pages": len(pages)}, ensure_ascii=False))
    return 0


def validate(args) -> int:
    manifest = load_manifest(args.manifest)
    missing = []
    for page in manifest.pages:
        if page.base is not None and not page.base.is_file():
            missing.append({"page": page.id, "field": "base", "path": str(page.base)})
        if not page.image.is_file():
            missing.append({"page": page.id, "field": "image", "path": str(page.image)})
    result = {
        "ok": True,
        "manifest": str(manifest.path),
        "pages": len(manifest.pages),
        "bubbles": sum(len(p.bubbles) for p in manifest.pages),
        "missing_files": missing,
        "over_page_limit": len(manifest.pages) > manifest.setting("max_pages"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Scaffold a manifest from page images (sorted by filename).")
    init.add_argument("--pages-dir", required=True, help="Directory for final composited pages.")
    init.add_argument("--base-dir", help="Directory of no-text base images; pages are listed from here when given.")
    init.add_argument("--out", required=True)
    init.add_argument("--title")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=init_manifest)
    val = sub.add_parser("validate", help="Validate schema and report missing files.")
    val.add_argument("--manifest", required=True)
    val.set_defaults(func=validate)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ManifestError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
