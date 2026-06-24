from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import load_json, material_route, resolve_path


QUALITY_RESOLUTION = {
    "mobile_low": 192,
    "low": 256,
    "medium": 384,
    "high": 512,
    "pc_high": 768,
}
DEFAULT_BACKGROUNDS = ["black", "neutral", "busy"]
DEFAULT_EXPOSURES = ["0"]
DEFAULT_DISTANCES = [0.0]
DEFAULT_ANGLES = [{"yaw": 30.0, "pitch": 15.0}]
DEFAULT_TIMES = [1.0]
DEFAULT_PARAMETER_TIERS = ["default"]
DEFAULT_QUALITY = ["medium"]
DEFAULT_LIGHTING = ["hdri"]


def split_values(values: list[str] | None, default: list[str]) -> list[str]:
    if not values:
        return list(default)
    result: list[str] = []
    for value in values:
        result.extend(item.strip() for item in str(value).split(",") if item.strip())
    return result or list(default)


def split_floats(values: list[str] | None, default: list[float]) -> list[float]:
    return [float(item) for item in split_values(values, [str(item) for item in default])]


def parse_angles(values: list[str] | None) -> list[dict[str, float]]:
    if not values:
        return list(DEFAULT_ANGLES)
    result: list[dict[str, float]] = []
    for value in values:
        for item in str(value).split(";"):
            item = item.strip()
            if not item:
                continue
            if "," not in item:
                raise SystemExit(f"Angle must look like yaw,pitch: {item}")
            yaw, pitch = item.split(",", 1)
            result.append({"yaw": float(yaw), "pitch": float(pitch)})
    return result or list(DEFAULT_ANGLES)


def load_matrix_spec(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    payload = load_json(path)
    axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else payload
    return axes if isinstance(axes, dict) else {}


def spec_list(spec: dict[str, Any], key: str) -> list[Any] | None:
    value = spec.get(key)
    if value is None:
        return None
    return value if isinstance(value, list) else [value]


def resolve_axes(args: argparse.Namespace) -> dict[str, list[Any]]:
    spec = load_matrix_spec(args.matrix_spec)
    backgrounds = [str(item) for item in (spec_list(spec, "backgrounds") or split_values(args.background, DEFAULT_BACKGROUNDS))]
    exposures = [str(item) for item in (spec_list(spec, "exposures") or split_values(args.exposure, DEFAULT_EXPOSURES))]
    distances = [float(item) for item in (spec_list(spec, "distances") or split_floats(args.distance, DEFAULT_DISTANCES))]
    if spec_list(spec, "angles"):
        angles = []
        for item in spec_list(spec, "angles") or []:
            if isinstance(item, dict):
                angles.append({"yaw": float(item.get("yaw", 30.0)), "pitch": float(item.get("pitch", 15.0))})
            else:
                angles.extend(parse_angles([str(item)]))
    else:
        angles = parse_angles(args.angle)
    times = [float(item) for item in (spec_list(spec, "times") or split_floats(args.time, DEFAULT_TIMES))]
    parameter_tiers = [str(item) for item in (spec_list(spec, "parameter_tiers") or split_values(args.parameter_tier, DEFAULT_PARAMETER_TIERS))]
    quality_profiles = [str(item) for item in (spec_list(spec, "quality_profiles") or split_values(args.quality, DEFAULT_QUALITY))]
    lighting = [str(item) for item in (spec_list(spec, "lighting") or split_values(args.lighting, DEFAULT_LIGHTING))]
    carriers = [str(item) for item in (spec_list(spec, "carriers") or split_values(args.carrier, [args.default_carrier]))]
    return {
        "backgrounds": backgrounds,
        "exposures": exposures,
        "distances": distances,
        "angles": angles,
        "times": times,
        "parameter_tiers": parameter_tiers,
        "quality_profiles": quality_profiles,
        "lighting": lighting,
        "carriers": carriers,
    }


def material_from_package(args: argparse.Namespace) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if not args.package:
        return {}, args.material_path, {}
    package_path = resolve_path(args.package, base=Path.cwd())
    package = load_json(package_path)
    route = material_route(package, None)
    material_path = args.material_path or str(package.get("material_path") or "")
    return package, material_path, route


def preview_tool_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tools" / "material_preview.py"


def environment_executor_tool_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tools" / "preview_environment_executor.py"


def quality_resolution(profile: str, explicit: int | None) -> int:
    if explicit:
        return int(explicit)
    return QUALITY_RESOLUTION.get(profile, QUALITY_RESOLUTION["medium"])


def should_use_environment_executor(args: argparse.Namespace, cell: dict[str, Any]) -> bool:
    if args.disable_environment_executor:
        return False
    if str(cell.get("carrier") or "") == "mesh":
        return False
    return bool(args.execute or args.prefer_environment_executor)


def make_preview_command(args: argparse.Namespace, material_path: str, cell: dict[str, Any]) -> list[str]:
    if should_use_environment_executor(args, cell):
        command = [
            sys.executable,
            str(environment_executor_tool_path()),
            "--root",
            str(args.root),
            "--material-path",
            material_path,
            "--carrier",
            str(cell["carrier"]),
            "--lighting",
            str(cell["lighting"]),
            "--background",
            str(cell["background"]),
            "--exposure",
            str(cell["exposure"]),
            "--resolution",
            str(cell["resolution"]),
            "--yaw",
            str(cell["yaw"]),
            "--pitch",
            str(cell["pitch"]),
            "--distance",
            str(cell["distance"]),
            "--sim-time",
            str(cell["time"]),
            "--effect",
            str(cell["preview_effect"]),
        ]
        if args.execute:
            command.append("--execute")
        if args.project:
            command.extend(["--project", args.project])
        if args.endpoint:
            command.extend(["--endpoint", args.endpoint])
        if args.timeout:
            command.extend(["--timeout", str(args.timeout)])
        if args.with_complexity:
            command.append("--with-complexity")
        if args.markdown_previews:
            command.append("--markdown-previews")
        return command
    command = [
        sys.executable,
        str(preview_tool_path()),
        "render",
        material_path,
        "--root",
        str(args.root),
        "--carrier",
        str(cell["carrier"]),
        "--lighting",
        str(cell["lighting"]),
        "--resolution",
        str(cell["resolution"]),
        "--yaw",
        str(cell["yaw"]),
        "--pitch",
        str(cell["pitch"]),
        "--distance",
        str(cell["distance"]),
        "--sim-time",
        str(cell["time"]),
    ]
    if args.project:
        command.extend(["--project", args.project])
    if args.endpoint:
        command.extend(["--endpoint", args.endpoint])
    if args.timeout:
        command.extend(["--timeout", str(args.timeout)])
    command.extend(["--effect", str(cell["preview_effect"])])
    if args.with_complexity:
        command.append("--with-complexity")
    if args.markdown_previews:
        command.append("--markdown")
    return command


def command_display(command: list[str]) -> str:
    return " ".join(json.dumps(part) if " " in part else part for part in command)


def build_cells(args: argparse.Namespace, axes: dict[str, list[Any]], material_path: str) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for index, values in enumerate(
        itertools.product(
            axes["backgrounds"],
            axes["exposures"],
            axes["distances"],
            axes["angles"],
            axes["times"],
            axes["parameter_tiers"],
            axes["quality_profiles"],
            axes["lighting"],
            axes["carriers"],
        ),
        start=1,
    ):
        background, exposure, distance, angle, time_value, tier, quality, lighting, carrier = values
        resolution = quality_resolution(str(quality), args.resolution)
        cell_id = f"cell-{index:03d}"
        preview_effect_base = slugify(args.effect or "preview-matrix")
        cell = {
            "id": cell_id,
            "preview_effect": f"{preview_effect_base}-{cell_id}",
            "background": background,
            "exposure": exposure,
            "distance": distance,
            "yaw": float(angle["yaw"]),
            "pitch": float(angle["pitch"]),
            "time": time_value,
            "parameter_tier": tier,
            "quality_profile": quality,
            "lighting": lighting,
            "carrier": carrier,
            "resolution": resolution,
        }
        if not should_use_environment_executor(args, cell):
            cell["unsupported_execute_axes"] = {
                "background": "preview_environment_executor.py is not active for this cell, so background stays intent-only.",
                "exposure": "preview_environment_executor.py is not active for this cell, so exposure stays intent-only.",
                "parameter_tier": "tracked as review context; use material_instance_batch.py or a prepared MI for actual value changes.",
            }
        else:
            cell["environment_executor"] = {
                "background_executable": True,
                "exposure_executable": True,
                "light_rig_executable": True,
            }
        cell["preview_command"] = make_preview_command(args, material_path, cell)
        cell["preview_command_text"] = command_display(cell["preview_command"])
        cells.append(cell)
    return cells


def execute_cell(cell: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(cell["preview_command"], capture_output=True, text=True, check=False)
    report_path = ""
    stdout_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if stdout_lines:
        report_path = stdout_lines[-1]
    outputs: dict[str, Any] = {}
    if report_path:
        path = Path(report_path)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
            except Exception as exc:
                outputs = {"load_error": str(exc)}
                payload = {}
        else:
            payload = {}
    else:
        payload = {}
    tool_name = str((payload or {}).get("tool") or "")
    preview_report_path = report_path
    passed = False
    if tool_name == "preview_environment_executor":
        preview_report_path = str((payload or {}).get("preview_report_path") or "")
        passed = bool(((payload or {}).get("gate") or {}).get("passed"))
    else:
        passed = outputs.get("shaded_ok") is True
    status = "pass" if completed.returncode == 0 and passed else "fail"
    return {
        "status": status,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "report_path": report_path,
        "preview_report_path": preview_report_path,
        "tool": tool_name,
        "outputs": outputs,
    }


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package, material_path, route = material_from_package(args)
    if not material_path:
        raise SystemExit("Provide --material-path or a --package with material_path.")
    if args.default_carrier == "auto":
        args.default_carrier = str(route.get("carrier") or "mesh")
    axes = resolve_axes(args)
    cells = build_cells(args, axes, material_path)
    if len(cells) > args.max_cells and not args.allow_large_matrix:
        raise SystemExit(f"Preview matrix would create {len(cells)} cells; raise --max-cells or pass --allow-large-matrix.")
    executions: list[dict[str, Any]] = []
    if args.execute:
        for cell in cells:
            result = execute_cell(cell)
            cell["execution"] = result
            executions.append(result)
    failed = [item for item in executions if item.get("status") != "pass"]
    passed = (not args.execute) or not failed
    effect = args.effect or package.get("effect") or material_path
    layer = args.layer or package.get("layer") or ""
    report = {
        "tool": "preview_matrix",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect if effect != material_path else "",
        "layer": layer,
        "material_path": material_path,
        "route": route,
        "axes": axes,
        "cells": cells,
        "summary": {
            "planned_cells": len(cells),
            "executed_cells": len(executions),
            "failed_cells": len(failed),
            "passed_cells": len(executions) - len(failed),
        },
        "gate": {
            "passed": passed,
            "executed": bool(args.execute),
            "ready_for_regression_coverage": bool(args.execute and not failed),
            "large_matrix_allowed": bool(args.allow_large_matrix),
        },
        "evidence": {
            "package": str(resolve_path(args.package, base=Path.cwd())) if args.package else "",
            "preview_reports": [item.get("preview_report_path") or item.get("report_path") for item in executions if item.get("preview_report_path") or item.get("report_path")],
        },
        "next_actions": next_actions(args, failed),
    }
    stem = slugify(effect if effect != material_path else material_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "preview-matrices", stem, "preview-matrix", ".json")
    return report, out


def next_actions(args: argparse.Namespace, failed: list[dict[str, Any]]) -> list[str]:
    if failed:
        return ["Inspect failed matrix cells and rerun material_preview.py for the failing contexts before accepting the material."]
    if args.execute:
        return ["Use the matrix preview reports as wider visual evidence before locking a regression baseline."]
    return ["Review the planned matrix, then rerun preview_matrix.py with --execute when UnrealBridge is available."]


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    lines = [
        f"# Preview Matrix: {report.get('effect') or report.get('material_path')}",
        "",
        f"- Executed: `{gate.get('executed')}`",
        f"- Passed: `{gate.get('passed')}`",
        f"- Planned cells: `{summary.get('planned_cells')}`",
        f"- Executed cells: `{summary.get('executed_cells')}`",
        f"- Failed cells: `{summary.get('failed_cells')}`",
        "",
        "## Cells",
        "",
        "| Cell | Carrier | Background | Exposure | Distance | Angle | Time | Tier | Quality | Status |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- |",
    ]
    for cell in report.get("cells") or []:
        execution = cell.get("execution") or {}
        status = execution.get("status") or "planned"
        lines.append(
            f"| `{cell.get('id')}` | `{cell.get('carrier')}` | `{cell.get('background')}` | `{cell.get('exposure')}` | "
            f"{cell.get('distance')} | `{cell.get('yaw')},{cell.get('pitch')}` | {cell.get('time')} | "
            f"`{cell.get('parameter_tier')}` | `{cell.get('quality_profile')}` | `{status}` |"
        )
    lines.extend(["", "## Preview Commands", ""])
    for cell in (report.get("cells") or [])[:12]:
        lines.append(f"- `{cell.get('id')}`: `{cell.get('preview_command_text')}`")
    if len(report.get("cells") or []) > 12:
        lines.append(f"- ... {len(report.get('cells') or []) - 12} more cells")
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
    parser = argparse.ArgumentParser(description="Plan or execute a controlled matrix of material previews across context, camera, time, parameter tier, and quality axes.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--package", default="", help="Optional delivery package used to derive material path/effect/carrier.")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--matrix-spec", default="", help="Optional JSON with axes/backgrounds/exposures/distances/angles/times/parameter_tiers/quality_profiles.")
    parser.add_argument("--background", action="append", default=None)
    parser.add_argument("--exposure", action="append", default=None)
    parser.add_argument("--distance", action="append", default=None)
    parser.add_argument("--angle", action="append", default=None, help="Repeatable yaw,pitch value. Use semicolons to pack multiple values.")
    parser.add_argument("--time", action="append", default=None)
    parser.add_argument("--parameter-tier", action="append", default=None)
    parser.add_argument("--quality", action="append", default=None)
    parser.add_argument("--lighting", action="append", default=None)
    parser.add_argument("--carrier", action="append", default=None)
    parser.add_argument("--default-carrier", default="auto")
    parser.add_argument("--resolution", type=int)
    parser.add_argument("--max-cells", type=int, default=64)
    parser.add_argument("--allow-large-matrix", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--prefer-environment-executor", action="store_true", help="Plan environment-adjusted preview commands even during dry-run.")
    parser.add_argument("--disable-environment-executor", action="store_true", help="Force legacy material_preview.py execution even when background/exposure axes exist.")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--with-complexity", action="store_true")
    parser.add_argument("--markdown-previews", action="store_true", help="Also ask each material_preview.py execution to write Markdown.")
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
