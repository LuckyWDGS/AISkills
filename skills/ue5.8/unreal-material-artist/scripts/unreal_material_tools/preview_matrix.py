from __future__ import annotations

import argparse
import itertools
import json
import math
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


def parse_focus(text: str) -> tuple[float, float, float] | None:
    if not text:
        return None
    parts = [float(item) for item in text.split(",")]
    if len(parts) != 3:
        raise SystemExit(f"--focus must be x,y,z: {text}")
    return parts[0], parts[1], parts[2]


def parse_tier_materials(values: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values or []:
        tier, sep, path = str(value).partition("=")
        if not sep or not tier.strip() or not path.strip():
            raise SystemExit(f"--tier-material must be TIER=/Game/Path/MI: {value}")
        mapping[tier.strip()] = path.strip()
    return mapping


def parse_cell_reports(values: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values or []:
        cell_id, sep, path = str(value).partition("=")
        if not sep:
            raise SystemExit(f"--cell-report must be CELL_ID=report.json: {value}")
        mapping[cell_id.strip()] = path.strip()
    return mapping


def orbit_pose(focus: tuple[float, float, float], radius: float, yaw: float, pitch: float) -> str:
    """Camera pose x,y,z,pitch,yaw,roll on a sphere around focus, looking at it (UE: yaw about Z, pitch up)."""
    yaw_rad, pitch_rad = math.radians(yaw), math.radians(pitch)
    x = focus[0] + radius * math.cos(pitch_rad) * math.cos(yaw_rad)
    y = focus[1] + radius * math.cos(pitch_rad) * math.sin(yaw_rad)
    z = focus[2] + radius * math.sin(pitch_rad)
    look_yaw = (yaw + 180.0 + 180.0) % 360.0 - 180.0
    return ",".join(f"{value:.2f}" for value in (x, y, z, -pitch, look_yaw, 0.0))


def cell_route(args: argparse.Namespace, carrier: str) -> str:
    if args.route != "auto":
        return args.route
    return "thumbnail" if carrier == "mesh" else "viewport"


def plan_capture(args: argparse.Namespace, axes: dict[str, list[Any]], material_path: str, cell: dict[str, Any]) -> dict[str, Any]:
    """Decide what an Epic MCP capture can really vary for this cell; everything else is intent-only.

    Axes MCP cannot drive (background, exposure, lighting, time, quality) only run at their first value,
    which means "whatever is staged in the level"; other values need manual staging and a --cell-report.
    """
    route = cell_route(args, str(cell["carrier"]))
    first = {
        "background": axes["backgrounds"][0],
        "exposure": axes["exposures"][0],
        "lighting": axes["lighting"][0],
        "time": axes["times"][0],
        "quality_profile": axes["quality_profiles"][0],
        "distance": axes["distances"][0],
        "angle": (axes["angles"][0]["yaw"], axes["angles"][0]["pitch"]),
        "parameter_tier": axes["parameter_tiers"][0],
    }
    intent_only: dict[str, str] = {}
    for axis in ("background", "exposure", "lighting", "time", "quality_profile"):
        if cell[axis] != first[axis]:
            intent_only[axis] = "Epic MCP capture has no control for this axis; stage it in the level and pass --cell-report."
    focus = parse_focus(args.focus)
    pose = ""
    if route == "viewport" and focus is not None:
        radius = args.orbit_radius * (1.0 + float(cell["distance"]))
        pose = orbit_pose(focus, radius, float(cell["yaw"]), float(cell["pitch"]))
    elif cell["distance"] != first["distance"] or (cell["yaw"], cell["pitch"]) != first["angle"]:
        intent_only["camera"] = ("the asset thumbnail has a fixed camera" if route == "thumbnail"
                                 else "pass --focus x,y,z so viewport cells can orbit the staged carrier")
    tier_materials = parse_tier_materials(args.tier_material)
    tier = str(cell["parameter_tier"])
    capture_material = tier_materials.get(tier) or (material_path if tier == first["parameter_tier"] else "")
    if not capture_material:
        intent_only["parameter_tier"] = f"no --tier-material {tier}=<MI> was given"
    elif capture_material != material_path and route == "viewport":
        intent_only["parameter_tier"] = "a viewport capture shows the staged actor's material; assign the tier MI or use --route thumbnail"
    return {
        "route": route,
        "material_path": capture_material or material_path,
        "pose": pose,
        "executable": not intent_only,
        "intent_only_axes": intent_only,
    }


def make_preview_command(args: argparse.Namespace, cell: dict[str, Any]) -> list[str]:
    capture = cell["capture"]
    command = [
        sys.executable,
        str(preview_tool_path()),
        "capture",
        capture["material_path"],
        "--root",
        str(args.root),
        "--route",
        capture["route"],
        "--carrier",
        str(cell["carrier"]),
        "--effect",
        str(cell["preview_effect"]),
    ]
    if capture["pose"]:
        command.extend(["--pose", capture["pose"]])
    if args.project:
        command.extend(["--project", args.project])
    if args.timeout:
        command.extend(["--timeout", str(args.timeout)])
    if args.markdown_previews:
        command.append("--markdown")
    return command


def make_staging_command(args: argparse.Namespace, material_path: str, cell: dict[str, Any]) -> list[str]:
    """The environment plan for a cell that needs manual staging before its capture."""
    command = [
        sys.executable,
        str(environment_executor_tool_path()),
        "--root",
        str(args.root),
        "--material-path",
        cell["capture"]["material_path"] or material_path,
        "--carrier",
        str(cell["carrier"]),
        "--background",
        str(cell["background"]),
        "--exposure",
        str(cell["exposure"]),
        "--effect",
        str(cell["preview_effect"]),
    ]
    if cell["capture"]["pose"]:
        command.extend(["--pose", cell["capture"]["pose"]])
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
        cell_id = f"cell-{index:03d}"
        cell = {
            "id": cell_id,
            "preview_effect": f"{slugify(args.effect or 'preview-matrix')}-{cell_id}",
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
            "resolution": quality_resolution(str(quality), args.resolution),
        }
        cell["capture"] = plan_capture(args, axes, material_path, cell)
        cell["preview_command"] = make_preview_command(args, cell)
        cell["preview_command_text"] = command_display(cell["preview_command"])
        if not cell["capture"]["executable"]:
            cell["staging_command"] = make_staging_command(args, material_path, cell)
        cells.append(cell)
    return cells


def load_preview_report(report_path: str) -> dict[str, Any]:
    path = Path(report_path) if report_path else None
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": str(exc)}
    return payload if isinstance(payload, dict) else {}


def execution_from_report(report_path: str, *, returncode: int = 0, stdout: str = "", stderr: str = "", source: str) -> dict[str, Any]:
    payload = load_preview_report(report_path)
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    passed = payload.get("tool") == "material_preview" and outputs.get("shaded_ok") is True
    return {
        "status": "pass" if returncode == 0 and passed else "fail",
        "source": source,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr or payload.get("_load_error", ""),
        "report_path": report_path,
        "preview_report_path": report_path,
        "tool": str(payload.get("tool") or ""),
        "outputs": outputs,
    }


def execute_cell(cell: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(cell["preview_command"], capture_output=True, text=True, check=False)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return execution_from_report(lines[-1] if lines else "", returncode=completed.returncode,
                                 stdout=completed.stdout.strip(), stderr=completed.stderr.strip(), source="mcp-capture")


def run_cells(args: argparse.Namespace, cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    staged = parse_cell_reports(args.cell_report)
    unknown = sorted(set(staged) - {cell["id"] for cell in cells})
    if unknown:
        raise SystemExit(f"--cell-report names unknown cells: {', '.join(unknown)}")
    executions: list[dict[str, Any]] = []
    for cell in cells:
        if cell["id"] in staged:
            cell["execution"] = execution_from_report(staged[cell["id"]], source="staged-capture")
        elif not args.execute:
            continue
        elif cell["capture"]["executable"]:
            cell["execution"] = execute_cell(cell)
        else:
            cell["execution"] = {
                "status": "pending_staging",
                "source": "",
                "intent_only_axes": cell["capture"]["intent_only_axes"],
                "detail": "Stage this context, capture it with preview_command, then rerun with --cell-report "
                          f"{cell['id']}=<material_preview report>.",
            }
        executions.append(cell["execution"])
    return executions


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
    executions = run_cells(args, cells)
    captured = [item for item in executions if item.get("status") in {"pass", "fail"}]
    failed = [item for item in captured if item["status"] == "fail"]
    pending = [item for item in executions if item.get("status") == "pending_staging"]
    executed = bool(args.execute or args.cell_report)
    effect = args.effect or package.get("effect") or material_path
    layer = args.layer or package.get("layer") or ""
    report = {
        "tool": "preview_matrix",
        "version": 2,
        "generated_utc": utc_now_iso(),
        "effect": effect if effect != material_path else "",
        "layer": layer,
        "material_path": material_path,
        "route": route,
        "axes": axes,
        "cells": cells,
        "summary": {
            "planned_cells": len(cells),
            "mcp_executable_cells": sum(1 for cell in cells if cell["capture"]["executable"]),
            "executed_cells": len(captured),
            "failed_cells": len(failed),
            "passed_cells": len(captured) - len(failed),
            "pending_staging_cells": len(pending),
        },
        "gate": {
            "passed": not failed,
            "executed": executed,
            # Full coverage only: a cell waiting for manual staging is missing evidence, not a pass.
            "ready_for_regression_coverage": bool(executed and captured and not failed and not pending),
            "large_matrix_allowed": bool(args.allow_large_matrix),
        },
        "evidence": {
            "package": str(resolve_path(args.package, base=Path.cwd())) if args.package else "",
            "preview_reports": [item["report_path"] for item in captured if item.get("report_path")],
        },
        "next_actions": next_actions(executed, failed, pending, cells),
    }
    stem = slugify(effect if effect != material_path else material_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "preview-matrices", stem, "preview-matrix", ".json")
    return report, out


def next_actions(executed: bool, failed: list[dict[str, Any]], pending: list[dict[str, Any]], cells: list[dict[str, Any]]) -> list[str]:
    if failed:
        return ["Inspect failed matrix cells and rerun material_preview.py capture for them before accepting the material."]
    if pending:
        return [f"{len(pending)} cell(s) vary axes Epic MCP cannot drive; stage each, capture it, and pass --cell-report CELL=report."]
    if executed:
        return ["Use the matrix preview reports as wider visual evidence before locking a regression baseline."]
    executable = sum(1 for cell in cells if cell["capture"]["executable"])
    return [f"Run with --execute against a live editor: {executable}/{len(cells)} cell(s) capture directly over Epic MCP."]


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    lines = [
        f"# Preview Matrix: {report.get('effect') or report.get('material_path')}",
        "",
        f"- Executed: `{gate.get('executed')}`",
        f"- Passed: `{gate.get('passed')}`",
        f"- Ready for regression coverage: `{gate.get('ready_for_regression_coverage')}`",
        f"- Planned cells: `{summary.get('planned_cells')}` (MCP-executable `{summary.get('mcp_executable_cells')}`)",
        f"- Executed cells: `{summary.get('executed_cells')}`, failed `{summary.get('failed_cells')}`, pending staging `{summary.get('pending_staging_cells')}`",
        "",
        "## Cells",
        "",
        "| Cell | Carrier | Route | Background | Exposure | Distance | Angle | Time | Tier | Quality | Status |",
        "| --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- | --- |",
    ]
    for cell in report.get("cells") or []:
        capture = cell.get("capture") or {}
        status = (cell.get("execution") or {}).get("status") or ("planned" if capture.get("executable") else "needs staging")
        lines.append(
            f"| `{cell.get('id')}` | `{cell.get('carrier')}` | `{capture.get('route')}` | `{cell.get('background')}` | "
            f"`{cell.get('exposure')}` | {cell.get('distance')} | `{cell.get('yaw')},{cell.get('pitch')}` | {cell.get('time')} | "
            f"`{cell.get('parameter_tier')}` | `{cell.get('quality_profile')}` | `{status}` |"
        )
    lines.extend(["", "## Preview Commands", ""])
    for cell in (report.get("cells") or [])[:12]:
        lines.append(f"- `{cell.get('id')}`: `{cell.get('preview_command_text')}`")
        for axis, reason in ((cell.get("capture") or {}).get("intent_only_axes") or {}).items():
            lines.append(f"  - intent only `{axis}`: {reason}")
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
    parser = argparse.ArgumentParser(description="Plan or capture a matrix of material previews across context, camera, time, parameter tier, and quality axes.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--package", default="", help="Optional delivery package used to derive material path/effect/carrier.")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--matrix-spec", default="", help="Optional JSON with axes/backgrounds/exposures/distances/angles/times/parameter_tiers/quality_profiles.")
    parser.add_argument("--background", action="append", default=None)
    parser.add_argument("--exposure", action="append", default=None)
    parser.add_argument("--distance", action="append", default=None, help="Orbit distance step: the camera sits at --orbit-radius * (1 + distance).")
    parser.add_argument("--angle", action="append", default=None, help="Repeatable yaw,pitch value. Use semicolons to pack multiple values.")
    parser.add_argument("--time", action="append", default=None)
    parser.add_argument("--parameter-tier", action="append", default=None)
    parser.add_argument("--tier-material", action="append", default=None, help="TIER=/Game/Path/MI: the instance to capture for a parameter tier.")
    parser.add_argument("--quality", action="append", default=None)
    parser.add_argument("--lighting", action="append", default=None)
    parser.add_argument("--carrier", action="append", default=None)
    parser.add_argument("--default-carrier", default="auto")
    parser.add_argument("--route", choices=["auto", "thumbnail", "viewport"], default="auto",
                        help="auto: mesh -> asset thumbnail, other carriers -> viewport of the staged carrier.")
    parser.add_argument("--focus", default="", help="x,y,z of the staged carrier; viewport cells orbit it for the angle/distance axes.")
    parser.add_argument("--orbit-radius", type=float, default=300.0)
    parser.add_argument("--cell-report", action="append", default=None, help="CELL_ID=report.json: a capture you staged for an intent-only cell.")
    parser.add_argument("--resolution", type=int)
    parser.add_argument("--max-cells", type=int, default=64)
    parser.add_argument("--allow-large-matrix", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Capture every MCP-executable cell through the live editor.")
    parser.add_argument("--project")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--with-complexity", action="store_true", help=argparse.SUPPRESS)  # MCP has no shader-complexity view
    parser.add_argument("--markdown-previews", action="store_true", help="Also ask each material_preview.py capture to write Markdown.")
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
