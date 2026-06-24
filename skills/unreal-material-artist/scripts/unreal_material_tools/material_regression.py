from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any

from .core import ensure_dir, resolve_root_context, save_json, sha256_file, slugify, utc_now_iso, write_text


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"JSON file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def effect_layer_slug(effect: str, layer: str) -> str:
    return slugify(f"{effect}-{layer}")


def regression_root(ctx, effect: str, layer: str) -> Path:
    return ctx.material_root / "regression" / effect_layer_slug(effect, layer)


def default_baseline_path(ctx, effect: str, layer: str) -> Path:
    return regression_root(ctx, effect, layer) / "material-regression-baseline.json"


def preview_report_summary(report_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    tool = payload.get("tool")
    if tool != "material_preview":
        raise SystemExit(f"Expected material_preview report, got `{tool}` from {report_path}")
    mode = str(payload.get("mode") or "")
    outputs = payload.get("outputs") or {}
    if mode == "render":
        image_paths = {
            "shaded": str(outputs.get("shaded_png") or ""),
            "complexity": str(outputs.get("complexity_png") or ""),
        }
    else:
        image_paths = {
            "shaded": str(outputs.get("grid_png") or ""),
            "complexity": "",
        }
    return {
        "report_path": str(report_path),
        "mode": mode,
        "material_path": payload.get("material_path") or payload.get("material_instance_path") or "",
        "param_name": payload.get("param_name", ""),
        "values": payload.get("values") or [],
        "options": payload.get("options") or {},
        "image_paths": image_paths,
    }


def preview_from_package(package_path: Path) -> tuple[str, str, dict[str, Any]]:
    package = load_json(package_path)
    if package.get("tool") != "delivery_packager":
        raise SystemExit(f"Expected delivery_packager report, got `{package.get('tool')}` from {package_path}")
    preview_reports = (((package.get("summaries") or {}).get("reports") or {}).get("preview")) or []
    if not preview_reports:
        raise SystemExit(f"Package has no preview report evidence: {package_path}")
    first = preview_reports[0]
    report_path = Path(str(first.get("path") or ""))
    if not report_path.exists():
        raise SystemExit(f"Preview report from package does not exist: {report_path}")
    return str(package.get("effect") or "Material"), str(package.get("layer") or "MainMaterial"), preview_report_summary(report_path, load_json(report_path))


def resolve_preview_source(args: argparse.Namespace) -> tuple[str, str, dict[str, Any]]:
    if getattr(args, "preview_report", None):
        path = Path(args.preview_report)
        preview = preview_report_summary(path, load_json(path))
        effect = args.effect or slugify(preview.get("material_path") or "Material")
        layer = args.layer or ("Sweep" if preview.get("mode") == "sweep" else "Preview")
        return effect, layer, preview
    if getattr(args, "package", None):
        effect, layer, preview = preview_from_package(Path(args.package))
        return args.effect or effect, args.layer or layer, preview
    raise SystemExit("Provide --preview-report or --package.")


def image_metadata(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path_text:
        return {"path": "", "exists": False}
    if not path.exists():
        return {"path": str(path), "exists": False}
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            return {
                "path": str(path),
                "exists": True,
                "sha256": sha256_file(path),
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
            }
    except Exception as exc:
        return {
            "path": str(path),
            "exists": True,
            "sha256": sha256_file(path),
            "warning": f"image metadata unavailable: {exc}",
        }


def copy_preview_images(preview: dict[str, Any], target_dir: Path) -> dict[str, str]:
    ensure_dir(target_dir)
    copied: dict[str, str] = {}
    for role, path_text in (preview.get("image_paths") or {}).items():
        if not path_text:
            copied[role] = ""
            continue
        src = Path(path_text)
        if not src.exists():
            copied[role] = str(src)
            continue
        dest = target_dir / f"baseline-{role}{src.suffix.lower() or '.png'}"
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        copied[role] = str(dest)
    return copied


def build_baseline(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    effect, layer, preview = resolve_preview_source(args)
    root = regression_root(ctx, effect, layer)
    image_dir = root / "baseline-images"
    copied = copy_preview_images(preview, image_dir)
    preview["baseline_image_paths"] = copied
    baseline = {
        "tool": "material_regression_baseline",
        "version": 1,
        "created_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "label": args.label,
        "status": args.status,
        "source_package": args.package or "",
        "notes": args.note,
        "preview": preview,
        "images": {
            role: image_metadata(path)
            for role, path in copied.items()
            if path
        },
        "thresholds": {
            "pixel_threshold": args.pixel_threshold,
            "alpha_threshold": args.alpha_threshold,
            "luma_threshold": args.luma_threshold,
            "max_mean_diff": args.max_mean_diff,
            "max_changed_ratio": args.max_changed_ratio,
            "max_alpha_coverage_delta": args.max_alpha_coverage_delta,
            "max_visual_coverage_delta": args.max_visual_coverage_delta,
            "max_brightness_delta": args.max_brightness_delta,
            "max_centroid_shift": args.max_centroid_shift,
            "max_complexity_mean_diff": args.max_complexity_mean_diff,
        },
    }
    out = Path(args.out) if args.out else default_baseline_path(ctx, effect, layer)
    return baseline, out


def _channel_extrema(values: list[int]) -> tuple[int, int]:
    if not values:
        return 0, 0
    return min(values), max(values)


def _centroid(mask_values: list[int], width: int, height: int) -> tuple[float, float]:
    total = 0
    sum_x = 0
    sum_y = 0
    for index, value in enumerate(mask_values):
        if value:
            x = index % width
            y = index // width
            total += value
            sum_x += x * value
            sum_y += y * value
    if total == 0:
        return 0.0, 0.0
    return round(sum_x / total, 3), round(sum_y / total, 3)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return round(math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2), 3)


def _mask_from_values(values: list[int], threshold: int) -> list[int]:
    return [255 if value >= threshold else 0 for value in values]


def _coverage(mask: list[int]) -> float:
    if not mask:
        return 0.0
    return round(sum(1 for value in mask if value > 0) / len(mask), 6)


def compare_images(
    baseline_path: Path,
    current_path: Path,
    *,
    pixel_threshold: int,
    alpha_threshold: int,
    luma_threshold: int,
    output_dir: Path,
    stem: str,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops, ImageStat  # type: ignore
    except Exception as exc:
        return {
            "role": stem,
            "baseline_path": str(baseline_path),
            "current_path": str(current_path),
            "error": f"Pillow is required for image comparison: {exc}",
            "metrics": {},
            "outputs": {},
        }

    if not str(baseline_path).strip() or not str(current_path).strip() or not baseline_path.is_file() or not current_path.is_file():
        return {
            "role": stem,
            "baseline_path": str(baseline_path),
            "current_path": str(current_path),
            "error": "baseline or current image does not exist or is not a file",
            "metrics": {},
            "outputs": {},
        }

    ensure_dir(output_dir)
    with Image.open(baseline_path) as baseline_image, Image.open(current_path) as current_image:
        baseline = baseline_image.convert("RGBA")
        current_original = current_image.convert("RGBA")
        size_mismatch = baseline.size != current_original.size
        current = current_original.resize(baseline.size, Image.Resampling.LANCZOS) if size_mismatch else current_original
        diff = ImageChops.difference(baseline, current)
        diff_stat = ImageStat.Stat(diff)
        baseline_stat = ImageStat.Stat(baseline)
        current_stat = ImageStat.Stat(current)

        baseline_data = list(baseline.getdata())
        current_data = list(current.getdata())
        total_pixels = max(1, len(baseline_data))
        changed = 0
        max_rgb = 0
        baseline_luma: list[int] = []
        current_luma: list[int] = []
        baseline_alpha: list[int] = []
        current_alpha: list[int] = []
        for base_pixel, cur_pixel in zip(baseline_data, current_data):
            dr = abs(base_pixel[0] - cur_pixel[0])
            dg = abs(base_pixel[1] - cur_pixel[1])
            db = abs(base_pixel[2] - cur_pixel[2])
            da = abs(base_pixel[3] - cur_pixel[3])
            max_rgb = max(max_rgb, dr, dg, db)
            if max(dr, dg, db, da) >= pixel_threshold:
                changed += 1
            baseline_luma.append(int(round(0.2126 * base_pixel[0] + 0.7152 * base_pixel[1] + 0.0722 * base_pixel[2])))
            current_luma.append(int(round(0.2126 * cur_pixel[0] + 0.7152 * cur_pixel[1] + 0.0722 * cur_pixel[2])))
            baseline_alpha.append(base_pixel[3])
            current_alpha.append(cur_pixel[3])

        baseline_alpha_min, baseline_alpha_max = _channel_extrema(baseline_alpha)
        current_alpha_min, current_alpha_max = _channel_extrema(current_alpha)
        alpha_has_signal = baseline_alpha_min < 250 or current_alpha_min < 250 or baseline_alpha_max < 255 or current_alpha_max < 255
        baseline_alpha_mask = _mask_from_values(baseline_alpha, alpha_threshold)
        current_alpha_mask = _mask_from_values(current_alpha, alpha_threshold)
        baseline_luma_mask = _mask_from_values(baseline_luma, luma_threshold)
        current_luma_mask = _mask_from_values(current_luma, luma_threshold)
        baseline_centroid_mask = baseline_alpha_mask if alpha_has_signal else baseline_luma_mask
        current_centroid_mask = current_alpha_mask if alpha_has_signal else current_luma_mask
        baseline_centroid = _centroid(baseline_centroid_mask, baseline.width, baseline.height)
        current_centroid = _centroid(current_centroid_mask, baseline.width, baseline.height)

        heat = Image.merge(
            "RGB",
            (
                diff.convert("RGBA").split()[0],
                diff.convert("RGBA").split()[1],
                diff.convert("RGBA").split()[2],
            ),
        )
        composite = Image.new("RGB", (baseline.width * 3, baseline.height))
        composite.paste(baseline.convert("RGB"), (0, 0))
        composite.paste(current.convert("RGB"), (baseline.width, 0))
        composite.paste(heat, (baseline.width * 2, 0))
        heat_path = output_dir / f"{stem}-diff-heat.png"
        composite_path = output_dir / f"{stem}-diff-composite.png"
        heat.save(heat_path)
        composite.save(composite_path)

        mean_abs_rgba = [round(value, 4) for value in diff_stat.mean]
        metrics = {
            "size": {"width": baseline.width, "height": baseline.height},
            "current_original_size": {"width": current_original.width, "height": current_original.height},
            "size_mismatch": size_mismatch,
            "mean_abs_rgba": mean_abs_rgba,
            "mean_abs_rgb": round(sum(mean_abs_rgba[:3]) / 3.0, 4),
            "rms_rgba": [round(value, 4) for value in diff_stat.rms],
            "max_abs_rgb": max_rgb,
            "changed_pixel_ratio": round(changed / total_pixels, 6),
            "baseline_brightness_mean": round(sum(baseline_luma) / total_pixels, 4),
            "current_brightness_mean": round(sum(current_luma) / total_pixels, 4),
            "brightness_delta": round((sum(current_luma) - sum(baseline_luma)) / total_pixels, 4),
            "baseline_alpha_coverage": _coverage(baseline_alpha_mask),
            "current_alpha_coverage": _coverage(current_alpha_mask),
            "alpha_coverage_delta": round(_coverage(current_alpha_mask) - _coverage(baseline_alpha_mask), 6),
            "baseline_visual_coverage": _coverage(baseline_luma_mask),
            "current_visual_coverage": _coverage(current_luma_mask),
            "visual_coverage_delta": round(_coverage(current_luma_mask) - _coverage(baseline_luma_mask), 6),
            "centroid_source": "alpha" if alpha_has_signal else "luminance",
            "baseline_centroid": baseline_centroid,
            "current_centroid": current_centroid,
            "centroid_shift_px": _distance(baseline_centroid, current_centroid),
            "baseline_rgb_mean": [round(value, 4) for value in baseline_stat.mean[:3]],
            "current_rgb_mean": [round(value, 4) for value in current_stat.mean[:3]],
        }
        return {
            "role": stem,
            "baseline_path": str(baseline_path),
            "current_path": str(current_path),
            "error": "",
            "metrics": metrics,
            "outputs": {
                "heat_png": str(heat_path),
                "composite_png": str(composite_path),
            },
        }


def evaluate_gate(comparisons: list[dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    for comparison in comparisons:
        role = comparison.get("role")
        if comparison.get("error"):
            add("error", f"{role}_comparison_error", str(comparison["error"]))
            continue
        metrics = comparison.get("metrics") or {}
        mean_limit = thresholds["max_complexity_mean_diff"] if role == "complexity" else thresholds["max_mean_diff"]
        if metrics.get("size_mismatch"):
            add("warning", f"{role}_size_mismatch", "Current image was resized to baseline size for comparison.")
        if float(metrics.get("mean_abs_rgb") or 0) > float(mean_limit):
            add("error", f"{role}_mean_diff", f"Mean RGB diff {metrics.get('mean_abs_rgb')} exceeded {mean_limit}.")
        if float(metrics.get("changed_pixel_ratio") or 0) > float(thresholds["max_changed_ratio"]):
            add("warning", f"{role}_changed_ratio", f"Changed pixel ratio {metrics.get('changed_pixel_ratio')} exceeded {thresholds['max_changed_ratio']}.")
        if abs(float(metrics.get("alpha_coverage_delta") or 0)) > float(thresholds["max_alpha_coverage_delta"]):
            add("warning", f"{role}_alpha_coverage", f"Alpha coverage delta {metrics.get('alpha_coverage_delta')} exceeded {thresholds['max_alpha_coverage_delta']}.")
        if abs(float(metrics.get("visual_coverage_delta") or 0)) > float(thresholds["max_visual_coverage_delta"]):
            add("warning", f"{role}_visual_coverage", f"Visual coverage delta {metrics.get('visual_coverage_delta')} exceeded {thresholds['max_visual_coverage_delta']}.")
        if abs(float(metrics.get("brightness_delta") or 0)) > float(thresholds["max_brightness_delta"]):
            add("warning", f"{role}_brightness", f"Brightness delta {metrics.get('brightness_delta')} exceeded {thresholds['max_brightness_delta']}.")
        if float(metrics.get("centroid_shift_px") or 0) > float(thresholds["max_centroid_shift"]):
            add("warning", f"{role}_centroid_shift", f"Centroid shift {metrics.get('centroid_shift_px')}px exceeded {thresholds['max_centroid_shift']}px.")
    return {
        "passed": not any(item["severity"] == "error" for item in findings),
        "findings": findings,
        "errors": sum(1 for item in findings if item["severity"] == "error"),
        "warnings": sum(1 for item in findings if item["severity"] == "warning"),
    }


def build_comparison(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    if args.baseline:
        baseline_path = Path(args.baseline)
    else:
        if not args.effect or not args.layer:
            raise SystemExit("Provide --effect and --layer when --baseline is not supplied.")
        baseline_path = default_baseline_path(ctx, args.effect, args.layer)
    baseline = load_json(baseline_path)
    if baseline.get("tool") != "material_regression_baseline":
        raise SystemExit(f"Expected material_regression_baseline, got `{baseline.get('tool')}` from {baseline_path}")
    effect = args.effect or str(baseline.get("effect") or "Material")
    layer = args.layer or str(baseline.get("layer") or "Preview")
    _effect, _layer, current_preview = resolve_preview_source(args)
    root = regression_root(ctx, effect, layer)
    output_dir = ensure_dir(root / "comparisons" / slugify(args.label or Path(current_preview["report_path"]).stem))
    thresholds = dict(baseline.get("thresholds") or {})
    for key in (
        "pixel_threshold",
        "alpha_threshold",
        "luma_threshold",
        "max_mean_diff",
        "max_changed_ratio",
        "max_alpha_coverage_delta",
        "max_visual_coverage_delta",
        "max_brightness_delta",
        "max_centroid_shift",
        "max_complexity_mean_diff",
    ):
        override = getattr(args, key, None)
        if override is not None:
            thresholds[key] = override
    baseline_images = baseline.get("preview", {}).get("baseline_image_paths") or {}
    current_images = current_preview.get("image_paths") or {}
    comparisons: list[dict[str, Any]] = []
    for role in ("shaded", "complexity"):
        baseline_image = str(baseline_images.get(role) or "")
        current_image = str(current_images.get(role) or "")
        if not baseline_image and not current_image:
            continue
        comparisons.append(
            compare_images(
                Path(baseline_image),
                Path(current_image),
                pixel_threshold=int(thresholds.get("pixel_threshold", 8)),
                alpha_threshold=int(thresholds.get("alpha_threshold", 8)),
                luma_threshold=int(thresholds.get("luma_threshold", 16)),
                output_dir=output_dir,
                stem=role,
            )
        )
    gate = evaluate_gate(comparisons, thresholds)
    report = {
        "tool": "material_regression_compare",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "label": args.label,
        "baseline_path": str(baseline_path),
        "baseline": {
            "label": baseline.get("label"),
            "status": baseline.get("status"),
            "created_utc": baseline.get("created_utc"),
            "preview_report": ((baseline.get("preview") or {}).get("report_path")),
            "source_package": baseline.get("source_package", ""),
        },
        "current": current_preview,
        "thresholds": thresholds,
        "comparisons": comparisons,
        "gate": gate,
    }
    out = Path(args.out) if args.out else output_dir / "material-regression-comparison.json"
    return report, out


def render_baseline_markdown(baseline: dict[str, Any]) -> str:
    preview = baseline.get("preview") or {}
    images = baseline.get("images") or {}
    lines = [
        f"# Material Regression Baseline: {baseline.get('effect')} / {baseline.get('layer')}",
        "",
        f"- Label: `{baseline.get('label')}`",
        f"- Status: `{baseline.get('status')}`",
        f"- Preview report: `{preview.get('report_path')}`",
        f"- Material path: `{preview.get('material_path')}`",
        f"- Source package: `{baseline.get('source_package') or 'none'}`",
        "",
        "## Images",
        "",
    ]
    for role, meta in images.items():
        lines.append(f"- `{role}` path=`{meta.get('path')}` size=`{meta.get('width')}x{meta.get('height')}`")
    if baseline.get("notes"):
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {item}" for item in baseline.get("notes") or [])
    return "\n".join(lines).rstrip() + "\n"


def render_compare_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    lines = [
        f"# Material Regression Compare: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Passed: `{gate.get('passed')}`",
        f"- Errors: `{gate.get('errors')}`",
        f"- Warnings: `{gate.get('warnings')}`",
        f"- Baseline: `{report.get('baseline_path')}`",
        f"- Current preview: `{(report.get('current') or {}).get('report_path')}`",
        "",
        "## Metrics",
        "",
    ]
    for comparison in report.get("comparisons") or []:
        role = comparison.get("role")
        metrics = comparison.get("metrics") or {}
        if comparison.get("error"):
            lines.append(f"- `{role}` error: {comparison.get('error')}")
            continue
        lines.append(
            f"- `{role}` mean_rgb=`{metrics.get('mean_abs_rgb')}` changed=`{metrics.get('changed_pixel_ratio')}` "
            f"brightness_delta=`{metrics.get('brightness_delta')}` alpha_delta=`{metrics.get('alpha_coverage_delta')}` "
            f"visual_delta=`{metrics.get('visual_coverage_delta')}` centroid_shift=`{metrics.get('centroid_shift_px')}`"
        )
        outputs = comparison.get("outputs") or {}
        if outputs:
            lines.append(f"- `{role}` composite: `{outputs.get('composite_png')}`")
            lines.append(f"- `{role}` heat: `{outputs.get('heat_png')}`")
    lines.extend(["", "## Findings", ""])
    if gate.get("findings"):
        for finding in gate["findings"]:
            lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
    else:
        lines.append("- No regression findings.")
    return "\n".join(lines).rstrip() + "\n"


def command_baseline(args: argparse.Namespace) -> int:
    baseline, out = build_baseline(args)
    save_json(out, baseline)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_baseline_markdown(baseline))
    print(out)
    return 0


def command_compare(args: argparse.Namespace) -> int:
    report, out = build_comparison(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_compare_markdown(report))
    print(out)
    return 1 if args.strict and not report["gate"]["passed"] else 0


def add_threshold_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pixel-threshold", type=int, default=8)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--luma-threshold", type=int, default=16)
    parser.add_argument("--max-mean-diff", type=float, default=3.0)
    parser.add_argument("--max-changed-ratio", type=float, default=0.025)
    parser.add_argument("--max-alpha-coverage-delta", type=float, default=0.03)
    parser.add_argument("--max-visual-coverage-delta", type=float, default=0.04)
    parser.add_argument("--max-brightness-delta", type=float, default=5.0)
    parser.add_argument("--max-centroid-shift", type=float, default=12.0)
    parser.add_argument("--max-complexity-mean-diff", type=float, default=8.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lock material preview baselines and compare later previews for visual drift.")
    sub = parser.add_subparsers(dest="command", required=True)

    baseline = sub.add_parser("baseline", help="Lock a material_preview report as the accepted regression baseline.")
    baseline.add_argument("--root", default="auto")
    baseline.add_argument("--effect")
    baseline.add_argument("--layer")
    baseline.add_argument("--preview-report")
    baseline.add_argument("--package")
    baseline.add_argument("--label", default="accepted")
    baseline.add_argument("--status", default="accepted")
    baseline.add_argument("--note", action="append", default=[])
    baseline.add_argument("--out")
    baseline.add_argument("--markdown", action="store_true")
    add_threshold_args(baseline)
    baseline.set_defaults(func=command_baseline)

    compare = sub.add_parser("compare", help="Compare a current material_preview report against a locked baseline.")
    compare.add_argument("--root", default="auto")
    compare.add_argument("--effect")
    compare.add_argument("--layer")
    compare.add_argument("--baseline")
    compare.add_argument("--preview-report")
    compare.add_argument("--package")
    compare.add_argument("--label", default="")
    compare.add_argument("--out")
    compare.add_argument("--markdown", action="store_true")
    compare.add_argument("--strict", action="store_true")
    add_threshold_args(compare)
    compare.set_defaults(func=command_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
