from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import load_json, material_route, resolve_path
from .preview_matrix import DEFAULT_ANGLES, DEFAULT_BACKGROUNDS, DEFAULT_EXPOSURES, DEFAULT_LIGHTING, DEFAULT_QUALITY, DEFAULT_TIMES


DEFAULT_DISTANCES = [0.0]
DEFAULT_PARAMETER_TIERS = ["default"]


def split_values(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()] or list(default)


def parse_map(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Expected key=value mapping, got: {value}")
        key, mapped = value.split("=", 1)
        result[key.strip()] = mapped.strip()
    return result


def axes_from_matrix(path: Path) -> dict[str, list[Any]]:
    payload = load_json(path)
    axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else {}
    if not axes:
        return {}
    return {
        "backgrounds": list(axes.get("backgrounds") or DEFAULT_BACKGROUNDS),
        "exposures": list(axes.get("exposures") or DEFAULT_EXPOSURES),
        "distances": list(axes.get("distances") or DEFAULT_DISTANCES),
        "angles": list(axes.get("angles") or DEFAULT_ANGLES),
        "times": list(axes.get("times") or DEFAULT_TIMES),
        "parameter_tiers": list(axes.get("parameter_tiers") or DEFAULT_PARAMETER_TIERS),
        "quality_profiles": list(axes.get("quality_profiles") or DEFAULT_QUALITY),
        "lighting": list(axes.get("lighting") or DEFAULT_LIGHTING),
        "carriers": list(axes.get("carriers") or ["mesh"]),
    }


def axes_from_args(args: argparse.Namespace) -> dict[str, list[Any]]:
    if args.preview_matrix_report:
        return axes_from_matrix(resolve_path(args.preview_matrix_report, base=Path.cwd()))
    if args.matrix_spec:
        payload = load_json(resolve_path(args.matrix_spec, base=Path.cwd()))
        axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else payload
        if isinstance(axes, dict):
            return {
                "backgrounds": list(axes.get("backgrounds") or DEFAULT_BACKGROUNDS),
                "exposures": list(axes.get("exposures") or DEFAULT_EXPOSURES),
                "distances": list(axes.get("distances") or DEFAULT_DISTANCES),
                "angles": list(axes.get("angles") or DEFAULT_ANGLES),
                "times": list(axes.get("times") or DEFAULT_TIMES),
                "parameter_tiers": list(axes.get("parameter_tiers") or DEFAULT_PARAMETER_TIERS),
                "quality_profiles": list(axes.get("quality_profiles") or DEFAULT_QUALITY),
                "lighting": list(axes.get("lighting") or DEFAULT_LIGHTING),
                "carriers": list(axes.get("carriers") or [args.carrier or "mesh"]),
            }
    return {
        "backgrounds": split_values(args.backgrounds, DEFAULT_BACKGROUNDS),
        "exposures": split_values(args.exposures, DEFAULT_EXPOSURES),
        "distances": DEFAULT_DISTANCES,
        "angles": list(DEFAULT_ANGLES),
        "times": DEFAULT_TIMES,
        "parameter_tiers": split_values(args.parameter_tiers, DEFAULT_PARAMETER_TIERS),
        "quality_profiles": split_values(args.quality_profiles, DEFAULT_QUALITY),
        "lighting": split_values(args.lighting, DEFAULT_LIGHTING),
        "carriers": split_values(args.carrier, ["mesh"]),
    }


def material_from_package(args: argparse.Namespace) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if not args.package:
        return {}, args.material_path, {}
    package_path = resolve_path(args.package, base=Path.cwd())
    package = load_json(package_path)
    route = material_route(package, None)
    return package, args.material_path or str(package.get("material_path") or ""), route


def variant_map(args: argparse.Namespace) -> dict[str, str]:
    if not args.variant_report:
        return {}
    payload = load_json(resolve_path(args.variant_report, base=Path.cwd()))
    result: dict[str, str] = {}
    for item in payload.get("variants") or []:
        if isinstance(item, dict) and item.get("tier") and item.get("path"):
            result[str(item["tier"])] = str(item["path"])
    return result


def axis_status(axis: str, values: list[Any], mapping: dict[str, str], *, waived: bool = False) -> dict[str, Any]:
    if len(values) <= 1:
        return {"axis": axis, "status": "trivial", "values": values, "missing": [], "executable": True}
    missing = [str(value) for value in values if str(value) not in mapping]
    executable = not missing or waived
    status = "executable" if executable and not waived else "waived" if waived else "intent_only"
    return {"axis": axis, "status": status, "values": values, "missing": missing, "mapping": mapping, "executable": executable}


def preview_tool_command(args: argparse.Namespace, material_path: str, axes: dict[str, list[Any]], tier: str) -> list[str]:
    tool = Path(__file__).resolve().parents[2] / "tools" / "preview_matrix.py"
    command = [
        sys.executable,
        str(tool),
        "--material-path",
        material_path,
        "--parameter-tier",
        tier,
        "--background",
        ",".join(str(item) for item in axes.get("backgrounds") or []),
        "--exposure",
        ",".join(str(item) for item in axes.get("exposures") or []),
        "--quality",
        ",".join(str(item) for item in axes.get("quality_profiles") or []),
    ]
    if args.project:
        command.extend(["--project", args.project])
    if args.endpoint:
        command.extend(["--endpoint", args.endpoint])
    return command


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package, material_path, route = material_from_package(args)
    axes = axes_from_args(args)
    backgrounds = parse_map(args.background_map)
    exposures = parse_map(args.exposure_map)
    variants = variant_map(args)
    if "default" not in variants and material_path:
        variants["default"] = material_path
    parameter_status = axis_status("parameter_tier", axes["parameter_tiers"], variants, waived=args.waive_parameter_tiers)
    background_status = axis_status("background", axes["backgrounds"], backgrounds, waived=args.waive_backgrounds)
    exposure_status = axis_status("exposure", axes["exposures"], exposures, waived=args.waive_exposures)
    already_executable = [
        {"axis": "carrier", "status": "native_preview_matrix_axis", "values": axes.get("carriers"), "executable": True},
        {"axis": "lighting", "status": "native_preview_matrix_axis", "values": axes.get("lighting"), "executable": True},
        {"axis": "quality_profile", "status": "native_preview_matrix_axis", "values": axes.get("quality_profiles"), "executable": True},
        {"axis": "distance", "status": "native_preview_matrix_axis", "values": axes.get("distances"), "executable": True},
        {"axis": "angle", "status": "native_preview_matrix_axis", "values": axes.get("angles"), "executable": True},
        {"axis": "time", "status": "native_preview_matrix_axis", "values": axes.get("times"), "executable": True},
    ]
    axis_rows = [background_status, exposure_status, parameter_status, *already_executable]
    blockers = [row for row in axis_rows if not row.get("executable")]
    commands = [
        {
            "tier": tier,
            "material_path": variants.get(tier, material_path),
            "preview_matrix_command": preview_tool_command(args, variants.get(tier, material_path), axes, tier),
        }
        for tier in axes.get("parameter_tiers", [])
        if variants.get(tier, material_path)
    ]
    effect = args.effect or package.get("effect") or material_path or "preview-scene-harness"
    report = {
        "tool": "preview_scene_harness_upgrade",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "material_path": material_path,
        "route": route,
        "axes": axes,
        "axis_status": axis_rows,
        "background_harness": {
            "mapped_backgrounds": backgrounds,
            "required_material_preview_capability": "scene background/material or environment override for black/grey/bright/busy contexts",
        },
        "exposure_harness": {
            "mapped_exposures": exposures,
            "required_material_preview_capability": "camera exposure or post-process exposure override per cell",
        },
        "parameter_tier_harness": {
            "variant_report": str(resolve_path(args.variant_report, base=Path.cwd())) if args.variant_report else "",
            "tier_to_material_instance": variants,
            "executable_now": bool(parameter_status.get("executable")),
        },
        "recommended_commands": commands,
        "summary": {
            "axis_count": len(axis_rows),
            "blocked_axis_count": len(blockers),
            "recommended_command_count": len(commands),
        },
        "gate": {
            "passed": not blockers,
            "ready_for_live_matrix": not blockers,
            "backgrounds_executable": bool(background_status.get("executable")),
            "exposures_executable": bool(exposure_status.get("executable")),
            "parameter_tiers_executable": bool(parameter_status.get("executable")),
            "blocked_axes": [row["axis"] for row in blockers],
        },
        "next_actions": next_actions(blockers),
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "preview-harness", effect, "preview-scene-harness-upgrade", ".json")
    return report, out


def next_actions(blockers: list[dict[str, Any]]) -> list[str]:
    axes = {str(item.get("axis")) for item in blockers}
    actions: list[str] = []
    if "parameter_tier" in axes:
        actions.append("Run material_variant_runner.py and pass --variant-report so parameter tiers resolve to concrete MIs.")
    if "background" in axes:
        actions.append("Provide --background-map entries or extend material_preview.py with a real background-scene override.")
    if "exposure" in axes:
        actions.append("Provide --exposure-map entries or extend material_preview.py with a real camera/post-process exposure override.")
    if not actions:
        actions.append("Preview matrix axes have an executable harness plan; run the recommended commands and then readability/regression gates.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    lines = [
        f"# Preview Scene Harness Upgrade: {report.get('effect')}",
        "",
        f"- Ready for live matrix: `{gate.get('ready_for_live_matrix')}`",
        f"- Blocked axes: `{', '.join(gate.get('blocked_axes') or []) or 'none'}`",
        "",
        "## Axis Status",
        "",
        "| Axis | Status | Executable | Missing |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("axis_status") or []:
        lines.append(f"| `{row.get('axis')}` | `{row.get('status')}` | `{row.get('executable')}` | `{', '.join(row.get('missing') or [])}` |")
    lines.extend(["", "## Recommended Commands", ""])
    for row in report.get("recommended_commands") or []:
        lines.append(f"- `{row.get('tier')}`: `{' '.join(str(item) for item in row.get('preview_matrix_command') or [])}`")
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
    if args.require_ready and not (report.get("gate") or {}).get("ready_for_live_matrix"):
        print(f"Preview scene harness is not ready: {out}", file=sys.stderr)
        return 2
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upgrade preview-matrix intent axes into an executable scene/variant harness plan.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--package", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--preview-matrix-report", default="")
    parser.add_argument("--matrix-spec", default="")
    parser.add_argument("--variant-report", default="", help="material_variant_runner.py report mapping parameter tiers to MI paths.")
    parser.add_argument("--backgrounds", default="")
    parser.add_argument("--exposures", default="")
    parser.add_argument("--parameter-tiers", default="")
    parser.add_argument("--quality-profiles", default="")
    parser.add_argument("--lighting", default="")
    parser.add_argument("--carrier", default="")
    parser.add_argument("--background-map", action="append", default=[], help="Map matrix background to harness asset/color, e.g. black=/Game/... or busy=D:/ref.png.")
    parser.add_argument("--exposure-map", action="append", default=[], help="Map exposure tier to a concrete numeric/profile value, e.g. low=-1.")
    parser.add_argument("--waive-backgrounds", action="store_true")
    parser.add_argument("--waive-exposures", action="store_true")
    parser.add_argument("--waive-parameter-tiers", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
