"""Review material and machine checks for the final story pages in story_manifest.json.

Outputs (default <manifest dir>/qa/):
  contact-sheet.png          all pages in order with id and short hash
  narrow/<id>.png            each page at the reading width (default 390 px, local simulation)
  narrow/strip-NN.png        consecutive pages stitched for continuous reading
  reader.html                full-resolution pages in a 390 px column
  crops/<id>-b<n>.png        every bubble with surrounding context
  crops/<id>-r<n>.png        every review region with context (hands, props, faces)
  hashes.json                sha256 per page; the previous run is kept as hashes.prev.json
  qa-report.json             checks, version diff and pages to re-review

These are machine checks and review aids. They do not judge anatomy, speaker
attribution or story causality, and a clean report is not a visual pass.

Usage:
  python qa_preview.py --manifest story_manifest.json [--out-dir qa] [--only sheet,narrow,crops,check,hashes]
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_bubbles import find_font, load_font  # noqa: E402
from story_manifest import ManifestError, box_px, load_manifest, sha256_file  # noqa: E402

STEPS = ("sheet", "narrow", "crops", "check", "hashes")
ENDING_MARKERS = ("本篇完", "未完待续")
STRIP_PAGES = 4


def label_font(size: int):
    return load_font(find_font(None), size)


def open_pages(manifest) -> dict:
    pages = {}
    for page in manifest.pages:
        entry = {"page": page, "path": page.image, "exists": page.image.is_file()}
        if entry["exists"]:
            try:
                with Image.open(page.image) as im:
                    im.load()
                    entry["image"] = im.convert("RGB")
                entry["sha256"] = sha256_file(page.image)
                entry["bytes"] = page.image.stat().st_size
            except OSError as exc:
                entry["error"] = f"unreadable:{type(exc).__name__}"
        pages[page.id] = entry
    return pages


def contact_sheet(manifest, pages, out: Path, cols: int, thumb: int) -> str:
    ready = [p for p in pages.values() if "image" in p]
    if not ready:
        return ""
    ratio = max(p["image"].height / p["image"].width for p in ready)
    cell_w, cell_h, label_h, gap = thumb, int(thumb * ratio), 34, 16
    rows = math.ceil(len(pages) / cols)
    header = 56
    sheet = Image.new("RGB", (cols * (cell_w + gap) + gap, header + rows * (cell_h + label_h + gap) + gap), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 14), f"{manifest.title or manifest.path.stem} · {len(pages)} pages", fill=(30, 30, 30), font=label_font(26))
    small = label_font(18)
    for i, entry in enumerate(pages.values()):
        x = gap + (i % cols) * (cell_w + gap)
        y = header + (i // cols) * (cell_h + label_h + gap)
        if "image" in entry:
            im = entry["image"].copy()
            im.thumbnail((cell_w, cell_h))
            sheet.paste(im, (x + (cell_w - im.width) // 2, y))
            label = f"{i + 1:02d} {entry['page'].id} · {entry['sha256'][:8]}"
        else:
            draw.rectangle((x, y, x + cell_w, y + cell_h), outline=(200, 40, 40), width=3)
            label = f"{i + 1:02d} {entry['page'].id} · MISSING"
        draw.text((x, y + cell_h + 6), label, fill=(40, 40, 40), font=small)
    sheet.save(out)
    return str(out)


def narrow_previews(pages, out_dir: Path, width: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    singles, strips = [], []
    scaled = []
    for entry in pages.values():
        if "image" not in entry:
            continue
        im = entry["image"]
        small = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        path = out_dir / f"{entry['page'].id}.png"
        small.save(path)
        singles.append(str(path))
        scaled.append(small)
    gap = 8
    for start in range(0, len(scaled), STRIP_PAGES):
        chunk = scaled[start:start + STRIP_PAGES]
        strip = Image.new("RGB", (width, sum(c.height for c in chunk) + gap * (len(chunk) - 1)), (255, 255, 255))
        y = 0
        for c in chunk:
            strip.paste(c, (0, y))
            y += c.height + gap
        path = out_dir / f"strip-{start // STRIP_PAGES + 1:02d}.png"
        strip.save(path)
        strips.append(str(path))
    return {"width_px": width, "pages": singles, "strips": strips,
            "note": f"Local {width}px simulation, not a physical phone test."}


def reader_html(manifest, pages, out: Path, width: int) -> str:
    items = []
    for i, entry in enumerate(pages.values()):
        try:
            src = Path(os.path.relpath(Path(entry["path"]).resolve(), out.parent.resolve())).as_posix()
        except ValueError:  # different drive on Windows
            src = Path(entry["path"]).resolve().as_uri()
        items.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(entry["page"].id)}">'
                     f'<figcaption>{i + 1:02d} · {html.escape(entry["page"].id)}</figcaption></figure>')
    out.write_text(
        "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(manifest.title or 'story')}</title>"
        f"<style>body{{margin:0;background:#ededed}}main{{max-width:{width}px;margin:0 auto;background:#fff}}"
        "img{display:block;width:100%;height:auto}figure{margin:0 0 6px}"
        "figcaption{font:12px sans-serif;color:#888;padding:2px 8px}</style>"
        f"<main>{''.join(items)}</main>",
        encoding="utf-8",
    )
    return str(out)


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")[:24]


def context_crops(manifest, pages, out_dir: Path, margin: float, max_side: int) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    crops = []
    for entry in pages.values():
        if "image" not in entry:
            continue
        im = entry["image"]
        page = entry["page"]
        targets = [(f"b{b.index}", f"{b.speaker or b.kind}: {b.text}", b.box) for b in page.bubbles]
        targets += [(f"r{i}-{safe_name(r.label)}".rstrip("-"), r.label, r.box) for i, r in enumerate(page.review_regions)]
        for key, label, box in targets:
            x0, y0, x1, y1 = box_px(box, im.size)
            mx, my = max(24, int((x1 - x0) * margin)), max(24, int((y1 - y0) * margin))
            region = (max(0, x0 - mx), max(0, y0 - my), min(im.width, x1 + mx), min(im.height, y1 + my))
            crop = im.crop(region)
            if max(crop.size) > max_side:
                crop.thumbnail((max_side, max_side))
            path = out_dir / f"{page.id}-{key}.png"
            crop.save(path)
            crops.append({"page": page.id, "target": key, "label": label, "crop_box_px": region, "path": str(path),
                          "upscaled": False})
    return crops


def load_compose_report(manifest) -> dict:
    path = manifest.root / "qa" / "compose-report.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {p["page"]: p for p in data.get("pages", [])}


def run_checks(manifest, pages) -> dict:
    errors, warnings = [], []
    max_pages = manifest.setting("max_pages")
    if len(pages) > max_pages:
        errors.append(f"page_count {len(pages)} exceeds max_pages {max_pages}; split the story")
    for entry in pages.values():
        if not entry["exists"]:
            errors.append(f"{entry['page'].id}: missing {entry['path']}")
        elif "error" in entry:
            errors.append(f"{entry['page'].id}: {entry['error']}")
    ready = [e for e in pages.values() if "image" in e]
    widths = {e["image"].width for e in ready}
    ratios = {round(e["image"].height / e["image"].width, 3) for e in ready}
    if len(widths) > 1:
        warnings.append(f"page widths differ: {sorted(widths)}")
    if len(ratios) > 1:
        warnings.append(f"page aspect ratios differ: {sorted(ratios)}")

    compose = load_compose_report(manifest)
    fonts = []
    for entry in ready:
        page_id = entry["page"].id
        record = compose.get(page_id)
        if entry["page"].bubbles:
            if not record or record.get("sha256") != entry["sha256"] or not record.get("bubbles"):
                warnings.append(f"{page_id}: compose report missing or stale for this file; bubble font/contrast not checked")
                continue
            for bubble in record["bubbles"]:
                fonts.append(bubble["font_px_at_reading_width"])
                for w in bubble.get("warnings", []):
                    warnings.append(f"{page_id} bubble[{bubble['index']}]: {w}")
            errors.extend(f"{page_id}: {e}" for e in record.get("errors", []))

    last = manifest.pages[-1]
    if not any(marker in b.text for b in last.bubbles for marker in ENDING_MARKERS):
        warnings.append("last page text in the manifest has no 本篇完/未完待续; confirm it is drawn in the image")
    return {
        "page_count": len(pages),
        "max_pages": max_pages,
        "dimensions": sorted({e["image"].size for e in ready}),
        "min_bubble_font_px_at_reading_width": min(fonts) if fonts else None,
        "errors": errors,
        "warnings": warnings,
    }


def hash_manifest(manifest, pages, out_dir: Path, previous: Path | None) -> dict:
    current_path = out_dir / "hashes.json"
    prev_data = None
    source = previous or (current_path if current_path.is_file() else None)
    if source and source.is_file():
        prev_data = json.loads(source.read_text(encoding="utf-8"))
        if source == current_path:
            shutil.copy2(current_path, out_dir / "hashes.prev.json")
    current = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "manifest": str(manifest.path),
        "order": [p.id for p in manifest.pages],
        "pages": {pid: {"path": str(e["path"]), "sha256": e.get("sha256"), "bytes": e.get("bytes"),
                        "size": list(e["image"].size) if "image" in e else None} for pid, e in pages.items()},
    }
    current_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    diff = {"baseline": str(source) if prev_data else None}
    if prev_data:
        old, new = prev_data.get("pages", {}), current["pages"]
        changed = [pid for pid in new if pid in old and old[pid].get("sha256") != new[pid].get("sha256")]
        added = [pid for pid in new if pid not in old]
        removed = [pid for pid in old if pid not in new]
        order = current["order"]
        recheck = set(changed) | set(added)
        for pid in list(recheck):
            i = order.index(pid)
            recheck.update(order[max(0, i - 1):i + 2])
        reordered = [pid for pid in order if pid in old] != [pid for pid in prev_data.get("order", []) if pid in new]
        diff.update(changed=changed, added=added, removed=removed, reordered=reordered,
                    recheck=[pid for pid in order if pid in recheck],
                    note="Earlier review conclusions do not apply to changed pages; re-review them and their neighbours.")
    return {"path": str(current_path), "diff": diff}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", help="Default <manifest dir>/qa.")
    parser.add_argument("--only", help=f"Comma-separated subset of {','.join(STEPS)}.")
    parser.add_argument("--width", type=int, help="Reading width in px; default manifest reading_width_px (390).")
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--thumb", type=int, default=280, help="Contact-sheet cell width in px.")
    parser.add_argument("--crop-margin", type=float, default=0.6, help="Context around a target, as a fraction of its size.")
    parser.add_argument("--crop-max", type=int, default=1200, help="Longest crop side; crops are never upscaled.")
    parser.add_argument("--previous", help="Baseline hashes.json; default the existing <out-dir>/hashes.json.")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        steps = [s.strip() for s in args.only.split(",")] if args.only else list(STEPS)
        unknown = set(steps) - set(STEPS)
        if unknown:
            raise ManifestError(f"unknown steps {sorted(unknown)}; choose from {STEPS}")
    except ManifestError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else manifest.root / "qa"
    out_dir.mkdir(parents=True, exist_ok=True)
    width = args.width or manifest.setting("reading_width_px")
    pages = open_pages(manifest)
    report = {"manifest": str(manifest.path), "out_dir": str(out_dir.resolve()), "steps": steps,
              "note": "Machine checks and review aids only; inspect every final page, crops and the narrow preview."}
    if "sheet" in steps:
        report["contact_sheet"] = contact_sheet(manifest, pages, out_dir / "contact-sheet.png", args.cols, args.thumb)
    if "narrow" in steps:
        report["narrow"] = narrow_previews(pages, out_dir / "narrow", width)
        report["reader_html"] = reader_html(manifest, pages, out_dir / "reader.html", width)
    if "crops" in steps:
        report["crops"] = context_crops(manifest, pages, out_dir / "crops", args.crop_margin, args.crop_max)
    if "check" in steps:
        report["check"] = run_checks(manifest, pages)
    if "hashes" in steps:
        report["hashes"] = hash_manifest(manifest, pages, out_dir, Path(args.previous) if args.previous else None)
    errors = report.get("check", {}).get("errors", [])
    report["ok"] = not errors
    (out_dir / "qa-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {
        "ok": report["ok"],
        "report": str((out_dir / "qa-report.json").resolve()),
        "contact_sheet": report.get("contact_sheet"),
        "reader_html": report.get("reader_html"),
        "strips": report.get("narrow", {}).get("strips"),
        "crop_count": len(report.get("crops", [])),
        "errors": errors,
        "warnings": report.get("check", {}).get("warnings", []),
        "recheck": report.get("hashes", {}).get("diff", {}).get("recheck"),
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
