from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import read_jsonl, resolve_root_context, save_json, write_text
from .effect_state import (
    acceptance_default,
    approvals_default,
    asset_plan_default,
    effect_folder,
    integration_default,
    load_effect_record,
)
from .tuning_log import log_path
from .visual_layer_map import load_map


def build_manifest(ctx, effect: str, args: argparse.Namespace) -> dict[str, Any]:
    acceptance = load_effect_record(ctx, "reference-acceptance", effect, acceptance_default(effect))
    approvals = load_effect_record(ctx, "preview-approvals", effect, approvals_default(effect))
    asset_plan = load_effect_record(ctx, "asset-plans", effect, asset_plan_default(effect))
    integration = load_effect_record(ctx, "integration-plans", effect, integration_default(effect))
    tuning_entries = read_jsonl(log_path(ctx, effect))
    layer_map = load_map(ctx, effect)
    approved_previews = [item for item in approvals["reviews"] if item["status"] == "approved"]
    return {
        "version": 1,
        "effect_name": effect,
        "approved_anchor": acceptance["anchor_lock"]["entry_id"],
        "approved_previews": approved_previews,
        "layer_count": len(layer_map["layers"]),
        "active_assets": args.asset,
        "final_systems": args.final_system,
        "final_materials": args.final_material,
        "low_end_note": args.low_end_note,
        "risks": args.risk,
        "notes": args.notes,
        "supporting_records": {
            "layer_map_effect": effect,
            "asset_plan_present": bool(asset_plan.get("assets")),
            "integration_present": bool(integration.get("runtime_contract")),
            "tuning_entry_count": len(tuning_entries),
        },
    }


def render_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# Delivery Package: {manifest['effect_name']}",
        "",
        f"- Approved anchor: `{manifest['approved_anchor'] or 'unset'}`",
        f"- Approved previews: `{len(manifest['approved_previews'])}`",
        f"- Layer count: `{manifest['layer_count']}`",
        f"- Final systems: {', '.join(manifest['final_systems']) or 'none'}",
        f"- Final materials: {', '.join(manifest['final_materials']) or 'none'}",
        f"- Active assets: {', '.join(manifest['active_assets']) or 'none'}",
        f"- Low-end note: {manifest['low_end_note'] or 'none'}",
        "",
        "## Risks",
        "",
    ]
    for item in manifest["risks"]:
        lines.append(f"- {item}")
    if not manifest["risks"]:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    manifest = build_manifest(ctx, args.effect, args)
    folder = effect_folder(ctx, "delivery", args.effect)
    manifest_path = folder / "manifest.json"
    save_json(manifest_path, manifest)
    write_text(folder / "summary.md", render_markdown(manifest))
    print(manifest_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assemble a delivery manifest from the effect's closed-loop records.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", required=True)
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--final-system", action="append", default=[])
    parser.add_argument("--final-material", action="append", default=[])
    parser.add_argument("--low-end-note", default="")
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
