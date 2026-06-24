from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .core import load_json, normalize_cli_global_args, read_jsonl, resolve_root_context, write_text
from .effect_state import learning_default, load_effect_record, save_effect_record
from .preview_approval import approvals_default
from .reference_acceptance import acceptance_default
from .tuning_log import log_path


def summarize_rules(effect: str, acceptance: dict, approvals: dict, tuning_entries: list[dict]) -> dict:
    success_rules = []
    failure_rules = []
    reuse_rules = []
    if acceptance["anchor_lock"]["entry_id"]:
        success_rules.append(f"Lock the accepted anchor `{acceptance['anchor_lock']['entry_id']}` before downstream generation.")
    if int(acceptance.get("anchor_lock", {}).get("revision", 0) or 0) > 1:
        success_rules.append("When the active anchor changes, invalidate earlier previews and diagnoses before trusting old conclusions.")
        failure_rules.append("Anchor switches can make older visual judgments historical even if the runtime asset did not change.")
    rejected_diffs = [diff for review in approvals["reviews"] if review["status"] in {"revise", "rejected"} for diff in review["differences"]]
    for item, count in Counter(rejected_diffs).most_common(5):
        failure_rules.append(f"`{item}` appeared {count} time(s) during preview review.")
    parameter_counter = Counter(entry["parameter"] for entry in tuning_entries if entry.get("parameter"))
    for item, count in parameter_counter.most_common(5):
        reuse_rules.append(f"Parameter `{item}` was tuned {count} time(s) for `{effect}`.")
    return {
        "anchor_lock": acceptance["anchor_lock"]["entry_id"],
        "approved_preview_count": len([item for item in approvals["reviews"] if item["status"] == "approved"]),
        "tuning_entry_count": len(tuning_entries),
        "success_rules": success_rules,
        "failure_rules": failure_rules,
        "reuse_rules": reuse_rules,
    }


def latest_delivery_index(ctx, effect: str) -> dict:
    folder = ctx.vfx_root / "delivery" / effect
    if not folder.exists():
        return {}
    candidates = sorted(folder.rglob("delivery-index.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return {}
    payload = load_json(candidates[0], {})
    if isinstance(payload, dict):
        payload["_source_path"] = str(candidates[0])
        return payload
    return {}


def delivery_index_summary(delivery_index: dict) -> dict:
    health = delivery_index.get("health") or {}
    checks = health.get("checks") or {}
    open_gates = []
    for key, item in checks.items():
        if item.get("status") in {"pass", "not_applicable"}:
            continue
        open_gates.append(
            {
                "gate": key,
                "status": item.get("status", "unknown"),
                "detail": item.get("detail", ""),
                "action_needed": item.get("action_needed", ""),
            }
        )
    return {
        "delivery_index_path": delivery_index.get("_source_path", ""),
        "overall": health.get("overall", delivery_index.get("overall", "unknown")),
        "open_gates": open_gates,
    }


def summarize_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    acceptance = load_effect_record(ctx, "reference-acceptance", args.effect, acceptance_default(args.effect))
    approvals = load_effect_record(ctx, "preview-approvals", args.effect, approvals_default(args.effect))
    tuning_entries = read_jsonl(log_path(ctx, args.effect))
    payload = load_effect_record(ctx, "learning-loop", args.effect, learning_default(args.effect))
    payload["auto_summary"] = summarize_rules(args.effect, acceptance, approvals, tuning_entries)
    if args.delivery_index:
        delivery_index = load_json(Path(args.delivery_index), {})
        if isinstance(delivery_index, dict) and delivery_index:
            delivery_index["_source_path"] = str(Path(args.delivery_index))
    else:
        delivery_index = latest_delivery_index(ctx, args.effect)
    if delivery_index:
        payload["auto_summary"]["delivery_index"] = delivery_index_summary(delivery_index)
    payload["success_rules"] = payload["auto_summary"]["success_rules"]
    payload["failure_rules"] = payload["auto_summary"]["failure_rules"]
    payload["reuse_rules"] = payload["auto_summary"]["reuse_rules"]
    delivery_summary = payload["auto_summary"].get("delivery_index") or {}
    if delivery_summary:
        if delivery_summary.get("overall") == "ready":
            payload["success_rules"].append("Latest delivery index is ready; keep final package checks attached to delivery-index.json.")
        else:
            payload["failure_rules"].append(
                f"Latest delivery index is `{delivery_summary.get('overall', 'unknown')}`; resolve open delivery gates before claiming final delivery."
            )
    path = save_effect_record(ctx, "learning-loop", args.effect, payload)
    print(path)
    return 0


def add_lesson_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "learning-loop", args.effect, learning_default(args.effect))
    payload["manual_lessons"].append({"kind": args.kind, "text": args.text})
    path = save_effect_record(ctx, "learning-loop", args.effect, payload)
    print(path)
    return 0


def export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    payload = load_effect_record(ctx, "learning-loop", args.effect, learning_default(args.effect))
    target = Path(args.out) if args.out else Path(ctx.vfx_root / "learning-loop" / f"{args.effect}-case-study.md")
    lines = [f"# Learning Loop: {args.effect}", "", "## Success Rules", ""]
    for item in payload["success_rules"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Failure Rules", ""])
    for item in payload["failure_rules"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Reuse Rules", ""])
    for item in payload["reuse_rules"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Manual Lessons", ""])
    for item in payload["manual_lessons"]:
        lines.append(f"- [{item['kind']}] {item['text']}")
    write_text(target, "\n".join(lines).rstrip() + "\n")
    print(target)
    return 0


def show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    print(load_effect_record(ctx, "learning-loop", args.effect, learning_default(args.effect)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize reusable lessons from an effect's closed-loop records.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--effect", required=True)
    summarize.add_argument("--delivery-index", default="")
    summarize.set_defaults(func=summarize_command)

    add_lesson = subparsers.add_parser("add-lesson")
    add_lesson.add_argument("--effect", required=True)
    add_lesson.add_argument("--kind", required=True, choices=["success", "failure", "reuse"])
    add_lesson.add_argument("--text", required=True)
    add_lesson.set_defaults(func=add_lesson_command)

    export_md = subparsers.add_parser("export-md")
    export_md.add_argument("--effect", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=export_command)

    show = subparsers.add_parser("show")
    show.add_argument("--effect", required=True)
    show.set_defaults(func=show_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"summarize", "add-lesson", "export-md", "show"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
