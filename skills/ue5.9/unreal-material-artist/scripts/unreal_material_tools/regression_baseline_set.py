from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, ensure_dir, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_regression import build_baseline, default_baseline_path, load_json


def baseline_set_path(ctx, effect: str, layer: str) -> Path:
    return default_baseline_path(ctx, effect, layer).with_name("material-regression-baseline-set.json")


def context_fields() -> tuple[str, ...]:
    return (
        "parameter_tier",
        "carrier",
        "background",
        "exposure",
        "lighting",
        "quality_profile",
        "environment_id",
    )


def context_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {field: str(getattr(args, field, "") or "").strip() for field in context_fields()}


def entry_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    return int(entry.get("score", 0) or 0), str(entry.get("created_utc") or "")


def build_default_capture_path(ctx, effect: str, layer: str, context: dict[str, str], label: str) -> Path:
    parts = [label or "accepted"]
    for field in ("parameter_tier", "carrier", "background", "exposure", "lighting", "quality_profile", "environment_id"):
        value = context.get(field)
        if value:
            parts.append(value)
    stem = slugify("-".join(parts))
    root = default_baseline_path(ctx, effect, layer).parent / "baseline-set"
    return ensure_dir(root) / f"{stem}.json"


def load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tool": "regression_baseline_set", "version": 1, "updated_utc": "", "entries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Baseline set must be a JSON object: {path}")
    payload.setdefault("entries", [])
    return payload


def entry_context(entry: dict[str, Any]) -> dict[str, str]:
    context = entry.get("context") if isinstance(entry.get("context"), dict) else {}
    return {field: str(context.get(field, "") or "") for field in context_fields()}


def score_entry(entry: dict[str, Any], requested: dict[str, str]) -> dict[str, Any]:
    score = 0
    matches: list[str] = []
    mismatches: list[str] = []
    context = entry_context(entry)
    for field, requested_value in requested.items():
        if not requested_value:
            continue
        actual = context.get(field, "")
        if actual and actual == requested_value:
            score += 3
            matches.append(field)
        elif not actual:
            score += 1
        else:
            score -= 4
            mismatches.append(field)
    return {
        **entry,
        "score": score,
        "matches": matches,
        "mismatches": mismatches,
    }


def resolve_entry(entries: list[dict[str, Any]], requested: dict[str, str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    scored = [score_entry(entry, requested) for entry in entries]
    scored.sort(key=entry_sort_key, reverse=True)
    return (scored[0] if scored else None), scored


def upsert_entry(index: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    entries = [item for item in index.get("entries") or [] if isinstance(item, dict)]
    baseline_path = str(entry.get("baseline_path") or "")
    matched = next((item for item in entries if str(item.get("baseline_path") or "") == baseline_path and baseline_path), None)
    if matched is None:
        entries.append(entry)
        matched = entry
    else:
        matched.update(entry)
    index["entries"] = entries
    index["updated_utc"] = utc_now_iso()
    return matched


def register_baseline(args: argparse.Namespace, *, capture: bool) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    context = context_from_args(args)
    if capture:
        effect = args.effect or ""
        layer = args.layer or ""
        requested_out = Path(args.out) if args.out else None
        if not requested_out:
            temp_effect = effect or "Material"
            temp_layer = layer or "Preview"
            requested_out = build_default_capture_path(ctx, temp_effect, temp_layer, context, args.label)
        args.out = str(requested_out)
        baseline, baseline_path = build_baseline(args)
        save_json(baseline_path, baseline)
    else:
        baseline_path = Path(args.baseline)
        baseline = load_json(baseline_path)
        effect = args.effect or str(baseline.get("effect") or "Material")
        layer = args.layer or str(baseline.get("layer") or "Preview")

    effect = args.effect or str(baseline.get("effect") or "Material")
    layer = args.layer or str(baseline.get("layer") or "Preview")
    index_path = Path(args.index) if args.index else baseline_set_path(ctx, effect, layer)
    index = load_index(index_path)
    entry = {
        "effect": effect,
        "layer": layer,
        "label": args.label or str(baseline.get("label") or "accepted"),
        "status": args.status or str(baseline.get("status") or "accepted"),
        "baseline_path": str(baseline_path),
        "created_utc": str(baseline.get("created_utc") or utc_now_iso()),
        "preview_report": str(((baseline.get("preview") or {}).get("report_path")) or ""),
        "source_package": str(baseline.get("source_package") or getattr(args, "package", "") or ""),
        "context": context,
        "notes": list(args.note or []) if hasattr(args, "note") else [],
    }
    saved_entry = upsert_entry(index, entry)
    save_json(index_path, index)
    report = {
        "tool": "regression_baseline_set",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "mode": "capture" if capture else "register",
        "effect": effect,
        "layer": layer,
        "baseline_path": str(baseline_path),
        "baseline_index": str(index_path),
        "entry": saved_entry,
        "entry_count": len(index.get("entries") or []),
        "gate": {"passed": True, "has_entry": True},
    }
    out = Path(args.report_out) if getattr(args, "report_out", "") else default_report_path(
        ctx,
        "regression",
        slugify(f"{effect}-{layer}"),
        f"baseline-set-{report['mode']}",
        ".json",
    )
    return report, out


def resolve_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    if args.index:
        index_path = Path(args.index)
        index = load_index(index_path)
        effect = args.effect or str(index.get("effect") or "Material")
        layer = args.layer or str(index.get("layer") or "Preview")
    else:
        effect = args.effect or "Material"
        layer = args.layer or "Preview"
        index_path = baseline_set_path(ctx, effect, layer)
        index = load_index(index_path)
    requested = context_from_args(args)
    selected, candidates = resolve_entry([item for item in index.get("entries") or [] if isinstance(item, dict)], requested)
    report = {
        "tool": "regression_baseline_set",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "mode": "resolve",
        "effect": effect,
        "layer": layer,
        "baseline_index": str(index_path),
        "requested_context": requested,
        "selected": selected or {},
        "candidates": candidates[: int(args.max_candidates or 8)],
        "summary": {
            "entry_count": len(index.get("entries") or []),
            "candidate_count": len(candidates),
        },
        "gate": {
            "passed": selected is not None,
            "has_match": selected is not None,
            "selected_baseline_exists": bool(selected and Path(str(selected.get("baseline_path") or "")).exists()),
        },
        "next_actions": [
            "Capture or register a baseline for this context if no suitable match exists."
            if selected is None
            else "Use the selected baseline_path when running material_regression.py compare or material_delivery_smoke.py."
        ],
    }
    out = Path(args.report_out) if getattr(args, "report_out", "") else default_report_path(
        ctx,
        "regression",
        slugify(f"{effect}-{layer}"),
        "baseline-set-resolve",
        ".json",
    )
    return report, out


def list_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    effect = args.effect or "Material"
    layer = args.layer or "Preview"
    index_path = Path(args.index) if args.index else baseline_set_path(ctx, effect, layer)
    index = load_index(index_path)
    report = {
        "tool": "regression_baseline_set",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "mode": "list",
        "effect": effect,
        "layer": layer,
        "baseline_index": str(index_path),
        "entries": [item for item in index.get("entries") or [] if isinstance(item, dict)],
        "summary": {"entry_count": len(index.get("entries") or [])},
        "gate": {"passed": True},
    }
    out = Path(args.report_out) if getattr(args, "report_out", "") else default_report_path(
        ctx,
        "regression",
        slugify(f"{effect}-{layer}"),
        "baseline-set-list",
        ".json",
    )
    return report, out


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Regression Baseline Set: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Mode: `{report.get('mode')}`",
        f"- Baseline index: `{report.get('baseline_index')}`",
    ]
    if report.get("mode") == "resolve":
        selected = report.get("selected") or {}
        lines.append(f"- Selected baseline: `{selected.get('baseline_path') or 'none'}`")
        lines.append("")
        lines.append("## Candidates")
        lines.append("")
        for item in report.get("candidates") or []:
            lines.append(
                f"- score=`{item.get('score')}` baseline=`{item.get('baseline_path')}` matches=`{', '.join(item.get('matches') or []) or 'none'}` mismatches=`{', '.join(item.get('mismatches') or []) or 'none'}`"
            )
    else:
        entry = report.get("entry") if isinstance(report.get("entry"), dict) else {}
        if entry:
            lines.append(f"- Baseline path: `{entry.get('baseline_path')}`")
            lines.append(f"- Context: `{json.dumps(entry.get('context') or {}, ensure_ascii=False)}`")
        if report.get("entries"):
            lines.append("")
            lines.append("## Entries")
            lines.append("")
            for item in report.get("entries") or []:
                lines.append(f"- `{item.get('baseline_path')}` context=`{json.dumps(item.get('context') or {}, ensure_ascii=False)}`")
    return "\n".join(lines).rstrip() + "\n"


def emit_report(report: dict[str, Any], out: Path, markdown: bool) -> int:
    save_json(out, report)
    if markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def command_capture(args: argparse.Namespace) -> int:
    report, out = register_baseline(args, capture=True)
    return emit_report(report, out, args.markdown)


def command_register(args: argparse.Namespace) -> int:
    report, out = register_baseline(args, capture=False)
    return emit_report(report, out, args.markdown)


def command_resolve(args: argparse.Namespace) -> int:
    report, out = resolve_report(args)
    code = emit_report(report, out, args.markdown)
    if args.require_match and not (report.get("gate") or {}).get("has_match"):
        return 2
    return code


def command_list(args: argparse.Namespace) -> int:
    report, out = list_report(args)
    return emit_report(report, out, args.markdown)


def add_context_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--parameter-tier", default="")
    parser.add_argument("--carrier", default="")
    parser.add_argument("--background", default="")
    parser.add_argument("--exposure", default="")
    parser.add_argument("--lighting", default="")
    parser.add_argument("--quality-profile", default="")
    parser.add_argument("--environment-id", default="")


def add_common_index_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--index", default="")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--markdown", action="store_true")
    add_context_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a set of accepted regression baselines across tiers, carriers, and preview environments.")
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="Capture a new material_regression baseline and register it into the baseline set.")
    capture.add_argument("--root", default="auto")
    capture.add_argument("--effect", default="")
    capture.add_argument("--layer", default="")
    capture.add_argument("--preview-report", default="")
    capture.add_argument("--package", default="")
    capture.add_argument("--label", default="accepted")
    capture.add_argument("--status", default="accepted")
    capture.add_argument("--note", action="append", default=[])
    capture.add_argument("--out")
    capture.add_argument("--index", default="")
    capture.add_argument("--report-out", default="")
    capture.add_argument("--markdown", action="store_true")
    add_context_args(capture)
    from .material_regression import add_threshold_args

    add_threshold_args(capture)
    capture.set_defaults(func=command_capture)

    register = sub.add_parser("register", help="Register an existing baseline JSON into the baseline set.")
    add_common_index_args(register)
    register.add_argument("--baseline", required=True)
    register.add_argument("--label", default="")
    register.add_argument("--status", default="")
    register.add_argument("--note", action="append", default=[])
    register.set_defaults(func=command_register)

    resolve = sub.add_parser("resolve", help="Resolve the best baseline for a requested tier/environment context.")
    add_common_index_args(resolve)
    resolve.add_argument("--max-candidates", type=int, default=8)
    resolve.add_argument("--require-match", action="store_true")
    resolve.set_defaults(func=command_resolve)

    listing = sub.add_parser("list", help="List every registered baseline entry for an effect/layer.")
    add_common_index_args(listing)
    listing.set_defaults(func=command_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
