from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .bridge import BridgeClient, BridgeError
from .core import default_report_path, normalize_cli_global_args_no_subcommand, resolve_root_context, save_json, utc_now_iso, write_text
from .live_asset_verify import build_ue_script as build_live_asset_verify_script
from .live_asset_verify import verification_passed


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# UE Smoke: {report.get('effect') or 'shared'}",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Generated UTC: `{report.get('generated_utc')}`",
        f"- Project: `{report.get('project') or 'default'}`",
        f"- Endpoint: `{report.get('endpoint') or 'auto'}`",
        f"- Verification passed: `{report.get('verification_passed')}`",
        f"- Blocked reason: {report.get('blocked_reason') or 'none'}",
        "",
        "## Live Asset Route",
        "",
        f"- Source policy: `{report.get('source_policy', '')}`",
        f"- Texture: `{report.get('texture_asset_path', '')}`",
        f"- Material: `{report.get('material_path', '')}`",
        f"- Renderer: `{report.get('renderer_path', '')}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    out = Path(args.out) if args.out else default_report_path(ctx, "ue-smoke", args.effect or "shared", "ue-smoke", ".json")
    report: dict[str, Any] = {
        "tool": "ue_smoke",
        "generated_utc": utc_now_iso(),
        "effect": args.effect or "",
        "project": args.project or "",
        "endpoint": args.endpoint or "",
        "status": "unknown",
        "blocked_reason": "",
        "source_policy": args.source_policy,
        "local_file": str(Path(args.local_file).resolve()) if args.local_file else "",
        "local_file_exists": bool(args.local_file and Path(args.local_file).exists()),
        "texture_asset_path": args.texture_asset_path,
        "material_path": args.material_path,
        "renderer_path": args.renderer_path,
        "verification_passed": False,
    }
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    try:
        report["ping"] = client.ping()
    except BridgeError as exc:
        report["status"] = "blocked"
        report["blocked_reason"] = str(exc)
        save_json(out, report)
        if args.markdown:
            write_text(out.with_suffix(".md"), render_markdown(report))
        print(out)
        return 2 if args.require_ue else 0

    if args.texture_asset_path and args.material_path:
        raw = client.exec_json(
            build_live_asset_verify_script(args.texture_asset_path, args.material_path, args.renderer_path),
            no_preflight=True,
        )
        report.update(raw)
        report["source_policy"] = args.source_policy
        report["verification_passed"] = verification_passed(report)
        report["status"] = "pass" if report["verification_passed"] else "risk"
    else:
        report["verification_passed"] = True
        report["status"] = "pass"

    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0 if report["status"] == "pass" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optional Unreal online smoke test. Missing UE records blocked instead of crashing the workflow.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--require-ue", action="store_true", help="Return non-zero if UE is unavailable; otherwise blocked smoke is recorded and skipped.")
    parser.add_argument("--source-policy", default="ue-only", choices=("generated", "required", "ue-only"))
    parser.add_argument("--local-file", default="")
    parser.add_argument("--texture-asset-path", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--renderer-path", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args_no_subcommand(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
