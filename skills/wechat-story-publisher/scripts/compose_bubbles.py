"""Composite Chinese speech bubbles onto no-text base pages from story_manifest.json.

- Bubble body and tail share one mask, so a semi-transparent fill has no seam.
- Text is drawn last in an opaque color; it never inherits the bubble opacity.
- Line breaks follow Chinese rules: no closing punctuation at line start, no
  opening punctuation at line end, no single-character last line.
- Font size is fitted per bubble, then unified per page and kind, and never
  drops below the minimum readable size at the target reading width.
- The report lists font size at reading width, text/background contrast,
  background texture and overlaps with watermark or avoid regions.

The script lays out what the manifest says. It does not decide who speaks or
where the speaker's head is; check attribution in the real composite.

Usage:
  python compose_bubbles.py --manifest story_manifest.json [--pages p01,p03] [--save-overlay] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_manifest import (Bubble, ManifestError, Page, boxes_overlap, box_px,  # noqa: E402
                            load_manifest, sha256_file)

FONT_CANDIDATES = (
    "C:/Windows/Fonts/NotoSansSC-VF.ttf",
    "C:/Windows/Fonts/SourceHanSansSC-Regular.otf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
)
NO_LINE_START = set("，。、；：？！）》」』”’…—～·,.;:?!)]}%")
NO_LINE_END = set("（《「『“‘([{")
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
TOKEN_RE = re.compile(r"[A-Za-z0-9@#&'\-\.]+|\s+|.", re.S)
LINE_HEIGHT = 1.3
TEXTURE_STD_LIMIT = 0.09


def find_font(explicit: str | None) -> str | None:
    if explicit:
        if not Path(explicit).is_file():
            raise ManifestError(f"font not found: {explicit}")
        return explicit
    return next((path for path in FONT_CANDIDATES if Path(path).is_file()), None)


def load_font(path: str | None, size: int):
    if path is None:
        return ImageFont.load_default(size=size)
    font = ImageFont.truetype(path, size=size)
    try:
        names = [n.decode() if isinstance(n, bytes) else n for n in font.get_variation_names()]
        for wanted in ("Medium", "Regular"):
            if wanted in names:
                font.set_variation_by_name(wanted)
                break
    except (OSError, AttributeError):
        pass
    return font


def wrap_text(text: str, max_width: float, measure) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        para_lines: list[str] = []
        for token in TOKEN_RE.findall(paragraph):
            candidate = current + token
            if not current or measure(candidate) <= max_width:
                current = candidate
                continue
            if token[0] in NO_LINE_START or current[-1] in NO_LINE_END:
                if len(current) >= 2:
                    para_lines.append(current[:-1])
                    current = current[-1] + token
                else:
                    current = candidate
                continue
            para_lines.append(current.rstrip())
            current = token.lstrip()
        para_lines.append(current)
        last_letters = [ch for ch in para_lines[-1].strip() if ch not in NO_LINE_START and not ch.isspace()]
        if len(para_lines) >= 2 and len(last_letters) <= 1 and len(para_lines[-2]) >= 3:
            prev = para_lines[-2]
            k = 1
            while k < len(prev) - 1 and prev[-k] in NO_LINE_START:
                k += 1
            para_lines[-2], para_lines[-1] = prev[:-k], prev[-k:] + para_lines[-1]
        lines.extend(para_lines)
    return lines


def text_area(bubble: Bubble, rect: tuple[int, int, int, int]) -> tuple[float, float]:
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    pad = 0.12 * min(width, height)
    factor = 0.72 if bubble.shape == "ellipse" else 1.0
    return max(1.0, width * factor - 2 * pad), max(1.0, height * factor - 2 * pad)


def fit_font_px(bubble: Bubble, rect, font_path, min_px: int, max_px: int) -> tuple[int, list[str], bool]:
    avail_w, avail_h = text_area(bubble, rect)
    max_px = max(min_px, min(int(avail_h), max_px))
    for size in range(max_px, min_px - 1, -1):
        font = load_font(font_path, size)
        lines = wrap_text(bubble.text, avail_w, font.getlength)
        widest = max(font.getlength(line) for line in lines)
        if len(lines) * size * LINE_HEIGHT <= avail_h and widest <= avail_w * 1.04:
            return size, lines, False
    font = load_font(font_path, min_px)
    return min_px, wrap_text(bubble.text, avail_w, font.getlength), True


def shape_mask(size, bubble: Bubble, rect) -> tuple[Image.Image, list[str]]:
    notes = []
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    if bubble.shape == "ellipse":
        draw.ellipse(rect, fill=255)
    elif bubble.shape == "rect":
        draw.rectangle(rect, fill=255)
    else:
        draw.rounded_rectangle(rect, radius=int(0.3 * min(w, h)), fill=255)
    if bubble.tail is not None:
        tx, ty = bubble.tail[0] * size[0], bubble.tail[1] * size[1]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if x0 <= tx <= x1 and y0 <= ty <= y1:
            notes.append("tail_inside_bubble")
        else:
            dx, dy = tx - cx, ty - cy
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            if bubble.kind == "thought":
                for step, radius in ((0.62, 0.07), (0.78, 0.05), (0.92, 0.035)):
                    px, py = cx + dx * step, cy + dy * step
                    r = radius * min(w, h) * 1.6
                    draw.ellipse((px - r, py - r, px + r, py + r), fill=255)
            else:
                half = max(3.0, 0.11 * min(w, h))
                draw.polygon([(cx + nx * half, cy + ny * half), (cx - nx * half, cy - ny * half), (tx, ty)], fill=255)
    return mask, notes


def outline_ring(mask: Image.Image, stroke: int) -> Image.Image:
    box = mask.getbbox()
    ring = Image.new("L", mask.size, 0)
    if not box or stroke <= 0:
        return ring
    margin = stroke + 2
    crop_box = (max(0, box[0] - margin), max(0, box[1] - margin),
                min(mask.width, box[2] + margin), min(mask.height, box[3] + margin))
    part = mask.crop(crop_box)
    grown = part.filter(ImageFilter.MaxFilter(2 * stroke + 1))
    ring.paste(ImageChops.subtract(grown, part), crop_box[:2])
    return ring


def relative_luminance(value_0_255: float) -> float:
    c = value_0_255 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(a: float, b: float) -> float:
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def background_stats(result: Image.Image, mask: Image.Image, text_alpha: Image.Image, text_rgb) -> dict:
    interior = mask.filter(ImageFilter.MinFilter(5)) if min(mask.size) > 10 else mask
    text_zone = text_alpha.point(lambda v: 255 if v else 0).filter(ImageFilter.MaxFilter(5))
    sample = ImageChops.subtract(interior, text_zone)
    hist = result.convert("L").histogram(sample)
    total = sum(hist)
    if not total:
        return {"sampled_pixels": 0}

    def percentile(p):
        target, acc = total * p, 0
        for value, count in enumerate(hist):
            acc += count
            if acc >= target:
                return value
        return 255

    mean = sum(v * c for v, c in enumerate(hist)) / total
    std = math.sqrt(sum(c * (v - mean) ** 2 for v, c in enumerate(hist)) / total) / 255
    text_l = relative_luminance(0.299 * text_rgb[0] + 0.587 * text_rgb[1] + 0.114 * text_rgb[2])
    worst_bg = percentile(0.05) if text_l < 0.5 else percentile(0.95)
    return {
        "sampled_pixels": total,
        "background_mean": round(mean / 255, 3),
        "background_std": round(std, 3),
        "contrast_min": round(contrast_ratio(text_l, relative_luminance(worst_bg)), 2),
        "contrast_mean": round(contrast_ratio(text_l, relative_luminance(mean)), 2),
    }


def compose_page(manifest, page: Page, font_path, args) -> dict:
    report = {"page": page.id, "base": str(page.base) if page.base else None, "image": str(page.image),
              "bubbles": [], "errors": [], "warnings": []}
    if page.base is None:
        report["errors"].append("no_base_image")
        return report
    if not page.base.is_file():
        report["errors"].append(f"base_missing:{page.base}")
        return report
    if page.base.resolve() == page.image.resolve():
        report["errors"].append("base_and_image_must_differ")
        return report
    base = Image.open(page.base)
    base.load()
    size = base.size
    reading_width = manifest.setting("reading_width_px")
    min_px = math.ceil(manifest.setting("min_reading_font_px") * size[0] / reading_width)
    max_px = max(min_px, math.floor(manifest.setting("max_reading_font_px") * size[0] / reading_width))
    stroke = max(1, round(1.4 * size[0] / reading_width))

    # 1. Fit each bubble, then unify size per kind on this page unless set explicitly.
    fits = []
    for bubble in page.bubbles:
        rect = box_px(bubble.box, size)
        if bubble.font_px:
            font = load_font(font_path, bubble.font_px)
            avail_w, avail_h = text_area(bubble, rect)
            lines = wrap_text(bubble.text, avail_w, font.getlength)
            overflow = len(lines) * bubble.font_px * LINE_HEIGHT > avail_h
            fits.append((bubble, rect, bubble.font_px, lines, overflow, True))
        else:
            fits.append((bubble, rect, *fit_font_px(bubble, rect, font_path, min_px, max_px), False))
    unified = {}
    for bubble, _rect, px, _lines, _over, explicit in fits:
        if not explicit:
            unified[bubble.kind] = min(px, unified.get(bubble.kind, px))
    layout = []
    for bubble, rect, px, lines, overflow, explicit in fits:
        if not explicit and px != unified[bubble.kind]:
            px = unified[bubble.kind]
            font = load_font(font_path, px)
            lines = wrap_text(bubble.text, text_area(bubble, rect)[0], font.getlength)
        layout.append((bubble, rect, px, lines, overflow))

    # 2. Draw every bubble into one overlay.
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    text_layers = []
    for bubble, rect, px, lines, overflow in layout:
        entry = {"index": bubble.index, "speaker": bubble.speaker, "kind": bubble.kind, "text": bubble.text,
                 "box_px": rect, "font_px": px, "font_px_at_reading_width": round(px * reading_width / size[0], 1),
                 "lines": lines, "warnings": []}
        if overflow:
            entry["warnings"].append("text_overflow")
            report["errors"].append(f"bubble[{bubble.index}] text_overflow: enlarge the box or shorten the line")
        if font_path is None and CJK_RE.search(bubble.text):
            report["errors"].append("no_cjk_font_found: pass --font or set manifest.font")
        mask, notes = shape_mask(size, bubble, rect)
        entry["warnings"].extend(notes)
        alpha = bubble.fill_alpha if bubble.fill_alpha is not None else (
            args.fill_alpha if args.fill_alpha is not None else manifest.setting("fill_alpha"))
        entry["fill_alpha"] = alpha
        entry["fill_opacity_percent"] = round(alpha / 255 * 100)
        fill = Image.new("RGBA", size, ImageColor.getrgb(bubble.fill)[:3] + (0,))
        fill.putalpha(mask.point(lambda v, a=alpha: v * a // 255))
        overlay = Image.alpha_composite(overlay, fill)
        ring = outline_ring(mask, stroke)
        line_layer = Image.new("RGBA", size, ImageColor.getrgb(bubble.outline)[:3] + (0,))
        line_layer.putalpha(ring)
        overlay = Image.alpha_composite(overlay, line_layer)

        text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)
        font = load_font(font_path, px)
        text_rgb = ImageColor.getrgb(bubble.text_color)[:3]
        cx = (rect[0] + rect[2]) / 2
        top = (rect[1] + rect[3]) / 2 - len(lines) * px * LINE_HEIGHT / 2
        for i, line in enumerate(lines):
            draw.text((cx, top + px * LINE_HEIGHT * (i + 0.5)), line, font=font, fill=text_rgb + (255,), anchor="mm")
        text_layers.append((text_layer, mask, text_rgb, entry))

        for zone in manifest.watermark_zones:
            if boxes_overlap(bubble.box, zone) > 0:
                entry["warnings"].append("overlaps_watermark_zone")
        for region in page.review_regions:
            if region.avoid and boxes_overlap(bubble.box, region.box) > 0:
                entry["warnings"].append(f"covers_avoid_region:{region.label}")
        report["bubbles"].append(entry)

    for i, first in enumerate(page.bubbles):
        for second in page.bubbles[i + 1:]:
            if boxes_overlap(first.box, second.box) > 0:
                report["warnings"].append(f"bubbles_overlap:{first.index}&{second.index}")

    for text_layer, _mask, _rgb, _entry in text_layers:
        overlay = Image.alpha_composite(overlay, text_layer)
    result = Image.alpha_composite(base.convert("RGBA"), overlay)
    for text_layer, mask, text_rgb, entry in text_layers:
        stats = background_stats(result, mask, text_layer.getchannel("A"), text_rgb)
        entry["background"] = stats
        if stats.get("contrast_min", 99) < manifest.setting("min_contrast"):
            entry["warnings"].append("low_contrast")
        if stats.get("background_std", 0) > TEXTURE_STD_LIMIT:
            entry["warnings"].append("textured_background_shows_through")
        if entry["font_px_at_reading_width"] < manifest.setting("min_reading_font_px"):
            entry["warnings"].append("small_font_at_reading_width")
    report["warnings"].extend(f"bubble[{e['index']}] {w}" for e in report["bubbles"] for w in e["warnings"])

    if report["errors"] or args.dry_run:
        report["written"] = False
        return report
    page.image.parent.mkdir(parents=True, exist_ok=True)
    final = result if base.mode in ("RGBA", "LA", "P") and "A" in base.getbands() else result.convert("RGB")
    tmp = page.image.with_name(page.image.stem + ".tmp" + page.image.suffix)
    final.save(tmp)
    if page.image.exists():
        old_hash = sha256_file(page.image)
        if old_hash == sha256_file(tmp):
            tmp.unlink()
            report.update(written=False, unchanged=True, sha256=old_hash)
            return report
        versions = page.image.parent / "_versions"
        versions.mkdir(exist_ok=True)
        kept = versions / f"{page.image.stem}-{old_hash[:8]}{page.image.suffix}"
        if not kept.exists():
            shutil.copy2(page.image, kept)
        report["previous_version"] = str(kept)
    tmp.replace(page.image)
    report.update(written=True, sha256=sha256_file(page.image))
    if args.save_overlay:
        overlays = page.image.parent / "_overlays"
        overlays.mkdir(exist_ok=True)
        overlay_path = overlays / f"{page.image.stem}.overlay.png"
        overlay.save(overlay_path)
        report["overlay"] = str(overlay_path)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pages", help="Comma-separated page ids; default all.")
    parser.add_argument("--font", help="Font file; default manifest.font, then common CJK system fonts.")
    parser.add_argument("--fill-alpha", type=int, help="Override bubble fill alpha 0-255 for this run.")
    parser.add_argument("--save-overlay", action="store_true", help="Also save the bubble layer to _overlays/.")
    parser.add_argument("--dry-run", action="store_true", help="Lay out and report without writing pages.")
    parser.add_argument("--report", help="Report path; default <manifest dir>/qa/compose-report.json.")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if args.fill_alpha is not None and not 0 <= args.fill_alpha <= 255:
            raise ManifestError("--fill-alpha must be 0-255")
        font_path = find_font(args.font or manifest.font)
        wanted = {p.strip() for p in args.pages.split(",")} if args.pages else None
        if wanted:
            unknown = wanted - {p.id for p in manifest.pages}
            if unknown:
                raise ManifestError(f"unknown page ids: {sorted(unknown)}")
        pages = [p for p in manifest.pages if not wanted or p.id in wanted]
        reports = [compose_page(manifest, page, font_path, args) for page in pages]
    except ManifestError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    summary = {
        "ok": not any(r["errors"] for r in reports),
        "manifest": str(manifest.path),
        "font": font_path,
        "dry_run": args.dry_run,
        "pages": reports,
        "note": "Layout and pixel checks only. Verify speaker attribution, tails and anatomy in the real composites.",
    }
    report_path = Path(args.report) if args.report else manifest.root / "qa" / "compose-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if wanted and not args.dry_run and report_path.is_file():
        # Partial run: keep other pages' records so qa_preview can still match them by hash.
        try:
            previous = {p["page"]: p for p in json.loads(report_path.read_text(encoding="utf-8")).get("pages", [])}
        except ValueError:
            previous = {}
        merged = {**previous, **{r["page"]: r for r in reports}}
        summary["pages"] = [merged[p.id] for p in manifest.pages if p.id in merged]
        summary["ok"] = not any(r["errors"] for r in summary["pages"])
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {
        "ok": summary["ok"],
        "report": str(report_path.resolve()),
        "font": font_path,
        "written": [r["page"] for r in reports if r.get("written")],
        "unchanged": [r["page"] for r in reports if r.get("unchanged")],
        "errors": {r["page"]: r["errors"] for r in reports if r["errors"]},
        "warnings": {r["page"]: r["warnings"] for r in reports if r["warnings"]},
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
