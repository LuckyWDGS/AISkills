from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_regression import default_baseline_path
from .material_toolset_builder import GRAPH_DIFF_CATEGORY_TO_OPERATION, REFACTOR_OPERATIONS, normal_operation_name


SUPPORTED_APPLY_OPERATIONS = {
    "restore_route_contract",
    "repair_output_chain",
    "add_fresnel_layer",
    "add_depth_fade",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"JSON file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def resolve_existing_path(path_text: str, base: Path | None = None) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    if base:
        candidate = (base / path).resolve()
        if candidate.exists():
            return candidate
    return path.resolve()


def object_path(material_path: str) -> str:
    return str(material_path or "").split(".", 1)[0]


def object_ref(material_path: str) -> str:
    path = object_path(material_path)
    if not path:
        return ""
    return f"{path}.{path.rsplit('/', 1)[-1]}"


def default_apply_paths(target_material: str, label: str) -> dict[str, str]:
    name = object_path(target_material).rsplit("/", 1)[-1] or "Material"
    stem = slugify(f"{name}-{label}").replace("-", "_")[:96]
    folder = "/Game/CodexTemp/MaterialRefactorApply"
    return {
        "candidate_path": f"{folder}/{stem}_Candidate",
        "backup_path": f"{folder}/{stem}_Backup",
    }


def graph_diff_operations(graph_diff: dict[str, Any]) -> list[dict[str, Any]]:
    requested: list[str] = []
    for cause in graph_diff.get("likely_causes") or []:
        if not isinstance(cause, dict):
            continue
        op = GRAPH_DIFF_CATEGORY_TO_OPERATION.get(str(cause.get("category") or "").lower())
        if op and op not in requested:
            requested.append(op)
    if not requested:
        requested.append("normalize_parameters")
    rows: list[dict[str, Any]] = []
    for op in requested:
        definition = REFACTOR_OPERATIONS[op]
        rows.append(
            {
                "operation": op,
                "risk": definition.get("risk"),
                "candidate_nodes": definition.get("candidate_nodes") or [],
                "guardrails": definition.get("guardrails") or [],
            }
        )
    return rows


def resolve_inputs(args: argparse.Namespace) -> dict[str, Any]:
    refactor_plan: dict[str, Any] = {}
    patch_spec: dict[str, Any] = {}
    graph_diff: dict[str, Any] = {}
    source_paths = {"refactor_plan": "", "patch_spec": "", "graph_diff_report": ""}

    refactor_plan_path: Path | None = None
    if args.refactor_plan:
        refactor_plan_path = resolve_existing_path(args.refactor_plan)
        refactor_plan = load_json(refactor_plan_path)
        source_paths["refactor_plan"] = str(refactor_plan_path)
        if refactor_plan.get("tool") != "material_toolset_builder_refactor_plan":
            raise SystemExit(f"Expected material_toolset_builder_refactor_plan, got `{refactor_plan.get('tool')}`")
        if isinstance(refactor_plan.get("patch_spec"), dict):
            patch_spec = refactor_plan["patch_spec"]
        elif refactor_plan.get("patch_spec_path"):
            patch_path = resolve_existing_path(str(refactor_plan["patch_spec_path"]), refactor_plan_path.parent)
            if patch_path.exists():
                patch_spec = load_json(patch_path)
                source_paths["patch_spec"] = str(patch_path)
        if refactor_plan.get("source_graph_diff_report"):
            graph_path = resolve_existing_path(str(refactor_plan["source_graph_diff_report"]), refactor_plan_path.parent)
            if graph_path.exists():
                graph_diff = load_json(graph_path)
                source_paths["graph_diff_report"] = str(graph_path)

    if args.patch_spec:
        patch_path = resolve_existing_path(args.patch_spec)
        patch_spec = load_json(patch_path)
        source_paths["patch_spec"] = str(patch_path)

    if args.graph_diff_report:
        graph_path = resolve_existing_path(args.graph_diff_report)
        graph_diff = load_json(graph_path)
        source_paths["graph_diff_report"] = str(graph_path)
        if not patch_spec:
            patch_spec = {
                "target_material": (((graph_diff.get("identity") or {}).get("after") or {}).get("material_path")) or "",
                "operations": graph_diff_operations(graph_diff),
                "graph_diff_gate": graph_diff.get("gate") or {},
            }

    operations = patch_spec.get("operations") or refactor_plan.get("operations") or []
    normalized_ops: list[dict[str, Any]] = []
    for item in operations:
        if isinstance(item, str):
            op_name = normal_operation_name(item)
            definition = REFACTOR_OPERATIONS[op_name]
            item = {
                "operation": op_name,
                "risk": definition.get("risk"),
                "candidate_nodes": definition.get("candidate_nodes") or [],
                "guardrails": definition.get("guardrails") or [],
            }
        elif isinstance(item, dict):
            op_name = normal_operation_name(str(item.get("operation") or ""))
            item = {**item, "operation": op_name}
        else:
            continue
        normalized_ops.append(item)
    if not normalized_ops:
        normalized_ops = graph_diff_operations(graph_diff)

    target_material = args.material_path or patch_spec.get("target_material") or refactor_plan.get("target_material") or ""
    if not target_material and graph_diff:
        target_material = (((graph_diff.get("identity") or {}).get("after") or {}).get("material_path")) or ""
    if not target_material:
        raise SystemExit("Could not resolve target material. Provide --material-path, --patch-spec, --refactor-plan, or --graph-diff-report.")

    effect = args.effect or refactor_plan.get("effect") or graph_diff.get("effect") or "MaterialRefactor"
    layer = args.layer or refactor_plan.get("layer") or graph_diff.get("layer") or "Layer"
    label = args.label or refactor_plan.get("label") or graph_diff.get("label") or "apply"
    paths = default_apply_paths(target_material, label)
    candidate_path = args.candidate_path or paths["candidate_path"]
    backup_path = args.backup_path or paths["backup_path"]

    return {
        "refactor_plan": refactor_plan,
        "patch_spec": {**patch_spec, "operations": normalized_ops, "target_material": target_material},
        "graph_diff": graph_diff,
        "source_paths": source_paths,
        "effect": effect,
        "layer": layer,
        "label": label,
        "target_material": target_material,
        "candidate_path": candidate_path,
        "backup_path": backup_path,
    }


def route_from_graph_diff(graph_diff: dict[str, Any]) -> dict[str, Any]:
    before = (((graph_diff.get("diffs") or {}).get("route") or {}).get("before")) or {}
    if not before:
        return {}
    shading_models = before.get("shading_models") or []
    return {
        "domain": before.get("material_domain") or "Surface",
        "blend_mode": before.get("blend_mode") or "Opaque",
        "shading_model": shading_models[0] if shading_models else "DefaultLit",
        "two_sided": bool(before.get("two_sided")),
        "use_material_attributes": bool(before.get("use_material_attributes")),
        "usage_flags": before.get("usage_flags") or [],
    }


def before_output_connections(graph_diff: dict[str, Any]) -> list[dict[str, Any]]:
    before_path = (((graph_diff.get("inputs") or {}).get("before_audit")) or "")
    if not before_path:
        return []
    try:
        before_audit = load_json(resolve_existing_path(before_path))
    except Exception:
        return []
    raw = before_audit.get("raw_graph") or {}
    rows = raw.get("output_connections") or []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def operation_feasibility(operations: list[dict[str, Any]], graph_diff: dict[str, Any]) -> list[dict[str, Any]]:
    route = route_from_graph_diff(graph_diff)
    output_rows = before_output_connections(graph_diff)
    rows: list[dict[str, Any]] = []
    for operation in operations:
        name = str(operation.get("operation") or "")
        executable = name in SUPPORTED_APPLY_OPERATIONS
        reason = ""
        if name == "restore_route_contract" and not route:
            executable = False
            reason = "No before-route evidence is available from graph_diff_refactor."
        elif name == "repair_output_chain" and not output_rows:
            executable = False
            reason = "No before raw output connections are available; rerun material_audit.py with --include-raw-graph."
        elif name == "add_detail_normal":
            executable = False
            reason = "Detail normal apply needs texture/import evidence; first version leaves it review-only."
        elif name == "normalize_parameters":
            executable = False
            reason = "Parameter normalization is migration-sensitive; first version leaves it review-only."
        elif not executable:
            reason = "Operation is not in the graph_refactor_apply safe apply whitelist."
        rows.append({**operation, "executable": executable, "blocked_reason": reason})
    return rows


def build_apply_payload(resolved: dict[str, Any]) -> dict[str, Any]:
    graph_diff = resolved.get("graph_diff") or {}
    patch_spec = resolved.get("patch_spec") or {}
    operations = patch_spec.get("operations") or []
    feasible = operation_feasibility(operations, graph_diff)
    return {
        "tool": "graph_refactor_apply_payload",
        "version": 1,
        "target_material": resolved["target_material"],
        "candidate_path": resolved["candidate_path"],
        "backup_path": resolved["backup_path"],
        "operations": feasible,
        "route_restore": route_from_graph_diff(graph_diff),
        "before_output_connections": before_output_connections(graph_diff),
        "apply_scope": {
            "mode": "candidate_copy",
            "mutates_original": False,
            "backup_required": True,
            "review_required_before_replacing_original": True,
        },
    }


def summarize_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    try:
        payload = load_json(path)
    except Exception as exc:
        return {"path": str(path), "exists": True, "error": str(exc)}
    tool = payload.get("tool")
    summary: dict[str, Any] = {"path": str(path), "exists": True, "tool": tool}
    if tool == "material_audit":
        summary.update(
            {
                "material_path": (payload.get("material_info") or {}).get("path"),
                "analysis_findings": len((payload.get("analysis") or {}).get("findings") or []),
                "dead_nodes": len((payload.get("graph_summary") or {}).get("dead_nodes") or []),
            }
        )
    elif tool == "material_domain_audit":
        summary.update(payload.get("summary") or {})
    elif tool == "material_preview":
        outputs = payload.get("outputs") or {}
        contract = payload.get("contract_scan") or {}
        summary.update(
            {
                "material_path": payload.get("material_path"),
                "shaded_ok": outputs.get("shaded_ok"),
                "complexity_ok": outputs.get("complexity_ok"),
                "contract_findings": len(contract.get("findings") or []),
            }
        )
    elif tool == "material_regression_compare":
        summary.update(payload.get("gate") or {})
    return summary


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    report_path = ""
    for line in reversed(stdout.splitlines()):
        candidate = line.strip()
        if candidate and (candidate.endswith(".json") or Path(candidate).suffix == ".json"):
            report_path = candidate
            break
    row = {
        "command": command,
        "command_text": " ".join(command),
        "returncode": proc.returncode,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
        "report_path": report_path,
        "summary": summarize_report(Path(report_path)) if report_path else {},
    }
    return row


def validation_commands(args: argparse.Namespace, ctx: Any, target: str, candidate: str, preview_report_path: str | None = None) -> dict[str, list[str] | None]:
    tool_root = ctx.skill_root / "tools"

    def ue_args() -> list[str]:
        items: list[str] = []
        if args.project:
            items.extend(["--project", args.project])
        items.extend(["--timeout", str(args.timeout)])
        return items

    before_audit = [sys.executable, str(tool_root / "material_audit.py"), target, "--include-raw-graph", "--markdown", *ue_args()]
    before_domain = [sys.executable, str(tool_root / "material_domain_audit.py"), target, "--markdown", *ue_args()]
    after_audit = [sys.executable, str(tool_root / "material_audit.py"), candidate, "--include-raw-graph", "--markdown", *ue_args()]
    after_domain = [sys.executable, str(tool_root / "material_domain_audit.py"), candidate, "--markdown", *ue_args()]
    preview = [
        sys.executable,
        str(tool_root / "material_preview.py"),
        "capture",
        candidate,
        "--carrier",
        args.carrier,
        "--markdown",
        *ue_args(),
    ]
    regression: list[str] | None = None
    if preview_report_path:
        baseline = Path(args.baseline) if args.baseline else default_baseline_path(ctx, args.effect_resolved, args.layer_resolved)
        if baseline.exists():
            regression = [
                sys.executable,
                str(tool_root / "material_regression.py"),
                "compare",
                "--effect",
                args.effect_resolved,
                "--layer",
                args.layer_resolved,
                "--preview-report",
                preview_report_path,
                "--strict",
                "--markdown",
            ]
            if args.baseline:
                regression.extend(["--baseline", str(baseline)])
    return {
        "before_audit": before_audit,
        "before_domain_audit": before_domain,
        "after_audit": after_audit,
        "after_domain_audit": after_domain,
        "preview": preview,
        "regression": regression,
    }


def evaluate_gate(report: dict[str, Any]) -> dict[str, Any]:
    validation = report.get("validation") or {}
    before = validation.get("before_audit", {}).get("summary") or {}
    after = validation.get("after_audit", {}).get("summary") or {}
    domain = validation.get("after_domain_audit", {}).get("summary") or {}
    preview = validation.get("preview", {}).get("summary") or {}
    regression = validation.get("regression", {}).get("summary") or {}
    ue = report.get("ue_apply") or {}
    operations = ue.get("operations") or []
    skipped = [item for item in operations if item.get("skipped")]
    failed = [item for item in operations if not item.get("success") and not item.get("skipped")]
    regression_status = "not_run"
    if validation.get("regression", {}).get("skipped"):
        regression_status = "skipped"
    elif validation.get("regression"):
        regression_status = "passed" if regression.get("passed") is True else "failed"
    return {
        "candidate_created": bool(ue.get("candidate_ref")),
        "backup_created": bool(ue.get("backup_ref")),
        "operation_failures": len(failed),
        "operation_skipped": len(skipped),
        "before_audit_available": bool(before.get("exists")),
        "after_audit_findings": after.get("analysis_findings"),
        "after_dead_nodes": after.get("dead_nodes"),
        "after_domain_errors": domain.get("errors"),
        "after_domain_warnings": domain.get("warnings"),
        "preview_shaded_ok": preview.get("shaded_ok"),
        "preview_contract_findings": preview.get("contract_findings"),
        "regression_status": regression_status,
        "candidate_validated_without_regression": bool(
            ue.get("candidate_ref")
            and not failed
            and (after.get("analysis_findings") in (0, None))
            and (domain.get("errors") in (0, None))
            and (domain.get("warnings") in (0, None))
            and preview.get("shaded_ok") is not False
            and (preview.get("contract_findings") in (0, None))
            and regression_status in {"skipped", "not_run"}
        ),
        "ready_for_acceptance": bool(
            ue.get("candidate_ref")
            and not failed
            and (after.get("analysis_findings") in (0, None))
            and (domain.get("errors") in (0, None))
            and (domain.get("warnings") in (0, None))
            and preview.get("shaded_ok") is not False
            and (preview.get("contract_findings") in (0, None))
            and regression_status == "passed"
        ),
    }


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    resolved = resolve_inputs(args)
    args.effect_resolved = str(resolved["effect"])
    args.layer_resolved = str(resolved["layer"])
    payload = build_apply_payload(resolved)
    effect = str(resolved["effect"])
    layer = str(resolved["layer"])
    label = str(resolved["label"])
    out = Path(args.out) if args.out else default_report_path(
        ctx,
        "graph-refactor-apply",
        slugify(f"{effect}-{layer}"),
        f"{label}-graph-refactor-apply",
        ".json",
    )

    report: dict[str, Any] = {
        "tool": "graph_refactor_apply",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "label": label,
        "execute": False,  # Plan only: the UnrealBridge graph-surgery executor was retired.
        "inputs": resolved["source_paths"],
        "target_material": resolved["target_material"],
        "candidate_path": resolved["candidate_path"],
        "backup_path": resolved["backup_path"],
        "apply_payload": payload,
        "review": {
            "mutates_original": False,
            "review_required": True,
            "default_safe_action": "inspect candidate, compare evidence, then manually promote or discard",
        },
        "validation": {},
        "rollback": {
            "original_material_untouched": True,
            "backup_path": resolved["backup_path"],
            "candidate_reject_action": "Delete or ignore the candidate material if validation fails.",
            "manual_restore_action": "If a future commit-to-source flow is used, restore from backup before retrying.",
        },
        "gate": {},
    }

    report["validation_plan"] = validation_commands(args, ctx, resolved["target_material"], object_ref(resolved["candidate_path"]))
    report["mcp_route"] = [
        f"AssetTools.duplicate {resolved['target_material']} -> {resolved['backup_path']} (backup) and -> {resolved['candidate_path']}",
        "Apply each feasible operation to the candidate with MaterialTools.add_expression / connect_expressions / "
        "connect_to_output (builtin_mcp.py batch with get_expression_inputs / get_property_input readbacks), then recompile",
        "Run validation_plan: audits before/after, a capture of the candidate, and regression against the baseline",
    ]
    report["gate"] = {"ready_for_acceptance": False, "reason": "plan_only"}
    return report, out


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    lines = [
        f"# Graph Refactor Apply: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Execute: `{report.get('execute')}`",
        f"- Target: `{report.get('target_material')}`",
        f"- Candidate: `{report.get('candidate_path')}`",
        f"- Backup: `{report.get('backup_path')}`",
        f"- Mutates original: `{(report.get('review') or {}).get('mutates_original')}`",
        f"- Ready for acceptance: `{gate.get('ready_for_acceptance')}`",
        "",
        "## Operations",
        "",
    ]
    payload = report.get("apply_payload") or {}
    for item in payload.get("operations") or []:
        lines.append(
            f"- `{item.get('operation')}` executable=`{item.get('executable')}` "
            f"risk=`{item.get('risk')}` reason=`{item.get('blocked_reason') or ''}`"
        )
    if report.get("ue_apply"):
        lines.extend(["", "## UE Apply", ""])
        for item in (report["ue_apply"].get("operations") or []):
            lines.append(
                f"- `{item.get('operation')}` success=`{item.get('success')}` "
                f"skipped=`{item.get('skipped', False)}` error=`{item.get('error') or item.get('reason') or ''}`"
            )
    if report.get("validation_plan") and not report.get("validation"):
        lines.extend(["", "## Validation Plan", ""])
        for key, command in (report.get("validation_plan") or {}).items():
            if command:
                lines.append(f"- `{key}`: `{' '.join(command)}`")
            else:
                lines.append(f"- `{key}`: `not available`")
    lines.extend(["", "## Validation", ""])
    for key, item in (report.get("validation") or {}).items():
        if item.get("skipped"):
            lines.append(f"- `{key}` skipped: {item.get('reason')}")
            continue
        lines.append(
            f"- `{key}` rc=`{item.get('returncode')}` report=`{item.get('report_path') or ''}` "
            f"summary=`{json.dumps(item.get('summary') or {}, ensure_ascii=False)}`"
        )
    lines.extend(
        [
            "",
            "## Rollback",
            "",
            f"- Original untouched: `{(report.get('rollback') or {}).get('original_material_untouched')}`",
            f"- Backup path: `{(report.get('rollback') or {}).get('backup_path')}`",
            f"- Reject action: {(report.get('rollback') or {}).get('candidate_reject_action')}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 1 if args.strict and not (report.get("gate") or {}).get("ready_for_acceptance") else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply a reviewed graph refactor plan to a duplicated candidate material with audit/preview/regression evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--refactor-plan", help="material_toolset_builder.py refactor-plan JSON report.")
    parser.add_argument("--patch-spec", help="material-refactor-patch-spec.json.")
    parser.add_argument("--graph-diff-report", help="graph_diff_refactor.py report; used for route/output evidence.")
    parser.add_argument("--material-path", help="Override target material path.")
    parser.add_argument("--candidate-path", help="Package path for the patched candidate material.")
    parser.add_argument("--backup-path", help="Package path for the backup duplicate.")
    parser.add_argument("--effect")
    parser.add_argument("--layer")
    parser.add_argument("--label")
    parser.add_argument("--carrier", default="mesh")
    parser.add_argument("--baseline", help="Optional material_regression baseline path.")
    parser.add_argument("--project")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.refactor_plan or args.patch_spec or args.graph_diff_report or args.material_path):
        parser.error("Provide --refactor-plan, --patch-spec, --graph-diff-report, or --material-path.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
