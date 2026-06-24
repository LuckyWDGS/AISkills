from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import append_jsonl, default_report_path, read_jsonl, resolve_root_context, slugify, utc_now_iso, write_text


SUSPECT_LAYERS = (
    "reference",
    "texture",
    "material",
    "niagara",
    "renderer",
    "integration",
    "preview",
    "performance",
    "unknown",
)


SYMPTOMS = (
    "silhouette",
    "brightness",
    "color",
    "texture-detail",
    "density",
    "width",
    "motion",
    "timing",
    "spacing",
    "sorting",
    "cutoff",
    "performance",
    "other",
)


VALID_STATUS = (
    "open",
    "testing",
    "fixed",
    "rejected",
    "deferred",
    "historical",
    "blocked-missing-anchor-cache",
    "invalidated-by-anchor-switch",
)


def diagnosis_path(ctx, effect: str) -> Path:
    return ctx.vfx_root / "gap-diagnosis" / f"{slugify(effect)}.jsonl"


def make_id(effect: str, layer: str, symptom: str) -> str:
    timestamp = utc_now_iso().replace(":", "").replace("-", "").replace("+", "z")
    return f"diag-{slugify(effect)}-{slugify(layer)}-{slugify(symptom)}-{timestamp}"


def add_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    entry = {
        "id": args.id or make_id(args.effect, args.layer, args.symptom),
        "timestamp": utc_now_iso(),
        "effect": args.effect,
        "layer": args.layer,
        "preview_path": args.preview_path,
        "reference_path": args.reference_path,
        "symptom": args.symptom,
        "suspect_layer": args.suspect_layer,
        "confidence": args.confidence,
        "observation": args.observation,
        "evidence": args.evidence,
        "rejected_layers": args.rejected_layer,
        "next_action": args.next_action,
        "status": args.status,
    }
    append_jsonl(diagnosis_path(ctx, args.effect), entry)
    print(diagnosis_path(ctx, args.effect))
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    entries = read_jsonl(diagnosis_path(ctx, args.effect))
    if args.layer:
        entries = [entry for entry in entries if entry.get("layer") == args.layer]
    lines = [f"# Gap Diagnosis: {args.effect}", ""]
    for entry in entries:
        lines.extend(
            [
                f"## {entry['id']}",
                "",
                f"- Time: `{entry['timestamp']}`",
                f"- Layer: `{entry.get('layer', '')}`",
                f"- Symptom: `{entry.get('symptom', '')}`",
                f"- Suspect layer: `{entry.get('suspect_layer', '')}` confidence=`{entry.get('confidence', '')}`",
                f"- Preview: `{entry.get('preview_path', '')}`",
                f"- Reference: `{entry.get('reference_path', '')}`",
                f"- Observation: {entry.get('observation', '')}",
                f"- Evidence: {entry.get('evidence', '')}",
                f"- Rejected layers: {', '.join(entry.get('rejected_layers', [])) or 'none'}",
                f"- Next action: {entry.get('next_action', '')}",
                f"- Status: `{entry.get('status', '')}`",
                "",
            ]
        )
    out_path = Path(args.out) if args.out else default_report_path(ctx, "gap-diagnosis", args.effect, "gap-diagnosis", ".md")
    write_text(out_path, "\n".join(lines).rstrip() + "\n")
    print(out_path)
    return 0


def set_status_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    path = diagnosis_path(ctx, args.effect)
    entries = read_jsonl(path)
    changed = 0
    for entry in entries:
        if entry.get("id") != args.id:
            continue
        entry["status"] = args.status
        if args.note:
            entry["status_note"] = args.note
        entry["updated_at"] = utc_now_iso()
        changed += 1
    if not changed:
        raise SystemExit(f"Diagnosis id not found for effect {args.effect}: {args.id}")
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(path)
    return 0


def list_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    for entry in read_jsonl(diagnosis_path(ctx, args.effect)):
        if args.layer and entry.get("layer") != args.layer:
            continue
        print(entry)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record cross-layer visual gap diagnosis before tuning textures, materials, Niagara, or integration.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add")
    add.add_argument("--id", default="")
    add.add_argument("--effect", required=True)
    add.add_argument("--layer", required=True)
    add.add_argument("--preview-path", default="")
    add.add_argument("--reference-path", default="")
    add.add_argument("--symptom", required=True, choices=SYMPTOMS)
    add.add_argument("--suspect-layer", required=True, choices=SUSPECT_LAYERS)
    add.add_argument("--confidence", default="medium", choices=["low", "medium", "high"])
    add.add_argument("--observation", required=True)
    add.add_argument("--evidence", default="")
    add.add_argument("--rejected-layer", action="append", default=[], choices=SUSPECT_LAYERS)
    add.add_argument("--next-action", required=True)
    add.add_argument("--status", default="open", choices=VALID_STATUS)
    add.set_defaults(func=add_command)

    export = subparsers.add_parser("export-md")
    export.add_argument("--effect", required=True)
    export.add_argument("--layer", default="")
    export.add_argument("--out")
    export.set_defaults(func=export_command)

    set_status = subparsers.add_parser("set-status")
    set_status.add_argument("--effect", required=True)
    set_status.add_argument("--id", required=True)
    set_status.add_argument("--status", required=True, choices=VALID_STATUS)
    set_status.add_argument("--note", default="")
    set_status.set_defaults(func=set_status_command)

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--effect", required=True)
    list_cmd.add_argument("--layer", default="")
    list_cmd.set_defaults(func=list_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
