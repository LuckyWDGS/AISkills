"""Safely report and remove stale local VFX artifacts and Codex temp UE actors/assets.

UE reads and deletes go through Epic's built-in MCP: ``SceneTools.find_actors`` for
tagged preview actors, ``AssetTools.find_assets`` for temp assets (classified
locally), and a ``builtin_mcp`` batch for removal with an ``exists`` readback.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .core import default_report_path, load_json, resolve_root_context, save_json, utc_now_iso
from .mcp import DEFAULT_MCP_URL, builtin_mcp, connect


PREVIEW_ACTOR_TAG = "CodexVFXPreviewTemp"


def classify_ue_asset(package: str) -> dict[str, Any] | None:
    """Cleanup policy for a UE package path; None leaves it alone."""
    leaf = package.rsplit("/", 1)[-1]
    if package.startswith("/Game/CodexTemp/MaterialPreview/NS_CodexPreview_"):
        return {"reason": "codex-preview-niagara-asset", "safe_delete": True}
    if package.startswith("/Game/CodexTemp/") and "/Niagara/" in package:
        smoke_tokens = ("Smoke", "DryRun", "Pipeline", "Promote", "ApprovalGate")
        manual_tokens = ("Quarantine", "RendererTest", "TorchFlame_Codex", "SubUV_Test")
        if any(token in package or token in leaf for token in smoke_tokens):
            return {"reason": "codex-smoke-niagara-asset", "safe_delete": True}
        if any(token in package or token in leaf for token in manual_tokens):
            return {"reason": "manual-review-codex-niagara-experiment", "safe_delete": False}
    if package.startswith("/Game/VFX/") and "/Niagara/" in package and "Smoke" in leaf:
        return {"reason": "promoted-smoke-niagara-asset", "safe_delete": True}
    return None


def scan_ue(client: Any, module: Any, *, actors: bool, asset_roots: list[str]) -> list[dict[str, Any]]:
    def call(toolset: str, tool: str, args: dict[str, Any]) -> Any:
        return module.unwrap_result(client.call_resolved_tool(toolset, tool, args))

    rows: list[dict[str, Any]] = []
    if actors:
        found = call("SceneTools", "find_actors", {"name": "", "tag": PREVIEW_ACTOR_TAG, "collision_channels": [],
                                                   "root": None, "actor_type": None, "bounds": None})
        for actor in found or []:
            ref = actor.get("refPath", "") if isinstance(actor, dict) else str(actor)
            rows.append({"type": "ue-actor", "actor_name": ref.rsplit(".", 1)[-1], "actor_ref": ref,
                         "reason": PREVIEW_ACTOR_TAG, "safe_delete": True})
    for root in asset_roots:
        if not call("AssetTools", "exists", {"path": root}):
            continue
        for path in call("AssetTools", "find_assets", {"folder_path": root, "name": "", "asset_type": None,
                                                       "recursive": True, "tags": None}) or []:
            package = str(path).split(".", 1)[0]
            info = classify_ue_asset(package)
            if info:
                rows.append({"type": "ue-asset", "asset_path": package, **info})
    return sorted(rows, key=lambda item: item.get("asset_path") or item.get("actor_ref", ""))


def candidate_label(candidate: dict[str, Any]) -> str:
    if candidate["type"] == "ue-actor":
        return f"remove actor {candidate.get('actor_name')}"
    return f"delete {candidate.get('asset_path')}"


def build_delete_steps(candidates: list[dict[str, Any]], *, actors: bool, assets: bool) -> list[dict[str, Any]]:
    """Batch steps for the safe UE candidates the flags allow. Pure."""
    steps: list[dict[str, Any]] = []
    for candidate in candidates:
        if not candidate.get("safe_delete"):
            continue
        if candidate["type"] == "ue-actor" and actors and candidate.get("actor_ref"):
            steps.append({"label": candidate_label(candidate), "toolset": "SceneTools",
                          "tool": "remove_from_scene", "args": {"actor": {"refPath": candidate["actor_ref"]}}})
        elif candidate["type"] == "ue-asset" and assets:
            steps.append({"label": candidate_label(candidate), "toolset": "AssetTools", "tool": "delete",
                          "args": {"path": candidate["asset_path"]},
                          "readback": {"toolset": "AssetTools", "tool": "exists", "args": {"path": candidate["asset_path"]}},
                          "expect": False})
    return [{**step, "_line": index} for index, step in enumerate(steps, start=1)]


def latest_delivery_index(ctx, effect: str) -> dict[str, Any]:
    if not effect:
        return {}
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


def delivery_guard(delivery_index: dict[str, Any]) -> dict[str, Any]:
    if not delivery_index:
        return {
            "checked": False,
            "overall": "unknown",
            "delivery_index_path": "",
            "open_gates": [],
        }
    health = delivery_index.get("health") or {}
    checks = health.get("checks") or {}
    open_gates = [
        {
            "gate": key,
            "status": item.get("status", "unknown"),
            "detail": item.get("detail", ""),
            "action_needed": item.get("action_needed", ""),
        }
        for key, item in checks.items()
        if item.get("status") not in {"pass", "not_applicable"}
    ]
    return {
        "checked": True,
        "overall": health.get("overall", delivery_index.get("overall", "unknown")),
        "delivery_index_path": delivery_index.get("_source_path", ""),
        "open_gates": open_gates,
    }


def report_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    candidates: list[dict[str, Any]] = []
    base = ctx.vfx_root
    for folder_name in ("debug", "rejected"):
        folder = base / "reference-cache" / folder_name
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file():
                    candidates.append(
                        {
                            "type": "file",
                            "path": str(path),
                            "reason": f"reference-cache/{folder_name}",
                            "safe_delete": True,
                        }
                    )
    for folder_name in ("previews",):
        folder = base / folder_name
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".tmp", ".log"}:
                    candidates.append(
                        {
                            "type": "file",
                            "path": str(path),
                            "reason": "preview-temp",
                            "safe_delete": True,
                        }
                    )
    if args.scan_ue or args.scan_ue_assets:
        client = connect(ctx.skill_root, url=args.mcp_url, timeout=args.timeout, project=args.project)
        try:
            candidates += scan_ue(client, builtin_mcp(ctx.skill_root), actors=args.scan_ue,
                                  asset_roots=(args.ue_asset_root or ["/Game/CodexTemp"]) if args.scan_ue_assets else [])
        finally:
            client.close()
    report = {
        "version": 1,
        "generated_at": utc_now_iso(),
        "project_root": str(ctx.project_root),
        "delivery_guard": delivery_guard(latest_delivery_index(ctx, args.effect)),
        "candidates": candidates,
    }
    out_path = Path(args.out) if args.out else default_report_path(ctx, "cleanup", "shared", "cleanup-report", ".json")
    save_json(out_path, report)
    print(out_path)
    return 0


def apply_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    report = load_json(Path(args.report), None)
    if report is None:
        raise SystemExit(f"Cleanup report not found: {args.report}")
    removed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for candidate in report["candidates"]:
        if candidate.get("safe_delete") and candidate["type"] == "file":
            path = Path(candidate["path"]).resolve()
            if ctx.vfx_root.resolve() not in path.parents:
                continue
            if path.exists():
                path.unlink()
                removed.append(candidate)
    steps = build_delete_steps(report["candidates"], actors=args.delete_ue_temp_actors, assets=args.delete_ue_temp_assets)
    batch = None
    if steps:
        module = builtin_mcp(ctx.skill_root)
        client = connect(ctx.skill_root, url=args.mcp_url, timeout=args.timeout, project=args.project)
        try:
            batch = module.run_batch(client, steps, continue_on_error=True)
        finally:
            client.close()
        by_label = {row.get("label"): row for row in batch.get("results", [])}
        for candidate in report["candidates"]:
            row = by_label.get(candidate_label(candidate)) if candidate["type"] != "file" else None
            if row is not None:
                (removed if row.get("status") == "ok" else failed).append({**candidate, "delete_result": row})
        failed += [{"type": "batch", "problem": problem} for problem in batch.get("problems") or []]
    result = {
        "applied_at": utc_now_iso(),
        "removed": removed,
        "failed": failed,
        "transport": "epic-mcp batch" if batch else "local",
    }
    out_path = Path(args.out) if args.out else Path(args.report).with_name("cleanup-apply.json")
    save_json(out_path, result)
    print(out_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely report and remove stale local VFX artifacts and tagged UE temp actors.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report")
    report.add_argument("--effect", default="")
    report.add_argument("--out")
    report.add_argument("--scan-ue", action="store_true")
    report.add_argument("--scan-ue-assets", action="store_true")
    report.add_argument("--ue-asset-root", action="append", default=[])
    report.add_argument("--project")
    report.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    report.add_argument("--timeout", type=int, default=120)
    report.set_defaults(func=report_command)

    apply = subparsers.add_parser("apply")
    apply.add_argument("report")
    apply.add_argument("--out")
    apply.add_argument("--project")
    apply.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    apply.add_argument("--timeout", type=int, default=120)
    apply.add_argument("--delete-ue-temp-actors", action="store_true")
    apply.add_argument("--delete-ue-temp-assets", action="store_true")
    apply.set_defaults(func=apply_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
