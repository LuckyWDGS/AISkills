from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import delivery_dashboard, delivery_finalize, delivery_package, live_asset_verify, niagara_audit
from .core import default_report_path, normalize_cli_global_args_no_subcommand, resolve_root_context, save_json, utc_now_iso, write_text
from .delivery_package import check_delivery_payload, find_latest_delivery_index, load_delivery_payload


def run_step(name: str, fn, args: argparse.Namespace, *, allow_failure: bool = False) -> dict[str, Any]:
    try:
        code = fn(args)
        return {"name": name, "status": "pass" if code == 0 else "risk", "exit_code": code, "error": ""}
    except Exception as exc:
        if allow_failure:
            return {"name": name, "status": "blocked", "exit_code": 2, "error": str(exc)}
        raise


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Delivery Chain Smoke: {report.get('effect_name')}",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Generated UTC: `{report.get('generated_utc')}`",
        f"- Delivery index: `{report.get('delivery_index') or 'none'}`",
        "",
        "## Steps",
        "",
    ]
    for step in report.get("steps", []):
        lines.append(f"- `{step['name']}`: `{step['status']}` exit=`{step.get('exit_code')}` {step.get('error') or ''}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    steps: list[dict[str, Any]] = []
    if not args.skip_audit:
        for system_path in args.final_system:
            steps.append(
                run_step(
                    f"audit:{system_path}",
                    niagara_audit.command,
                    argparse.Namespace(
                        system_path=system_path,
                        root=args.root,
                        project=args.project,
                        endpoint=args.endpoint,
                        timeout=args.timeout,
                        out="",
                        markdown=True,
                    ),
                    allow_failure=args.allow_blocked_ue,
                )
            )
    if args.texture_asset_path and args.material_path:
        steps.append(
            run_step(
                "live-asset-verify",
                live_asset_verify.command,
                argparse.Namespace(
                    root=args.root,
                    effect=args.effect,
                    project=args.project,
                    endpoint=args.endpoint,
                    timeout=args.timeout,
                    local_file=args.local_file,
                    source_policy=args.source_policy,
                    texture_asset_path=args.texture_asset_path,
                    material_path=args.material_path,
                    renderer_path=args.renderer_path,
                    out="",
                    markdown=True,
                ),
                allow_failure=args.allow_blocked_ue,
            )
        )
    package_args = argparse.Namespace(
        root=args.root,
        effect=args.effect,
        asset=list(args.asset or []),
        final_system=list(args.final_system or []),
        final_material=list(args.final_material or []),
        effect_type_contract=args.effect_type_contract,
        require_niagara_renderer=list(args.require_niagara_renderer or []),
        require_niagara_material=list(args.require_niagara_material or []),
        require_attribute_reader_data_flow=args.require_attribute_reader_data_flow,
        require_niagara_bounds=args.require_niagara_bounds,
        forbid_test_emitter=args.forbid_test_emitter,
        require_visual_qa=args.require_visual_qa,
        max_visual_mean_diff=args.max_visual_mean_diff,
        max_visual_edge_mean_diff=args.max_visual_edge_mean_diff,
        max_visual_mask_delta=args.max_visual_mask_delta,
        low_end_note=args.low_end_note,
        risk=list(args.risk or []),
        notes=args.notes or "Full delivery chain smoke.",
        require_ready=args.require_ready,
    )
    steps.append(run_step("delivery-package", delivery_package.package_command, package_args))
    index_path = find_latest_delivery_index(ctx, args.effect)
    delivery_overall = "unknown"
    if index_path:
        payload = load_delivery_payload(index_path)
        delivery_overall = str((payload.get("health") or {}).get("overall") or payload.get("overall") or "unknown")
        gate_code = check_delivery_payload(payload, require_ready=args.require_ready)
        check_status = "pass" if gate_code == 0 and delivery_overall == "ready" else delivery_overall
        if check_status not in {"pass", "ready", "blocked", "risk", "incomplete"}:
            check_status = "risk"
        steps.append({"name": "delivery-check", "status": "pass" if check_status == "ready" else check_status, "exit_code": gate_code, "error": ""})
    steps.append(
        run_step(
            "delivery-dashboard",
            delivery_dashboard.command,
            argparse.Namespace(root=args.root, out="", markdown=True, markdown_out="", html=args.html_dashboard, html_out=""),
        )
    )
    if args.finalize and index_path:
        steps.append(
            run_step(
                "delivery-finalize",
                delivery_finalize.command,
                argparse.Namespace(
                    root=args.root,
                    index=str(index_path),
                    effect=args.effect,
                    notes=args.notes,
                    out="",
                    promote_assets=args.promote_assets,
                    promote_root=args.promote_root,
                    promote_map=list(args.promote_map or []),
                    promote_mode=args.promote_mode,
                    dry_run_promote=args.dry_run_promote,
                    save_promoted_assets=args.save_promoted_assets,
                    project=args.project,
                    endpoint=args.endpoint,
                    timeout=args.timeout,
                ),
            )
        )
    status = "pass"
    if any(step["status"] == "blocked" for step in steps):
        status = "blocked"
    elif any(step["status"] == "risk" for step in steps):
        status = "risk"
    elif any(step["status"] == "incomplete" for step in steps):
        status = "incomplete"
    report = {
        "tool": "delivery_chain_smoke",
        "generated_utc": utc_now_iso(),
        "effect_name": args.effect,
        "status": status,
        "delivery_overall": delivery_overall,
        "delivery_index": str(index_path or ""),
        "steps": steps,
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "chain-smoke", args.effect, "delivery-chain-smoke", ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.require_ready and status != "pass":
        return 2
    return 0 if status != "blocked" or args.allow_blocked_ue else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a real effect delivery-chain smoke: audit -> package/check -> dashboard -> optional finalize.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", required=True)
    parser.add_argument("--final-system", action="append", required=True)
    parser.add_argument("--final-material", action="append", default=[])
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--local-file", default="")
    parser.add_argument("--source-policy", default="ue-only", choices=("generated", "required", "ue-only"))
    parser.add_argument("--texture-asset-path", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--renderer-path", default="")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--allow-blocked-ue", action="store_true")
    parser.add_argument("--effect-type-contract", default="", choices=delivery_package.effect_type_names())
    parser.add_argument("--require-niagara-renderer", action="append", default=[])
    parser.add_argument("--require-niagara-material", action="append", default=[])
    parser.add_argument("--require-attribute-reader-data-flow", action="store_true")
    parser.add_argument("--require-niagara-bounds", action="store_true")
    parser.add_argument("--forbid-test-emitter", action="store_true")
    parser.add_argument("--require-visual-qa", action="store_true")
    parser.add_argument("--max-visual-mean-diff", type=float, default=64.0)
    parser.add_argument("--max-visual-edge-mean-diff", type=float, default=48.0)
    parser.add_argument("--max-visual-mask-delta", type=float, default=0.35)
    parser.add_argument("--low-end-note", default="")
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--html-dashboard", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--promote-assets", action="store_true")
    parser.add_argument("--promote-root", default="")
    parser.add_argument("--promote-map", action="append", default=[])
    parser.add_argument("--promote-mode", choices=("move", "duplicate"), default="move")
    parser.add_argument("--dry-run-promote", action="store_true")
    parser.add_argument("--save-promoted-assets", action="store_true")
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
