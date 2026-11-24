from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import (
    evidence_rows,
    load_json,
    package_report_paths,
    resolve_path,
    rows_by_tool,
    severity_counts,
)


def unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return float(ordered[index])


def mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def stdev(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def resolve_image_path(path_text: str, *, base: Path) -> Path:
    if not path_text:
        return Path("")
    path = Path(path_text)
    if path.is_absolute():
        return path
    candidate = (base / path).resolve()
    return candidate if candidate.exists() else path


def preview_image_path(preview_path: Path, payload: dict[str, Any]) -> Path:
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    image_text = str(outputs.get("shaded_png") or outputs.get("grid_png") or "")
    return resolve_image_path(image_text, base=preview_path.parent)


def preview_reports_from_matrix(matrix_path: Path) -> list[Path]:
    payload = load_json(matrix_path)
    paths: list[Path] = []
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    for item in evidence.get("preview_reports") or []:
        if item:
            paths.append(resolve_path(str(item), base=matrix_path.parent))
    for cell in payload.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        execution = cell.get("execution") if isinstance(cell.get("execution"), dict) else {}
        if execution.get("report_path"):
            paths.append(resolve_path(str(execution["report_path"]), base=matrix_path.parent))
    return unique_paths(paths)


def collect_preview_reports(args: argparse.Namespace) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if args.package:
        package_path = resolve_path(args.package, base=Path.cwd())
        package = load_json(package_path)
        rows = evidence_rows(package_report_paths(package, package_path=package_path))
        paths.extend(Path(row["path"]) for row in rows_by_tool(rows, "material_preview"))
        for row in rows_by_tool(rows, "preview_matrix"):
            paths.extend(preview_reports_from_matrix(Path(row["path"])))
    for item in args.preview_matrix_report:
        paths.extend(preview_reports_from_matrix(resolve_path(item, base=Path.cwd())))
    for item in args.preview_report:
        paths.append(resolve_path(item, base=Path.cwd()))
    rows = []
    for path in unique_paths(paths):
        payload: dict[str, Any] | None = None
        load_error = ""
        if not path.exists():
            load_error = "missing"
        else:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive path
                load_error = str(exc)
        rows.append({"path": str(path), "payload": payload or {}, "load_error": load_error})
    return rows


def analyze_image(image_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    if not str(image_path):
        return {"path": "", "exists": False, "error": "preview report does not reference a shaded image", "metrics": {}}
    if not image_path.exists():
        return {"path": str(image_path), "exists": False, "error": "image file does not exist", "metrics": {}}
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        return {"path": str(image_path), "exists": True, "error": f"Pillow is required for readability scoring: {exc}", "metrics": {}}

    try:
        with Image.open(image_path) as raw_image:
            image = raw_image.convert("RGBA")
            width, height = image.size
            pixels = list(image.getdata())
    except Exception as exc:
        return {"path": str(image_path), "exists": True, "error": f"could not read image: {exc}", "metrics": {}}

    total = max(1, len(pixels))
    luma: list[float] = []
    alpha: list[int] = []
    for r, g, b, a in pixels:
        luma.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
        alpha.append(a)

    border = max(1, int(min(width, height) * 0.06))
    border_luma = [
        luma[y * width + x]
        for y in range(height)
        for x in range(width)
        if x < border or y < border or x >= width - border or y >= height - border
    ]
    background_luma = mean(border_luma) if border_luma else mean(luma)
    contrast = [abs(value - background_luma) for value in luma]
    left = width // 4
    right = max(left + 1, width - left)
    top = height // 4
    bottom = max(top + 1, height - top)
    center_indexes = [y * width + x for y in range(top, bottom) for x in range(left, right)]
    center_contrast = [contrast[index] for index in center_indexes]
    center_luma = [luma[index] for index in center_indexes]

    step = max(1, int(math.sqrt(total / 12000)))
    gradients: list[float] = []
    for y in range(0, height, step):
        row = y * width
        for x in range(0, width - step, step):
            gradients.append(abs(luma[row + x] - luma[row + x + step]))
    for y in range(0, height - step, step):
        row = y * width
        next_row = (y + step) * width
        for x in range(0, width, step):
            gradients.append(abs(luma[row + x] - luma[next_row + x]))

    alpha_mask = [value >= args.alpha_threshold for value in alpha]
    alpha_has_signal = min(alpha) < 250 or max(alpha) < 255
    visual_mask = [
        alpha_mask[index]
        and (luma[index] >= args.luma_threshold or contrast[index] >= args.contrast_threshold)
        for index in range(total)
    ]
    contrast_mask = [value >= args.contrast_threshold for value in contrast]
    high_energy_mask = [value >= args.high_luma_threshold for value in luma]
    metrics = {
        "width": width,
        "height": height,
        "luma_mean": round(mean(luma), 4),
        "luma_max": round(max(luma), 4),
        "luma_p95": round(percentile(luma, 0.95), 4),
        "luma_p05": round(percentile(luma, 0.05), 4),
        "luma_stddev": round(stdev(luma), 4),
        "background_luma_estimate": round(background_luma, 4),
        "contrast_mean": round(mean(contrast), 4),
        "contrast_p95": round(percentile(contrast, 0.95), 4),
        "visual_coverage": round(sum(1 for value in visual_mask if value) / total, 6),
        "contrast_coverage": round(sum(1 for value in contrast_mask if value) / total, 6),
        "high_energy_ratio": round(sum(1 for value in high_energy_mask if value) / total, 6),
        "alpha_coverage": round(sum(1 for value in alpha_mask if value) / total, 6),
        "alpha_has_signal": alpha_has_signal,
        "center_luma_mean": round(mean(center_luma), 4),
        "center_contrast_mean": round(mean(center_contrast), 4),
        "edge_readability_mean": round(mean(gradients), 4),
        "edge_readability_p95": round(percentile(gradients, 0.95), 4),
    }
    return {"path": str(image_path), "exists": True, "error": "", "metrics": metrics}


def image_findings(analysis: dict[str, Any], args: argparse.Namespace) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if analysis.get("error"):
        add("error", "image_unavailable", str(analysis["error"]))
        return findings
    metrics = analysis.get("metrics") or {}
    if float(metrics.get("luma_max") or 0) < args.min_luma_max and float(metrics.get("contrast_p95") or 0) < args.contrast_threshold:
        add("error", "almost_empty_frame", "Image has very low luminance and very low foreground/background contrast.")
    if float(metrics.get("visual_coverage") or 0) < args.min_visual_coverage:
        add("error", "low_visual_coverage", f"Visible coverage is below {args.min_visual_coverage}.")
    if float(metrics.get("contrast_p95") or 0) < args.min_contrast_p95:
        add("warning", "low_background_contrast", f"95th percentile background contrast is below {args.min_contrast_p95}.")
    if float(metrics.get("center_contrast_mean") or 0) < args.min_center_energy:
        add("warning", "low_center_energy", f"Center-region contrast is below {args.min_center_energy}.")
    if float(metrics.get("edge_readability_p95") or 0) < args.min_edge_p95 and float(metrics.get("edge_readability_mean") or 0) < (args.min_edge_p95 * 0.75):
        add("warning", "low_edge_readability", f"Edge readability is below {args.min_edge_p95}.")
    if metrics.get("alpha_has_signal") and float(metrics.get("alpha_coverage") or 0) < args.min_alpha_coverage:
        add("warning", "low_alpha_coverage", f"Alpha coverage is below {args.min_alpha_coverage}.")
    if not findings:
        add("ok", "readable", "Preview has enough luminance, contrast, center energy, and coverage to be reviewable.")
    return findings


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    preview_rows = collect_preview_reports(args)
    image_rows: list[dict[str, Any]] = []
    for index, image in enumerate(args.image, start=1):
        analysis = analyze_image(resolve_path(image, base=Path.cwd()), args)
        image_rows.append(
            {
                "id": f"image-{index:03d}",
                "source_preview_report": "",
                "image": analysis,
                "findings": image_findings(analysis, args),
            }
        )
    for row in preview_rows:
        payload = row.get("payload") or {}
        image_path = preview_image_path(Path(row["path"]), payload) if not row.get("load_error") else Path("")
        analysis = analyze_image(image_path, args)
        findings = image_findings(analysis, args)
        if row.get("load_error"):
            findings.append({"severity": "error", "rule": "preview_report_load_error", "message": str(row["load_error"])})
        image_rows.append(
            {
                "id": f"preview-{len(image_rows) + 1:03d}",
                "source_preview_report": row["path"],
                "material_path": payload.get("material_path") or payload.get("material_instance_path") or "",
                "options": payload.get("options") if isinstance(payload.get("options"), dict) else {},
                "image": analysis,
                "findings": findings,
            }
        )

    all_findings: list[dict[str, Any]] = []
    if not image_rows:
        all_findings.append({"severity": "error", "rule": "no_preview_images", "message": "No preview reports or direct images were provided."})
    for row in image_rows:
        label = row.get("source_preview_report") or ((row.get("image") or {}).get("path")) or row.get("id")
        for finding in row.get("findings") or []:
            all_findings.append({"source": label, **finding})
    counts = severity_counts(all_findings)
    readable = counts["errors"] == 0 and (args.allow_warnings or counts["warnings"] == 0)
    effect = args.effect or ""
    if not effect and preview_rows:
        first = preview_rows[0].get("payload") or {}
        effect = first.get("effect") or first.get("material_path") or "preview-readability"
    report = {
        "tool": "preview_readability_score",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "material_path": args.material_path,
        "thresholds": {
            "luma_threshold": args.luma_threshold,
            "high_luma_threshold": args.high_luma_threshold,
            "alpha_threshold": args.alpha_threshold,
            "contrast_threshold": args.contrast_threshold,
            "min_luma_max": args.min_luma_max,
            "min_visual_coverage": args.min_visual_coverage,
            "min_contrast_p95": args.min_contrast_p95,
            "min_center_energy": args.min_center_energy,
            "min_edge_p95": args.min_edge_p95,
            "min_alpha_coverage": args.min_alpha_coverage,
        },
        "images": image_rows,
        "summary": {
            **counts,
            "image_count": len(image_rows),
            "readable_count": sum(1 for row in image_rows if not any(item.get("severity") in {"error", "warning"} for item in row.get("findings") or [])),
        },
        "gate": {
            "readable": readable,
            "passed": readable,
            "allow_warnings": bool(args.allow_warnings),
            "requires_triage": bool(counts["errors"] or counts["warnings"]),
        },
        "evidence": {
            "package": str(resolve_path(args.package, base=Path.cwd())) if args.package else "",
            "preview_reports": [row["path"] for row in preview_rows],
            "preview_matrix_reports": [str(resolve_path(item, base=Path.cwd())) for item in args.preview_matrix_report],
            "images": [str(resolve_path(item, base=Path.cwd())) for item in args.image],
        },
        "findings": all_findings,
        "next_actions": next_actions(all_findings),
    }
    stem = slugify(args.effect or args.material_path or effect or "preview-readability")
    out = Path(args.out) if args.out else default_report_path(ctx, "preview-readability", stem, "preview-readability-score", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {str(item.get("rule") or "") for item in findings if item.get("severity") in {"error", "warning"}}
    actions: list[str] = []
    if "no_preview_images" in rules or "image_unavailable" in rules:
        actions.append("Run material_preview.py or preview_matrix.py and include readable shaded PNG evidence.")
    if "almost_empty_frame" in rules or "low_visual_coverage" in rules:
        actions.append("Increase material visibility in the preview harness, check camera/framing, or add a stronger default parameter tier.")
    if "low_background_contrast" in rules:
        actions.append("Preview against multiple backgrounds and tune emissive/opacity so the material reads outside black-background tests.")
    if "low_center_energy" in rules:
        actions.append("Reframe the preview or adjust the material/carrier so the effect has energy in the central review area.")
    if "low_edge_readability" in rules:
        actions.append("Improve mask/alpha edge definition or capture at a closer distance before accepting visual evidence.")
    if not actions:
        actions.append("Preview readability evidence is strong enough for material acceptance gating.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    lines = [
        f"# Preview Readability Score: {report.get('effect') or report.get('material_path')}",
        "",
        f"- Readable: `{gate.get('readable')}`",
        f"- Images: `{summary.get('image_count')}`",
        f"- Errors: `{summary.get('errors', 0)}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Images",
        "",
        "| Image | Visual Coverage | Contrast P95 | Center Energy | Edge P95 | Luma Max | Findings |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("images") or []:
        metrics = ((row.get("image") or {}).get("metrics")) or {}
        lines.append(
            f"| `{row.get('id')}` | {metrics.get('visual_coverage', 'n/a')} | {metrics.get('contrast_p95', 'n/a')} | "
            f"{metrics.get('center_contrast_mean', 'n/a')} | {metrics.get('edge_readability_p95', 'n/a')} | "
            f"{metrics.get('luma_max', 'n/a')} | {len(row.get('findings') or [])} |"
        )
    lines.extend(["", "## Findings", ""])
    if report.get("findings"):
        for finding in report["findings"]:
            lines.append(f"- [{finding.get('severity')}] `{finding.get('rule')}` {finding.get('message')} ({finding.get('source')})")
    else:
        lines.append("- No readability findings.")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.require_readable and not (report.get("gate") or {}).get("readable"):
        print(f"Preview readability is not ready: {out}", file=sys.stderr)
        return 2
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score material preview images for real readability instead of only screenshot success.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--package", default="", help="delivery_packager.py report with preview or preview-matrix evidence.")
    parser.add_argument("--preview-report", action="append", default=[], help="material_preview.py JSON report.")
    parser.add_argument("--preview-matrix-report", action="append", default=[], help="preview_matrix.py JSON report.")
    parser.add_argument("--image", action="append", default=[], help="Direct shaded image path for fixture or ad-hoc scoring.")
    parser.add_argument("--luma-threshold", type=float, default=12.0)
    parser.add_argument("--high-luma-threshold", type=float, default=96.0)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--contrast-threshold", type=float, default=8.0)
    parser.add_argument("--min-luma-max", type=float, default=18.0)
    parser.add_argument("--min-visual-coverage", type=float, default=0.01)
    parser.add_argument("--min-contrast-p95", type=float, default=5.0)
    parser.add_argument("--min-center-energy", type=float, default=3.0)
    parser.add_argument("--min-edge-p95", type=float, default=2.0)
    parser.add_argument("--min-alpha-coverage", type=float, default=0.005)
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--require-readable", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.package or args.preview_report or args.preview_matrix_report or args.image):
        parser.error("Provide --package, --preview-report, --preview-matrix-report, or --image.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
