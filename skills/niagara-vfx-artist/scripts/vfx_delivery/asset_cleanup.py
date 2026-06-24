from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, load_json, resolve_root_context, save_json, utc_now_iso


def ue_temp_asset_report_script(roots: list[str]) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        ROOTS = {roots!r}
        rows = []

        def classify(pkg):
            leaf = pkg.rsplit("/", 1)[-1]
            if pkg.startswith("/Game/CodexTemp/MaterialPreview/NS_CodexPreview_"):
                return {{"reason": "codex-preview-niagara-asset", "safe_delete": True}}
            if pkg.startswith("/Game/CodexTemp/") and "/Niagara/" in pkg:
                smoke_tokens = ("Smoke", "DryRun", "Pipeline", "Promote", "ApprovalGate")
                manual_tokens = ("Quarantine", "RendererTest", "TorchFlame_Codex", "SubUV_Test")
                if any(token in pkg or token in leaf for token in smoke_tokens):
                    return {{"reason": "codex-smoke-niagara-asset", "safe_delete": True}}
                if any(token in pkg or token in leaf for token in manual_tokens):
                    return {{"reason": "manual-review-codex-niagara-experiment", "safe_delete": False}}
            if pkg.startswith("/Game/VFX/") and "/Niagara/" in pkg and "Smoke" in leaf:
                return {{"reason": "promoted-smoke-niagara-asset", "safe_delete": True}}
            return None

        for root in ROOTS:
            try:
                assets = EAL.list_assets(root, True, False)
            except Exception:
                assets = []
            for asset in assets:
                pkg = str(asset).split(".", 1)[0]
                info = classify(pkg)
                if info:
                    rows.append({{
                        "type": "ue-asset",
                        "asset_path": pkg,
                        "reason": info["reason"],
                        "safe_delete": bool(info["safe_delete"]),
                    }})

        print(json.dumps(sorted(rows, key=lambda item: item.get("asset_path", "")), ensure_ascii=False))
        """
    ).strip()


def ue_delete_asset_script(asset_path: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary
        asset_path = {asset_path!r}
        object_path = asset_path + "." + asset_path.rsplit("/", 1)[-1]
        asset_editor = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
        result = {{
            "asset_path": asset_path,
            "success": False,
            "editor_closed": False,
            "delete_error": "",
            "delete_method": "AssetTools.delete",
        }}
        try:
            asset = unreal.load_asset(asset_path)
            if asset is not None:
                try:
                    asset_editor.close_all_editors_for_asset(asset)
                    result["editor_closed"] = True
                except Exception:
                    pass
            try:
                unreal.SystemLibrary.collect_garbage()
            except Exception:
                pass
            tool = TR.execute_qualified_tool(
                'toolset_registry.toolsets.core.asset.AssetTools.delete',
                json.dumps({{'path': object_path}}, ensure_ascii=False),
                True,
            )
            output = None
            if tool.json_output:
                try:
                    output = json.loads(tool.json_output)
                except Exception:
                    output = tool.json_output
            result["tool_success"] = bool(tool.success)
            result["tool_output"] = output
            result["success"] = bool(tool.success) and bool((output or {{}}).get("returnValue", False))
            result["exists_after"] = bool(EAL.does_asset_exist(object_path))
            if result["exists_after"]:
                result["success"] = False
            if not result["success"]:
                result["delete_error"] = tool.error or f"AssetTools.delete returned {{output!r}}"
        except Exception as exc:
            result["delete_error"] = str(exc)
        asset = None
        try:
            unreal.SystemLibrary.collect_garbage()
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False))
        """
    ).strip()


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
    if (args.scan_ue or args.scan_ue_assets) and args.project:
        client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
        client.ping()
        if args.scan_ue:
            actors = client.exec_json(
                """
import json
import unreal
LV = unreal.UnrealBridgeLevelLibrary
print(json.dumps([str(item) for item in list(LV.find_actors_by_tag("CodexVFXPreviewTemp"))], ensure_ascii=False))
            )
            """.strip()
            )
            for actor_name in actors:
                candidates.append(
                    {
                        "type": "ue-actor",
                        "actor_name": actor_name,
                        "reason": "CodexVFXPreviewTemp",
                        "safe_delete": True,
                    }
                )
        if args.scan_ue_assets:
            roots = args.ue_asset_root or ["/Game/CodexTemp"]
            assets = client.exec_json(ue_temp_asset_report_script(roots))
            for row in assets:
                candidates.append(row)
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
    client = None
    for candidate in report["candidates"]:
        if not candidate.get("safe_delete"):
            continue
        if candidate["type"] == "file":
            path = Path(candidate["path"]).resolve()
            if ctx.vfx_root.resolve() not in path.parents:
                continue
            if path.exists():
                path.unlink()
                removed.append(candidate)
        elif candidate["type"] == "ue-actor" and args.delete_ue_temp_actors and args.project:
            if client is None:
                client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
                client.ping()
            client.exec_json(
                f"""
import json
import unreal
ok = unreal.UnrealBridgeLevelLibrary.destroy_actor({candidate['actor_name']!r})
print(json.dumps({{"success": bool(ok)}}, ensure_ascii=False))
                """.strip()
            )
            removed.append(candidate)
        elif candidate["type"] == "ue-asset" and args.delete_ue_temp_assets and args.project:
            if client is None:
                client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
                client.ping()
            result = client.exec_json(ue_delete_asset_script(candidate["asset_path"]))
            if result.get("success"):
                removed.append({**candidate, "delete_result": result})
            else:
                failed.append({**candidate, "delete_result": result})
    result = {
        "applied_at": utc_now_iso(),
        "removed": removed,
        "failed": failed,
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
    report.add_argument("--endpoint")
    report.add_argument("--timeout", type=int, default=120)
    report.set_defaults(func=report_command)

    apply = subparsers.add_parser("apply")
    apply.add_argument("report")
    apply.add_argument("--out")
    apply.add_argument("--project")
    apply.add_argument("--endpoint")
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
