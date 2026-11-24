from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import _text, load_json, resolve_path
from .material_variant_runner import normalize_type, schema_parameters, should_participate
from .static_switch_variant_expander import bool_value, collect_switch_rows


PLATFORM_LIMITS = {
    "pc": {"warn": 16, "fail": 32},
    "android": {"warn": 4, "fail": 8},
    "low_end": {"warn": 2, "fail": 4},
}


def split_platforms(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values or []:
        result.extend(item.strip().lower() for item in str(value).split(",") if item.strip())
    return result or ["pc", "android", "low_end"]


def load_switch_rows_from_schema(path: Path, include_non_regression: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    payload = load_json(path)
    parameters = schema_parameters(payload)
    switches, skipped = collect_switch_rows(
        parameters,
        include_non_regression=include_non_regression,
        overrides={},
    )
    return switches, skipped, payload


def load_switch_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str]:
    if args.switch_expander_report:
        path = resolve_path(args.switch_expander_report, base=Path.cwd())
        payload = load_json(path)
        switches = [item for item in payload.get("switch_parameters") or [] if isinstance(item, dict)]
        skipped = [item for item in payload.get("skipped_parameters") or [] if isinstance(item, dict)]
        return switches, skipped, payload, str(path)
    if args.parameter_schema:
        path = resolve_path(args.parameter_schema, base=Path.cwd())
        switches, skipped, payload = load_switch_rows_from_schema(path, args.include_non_regression)
        return switches, skipped, payload, str(path)
    raise SystemExit("Provide --switch-expander-report or --parameter-schema.")


def requested_permutations(switch_rows: list[dict[str, Any]]) -> int:
    if not switch_rows:
        return 1
    total = 1
    for row in switch_rows:
        allowed = row.get("allowed_values") if isinstance(row.get("allowed_values"), list) else []
        total *= max(1, len(allowed))
    return total


def material_identity(payload: dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    effect = args.effect or _text(payload.get("effect")) or "Material"
    material_path = args.material_path or _text(payload.get("material_path")) or ""
    return effect, material_path


def realized_groups(args: argparse.Namespace, material_path: str) -> list[dict[str, Any]]:
    if not args.shader_permutation_report:
        return []
    path = resolve_path(args.shader_permutation_report, base=Path.cwd())
    payload = load_json(path)
    rows = [item for item in payload.get("groups") or [] if isinstance(item, dict)]
    if not material_path:
        return rows
    return [item for item in rows if _text(item.get("base_path")) == material_path]


def build_findings(
    switch_rows: list[dict[str, Any]],
    requested: int,
    *,
    emitted: int,
    truncated: bool,
    skipped: list[dict[str, Any]],
    platforms: list[str],
    realized: list[dict[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not switch_rows:
        add("info", "no_static_switches", "No participating static-switch parameters were found.")
    for platform in platforms:
        limits = PLATFORM_LIMITS.get(platform)
        if not limits:
            add("warning", "unknown_platform", f"Unknown platform budget `{platform}`; no guard threshold was applied.")
            continue
        if requested > limits["fail"]:
            add("error", f"{platform}_permutation_budget", f"Estimated permutation count {requested} exceeds {platform} hard budget {limits['fail']}.")
        elif requested > limits["warn"]:
            add("warning", f"{platform}_permutation_pressure", f"Estimated permutation count {requested} exceeds {platform} warning budget {limits['warn']}.")
    if truncated:
        add("warning", "expansion_truncated", f"Static-switch expansion emitted only {emitted}/{requested} permutations.")
    if skipped:
        add("warning", "switch_rows_skipped", f"{len(skipped)} static-switch rows could not participate in the guard estimate.")
    if len(switch_rows) >= 5 and requested >= 16:
        add("warning", "switch_breadth", f"{len(switch_rows)} static switches are participating, which raises shader-permutation review pressure.")
    if realized:
        group_count = len(realized)
        if group_count > requested:
            add("warning", "realized_groups_exceed_estimate", f"Live permutation report found {group_count} realized groups, above the current estimated {requested}.")
        elif requested > 1 and group_count <= 1:
            add("info", "live_groups_low", "Live permutation report currently shows little realized MI spread even though the schema allows more switch combinations.")
    return findings


def summary_counts(findings: list[dict[str, str]]) -> dict[str, int]:
    return {
        "errors": sum(1 for item in findings if item["severity"] == "error"),
        "warnings": sum(1 for item in findings if item["severity"] == "warning"),
        "info": sum(1 for item in findings if item["severity"] == "info"),
    }


def next_actions(report: dict[str, Any]) -> list[str]:
    counts = report.get("summary") or {}
    requested = counts.get("requested_permutation_count", 0)
    actions: list[str] = []
    if (report.get("gate") or {}).get("passed"):
        actions.append("Permutation budget is within the selected platform guardrails; proceed with MI expansion and preview/regression coverage.")
    else:
        actions.append("Collapse static switches, split optional features into separate parents, or move non-runtime branches out of the master material.")
    if counts.get("realized_group_count", 0):
        actions.append("Compare the estimated switch space against shader_permutation_report.py output to see whether the project is already materializing too many MI signatures.")
    if requested > 1:
        actions.append("Run static_switch_variant_expander.py before material_delivery_smoke.py so smoke coverage includes the risky switch combinations, not only dynamic parameters.")
    return actions


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    switch_rows, skipped, payload, source_path = load_switch_rows(args)
    effect, material_path = material_identity(payload, args)
    requested = requested_permutations(switch_rows)
    emitted = int(((payload.get("summary") or {}).get("emitted_permutation_count")) or requested)
    truncated = bool(((payload.get("gate") or {}).get("switch_space_truncated")) or emitted < requested)
    platforms = split_platforms(args.platform)
    realized = realized_groups(args, material_path)
    findings = build_findings(
        switch_rows,
        requested,
        emitted=emitted,
        truncated=truncated,
        skipped=skipped,
        platforms=platforms,
        realized=realized,
    )
    counts = summary_counts(findings)
    out = Path(args.out) if args.out else default_report_path(ctx, "permutations", effect, "permutation-budget-guard", ".json")
    report = {
        "tool": "permutation_budget_guard",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "material_path": material_path,
        "source_report": source_path,
        "platforms": platforms,
        "switch_parameters": switch_rows,
        "estimated": {
            "switch_count": len(switch_rows),
            "requested_permutation_count": requested,
            "emitted_permutation_count": emitted,
            "truncated": truncated,
        },
        "realized_groups": realized,
        "findings": findings,
        "summary": {
            **counts,
            "requested_permutation_count": requested,
            "emitted_permutation_count": emitted,
            "switch_count": len(switch_rows),
            "skipped_switch_count": len(skipped),
            "realized_group_count": len(realized),
        },
        "gate": {
            "passed": counts["errors"] == 0,
            "within_budget": counts["errors"] == 0,
            "has_pressure": counts["warnings"] > 0,
        },
    }
    report["next_actions"] = next_actions(report)
    return report, out


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# Permutation Budget Guard: {report.get('effect')}",
        "",
        f"- Passed: `{(report.get('gate') or {}).get('passed')}`",
        f"- Platforms: `{', '.join(report.get('platforms') or [])}`",
        f"- Static switches: `{summary.get('switch_count', 0)}`",
        f"- Requested permutations: `{summary.get('requested_permutation_count', 0)}`",
        f"- Emitted permutations: `{summary.get('emitted_permutation_count', 0)}`",
        f"- Realized groups: `{summary.get('realized_group_count', 0)}`",
        "",
        "## Findings",
        "",
    ]
    if report.get("findings"):
        for item in report["findings"]:
            lines.append(f"- [{item['severity']}] `{item['rule']}` {item['message']}")
    else:
        lines.append("- No findings.")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guard single-material static-switch permutation pressure before it spreads into project-scale shader sprawl.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--parameter-schema", default="", help="material_parameter_schema.py report.")
    parser.add_argument("--switch-expander-report", default="", help="static_switch_variant_expander.py report.")
    parser.add_argument("--shader-permutation-report", default="", help="Optional shader_permutation_report.py output.")
    parser.add_argument("--effect", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--include-non-regression", action="store_true")
    parser.add_argument("--platform", action="append", default=[])
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
