from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .core import default_report_path, ensure_dir, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import resolve_path
from .material_regression import default_baseline_path
from .regression_baseline_set import baseline_set_path, load_index as load_baseline_set_index, resolve_entry as resolve_baseline_entry
from .smoke_resume_cache import cache_lookup, cache_store


DEFAULT_SMOKE_TIERS = ("default", "gameplay-safe")


def load_json_if_exists(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not str(path):
        return None, "missing_path"
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive path
        return None, f"invalid_json: {exc}"
    if not isinstance(payload, dict):
        return None, "json_root_not_object"
    return payload, ""


def split_repeatable_csv(values: list[str] | None, default: tuple[str, ...] | list[str] | None = None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        result.extend(item.strip() for item in str(value).split(",") if item.strip())
    if result:
        return unique_strings(result)
    return list(default or [])


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = str(value).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def tool_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "tools" / f"{name}.py"


def command_display(command: list[str]) -> str:
    return " ".join(json.dumps(part) if (" " in part or "\t" in part) else part for part in command)


def stdout_report_path(stdout_text: str) -> str:
    lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def smoke_label(args: argparse.Namespace) -> str:
    return slugify(args.label or "smoke")


def material_identity(package: dict[str, Any] | None, schema: dict[str, Any] | None) -> tuple[str, str, str]:
    effect = str((package or {}).get("effect") or (schema or {}).get("effect") or "Material")
    layer = str((package or {}).get("layer") or "Delivery")
    material_path = str((package or {}).get("material_path") or (schema or {}).get("material_path") or "")
    return effect, layer, material_path


def markdown_flag(args: argparse.Namespace) -> list[str]:
    return ["--markdown"] if args.markdown else []


def preview_matrix_axis_args(args: argparse.Namespace) -> list[str]:
    command: list[str] = []
    if args.matrix_spec:
        command.extend(["--matrix-spec", args.matrix_spec])
    for value in args.background:
        command.extend(["--background", value])
    for value in args.exposure:
        command.extend(["--exposure", value])
    for value in args.distance:
        command.extend(["--distance", value])
    for value in args.angle:
        command.extend(["--angle", value])
    for value in args.time:
        command.extend(["--time", value])
    for value in args.quality:
        command.extend(["--quality", value])
    if not args.quality and args.preview_quality:
        command.extend(["--quality", str(args.preview_quality)])
    for value in args.lighting:
        command.extend(["--lighting", value])
    for value in args.carrier:
        command.extend(["--carrier", value])
    if args.resolution:
        command.extend(["--resolution", str(args.resolution)])
    if args.max_cells is not None:
        command.extend(["--max-cells", str(args.max_cells)])
    if args.allow_large_matrix:
        command.append("--allow-large-matrix")
    if args.with_complexity:
        command.append("--with-complexity")
    if args.markdown_previews:
        command.append("--markdown-previews")
    return command


def build_variant_runner_command(
    args: argparse.Namespace,
    schema_path: Path,
    effect: str,
    run_dir: Path,
) -> tuple[list[str], Path, Path]:
    report_path = run_dir / "material-variant-runner.json"
    spec_path = run_dir / "material-instance-smoke-spec.json"
    command = [
        sys.executable,
        str(tool_path("material_variant_runner")),
        "--root",
        str(args.root),
        "--parameter-schema",
        str(schema_path),
        "--effect",
        effect,
        "--tiers",
        ",".join(split_repeatable_csv(args.smoke_tier, DEFAULT_SMOKE_TIERS)),
        "--preview-quality",
        args.preview_quality,
        "--spec-out",
        str(spec_path),
        "--out",
        str(report_path),
        "--strict",
    ]
    if args.parent_path:
        command.extend(["--parent-path", args.parent_path])
    if args.output_folder:
        command.extend(["--output-folder", args.output_folder])
    if args.include_non_regression:
        command.append("--include-non-regression")
    if args.reuse_existing:
        command.append("--reuse-existing")
    command.extend(markdown_flag(args))
    return command, report_path, spec_path


def build_static_switch_expander_command(
    args: argparse.Namespace,
    schema_path: Path,
    effect: str,
    run_dir: Path,
) -> tuple[list[str], Path, Path]:
    report_path = run_dir / "static-switch-variant-expander.json"
    spec_path = run_dir / "material-instance-static-switch-spec.json"
    command = [
        sys.executable,
        str(tool_path("static_switch_variant_expander")),
        "--root",
        str(args.root),
        "--parameter-schema",
        str(schema_path),
        "--effect",
        effect,
        "--tiers",
        ",".join(split_repeatable_csv(args.smoke_tier, DEFAULT_SMOKE_TIERS)),
        "--preview-quality",
        args.preview_quality,
        "--max-permutations",
        str(args.max_static_permutations),
        "--spec-out",
        str(spec_path),
        "--out",
        str(report_path),
        "--strict",
    ]
    if args.parent_path:
        command.extend(["--parent-path", args.parent_path])
    if args.output_folder:
        command.extend(["--output-folder", args.output_folder])
    if args.include_non_regression:
        command.append("--include-non-regression")
    if args.reuse_existing:
        command.append("--reuse-existing")
    command.extend(markdown_flag(args))
    return command, report_path, spec_path


def build_permutation_guard_command(
    args: argparse.Namespace,
    schema_path: Path,
    effect: str,
    run_dir: Path,
    expander_report_path: Path | None,
) -> tuple[list[str], Path]:
    report_path = run_dir / "permutation-budget-guard.json"
    command = [
        sys.executable,
        str(tool_path("permutation_budget_guard")),
        "--root",
        str(args.root),
        "--effect",
        effect,
        "--out",
        str(report_path),
    ]
    if expander_report_path:
        command.extend(["--switch-expander-report", str(expander_report_path)])
    else:
        command.extend(["--parameter-schema", str(schema_path)])
    for platform in args.permutation_platform:
        command.extend(["--platform", platform])
    if args.shader_permutation_report:
        command.extend(["--shader-permutation-report", args.shader_permutation_report])
    command.extend(markdown_flag(args))
    return command, report_path


def build_instance_batch_command(args: argparse.Namespace, spec_path: Path, effect: str, run_dir: Path) -> tuple[list[str], Path]:
    report_path = run_dir / "material-instance-batch.json"
    command = [
        sys.executable,
        str(tool_path("material_instance_batch")),
        str(spec_path),
        "--root",
        str(args.root),
        "--effect",
        effect,
        "--out",
        str(report_path),
    ]
    if args.project:
        command.extend(["--project", args.project])
    if args.endpoint:
        command.extend(["--endpoint", args.endpoint])
    if args.timeout:
        command.extend(["--timeout", str(args.timeout)])
    if args.reuse_existing:
        command.append("--reuse-existing")
    command.extend(markdown_flag(args))
    return command, report_path


def build_preview_matrix_command(
    args: argparse.Namespace,
    package_path: Path,
    effect: str,
    tier: str,
    layer_label: str,
    material_instance_path: str,
    run_dir: Path,
) -> tuple[list[str], Path]:
    report_path = run_dir / f"preview-matrix-{slugify(layer_label)}.json"
    command = [
        sys.executable,
        str(tool_path("preview_matrix")),
        "--root",
        str(args.root),
        "--package",
        str(package_path),
        "--material-path",
        material_instance_path,
        "--effect",
        effect,
        "--layer",
        layer_label,
        "--parameter-tier",
        tier,
        "--out",
        str(report_path),
        "--strict",
    ]
    command.extend(preview_matrix_axis_args(args))
    if args.execute:
        command.append("--execute")
    if args.project:
        command.extend(["--project", args.project])
    if args.endpoint:
        command.extend(["--endpoint", args.endpoint])
    if args.timeout:
        command.extend(["--timeout", str(args.timeout)])
    command.extend(markdown_flag(args))
    return command, report_path


def build_readability_command(
    args: argparse.Namespace,
    effect: str,
    material_path: str,
    matrix_reports: list[Path],
    run_dir: Path,
) -> tuple[list[str], Path]:
    report_path = run_dir / "preview-readability-score.json"
    command = [
        sys.executable,
        str(tool_path("preview_readability_score")),
        "--root",
        str(args.root),
        "--effect",
        effect,
        "--material-path",
        material_path,
        "--out",
        str(report_path),
        "--require-readable",
    ]
    for path in matrix_reports:
        command.extend(["--preview-matrix-report", str(path)])
    if args.allow_warnings:
        command.append("--allow-warnings")
    command.extend(markdown_flag(args))
    return command, report_path


def build_regression_command(
    args: argparse.Namespace,
    effect: str,
    layer: str,
    baseline_path: Path,
    preview_report_path: Path,
    run_dir: Path,
) -> tuple[list[str], Path]:
    report_path = run_dir / "material-regression-compare.json"
    command = [
        sys.executable,
        str(tool_path("material_regression")),
        "compare",
        "--root",
        str(args.root),
        "--effect",
        effect,
        "--layer",
        layer,
        "--baseline",
        str(baseline_path),
        "--preview-report",
        str(preview_report_path),
        "--label",
        smoke_label(args),
        "--out",
        str(report_path),
        "--strict",
    ]
    command.extend(markdown_flag(args))
    return command, report_path


def build_acceptance_command(
    args: argparse.Namespace,
    package_path: Path,
    material_path: str,
    schema_path: Path,
    source_reports: list[Path],
    sorting_reports: list[Path],
    matrix_reports: list[Path],
    readability_report: Path | None,
    regression_report: Path | None,
    run_dir: Path,
) -> tuple[list[str], Path]:
    report_path = run_dir / "material-acceptance-gate-v2.json"
    command = [
        sys.executable,
        str(tool_path("material_acceptance_gate_v2")),
        "--root",
        str(args.root),
        "--package",
        str(package_path),
        "--material-path",
        material_path,
        "--parameter-schema-report",
        str(schema_path),
        "--out",
        str(report_path),
        "--require-ready",
    ]
    for path in source_reports:
        command.extend(["--source-provenance-report", str(path)])
    for path in sorting_reports:
        command.extend(["--translucency-sorting-report", str(path)])
    for path in matrix_reports:
        command.extend(["--preview-matrix-report", str(path)])
    if readability_report:
        command.extend(["--preview-readability-report", str(readability_report)])
    if regression_report:
        command.extend(["--regression-report", str(regression_report)])
    for path in args.shader_cost_report:
        command.extend(["--shader-cost-report", str(resolve_path(path, base=Path.cwd()))])
    for path in args.platform_scalability_report:
        command.extend(["--platform-scalability-report", str(resolve_path(path, base=Path.cwd()))])
    if args.no_require_domain_audit:
        command.append("--no-require-domain-audit")
    if args.no_require_textures:
        command.append("--no-require-texture-set")
    if args.texture_set_waiver:
        command.extend(["--texture-set-waiver", args.texture_set_waiver])
    if args.no_require_regression:
        command.append("--no-require-regression")
    if args.no_require_parameters:
        command.append("--no-require-parameters")
    if args.parameter_table_waiver:
        command.extend(["--parameter-table-waiver", args.parameter_table_waiver])
    if args.no_require_readability:
        command.append("--no-require-readability")
    if args.require_shader_cost:
        command.append("--require-shader-cost")
    if args.require_platform_scalability:
        command.append("--require-platform-scalability")
    if args.allow_warnings:
        command.append("--allow-warnings")
    command.extend(markdown_flag(args))
    return command, report_path


def build_library_command(
    args: argparse.Namespace,
    asset_id: str,
    acceptance_report: Path,
    schema_path: Path,
    source_reports: list[Path],
    matrix_reports: list[Path],
    readability_report: Path | None,
    run_dir: Path,
) -> tuple[list[str], Path]:
    report_path = run_dir / "library-promotion-gate.json"
    command = [
        sys.executable,
        str(tool_path("library_promotion_gate")),
        "--root",
        str(args.root),
        "--out",
        str(report_path),
        "--require-ready",
        "--report-path",
        str(acceptance_report),
        "--report-path",
        str(schema_path),
    ]
    if asset_id:
        command.extend(["--asset-id", asset_id])
    for path in source_reports:
        command.extend(["--report-path", str(path)])
    for path in matrix_reports:
        command.extend(["--report-path", str(path)])
    if readability_report:
        command.extend(["--report-path", str(readability_report)])
    for path in args.shader_cost_report:
        command.extend(["--report-path", str(resolve_path(path, base=Path.cwd()))])
    for path in args.platform_scalability_report:
        command.extend(["--report-path", str(resolve_path(path, base=Path.cwd()))])
    if args.require_shader_cost:
        command.append("--require-shader-cost")
    if args.require_platform_scalability:
        command.append("--require-platform-scalability")
    if args.allow_warnings:
        command.append("--allow-warnings")
    if args.apply_library_promotion and asset_id:
        command.extend(["--apply", "--link-report", str(acceptance_report)])
    command.extend(markdown_flag(args))
    return command, report_path


def base_step(
    *,
    name: str,
    command: list[str] | None,
    planned_report_path: str = "",
    executed: bool = False,
    cached: bool = False,
    status: str = "planned",
    detail: str = "",
    report_path: str = "",
    exit_code: int | None = None,
    payload: dict[str, Any] | None = None,
    prerequisites: list[str] | None = None,
    stdout: str = "",
    stderr: str = "",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "executed": executed,
        "cached": cached,
        "status": status,
        "detail": detail,
        "exit_code": exit_code,
        "command": command or [],
        "command_text": command_display(command or []) if command else "",
        "planned_report_path": planned_report_path,
        "report_path": report_path,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "tool": (payload or {}).get("tool", ""),
        "prerequisites": prerequisites or [],
        "data": data or {},
    }


Evaluator = Callable[[int, dict[str, Any] | None, str], tuple[str, str, dict[str, Any]]]


def execute_step(
    ctx,
    *,
    effect: str,
    name: str,
    command: list[str],
    planned_report_path: Path,
    evaluator: Evaluator,
    input_paths: list[Path] | None = None,
    use_cache: bool = False,
) -> dict[str, Any]:
    cache_entry = None
    if use_cache:
        cache_entry, _cache_index = cache_lookup(ctx, effect, name, command, input_paths or [])
    if cache_entry:
        actual_path = Path(str(cache_entry.get("report_path") or planned_report_path))
        payload, load_error = load_json_if_exists(actual_path)
        returncode = int(cache_entry.get("exit_code", 0) or 0)
        status, detail, data = evaluator(returncode, payload, load_error)
        return base_step(
            name=name,
            command=command,
            planned_report_path=str(planned_report_path),
            executed=True,
            cached=True,
            status=status,
            detail=f"Reused cached result. {detail}".strip(),
            report_path=str(actual_path),
            exit_code=returncode,
            payload=payload,
            data=data,
        )
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except Exception as exc:  # pragma: no cover - defensive path
        return base_step(
            name=name,
            command=command,
            planned_report_path=str(planned_report_path),
            executed=True,
            status="blocked",
            detail=f"Subprocess failed to start: {exc}",
            report_path=str(planned_report_path),
            exit_code=2,
        )
    report_text = stdout_report_path(completed.stdout)
    actual_path = Path(report_text) if report_text else planned_report_path
    payload, load_error = load_json_if_exists(actual_path)
    status, detail, data = evaluator(completed.returncode, payload, load_error)
    step = base_step(
        name=name,
        command=command,
        planned_report_path=str(planned_report_path),
        executed=True,
        status=status,
        detail=detail,
        report_path=str(actual_path),
        exit_code=completed.returncode,
        payload=payload,
        stdout=completed.stdout,
        stderr=completed.stderr,
        data=data,
    )
    if use_cache:
        cache_store(ctx, effect=effect, name=name, command=command, input_paths=input_paths or [], step=step)
    return step


def evaluate_variant_runner(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    summary = dict((payload or {}).get("summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    variants = list((payload or {}).get("variants") or [])
    if returncode != 0:
        return "risk", f"variant runner exited {returncode}.", {"summary": summary, "gate": gate}
    if load_error:
        return "risk", f"variant runner report unavailable: {load_error}.", {"summary": summary, "gate": gate}
    if gate.get("variants_generated") is not True:
        return "risk", "Variant runner did not generate any smoke tiers.", {"summary": summary, "gate": gate}
    return "pass", f"Generated {len(variants)} smoke variant(s).", {"summary": summary, "gate": gate}


def evaluate_static_switch_expander(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    summary = dict((payload or {}).get("summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    if returncode != 0:
        return "risk", f"static_switch_variant_expander exited {returncode}.", {"summary": summary, "gate": gate}
    if load_error:
        return "risk", f"static_switch_variant_expander report unavailable: {load_error}.", {"summary": summary, "gate": gate}
    switch_count = int(summary.get("switch_parameter_count", 0) or 0)
    variant_count = int(summary.get("variant_count", 0) or 0)
    detail = f"switches={switch_count} variants={variant_count} requested_permutations={summary.get('requested_permutation_count', 0)}."
    return "pass", detail, {"summary": summary, "gate": gate}


def evaluate_permutation_guard(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    summary = dict((payload or {}).get("summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    if returncode != 0:
        return "risk", f"permutation_budget_guard exited {returncode}.", {"summary": summary, "gate": gate}
    if load_error:
        return "risk", f"permutation_budget_guard report unavailable: {load_error}.", {"summary": summary, "gate": gate}
    status = "pass" if gate.get("passed") is True else "risk"
    detail = f"requested_permutations={summary.get('requested_permutation_count', 0)} warnings={summary.get('warnings', 0)} errors={summary.get('errors', 0)}."
    return status, detail, {"summary": summary, "gate": gate}


def evaluate_instance_batch(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    rows = list((payload or {}).get("instances") or [])
    if returncode != 0:
        return "risk", f"material_instance_batch exited {returncode}.", {"instance_count": len(rows)}
    if load_error:
        return "risk", f"material_instance_batch report unavailable: {load_error}.", {"instance_count": len(rows)}
    failed = 0
    created = 0
    for row in rows:
        create = row.get("create") if isinstance(row.get("create"), dict) else {}
        set_params = row.get("set_params") if isinstance(row.get("set_params"), dict) else {}
        if create.get("success"):
            created += 1
        else:
            failed += 1
        if set_params and set_params.get("success") is False:
            failed += 1
    status = "pass" if failed == 0 else "risk"
    return status, f"Created {created}/{len(rows)} MI smoke variant(s); failures={failed}.", {"instance_count": len(rows), "failures": failed}


def evaluate_preview_matrix(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    summary = dict((payload or {}).get("summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    if returncode != 0:
        return "risk", f"preview_matrix exited {returncode}.", {"summary": summary, "gate": gate}
    if load_error:
        return "risk", f"preview_matrix report unavailable: {load_error}.", {"summary": summary, "gate": gate}
    passed = gate.get("ready_for_regression_coverage") is True
    status = "pass" if passed else "risk"
    detail = (
        f"Executed {summary.get('executed_cells', 0)}/{summary.get('planned_cells', 0)} preview cells; "
        f"failed={summary.get('failed_cells', 0)}."
    )
    return status, detail, {"summary": summary, "gate": gate}


def evaluate_readability(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    summary = dict((payload or {}).get("summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    if returncode != 0:
        return "risk", f"preview_readability_score exited {returncode}.", {"summary": summary, "gate": gate}
    if load_error:
        return "risk", f"preview_readability_score report unavailable: {load_error}.", {"summary": summary, "gate": gate}
    status = "pass" if gate.get("readable") is True else "risk"
    detail = f"Images={summary.get('image_count', 0)} errors={summary.get('errors', 0)} warnings={summary.get('warnings', 0)}."
    return status, detail, {"summary": summary, "gate": gate}


def evaluate_regression(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    gate = dict((payload or {}).get("gate") or {})
    comparisons = list((payload or {}).get("comparisons") or [])
    if returncode != 0:
        return "risk", f"material_regression compare exited {returncode}.", {"gate": gate, "comparison_count": len(comparisons)}
    if load_error:
        return "risk", f"material_regression report unavailable: {load_error}.", {"gate": gate, "comparison_count": len(comparisons)}
    status = "pass" if gate.get("passed") is True else "risk"
    detail = f"comparisons={len(comparisons)} errors={gate.get('errors', 0)} warnings={gate.get('warnings', 0)}."
    return status, detail, {"gate": gate, "comparison_count": len(comparisons)}


def evaluate_acceptance(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    delivery = dict((payload or {}).get("delivery_summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    if returncode != 0:
        return "risk", f"material_acceptance_gate_v2 exited {returncode}.", {"delivery_summary": delivery, "gate": gate}
    if load_error:
        return "risk", f"material_acceptance_gate_v2 report unavailable: {load_error}.", {"delivery_summary": delivery, "gate": gate}
    status = "pass" if delivery.get("approved_for_reuse") is True else "risk"
    detail = f"approved_for_reuse={delivery.get('approved_for_reuse')} errors={delivery.get('errors', 0)} warnings={delivery.get('warnings', 0)}."
    return status, detail, {"delivery_summary": delivery, "gate": gate}


def evaluate_library(returncode: int, payload: dict[str, Any] | None, load_error: str) -> tuple[str, str, dict[str, Any]]:
    delivery = dict((payload or {}).get("delivery_summary") or {})
    gate = dict((payload or {}).get("gate") or {})
    if returncode != 0:
        return "risk", f"library_promotion_gate exited {returncode}.", {"delivery_summary": delivery, "gate": gate}
    if load_error:
        return "risk", f"library_promotion_gate report unavailable: {load_error}.", {"delivery_summary": delivery, "gate": gate}
    status = "pass" if delivery.get("approved_for_library") is True else "risk"
    detail = f"approved_for_library={delivery.get('approved_for_library')} errors={delivery.get('errors', 0)} warnings={delivery.get('warnings', 0)}."
    return status, detail, {"delivery_summary": delivery, "gate": gate}


def planned_step(name: str, command: list[str], planned_report_path: Path, detail: str) -> dict[str, Any]:
    return base_step(name=name, command=command, planned_report_path=str(planned_report_path), status="planned", detail=detail)


def blocked_step(name: str, command: list[str] | None, planned_report_path: Path, detail: str, prerequisites: list[str]) -> dict[str, Any]:
    return base_step(
        name=name,
        command=command,
        planned_report_path=str(planned_report_path),
        status="blocked",
        detail=detail,
        prerequisites=prerequisites,
    )


def advisory_step(name: str, command: list[str] | None, planned_report_path: Path, detail: str) -> dict[str, Any]:
    return base_step(name=name, command=command, planned_report_path=str(planned_report_path), status="advisory", detail=detail)


def normalize_selection_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        numeric = float(text)
    except (TypeError, ValueError):
        return text.lower()
    if numeric.is_integer():
        return str(int(numeric))
    return format(numeric, "g")


def baseline_preview_selection_hints(baseline_path: Path | None) -> dict[str, str]:
    if baseline_path is None or not baseline_path.exists():
        return {}
    payload, error = load_json_if_exists(baseline_path)
    if error or not payload:
        return {}
    preview = payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
    options = preview.get("options") if isinstance(preview.get("options"), dict) else {}
    hints: dict[str, str] = {}
    carrier = normalize_selection_value(options.get("carrier"))
    if carrier:
        hints["carrier"] = carrier
    lighting = normalize_selection_value(options.get("lighting"))
    if lighting:
        hints["lighting"] = lighting
    background = normalize_selection_value(options.get("background_preset"))
    if background:
        hints["background"] = background
    elif preview:
        hints["background"] = "neutral"
    exposure_bias = options.get("exposure_bias")
    if exposure_bias not in (None, ""):
        hints["exposure"] = normalize_selection_value(exposure_bias)
    elif preview:
        hints["exposure"] = "0"
    return hints


def matrix_preview_candidates(matrix_report_paths: list[Path]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path in matrix_report_paths:
        payload, error = load_json_if_exists(path)
        if error or not payload:
            continue
        tiers = [str(item) for item in ((payload.get("axes") or {}).get("parameter_tiers") or []) if str(item)]
        default_tier = tiers[0] if tiers else str(payload.get("layer") or "")
        axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else {}
        default_carrier = str(((axes.get("carriers") or [""]) or [""])[0] or "")
        default_quality = str(((axes.get("quality_profiles") or [""]) or [""])[0] or "")
        default_lighting = str(((axes.get("lighting") or [""]) or [""])[0] or "")
        cells = [cell for cell in (payload.get("cells") or []) if isinstance(cell, dict)]
        if cells:
            for cell in cells:
                execution = cell.get("execution") if isinstance(cell.get("execution"), dict) else {}
                if execution and str(execution.get("status") or "") not in {"", "pass"}:
                    continue
                tool_name = str(execution.get("tool") or "")
                preview_report_path = str(execution.get("preview_report_path") or "")
                if tool_name == "preview_environment_executor":
                    report_path = preview_report_path
                else:
                    report_path = preview_report_path or execution.get("report_path")
                if not report_path:
                    continue
                candidates.append(
                    {
                        "matrix_report_path": str(path),
                        "matrix_layer": str(payload.get("layer") or ""),
                        "preview_report_path": str(report_path),
                        "cell_id": str(cell.get("id") or ""),
                        "generated_utc": str(payload.get("generated_utc") or ""),
                        "context": {
                            "parameter_tier": str(cell.get("parameter_tier") or default_tier or ""),
                            "carrier": str(cell.get("carrier") or default_carrier or ""),
                            "background": str(cell.get("background") or ""),
                            "exposure": str(cell.get("exposure") or ""),
                            "lighting": str(cell.get("lighting") or default_lighting or ""),
                            "quality_profile": str(cell.get("quality_profile") or default_quality or ""),
                            "environment_id": str(cell.get("preview_effect") or cell.get("id") or ""),
                        },
                    }
                )
            continue
        previews = [str(item) for item in (((payload.get("evidence") or {}).get("preview_reports")) or []) if item]
        for index, report_path in enumerate(previews, start=1):
            candidates.append(
                {
                    "matrix_report_path": str(path),
                    "matrix_layer": str(payload.get("layer") or ""),
                    "preview_report_path": str(report_path),
                    "cell_id": f"preview-{index:03d}",
                    "generated_utc": str(payload.get("generated_utc") or ""),
                    "context": {
                        "parameter_tier": default_tier,
                        "carrier": default_carrier,
                        "background": "",
                        "exposure": "",
                        "lighting": default_lighting,
                        "quality_profile": default_quality,
                        "environment_id": "",
                    },
                }
            )
    return candidates


def score_preview_candidate(candidate: dict[str, Any], requested_context: dict[str, str], hint_context: dict[str, str]) -> dict[str, Any]:
    context = candidate.get("context") if isinstance(candidate.get("context"), dict) else {}
    score = 0
    matches: list[str] = []
    mismatches: list[str] = []
    hint_matches: list[str] = []
    for field, requested_value in requested_context.items():
        requested = normalize_selection_value(requested_value)
        if not requested:
            continue
        actual = normalize_selection_value(context.get(field))
        if actual == requested:
            score += 3
            matches.append(field)
        else:
            score -= 4
            mismatches.append(field)
    for field, hint_value in hint_context.items():
        if normalize_selection_value(requested_context.get(field, "")):
            continue
        hint = normalize_selection_value(hint_value)
        if not hint:
            continue
        actual = normalize_selection_value(context.get(field))
        if actual == hint:
            score += 2
            hint_matches.append(field)
        elif field == "background" and hint == "neutral" and actual in {"gray", "grey"}:
            score += 1
            hint_matches.append(field)
    return {
        **candidate,
        "score": score,
        "matches": matches,
        "mismatches": mismatches,
        "hint_matches": hint_matches,
    }


def preview_candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, str, str, str]:
    return (
        int(candidate.get("score", 0) or 0),
        len(candidate.get("matches") or []),
        len(candidate.get("hint_matches") or []),
        str(candidate.get("generated_utc") or ""),
        str(candidate.get("matrix_report_path") or ""),
        str(candidate.get("preview_report_path") or ""),
    )


def regression_preview_path(
    args: argparse.Namespace,
    matrix_report_paths: list[Path],
    *,
    baseline_path: Path | None = None,
    baseline_resolution: dict[str, Any] | None = None,
) -> tuple[Path | None, str, dict[str, Any]]:
    candidates = matrix_preview_candidates(matrix_report_paths)
    target_tier = args.regression_tier
    if not candidates:
        return None, "No executed preview_matrix report exposed preview reports for regression.", {}
    by_tier: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        tier = str(((candidate.get("context") or {}).get("parameter_tier")) or "")
        if tier:
            by_tier.setdefault(tier, []).append(candidate)
    tier_candidates = by_tier.get(target_tier, [])
    if not tier_candidates:
        available = ", ".join(sorted(by_tier))
        return None, f"Regression tier `{target_tier}` was not captured. Available tiers: {available or 'none'}.", {}
    selected_context = (
        ((baseline_resolution or {}).get("selected") or {}).get("context")
        if isinstance((baseline_resolution or {}).get("selected"), dict)
        else {}
    )
    requested_context = {
        field: str((selected_context or {}).get(field, "") or "")
        for field in baseline_set_context(args)
    }
    if not any(normalize_selection_value(value) for value in requested_context.values()):
        requested_context = baseline_set_context(args)
    hint_context = baseline_preview_selection_hints(baseline_path)
    scored = [score_preview_candidate(candidate, requested_context, hint_context) for candidate in tier_candidates]
    scored.sort(key=preview_candidate_sort_key, reverse=True)
    selected = scored[0]
    context = selected.get("context") if isinstance(selected.get("context"), dict) else {}
    detail = (
        f"Selected regression preview cell `{selected.get('cell_id') or 'unknown'}` from `{selected.get('matrix_layer') or 'preview_matrix'}` "
        f"using context score {selected.get('score', 0)}."
    )
    selection = {
        "requested_context": requested_context,
        "baseline_hints": hint_context,
        "selected": {
            "preview_report_path": selected.get("preview_report_path"),
            "matrix_report_path": selected.get("matrix_report_path"),
            "matrix_layer": selected.get("matrix_layer"),
            "cell_id": selected.get("cell_id"),
            "context": context,
            "score": selected.get("score", 0),
            "matches": selected.get("matches") or [],
            "mismatches": selected.get("mismatches") or [],
            "hint_matches": selected.get("hint_matches") or [],
        },
        "candidates": [
            {
                "preview_report_path": item.get("preview_report_path"),
                "matrix_report_path": item.get("matrix_report_path"),
                "matrix_layer": item.get("matrix_layer"),
                "cell_id": item.get("cell_id"),
                "context": item.get("context") or {},
                "score": item.get("score", 0),
                "matches": item.get("matches") or [],
                "mismatches": item.get("mismatches") or [],
                "hint_matches": item.get("hint_matches") or [],
            }
            for item in scored[:8]
        ],
    }
    return Path(str(selected.get("preview_report_path") or "")), detail, selection


def baseline_set_context(args: argparse.Namespace) -> dict[str, str]:
    first_value = lambda values: str(values[0]).strip() if values else ""
    return {
        "parameter_tier": str(args.regression_tier or ""),
        "carrier": first_value(args.carrier),
        "background": first_value(args.background),
        "exposure": first_value(args.exposure),
        "lighting": first_value(args.lighting),
        "quality_profile": first_value(args.quality),
        "environment_id": "",
    }


def resolve_baseline_from_set(ctx, effect: str, layer: str, args: argparse.Namespace) -> tuple[Path | None, str, dict[str, Any] | None]:
    index_path = Path(args.baseline_set) if args.baseline_set else baseline_set_path(ctx, effect, layer)
    if not index_path.exists():
        return None, "", None
    index = load_baseline_set_index(index_path)
    selected, candidates = resolve_baseline_entry(
        [item for item in index.get("entries") or [] if isinstance(item, dict)],
        baseline_set_context(args),
    )
    if not selected:
        return None, str(index_path), {"candidates": candidates[:8], "requested_context": baseline_set_context(args)}
    path = Path(str(selected.get("baseline_path") or ""))
    if not path.exists():
        return None, str(index_path), {"selected": selected, "missing_baseline_path": str(path)}
    return path, str(index_path), {"selected": selected, "candidates": candidates[:8], "requested_context": baseline_set_context(args)}


def summarize_variants(variant_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in (variant_payload or {}).get("variants") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "tier": item.get("tier"),
                "variant_id": item.get("variant_id"),
                "switch_permutation": item.get("switch_permutation"),
                "path": item.get("path"),
                "param_count": len(item.get("params") or []),
                "skipped_parameter_count": len(item.get("skipped_parameters") or []),
            }
        )
    return rows


def report_status(steps: list[dict[str, Any]], execute: bool) -> str:
    statuses = [str(step.get("status") or "") for step in steps]
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if any(status == "risk" for status in statuses):
        return "risk"
    if any(status == "planned" for status in statuses):
        return "planned"
    if any(status == "advisory" for status in statuses):
        return "pass_with_advisories" if execute else "planned"
    return "pass"


def next_actions(
    args: argparse.Namespace,
    status: str,
    ready_for_live_smoke: bool,
    blocked: list[str],
    advisory: list[str],
    risky: list[str],
    baseline_path: Path,
) -> list[str]:
    actions: list[str] = []
    if not ready_for_live_smoke:
        actions.append("Fix package or parameter-schema availability first so the smoke chain can plan real variants.")
    if not args.execute:
        actions.append("Rerun with --execute when live UnrealBridge/UE is available to create variants and capture preview evidence.")
    if "material_regression" in advisory and not args.no_require_regression:
        actions.append(f"Lock an accepted baseline with material_regression.py baseline so smoke can prove drift safety. Expected path: `{baseline_path}`.")
    if args.resume_cache:
        actions.append("Rerun with the same inputs to reuse smoke_resume_cache.py hits instead of recomputing unchanged steps.")
    if "material_acceptance_gate_v2" in risky:
        actions.append("Review the v2 acceptance report and fill whichever material-side evidence is still missing or failing.")
    if "library_promotion_gate" in risky:
        actions.append("Treat library promotion as advisory until acceptance, provenance, readability, and any optional platform/cost gates all pass.")
    if blocked and args.execute:
        actions.append("Resolve blocked live steps first; downstream gates are only as trustworthy as the preview evidence they receive.")
    if status == "pass":
        actions.append("Material delivery smoke passed end-to-end; this evidence bundle is ready for downstream reuse review.")
    return actions


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package_path = resolve_path(args.package, base=Path.cwd())
    schema_path = resolve_path(args.parameter_schema_report, base=Path.cwd())
    package_payload, package_error = load_json_if_exists(package_path)
    schema_payload, schema_error = load_json_if_exists(schema_path)
    effect, layer, material_path = material_identity(package_payload, schema_payload)
    out = Path(args.out) if args.out else default_report_path(
        ctx,
        "delivery-smoke",
        slugify(f"{effect}-{layer}-{smoke_label(args)}"),
        "material-delivery-smoke",
        ".json",
    )
    run_dir = ensure_dir(out.parent)
    source_reports = [resolve_path(item, base=Path.cwd()) for item in args.source_provenance_report]
    sorting_reports = [resolve_path(item, base=Path.cwd()) for item in args.translucency_sorting_report]
    selected_tiers = split_repeatable_csv(args.smoke_tier, DEFAULT_SMOKE_TIERS)
    variant_command, variant_report_path, variant_spec_path = build_variant_runner_command(args, schema_path, effect, run_dir)
    switch_command, switch_report_path, switch_spec_path = build_static_switch_expander_command(args, schema_path, effect, run_dir)
    steps: list[dict[str, Any]] = []

    prerequisites = []
    if schema_error:
        prerequisites.append(f"parameter schema `{schema_path}` is {schema_error}")
    if prerequisites:
        steps.append(blocked_step("material_variant_runner", variant_command, variant_report_path, "Variant generation could not start.", prerequisites))
        steps.append(blocked_step("static_switch_variant_expander", switch_command, switch_report_path, "Static-switch expansion could not start.", prerequisites))
        variant_payload = None
        switch_payload = None
    else:
        steps.append(
            execute_step(
                ctx,
                effect=effect,
                name="material_variant_runner",
                command=variant_command,
                planned_report_path=variant_report_path,
                evaluator=evaluate_variant_runner,
                input_paths=[schema_path],
                use_cache=args.resume_cache,
            )
        )
        variant_payload = load_json_if_exists(Path(steps[-1]["report_path"]))[0]
        steps.append(
            execute_step(
                ctx,
                effect=effect,
                name="static_switch_variant_expander",
                command=switch_command,
                planned_report_path=switch_report_path,
                evaluator=evaluate_static_switch_expander,
                input_paths=[schema_path],
                use_cache=args.resume_cache,
            )
        )
        switch_payload = load_json_if_exists(Path(steps[-1]["report_path"]))[0]

    permutation_command, permutation_report_path = build_permutation_guard_command(
        args,
        schema_path,
        effect,
        run_dir,
        switch_report_path if switch_payload else None,
    )
    if prerequisites:
        steps.append(blocked_step("permutation_budget_guard", permutation_command, permutation_report_path, "Permutation budget guard is blocked until parameter evidence exists.", prerequisites))
    else:
        steps.append(
            execute_step(
                ctx,
                effect=effect,
                name="permutation_budget_guard",
                command=permutation_command,
                planned_report_path=permutation_report_path,
                evaluator=evaluate_permutation_guard,
                input_paths=[schema_path, switch_report_path],
                use_cache=args.resume_cache,
            )
        )

    active_variant_payload = switch_payload if switch_payload and (switch_payload.get("summary") or {}).get("variant_count") else variant_payload
    active_spec_path = switch_spec_path if switch_payload and Path(switch_spec_path).exists() else variant_spec_path
    variant_rows = summarize_variants(active_variant_payload)
    selected_variant_rows = [item for item in variant_rows if str(item.get("tier")) in selected_tiers]

    batch_command, batch_report_path = build_instance_batch_command(args, active_spec_path, effect, run_dir)
    if not active_variant_payload or not selected_variant_rows:
        steps.append(
            blocked_step(
                "material_instance_batch",
                batch_command,
                batch_report_path,
                "Material-instance smoke batch is blocked until smoke variants exist.",
                ["variant generation must emit at least one smoke variant"],
            )
        )
    elif not args.execute:
        steps.append(planned_step("material_instance_batch", batch_command, batch_report_path, "Run with --execute to create the smoke MIs in live UE."))
    else:
        steps.append(
            execute_step(
                ctx,
                effect=effect,
                name="material_instance_batch",
                command=batch_command,
                planned_report_path=batch_report_path,
                evaluator=evaluate_instance_batch,
                input_paths=[active_spec_path],
                use_cache=args.resume_cache,
            )
        )

    matrix_report_paths: list[Path] = []
    if package_error:
        preview_prereq = [f"delivery package `{package_path}` is {package_error}"]
    else:
        preview_prereq = []

    for variant_row in selected_variant_rows:
        tier = str(variant_row.get("tier") or "")
        variant_label = str(variant_row.get("variant_id") or variant_row.get("switch_permutation") or tier or "variant")
        preview_name = f"preview_matrix:{variant_label}"
        preview_path = run_dir / f"preview-matrix-{slugify(variant_label)}.json"
        material_instance_path = str(variant_row.get("path") or "")
        if preview_prereq:
            steps.append(
                blocked_step(
                    preview_name,
                    None,
                    preview_path,
                    "Preview matrix is blocked until the delivery package is available.",
                    preview_prereq,
                )
            )
            continue
        if not material_instance_path:
            steps.append(
                blocked_step(
                    preview_name,
                    None,
                    preview_path,
                    "Preview matrix is blocked until the requested smoke tier exists.",
                    [f"tier `{tier}` / variant `{variant_label}` was not emitted by variant expansion"],
                )
            )
            continue
        command, preview_path = build_preview_matrix_command(args, package_path, effect, tier, variant_label, material_instance_path, run_dir)
        if not args.execute:
            steps.append(planned_step(preview_name, command, preview_path, "Run with --execute to capture live preview-matrix evidence for this tier."))
        else:
            step = execute_step(
                ctx,
                effect=effect,
                name=preview_name,
                command=command,
                planned_report_path=preview_path,
                evaluator=evaluate_preview_matrix,
                input_paths=[package_path, batch_report_path],
                use_cache=args.resume_cache,
            )
            steps.append(step)
            if step.get("report_path"):
                matrix_report_paths.append(Path(str(step["report_path"])))

    readability_command, readability_report_path = build_readability_command(args, effect, material_path, matrix_report_paths, run_dir)
    if not args.execute:
        steps.append(planned_step("preview_readability_score", readability_command, readability_report_path, "Will score the preview-matrix evidence after live capture."))
        readability_path: Path | None = None
    elif not matrix_report_paths:
        steps.append(
            blocked_step(
                "preview_readability_score",
                readability_command,
                readability_report_path,
                "Readability scoring is blocked until preview-matrix reports exist.",
                ["preview_matrix must produce at least one report"],
            )
        )
        readability_path = None
    else:
        step = execute_step(
            ctx,
            effect=effect,
            name="preview_readability_score",
            command=readability_command,
            planned_report_path=readability_report_path,
            evaluator=evaluate_readability,
            input_paths=matrix_report_paths,
            use_cache=args.resume_cache,
        )
        steps.append(step)
        readability_path = Path(str(step["report_path"])) if step.get("report_path") else None

    baseline_resolution = None
    baseline_set_index_path = ""
    if args.baseline:
        baseline_path = Path(args.baseline)
    else:
        resolved_baseline, baseline_set_index_path, baseline_resolution = resolve_baseline_from_set(ctx, effect, layer, args)
        baseline_path = resolved_baseline or default_baseline_path(ctx, effect, layer)
    preview_report_path, regression_note, regression_selection = regression_preview_path(
        args,
        matrix_report_paths,
        baseline_path=baseline_path if baseline_path.exists() else None,
        baseline_resolution=baseline_resolution,
    )
    regression_report_path = run_dir / "material-regression-compare.json"
    if args.no_require_regression:
        steps.append(advisory_step("material_regression", None, regression_report_path, "Regression requirement is disabled for this smoke run."))
        regression_path: Path | None = None
    elif args.baseline == "" and baseline_set_index_path and not baseline_path.exists():
        steps.append(advisory_step("material_regression", None, regression_report_path, f"Baseline set `{baseline_set_index_path}` did not resolve a usable baseline for context `{baseline_set_context(args)}`."))
        regression_path = None
    elif not baseline_path.exists():
        steps.append(advisory_step("material_regression", None, regression_report_path, f"No regression baseline exists at `{baseline_path}`."))
        regression_path = None
    elif not args.execute:
        detail = "Will compare the selected smoke preview against the accepted baseline after live capture."
        if preview_report_path is not None and regression_note:
            detail = f"{detail} {regression_note}"
        steps.append(planned_step("material_regression", None, regression_report_path, detail))
        regression_path = None
    elif preview_report_path is None:
        steps.append(advisory_step("material_regression", None, regression_report_path, regression_note))
        regression_path = None
    else:
        regression_command, regression_report_path = build_regression_command(args, effect, layer, baseline_path, preview_report_path, run_dir)
        step = execute_step(
            ctx,
            effect=effect,
            name="material_regression",
            command=regression_command,
            planned_report_path=regression_report_path,
            evaluator=evaluate_regression,
            input_paths=[baseline_path, preview_report_path],
            use_cache=args.resume_cache,
        )
        if regression_note:
            step["detail"] = f"{step['detail']} {regression_note}".strip()
        if regression_selection:
            step.setdefault("data", {})["preview_selection"] = regression_selection
        steps.append(step)
        regression_path = Path(str(step["report_path"])) if step.get("report_path") else None

    acceptance_command, acceptance_report_path = build_acceptance_command(
        args,
        package_path,
        material_path,
        schema_path,
        source_reports,
        sorting_reports,
        matrix_report_paths,
        readability_path,
        regression_path,
        run_dir,
    )
    if package_error:
        steps.append(
            blocked_step(
                "material_acceptance_gate_v2",
                acceptance_command,
                acceptance_report_path,
                "Acceptance gate is blocked until the delivery package is valid.",
                [f"delivery package `{package_path}` is {package_error}"],
            )
        )
        acceptance_path: Path | None = None
    elif not args.execute:
        steps.append(planned_step("material_acceptance_gate_v2", acceptance_command, acceptance_report_path, "Will evaluate the fresh smoke evidence after live execution."))
        acceptance_path = None
    else:
        step = execute_step(
            ctx,
            effect=effect,
            name="material_acceptance_gate_v2",
            command=acceptance_command,
            planned_report_path=acceptance_report_path,
            evaluator=evaluate_acceptance,
            input_paths=[package_path, schema_path, *source_reports, *sorting_reports, *matrix_report_paths, *( [readability_path] if readability_path else [] ), *( [regression_path] if regression_path else [] )],
            use_cache=args.resume_cache,
        )
        steps.append(step)
        acceptance_path = Path(str(step["report_path"])) if step.get("report_path") else None

    library_command, library_report_path = build_library_command(
        args,
        args.asset_id,
        acceptance_report_path,
        schema_path,
        source_reports,
        matrix_report_paths,
        readability_path,
        run_dir,
    )
    if args.apply_library_promotion and not args.asset_id:
        apply_note = "Apply was requested, but no --asset-id was supplied, so this remains advisory only."
    else:
        apply_note = ""
    if not args.execute:
        detail = "Will judge reusable-library readiness after acceptance is recomputed."
        if apply_note:
            detail += f" {apply_note}"
        steps.append(planned_step("library_promotion_gate", library_command, library_report_path, detail))
    elif acceptance_path is None:
        detail = "Library promotion gate is blocked until the v2 acceptance report exists."
        if apply_note:
            detail += f" {apply_note}"
        steps.append(
            blocked_step(
                "library_promotion_gate",
                library_command,
                library_report_path,
                detail,
                ["material_acceptance_gate_v2 must produce a report"],
            )
        )
    else:
        step = execute_step(
            ctx,
            effect=effect,
            name="library_promotion_gate",
            command=library_command,
            planned_report_path=library_report_path,
            evaluator=evaluate_library,
            input_paths=[acceptance_path, schema_path, *source_reports, *matrix_report_paths, *( [readability_path] if readability_path else [] )],
            use_cache=args.resume_cache,
        )
        if apply_note:
            step["detail"] = f"{step['detail']} {apply_note}".strip()
        steps.append(step)

    status = report_status(steps, args.execute)
    blocked = [step["name"] for step in steps if step.get("status") == "blocked"]
    advisory = [step["name"] for step in steps if step.get("status") == "advisory"]
    risky = [step["name"] for step in steps if step.get("status") == "risk"]
    ready_for_live_smoke = not package_error and not schema_error and bool(selected_variant_rows)
    report = {
        "tool": "material_delivery_smoke",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "label": args.label or "smoke",
        "status": status,
        "source": {
            "package": str(package_path),
            "parameter_schema": str(schema_path),
            "source_provenance_reports": [str(path) for path in source_reports],
            "translucency_sorting_reports": [str(path) for path in sorting_reports],
            "shader_cost_reports": [str(resolve_path(path, base=Path.cwd())) for path in args.shader_cost_report],
            "platform_scalability_reports": [str(resolve_path(path, base=Path.cwd())) for path in args.platform_scalability_report],
            "baseline": str(baseline_path) if baseline_path else "",
            "baseline_set": baseline_set_index_path,
            "baseline_set_resolution": baseline_resolution or {},
            "regression_preview_selection": regression_selection or {},
            "asset_id": args.asset_id,
        },
        "material_path": material_path,
        "smoke_tiers": selected_tiers,
        "regression_tier": args.regression_tier,
        "variants": variant_rows,
        "steps": steps,
        "summary": {
            "step_count": len(steps),
            "pass_count": sum(1 for step in steps if step.get("status") == "pass"),
            "planned_count": sum(1 for step in steps if step.get("status") == "planned"),
            "risk_count": len(risky),
            "blocked_count": len(blocked),
            "advisory_count": len(advisory),
            "cached_count": sum(1 for step in steps if step.get("cached")),
        },
        "gate": {
            "ready_for_live_smoke": ready_for_live_smoke,
            "executed": bool(args.execute),
            "smoke_passed": bool(args.execute and status == "pass"),
            "blocked_steps": blocked,
            "risk_steps": risky,
            "advisory_steps": advisory,
        },
        "produced_reports": {
            "variant_runner": str(variant_report_path) if variant_report_path else "",
            "static_switch_variant_expander": str(switch_report_path) if switch_report_path else "",
            "permutation_budget_guard": str(permutation_report_path) if permutation_report_path else "",
            "material_instance_batch": str(batch_report_path) if batch_report_path else "",
            "preview_matrix": [str(path) for path in matrix_report_paths],
            "preview_readability_score": str(readability_path) if readability_path else "",
            "material_regression": str(regression_path) if regression_path else "",
            "material_acceptance_gate_v2": str(acceptance_report_path),
            "library_promotion_gate": str(library_report_path),
        },
        "next_actions": next_actions(args, status, ready_for_live_smoke, blocked, advisory, risky, baseline_path),
        "boundary": {
            "material_side": "This smoke run closes the material-side delivery chain only.",
            "niagara_side": "Real Niagara System/Emitter/Renderer integration still belongs to niagara-vfx-artist.",
        },
    }
    return report, out


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    lines = [
        f"# Material Delivery Smoke: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Executed: `{gate.get('executed')}`",
        f"- Ready for live smoke: `{gate.get('ready_for_live_smoke')}`",
        f"- Smoke passed: `{gate.get('smoke_passed')}`",
        f"- Material path: `{report.get('material_path') or 'unset'}`",
        f"- Smoke tiers: `{', '.join(report.get('smoke_tiers') or []) or 'none'}`",
        "",
        "## Steps",
        "",
        "| Step | Status | Exit | Report | Detail |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for step in report.get("steps") or []:
        detail = str(step.get("detail") or "").replace("|", "\\|")
        lines.append(
            f"| `{step.get('name')}` | `{step.get('status')}` | {step.get('exit_code', '') if step.get('exit_code') is not None else ''} | "
            f"`{step.get('report_path') or step.get('planned_report_path') or ''}` | {detail} |"
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Pass: `{summary.get('pass_count', 0)}`",
            f"- Planned: `{summary.get('planned_count', 0)}`",
            f"- Risk: `{summary.get('risk_count', 0)}`",
            f"- Blocked: `{summary.get('blocked_count', 0)}`",
            f"- Advisory: `{summary.get('advisory_count', 0)}`",
            "",
            "## Next Actions",
            "",
        ]
    )
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.require_ready and not (report.get("gate") or {}).get("smoke_passed"):
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the material-side delivery smoke chain from variants to acceptance and optional library promotion.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--package", required=True, help="delivery_packager.py JSON report.")
    parser.add_argument("--parameter-schema-report", required=True, help="material_parameter_schema.py JSON report.")
    parser.add_argument("--source-provenance-report", action="append", default=[])
    parser.add_argument("--translucency-sorting-report", action="append", default=[])
    parser.add_argument("--shader-cost-report", action="append", default=[])
    parser.add_argument("--platform-scalability-report", action="append", default=[])
    parser.add_argument("--asset-id", default="")
    parser.add_argument("--baseline", default="", help="Optional explicit material_regression baseline JSON path.")
    parser.add_argument("--baseline-set", default="", help="Optional regression_baseline_set.py index to resolve a context-matched baseline when --baseline is omitted.")
    parser.add_argument("--smoke-tier", action="append", default=[])
    parser.add_argument("--regression-tier", default="default")
    parser.add_argument("--parent-path", default="", help="Optional material parent override for material_variant_runner.py.")
    parser.add_argument("--output-folder", default="", help="Optional UE output folder override for generated smoke MIs.")
    parser.add_argument("--include-non-regression", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--preview-quality", default="low")
    parser.add_argument("--max-static-permutations", type=int, default=16)
    parser.add_argument("--permutation-platform", action="append", default=[])
    parser.add_argument("--shader-permutation-report", default="")
    parser.add_argument("--matrix-spec", default="")
    parser.add_argument("--background", action="append", default=[])
    parser.add_argument("--exposure", action="append", default=[])
    parser.add_argument("--distance", action="append", default=[])
    parser.add_argument("--angle", action="append", default=[])
    parser.add_argument("--time", action="append", default=[])
    parser.add_argument("--quality", action="append", default=[])
    parser.add_argument("--lighting", action="append", default=[])
    parser.add_argument("--carrier", action="append", default=[])
    parser.add_argument("--resolution", type=int)
    parser.add_argument("--max-cells", type=int, default=64)
    parser.add_argument("--allow-large-matrix", action="store_true")
    parser.add_argument("--with-complexity", action="store_true")
    parser.add_argument("--markdown-previews", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--execute", action="store_true", help="Run live UE-dependent steps instead of only planning them.")
    parser.add_argument("--resume-cache", action="store_true", help="Reuse matching step reports from smoke_resume_cache.py when commands and inputs have not changed.")
    parser.add_argument("--no-require-domain-audit", action="store_true")
    parser.add_argument("--no-require-textures", action="store_true")
    parser.add_argument("--texture-set-waiver", default="")
    parser.add_argument("--no-require-regression", action="store_true")
    parser.add_argument("--no-require-parameters", action="store_true")
    parser.add_argument("--parameter-table-waiver", default="")
    parser.add_argument("--no-require-readability", action="store_true")
    parser.add_argument("--require-shader-cost", action="store_true")
    parser.add_argument("--require-platform-scalability", action="store_true")
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--apply-library-promotion", action="store_true")
    parser.add_argument("--label", default="")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
