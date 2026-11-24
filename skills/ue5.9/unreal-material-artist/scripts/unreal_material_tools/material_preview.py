"""Preview Unreal materials through Epic's built-in MCP and record a ``material_preview`` report.

``capture`` saves the editor's material thumbnail or posed level-viewport frames of a
carrier already placed in the level (EditorAppToolset). With a ``material_audit
--include-raw-graph`` report it also scans the material against the carrier preset
contract (``assets/material-preview-presets.json``). The report feeds the acceptance
gate, regression baselines, readability score and delivery packager.

The UnrealBridge-era ``render`` / ``sweep`` harnesses (temporary Niagara systems,
decal walls, post-process volumes, shader-complexity views) were retired; place the
carrier with official SceneTools and capture it instead.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, load_json, resolve_root_context, save_json, slugify, write_text


def _norm(value: Any) -> str:
    return str(value or "").strip()


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def preview_presets_path() -> Path:
    return skill_root() / "assets" / "material-preview-presets.json"


def load_preview_presets() -> dict[str, Any]:
    path = preview_presets_path()
    if not path.exists():
        return {"defaults": {}, "presets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_preview_preset(carrier: str, preset_name: str | None) -> tuple[str | None, dict[str, Any]]:
    data = load_preview_presets()
    presets = data.get("presets") or {}
    defaults = data.get("defaults") or {}
    resolved_name = preset_name or defaults.get(carrier)
    if not resolved_name:
        return None, {}
    preset = presets.get(resolved_name)
    if not isinstance(preset, dict):
        return None, {}
    return str(resolved_name), preset


def build_preview_contract_scan(snapshot: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    info = snapshot["material_info"]
    graph = snapshot["graph"]
    nodes = graph.get("nodes") or []
    captions = " ".join(
        [
            str(node.get("class_name") or "")
            + " "
            + str(node.get("caption") or "")
            + " "
            + str(node.get("desc") or "")
            + " "
            + str(node.get("key_properties") or "")
            for node in nodes
        ]
    ).lower()
    param_names = {
        str(item.get("name") or "")
        for key in ("scalar_parameters", "vector_parameters", "texture_parameters", "static_switch_parameters")
        for item in info.get(key) or []
    }
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    required_flags = set(preset.get("usage_flags_required") or [])
    current_flags = set(info.get("usage_flags") or [])
    missing_flags = sorted(required_flags - current_flags)
    if missing_flags:
        add("warning", "usage_flags", f"Material is missing required usage flags: {', '.join(missing_flags)}")

    if "two_sided_expected" in preset:
        expected_two_sided = bool(preset.get("two_sided_expected"))
        current_two_sided = bool(info.get("two_sided"))
        if current_two_sided != expected_two_sided:
            add(
                "warning",
                "two_sided_contract",
                f"Preset expects Two Sided `{expected_two_sided}` but material reports `{current_two_sided}`.",
            )

    subuv_grid = preset.get("subuv_grid")
    if subuv_grid:
        if not any(token in captions for token in ("flipbook", "subuv", "sub-image", "subimage")):
            add("warning", "subuv_contract", f"Preset expects SubUV/flipbook usage ({subuv_grid}) but the graph has no obvious SubUV/flipbook evidence.")

    dynamic_params = preset.get("dynamic_parameters") or []
    if dynamic_params:
        has_particle_color = "particlecolor" in captions
        has_dynamic_parameter = "dynamicparameter" in captions
        if "ParticleColor" in dynamic_params and not has_particle_color:
            add("warning", "particle_color_contract", "Preset expects ParticleColor participation but no ParticleColor node was found.")
        if any(item in {"DynamicParameter", "RibbonWidth"} for item in dynamic_params) and not has_dynamic_parameter:
            add("warning", "dynamic_parameter_contract", "Preset expects DynamicParameter-style control but no DynamicParameter node was found.")

    ribbon_uv_mode = preset.get("ribbon_uv_mode")
    if ribbon_uv_mode:
        if not any(token in captions for token in ("panner", "texcoord", "texturecoordinate", "uv")):
            add("info", "ribbon_uv_contract", "Ribbon preset declares a UV contract, but the graph evidence does not strongly show how ribbon UVs are shaped.")

    return {
        "preset_contract": preset,
        "usage_flags": sorted(current_flags),
        "parameter_names": sorted(param_names),
        "findings": findings,
    }


def build_post_process_gate(snapshot: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    info = snapshot["material_info"]
    graph = snapshot["graph"]
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    domain = str(info.get("material_domain") or "")
    if domain != "PostProcess":
        add("error", "post_process_domain", f"Material domain is `{domain or 'Unknown'}`, but post_process preview requires `PostProcess`.")

    output_names = {
        _norm(connection.get("dst_property_name"))
        for connection in graph.get("output_connections") or []
        if _norm(connection.get("dst_property_name"))
    }
    if output_names and "EmissiveColor" not in output_names:
        add("warning", "post_process_output", f"Post-process preview expects `EmissiveColor` output, but current outputs are `{sorted(output_names)}`.")

    return {
        "domain": domain,
        "output_names": sorted(output_names),
        "findings": findings,
        "blocked": any(item["severity"] == "error" for item in findings),
    }


def build_decal_gate(snapshot: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    info = snapshot["material_info"]
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    domain = str(info.get("material_domain") or "")
    if domain != "DeferredDecal":
        add("error", "decal_domain", f"Material domain is `{domain or 'Unknown'}`, but decal preview requires `DeferredDecal`.")

    usage_flags = set(info.get("usage_flags") or [])
    required_flags = set(preset.get("usage_flags_required") or [])
    missing_flags = sorted(required_flags - usage_flags)
    if missing_flags:
        add("warning", "usage_flags", f"Material is missing required usage flags: {', '.join(missing_flags)}")

    return {
        "domain": domain,
        "findings": findings,
        "blocked": any(item["severity"] == "error" for item in findings),
    }


CAPTURE_SCHEMA_VERSION = "material_preview/2"


def build_capture_report(material_path: str, route: str, carrier: str, capture: dict[str, Any],
                         contract_scan: dict[str, Any] | None = None) -> dict[str, Any]:
    """A material_preview report from an Epic MCP capture, in the shape the gate, regression and packager read."""
    frames = capture.get("frames") or []
    return {
        "tool": "material_preview",
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "mode": "capture",
        "material_path": material_path,
        "transport": capture.get("transport", ""),
        "options": {
            "carrier": carrier if route == "viewport" else "thumbnail",
            "preview_route": f"epic-mcp {route}",
            "pose": capture.get("pose"),
        },
        "outputs": {
            "shaded_png": frames[0]["path"] if frames else "",
            "shaded_ok": bool(capture.get("ok")),
            "frame_pngs": [frame["path"] for frame in frames],
            "complexity_png": "",
            "complexity_ok": None,  # Shader complexity view is not exposed by MCP; not a failure.
        },
        "capture": capture,
        "contract_scan": contract_scan or {},
    }


def command_capture(args: argparse.Namespace) -> int:
    from .mcp import capture_report, connect, parse_pose

    ctx = resolve_root_context(args.root)
    contract_scan: dict[str, Any] = {}
    if args.audit_report:
        audit_report = load_json(Path(args.audit_report), {})
        if "raw_graph" not in audit_report:
            raise SystemExit(f"{args.audit_report} has no raw_graph; re-run material_audit.py with --include-raw-graph.")
        _, preset = resolve_preview_preset(args.carrier, args.preset)
        snapshot = {"material_info": audit_report["material_info"], "graph": audit_report["raw_graph"],
                    "analysis": audit_report["analysis"]}
        contract_scan = build_preview_contract_scan(snapshot, preset)
        if args.carrier == "decal":
            contract_scan["decal_gate"] = build_decal_gate(snapshot, preset)
        if args.carrier == "post_process":
            contract_scan["post_process_gate"] = build_post_process_gate(snapshot, preset)
    effect = slugify(args.effect or args.material_path)
    stem = f"{slugify(args.material_path)}-preview"
    out_dir = default_report_path(ctx, "previews", effect, stem, "").parent
    client = connect(ctx.skill_root, timeout=args.timeout, project=args.project)
    try:
        capture = capture_report(client, "asset" if args.route == "thumbnail" else "viewport", out_dir,
                                 f"{stem}-{args.route}", asset_path=args.material_path,
                                 pose=parse_pose(args.pose) if args.pose else None,
                                 frames=args.frames, interval=args.interval)
    finally:
        client.close()
    report = build_capture_report(args.material_path, args.route, args.carrier, capture, contract_scan)
    report_path = Path(args.out) if args.out else out_dir / f"{stem}.json"
    save_json(report_path, report)
    if args.markdown:
        lines = [f"# Material Preview: {args.material_path}", "",
                 f"- Route: `{report['options']['preview_route']}` carrier `{report['options']['carrier']}`",
                 f"- Shaded ok: `{report['outputs']['shaded_ok']}`" + (f" ({capture['error']})" if capture.get("error") else ""),
                 *[f"- Frame: `{path}`" for path in report["outputs"]["frame_pngs"]]]
        write_text(report_path.with_suffix(".md"), "\n".join(lines) + "\n")
    print(report_path)
    return 0 if capture.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture material previews through Epic's built-in MCP.")
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser(
        "capture",
        help="Capture a preview through Epic MCP (thumbnail, or a posed viewport frame of a placed carrier).",
    )
    capture.add_argument("material_path")
    capture.add_argument("--route", choices=["thumbnail", "viewport"], default="thumbnail",
                         help="thumbnail: the editor's material sphere; viewport: frames of a carrier already in the level")
    capture.add_argument("--carrier", default="mesh",
                         choices=["mesh", "sprite", "ribbon", "sprite_card", "ribbon_card", "decal", "post_process"],
                         help="Carrier shown in the viewport capture (recorded; the tool does not spawn it)")
    capture.add_argument("--pose", help="Viewport camera pose x,y,z,pitch,yaw,roll; default: the current viewport camera")
    capture.add_argument("--frames", type=int, default=1, help="Viewport only: time-separated frames for motion review")
    capture.add_argument("--interval", type=float, default=0.5)
    capture.add_argument("--audit-report", help="material_audit.py --include-raw-graph report for the carrier contract scan")
    capture.add_argument("--preset")
    capture.add_argument("--effect")
    capture.add_argument("--root", default="auto")
    capture.add_argument("--project")
    capture.add_argument("--timeout", type=int, default=60)
    capture.add_argument("--out")
    capture.add_argument("--markdown", action="store_true")
    capture.set_defaults(func=command_capture)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
