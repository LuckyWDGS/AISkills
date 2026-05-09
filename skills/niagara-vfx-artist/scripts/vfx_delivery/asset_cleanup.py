from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, load_json, resolve_root_context, save_json, utc_now_iso


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
    if args.scan_ue and args.project:
        client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
        client.ping()
        actors = client.exec_json(
            """
import json
import unreal
LV = unreal.UnrealBridgeLevelLibrary
print(json.dumps(LV.find_actors_by_tag("CodexVFXPreviewTemp"), ensure_ascii=False))
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
    report = {
        "version": 1,
        "generated_at": utc_now_iso(),
        "project_root": str(ctx.project_root),
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
                client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
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
    result = {
        "applied_at": utc_now_iso(),
        "removed": removed,
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
    report.add_argument("--out")
    report.add_argument("--scan-ue", action="store_true")
    report.add_argument("--project")
    report.add_argument("--timeout", type=int, default=120)
    report.set_defaults(func=report_command)

    apply = subparsers.add_parser("apply")
    apply.add_argument("report")
    apply.add_argument("--out")
    apply.add_argument("--project")
    apply.add_argument("--timeout", type=int, default=120)
    apply.add_argument("--delete-ue-temp-actors", action="store_true")
    apply.set_defaults(func=apply_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
