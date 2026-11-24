from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, ensure_dir, resolve_root_context, save_json, sha256_file, slugify, utc_now_iso, write_text


def cache_root(ctx) -> Path:
    return ensure_dir(ctx.material_root / "smoke-cache")


def cache_index_path(ctx, effect: str) -> Path:
    return cache_root(ctx) / slugify(effect) / "smoke-resume-cache.json"


def input_fingerprint(path: Path) -> dict[str, Any]:
    if not str(path):
        return {"path": "", "exists": False}
    if not path.exists():
        return {"path": str(path), "exists": False}
    if path.is_file():
        return {"path": str(path), "exists": True, "sha256": sha256_file(path)}
    return {"path": str(path), "exists": True, "kind": "directory"}


def step_cache_key(name: str, command: list[str], input_paths: list[Path]) -> str:
    payload = {
        "name": name,
        "command": command,
        "inputs": [str(path) for path in input_paths],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tool": "smoke_resume_cache", "version": 1, "updated_utc": "", "entries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Smoke cache index must be a JSON object: {path}")
    payload.setdefault("entries", [])
    return payload


def find_entry(index: dict[str, Any], key: str) -> dict[str, Any] | None:
    for entry in index.get("entries") or []:
        if isinstance(entry, dict) and str(entry.get("key") or "") == key:
            return entry
    return None


def inputs_match(entry: dict[str, Any], input_paths: list[Path]) -> bool:
    recorded = entry.get("inputs") if isinstance(entry.get("inputs"), list) else []
    current = [input_fingerprint(path) for path in input_paths]
    return recorded == current


def entry_valid(entry: dict[str, Any], input_paths: list[Path]) -> bool:
    report_path = Path(str(entry.get("report_path") or ""))
    if not report_path.exists():
        return False
    return inputs_match(entry, input_paths)


def cache_lookup(ctx, effect: str, name: str, command: list[str], input_paths: list[Path]) -> tuple[dict[str, Any] | None, Path]:
    index_path = cache_index_path(ctx, effect)
    index = load_index(index_path)
    key = step_cache_key(name, command, input_paths)
    entry = find_entry(index, key)
    if entry and entry_valid(entry, input_paths):
        return entry, index_path
    return None, index_path


def cache_store(
    ctx,
    *,
    effect: str,
    name: str,
    command: list[str],
    input_paths: list[Path],
    step: dict[str, Any],
) -> Path:
    index_path = cache_index_path(ctx, effect)
    index = load_index(index_path)
    key = step_cache_key(name, command, input_paths)
    entry = {
        "key": key,
        "name": name,
        "cached_utc": utc_now_iso(),
        "command": command,
        "command_text": step.get("command_text") or "",
        "report_path": step.get("report_path") or "",
        "planned_report_path": step.get("planned_report_path") or "",
        "status": step.get("status") or "",
        "exit_code": step.get("exit_code"),
        "tool": step.get("tool") or "",
        "inputs": [input_fingerprint(path) for path in input_paths],
    }
    existing = find_entry(index, key)
    entries = [item for item in index.get("entries") or [] if isinstance(item, dict)]
    if existing is None:
        entries.append(entry)
    else:
        existing.update(entry)
    index["entries"] = entries
    index["updated_utc"] = utc_now_iso()
    save_json(index_path, index)
    return index_path


def inspect_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    effect = args.effect or "material-delivery-smoke"
    index_path = Path(args.index) if args.index else cache_index_path(ctx, effect)
    index = load_index(index_path)
    entries = [item for item in index.get("entries") or [] if isinstance(item, dict)]
    report = {
        "tool": "smoke_resume_cache",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "mode": "inspect",
        "index": str(index_path),
        "entries": [
            {
                **item,
                "report_exists": Path(str(item.get("report_path") or "")).exists(),
            }
            for item in entries
        ],
        "summary": {
            "entry_count": len(entries),
            "valid_report_count": sum(1 for item in entries if Path(str(item.get("report_path") or "")).exists()),
        },
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "smoke-cache", effect, "smoke-resume-cache-inspect", ".json")
    return report, out


def prune_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    effect = args.effect or "material-delivery-smoke"
    index_path = Path(args.index) if args.index else cache_index_path(ctx, effect)
    index = load_index(index_path)
    entries = [item for item in index.get("entries") or [] if isinstance(item, dict)]
    stale = [item for item in entries if not Path(str(item.get("report_path") or "")).exists()]
    kept = [item for item in entries if Path(str(item.get("report_path") or "")).exists()]
    if args.apply:
        index["entries"] = kept
        index["updated_utc"] = utc_now_iso()
        save_json(index_path, index)
    report = {
        "tool": "smoke_resume_cache",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "mode": "prune",
        "index": str(index_path),
        "dry_run": not args.apply,
        "stale_entries": stale,
        "summary": {
            "entry_count_before": len(entries),
            "stale_count": len(stale),
            "kept_count": len(kept),
        },
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "smoke-cache", effect, "smoke-resume-cache-prune", ".json")
    return report, out


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Smoke Resume Cache: {report.get('mode')}",
        "",
        f"- Index: `{report.get('index')}`",
    ]
    summary = report.get("summary") or {}
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    if report.get("entries"):
        lines.append("## Entries")
        lines.append("")
        for item in report.get("entries") or []:
            lines.append(f"- `{item.get('name')}` status=`{item.get('status')}` report=`{item.get('report_path')}` exists=`{item.get('report_exists')}`")
    if report.get("stale_entries"):
        lines.append("## Stale Entries")
        lines.append("")
        for item in report.get("stale_entries") or []:
            lines.append(f"- `{item.get('name')}` report=`{item.get('report_path')}`")
    return "\n".join(lines).rstrip() + "\n"


def emit_report(report: dict[str, Any], out: Path, markdown: bool) -> int:
    save_json(out, report)
    if markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    report, out = inspect_report(args)
    return emit_report(report, out, args.markdown)


def command_prune(args: argparse.Namespace) -> int:
    report, out = prune_report(args)
    return emit_report(report, out, args.markdown)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or prune cached material_delivery_smoke step results for resume-friendly reruns.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="Inspect cached smoke-step results.")
    inspect.add_argument("--root", default="auto")
    inspect.add_argument("--effect", default="")
    inspect.add_argument("--index", default="")
    inspect.add_argument("--out")
    inspect.add_argument("--markdown", action="store_true")
    inspect.set_defaults(func=command_inspect)

    prune = sub.add_parser("prune", help="Remove stale cache entries whose reports no longer exist.")
    prune.add_argument("--root", default="auto")
    prune.add_argument("--effect", default="")
    prune.add_argument("--index", default="")
    prune.add_argument("--apply", action="store_true")
    prune.add_argument("--out")
    prune.add_argument("--markdown", action="store_true")
    prune.set_defaults(func=command_prune)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
