from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .niagara_audit import build_ue_script as build_niagara_audit_script
from .niagara_audit import summarize as summarize_niagara_audit


RENDERER_PROPS = [
    "Material",
    "SubImageSize",
    "SubImageBlend",
    "SubImageIndexBinding",
    "ColorBinding",
    "DynamicMaterialBinding",
    "DynamicMaterial1Binding",
    "DynamicMaterial2Binding",
    "DynamicMaterial3Binding",
    "MaterialParameterBindings",
    "RibbonWidthBinding",
    "SortMode",
    "CustomSortingBinding",
    "RendererVisibilityTagBinding",
]


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise SystemExit(f"JSON file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def object_path(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"/(?:Game|Engine)/[^'\",)\s]+", text)
    if match:
        text = match.group(0)
    if text.startswith("/Game") or text.startswith("/Engine"):
        return text.split(".", 1)[0]
    return text


def split_csv(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        rows: list[str] = []
        for item in value:
            rows.extend(split_csv(item))
        return rows
    return [item.strip() for item in value.split(",") if item.strip()]


def text_has_any(blob: str, tokens: list[str]) -> bool:
    lowered = blob.lower()
    return any(token.lower() in lowered for token in tokens if token)


def build_renderer_props_script(renderer_paths: list[str]) -> str:
    paths = [path for path in renderer_paths if path]
    return textwrap.dedent(
        f"""
        import json
        import unreal

        PROP = unreal.UnrealBridgePropertyLibrary
        RENDERER_PATHS = {paths!r}
        PROP_NAMES = {RENDERER_PROPS!r}

        def read_export(path, prop_name):
            try:
                text, ok = PROP.get_u_property_as_export_text(path, prop_name)
                return {{"success": bool(ok), "text": text}}
            except Exception as exc:
                return {{"success": False, "text": "", "error": str(exc)}}

        rows = []
        for renderer_path in RENDERER_PATHS:
            rows.append({{
                "renderer_path": renderer_path,
                "properties": {{name: read_export(renderer_path, name) for name in PROP_NAMES}},
            }})
        print(json.dumps({{"renderer_properties": rows}}, ensure_ascii=False))
        """
    ).strip()


def audit_renderer_paths(audit: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for emitter in audit.get("emitters") or []:
        parsed = emitter.get("parsed") or {}
        for key in ("renderer_objects", "versioned_renderer_objects"):
            for renderer in parsed.get(key) or emitter.get(key) or []:
                if isinstance(renderer, dict):
                    path = str(renderer.get("object_path") or "")
                    if path:
                        paths.append(path)
    return sorted(dict.fromkeys(paths))


def collect_renderer_evidence(audit: dict[str, Any], live_props: dict[str, Any]) -> list[dict[str, Any]]:
    prop_by_path = {
        str(item.get("renderer_path") or ""): item.get("properties") or {}
        for item in live_props.get("renderer_properties") or []
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for emitter in audit.get("emitters") or []:
        parsed = emitter.get("parsed") or {}
        classes = [str(item) for item in parsed.get("renderer_classes") or []]
        materials = [object_path(item) for item in parsed.get("renderer_materials") or [] if object_path(item)]
        renderer_objects = []
        for key in ("renderer_objects", "versioned_renderer_objects"):
            renderer_objects.extend(parsed.get(key) or emitter.get(key) or [])
        if not renderer_objects and (classes or materials):
            rows.append(
                {
                    "emitter": emitter.get("name") or "",
                    "renderer_path": "",
                    "classes": classes,
                    "materials": materials,
                    "properties": {},
                    "text_blob": " ".join(classes + materials),
                }
            )
            continue
        for renderer in renderer_objects:
            if not isinstance(renderer, dict):
                continue
            renderer_path = str(renderer.get("object_path") or "")
            class_name = str(renderer.get("class_name") or renderer.get("class_path") or "")
            material_path = object_path(renderer.get("material_path") or "")
            props = prop_by_path.get(renderer_path, {})
            prop_text = " ".join(str((value or {}).get("text") or "") for value in props.values() if isinstance(value, dict))
            material_from_prop = object_path((props.get("Material") or {}).get("text") if isinstance(props.get("Material"), dict) else "")
            rows.append(
                {
                    "emitter": emitter.get("name") or "",
                    "renderer_path": renderer_path,
                    "classes": sorted(dict.fromkeys([*classes, class_name])),
                    "materials": sorted(dict.fromkeys([item for item in [*materials, material_path, material_from_prop] if item])),
                    "properties": props,
                    "text_blob": " ".join([class_name, material_path, material_from_prop, prop_text]),
                }
            )
    return rows


def collect_system_blob(audit: dict[str, Any], renderer_rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for prop in (audit.get("system_properties") or {}).values():
        if isinstance(prop, dict):
            parts.append(str(prop.get("text") or ""))
    for emitter in audit.get("emitters") or []:
        parsed = emitter.get("parsed") or {}
        parts.extend(str(item) for item in parsed.get("function_names") or [])
        parts.extend(str(item) for item in parsed.get("data_interface_classes") or [])
        for binding in parsed.get("data_interface_bindings") or []:
            if isinstance(binding, dict):
                parts.extend(str(value) for value in binding.values())
        for prop in (emitter.get("properties") or {}).values():
            if isinstance(prop, dict):
                parts.append(str(prop.get("text") or ""))
    for row in renderer_rows:
        parts.append(str(row.get("text_blob") or ""))
    return "\n".join(parts)


def texture_grid_from_payload(payload: dict[str, Any]) -> str:
    for item in payload.get("texture_requirements") or payload.get("textures") or []:
        if not isinstance(item, dict):
            continue
        role_blob = " ".join(str(item.get(key) or "") for key in ("role", "name", "description", "usage")).lower()
        grid = str(item.get("grid") or item.get("subuv_grid") or "").strip()
        if grid and any(token in role_blob for token in ("flipbook", "subuv", "atlas")):
            return grid
    return ""


def derive_expectations(args: argparse.Namespace, contract: dict[str, Any], package: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    contract_carrier = contract.get("carrier") or {}
    contract_material = contract.get("material") or {}
    package_route = package.get("route") or {}
    preview_options = preview.get("options") or {}
    preview_outputs = preview.get("outputs") or {}
    material_path = (
        args.material_path
        or package.get("material_path")
        or preview.get("material_path")
        or preview.get("material_instance_path")
        or ""
    )
    carrier = (
        args.carrier
        or contract_carrier.get("renderer")
        or package_route.get("carrier")
        or preview_options.get("carrier")
        or ""
    )
    particle_inputs = sorted(dict.fromkeys([*contract_carrier.get("particle_inputs", []), *split_csv(args.particle_input)]))
    dynamic_parameters = sorted(dict.fromkeys([*contract_carrier.get("dynamic_parameters", []), *split_csv(args.dynamic_parameter)]))
    subuv_grid = args.subuv_grid or texture_grid_from_payload(package) or texture_grid_from_payload(contract) or str(preview_outputs.get("renderer_subuv_grid") or "")
    uv_text = " ".join(
        str(value or "")
        for value in (
            contract_carrier.get("uv_expectations"),
            package_route.get("uv_expectations"),
            preview_options.get("preview_route"),
            subuv_grid,
        )
    ).lower()
    blend_mode = str(contract_material.get("blend_mode") or package_route.get("blend_mode") or "").lower()
    sort_notes = str(contract_carrier.get("sort_or_depth_notes") or "").strip()
    return {
        "material_path": object_path(material_path),
        "carrier": str(carrier or "").lower(),
        "particle_inputs": particle_inputs,
        "dynamic_parameters": dynamic_parameters,
        "subuv_grid": subuv_grid,
        "expects_subuv": bool(args.require_subimage_index or subuv_grid or "subuv" in uv_text or "flipbook" in uv_text),
        "expects_particle_color": bool(args.require_particle_color or any("particlecolor" == item.replace(" ", "").lower() for item in particle_inputs)),
        "expects_dynamic_parameter": bool(args.require_dynamic_parameter or dynamic_parameters or any("dynamic" in item.lower() for item in particle_inputs)),
        "expects_ribbon_width": bool(args.require_ribbon_width or str(carrier or "").lower() == "ribbon"),
        "expects_sorting": bool(args.require_sorting or sort_notes or blend_mode in {"additive", "translucent", "alpha composite", "alphacomposite"}),
        "expects_bounds": not args.no_require_bounds,
        "source_files": {
            "material_contract": str(args.material_contract or ""),
            "material_delivery_package": str(args.material_delivery_package or ""),
            "preview_report": str(args.preview_report or ""),
        },
    }


def renderer_classes_match(renderer_rows: list[dict[str, Any]], carrier: str) -> bool:
    token = {
        "sprite": "sprite",
        "ribbon": "ribbon",
        "mesh": "mesh",
    }.get(carrier)
    if not token:
        return True
    return any(token in " ".join(row.get("classes") or []).lower() for row in renderer_rows)


def material_binding_match(renderer_rows: list[dict[str, Any]], material_path: str) -> bool:
    expected = object_path(material_path)
    if not expected:
        return True
    for row in renderer_rows:
        for material in row.get("materials") or []:
            if object_path(material) == expected:
                return True
        if expected in str(row.get("text_blob") or ""):
            return True
    return False


def grid_matches(blob: str, grid: str) -> bool:
    if not grid:
        return True
    parts = re.findall(r"\d+", grid)
    if len(parts) < 2:
        return grid.lower() in blob.lower()
    x, y = parts[0], parts[1]
    lowered = blob.lower()
    patterns = [
        f"x={x}",
        f"y={y}",
        f"subimagesize=({x},{y})",
        f"{x}x{y}",
    ]
    return (patterns[0] in lowered and patterns[1] in lowered) or any(item in lowered for item in patterns[2:])


def renderer_sorting_evidence_present(renderer_rows: list[dict[str, Any]]) -> bool:
    for row in renderer_rows:
        properties = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        sort_mode = properties.get("SortMode")
        if isinstance(sort_mode, dict) and sort_mode.get("success"):
            return True
        custom_sorting = properties.get("CustomSortingBinding")
        if isinstance(custom_sorting, dict) and custom_sorting.get("success") and str(custom_sorting.get("text") or "").strip():
            return True
    return False


def build_findings(expectations: dict[str, Any], audit: dict[str, Any], renderer_rows: list[dict[str, Any]], strict_unknown: bool = False) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    blob = collect_system_blob(audit, renderer_rows)

    def add(severity: str, rule: str, message: str, evidence: str = "") -> None:
        findings.append({"severity": severity, "rule": rule, "message": message, "evidence": evidence})

    carrier = expectations.get("carrier") or ""
    material_path = expectations.get("material_path") or ""
    if not audit.get("system_path"):
        add("error", "missing_system_audit", "No Niagara system audit evidence is available.")
    else:
        add("ok", "system_audit", "Real Niagara system audit evidence is present.", str(audit.get("system_path")))

    if carrier in {"sprite", "ribbon", "mesh"}:
        if renderer_classes_match(renderer_rows, carrier):
            add("ok", "renderer_class", f"Live renderer includes the expected `{carrier}` carrier.")
        else:
            add("error", "renderer_class", f"Live renderer does not include expected `{carrier}` renderer.", ", ".join(str(row.get("classes")) for row in renderer_rows))

    if material_path:
        if material_binding_match(renderer_rows, material_path):
            add("ok", "material_binding", "Expected material is bound on the live Niagara renderer.", material_path)
        else:
            add("error", "material_binding", "Expected material is not bound on the live Niagara renderer.", material_path)
    else:
        add("warning", "material_binding_unknown", "No expected material path was provided by contract/package/preview.")

    if expectations.get("expects_subuv"):
        if text_has_any(blob, ["SubImageSize", "SubImageIndex", "SubUV"]):
            if expectations.get("subuv_grid") and not grid_matches(blob, str(expectations.get("subuv_grid"))):
                add("warning", "subuv_grid", f"SubUV evidence exists but does not clearly match expected grid `{expectations.get('subuv_grid')}`.")
            else:
                add("ok", "subuv", "Live renderer/system exposes SubUV/SubImage evidence.", str(expectations.get("subuv_grid") or ""))
        else:
            add("error" if strict_unknown else "warning", "subuv_missing", "Material expects SubUV/flipbook, but live Niagara did not expose SubImageSize/SubImageIndex evidence.")

    if expectations.get("expects_particle_color"):
        if text_has_any(blob, ["ColorBinding", "ParticleColor", "Particles.Color", "Initial.Color", "Scale Color"]):
            add("ok", "particle_color", "ParticleColor / ColorBinding evidence exists in the live Niagara route.")
        else:
            add("error" if strict_unknown else "warning", "particle_color_missing", "Material expects ParticleColor, but live Niagara did not expose ColorBinding/Particles.Color evidence.")

    if expectations.get("expects_dynamic_parameter"):
        if text_has_any(blob, ["DynamicMaterial", "Dynamic Parameter", "DynamicParameter", "MaterialParameterBindings"]):
            add("ok", "dynamic_parameter", "Dynamic material parameter evidence exists in the live Niagara route.")
        else:
            add("error" if strict_unknown else "warning", "dynamic_parameter_missing", "Material expects DynamicParameter/material parameter input, but live Niagara did not expose binding evidence.")

    if expectations.get("expects_ribbon_width"):
        if text_has_any(blob, ["RibbonWidthBinding", "RibbonWidth", "Particles.RibbonWidth"]):
            add("ok", "ribbon_width", "RibbonWidth binding evidence exists.")
        else:
            add("error" if strict_unknown else "warning", "ribbon_width_missing", "Ribbon material/route expects ribbon width, but live Niagara did not expose RibbonWidth evidence.")

    if expectations.get("expects_sorting"):
        if text_has_any(blob, ["SortMode", "CustomSortingBinding", "SortKey", "SortOrder"]) or renderer_sorting_evidence_present(renderer_rows):
            add("ok", "sorting", "Sorting/custom sort evidence exists for the translucent/additive route.")
        else:
            add("warning", "sorting_unproven", "Sort/depth risk exists, but live Niagara did not expose sorting evidence.")

    fixed_bounds = str(((audit.get("system_properties") or {}).get("FixedBounds") or {}).get("text") or "")
    if expectations.get("expects_bounds"):
        if fixed_bounds.strip():
            add("ok", "bounds", "System FixedBounds evidence exists.", fixed_bounds)
        else:
            add("error", "bounds_missing", "No system FixedBounds evidence found for the real Niagara system.")

    add("info", "ownership_boundary", "Material preview evidence is useful material-side evidence, but this probe owns the real Niagara system integration check.")
    return findings


def counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    result = {"errors": 0, "warnings": 0, "info": 0, "ok": 0}
    for item in findings:
        severity = str(item.get("severity") or "info").lower()
        if severity == "error":
            result["errors"] += 1
        elif severity == "warning":
            result["warnings"] += 1
        elif severity == "ok":
            result["ok"] += 1
        else:
            result["info"] += 1
    return result


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    contract = load_json(Path(args.material_contract) if args.material_contract else None)
    package = load_json(Path(args.material_delivery_package) if args.material_delivery_package else None)
    preview = load_json(Path(args.preview_report) if args.preview_report else None)
    audit = load_json(Path(args.niagara_audit) if args.niagara_audit else None)
    live_props: dict[str, Any] = {}
    generated_audit_path = ""

    if args.system_path and not audit:
        client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
        client.ping()
        raw_audit = client.exec_json(build_niagara_audit_script(args.system_path), no_preflight=True)
        audit = summarize_niagara_audit(raw_audit)
        audit_path = default_report_path(ctx, "audits/niagara", slugify(args.system_path), "niagara-audit", ".json")
        save_json(audit_path, audit)
        generated_audit_path = str(audit_path)

    should_fetch_renderer_props = bool(
        args.system_path
        and audit_renderer_paths(audit)
        and (not args.niagara_audit or args.project or args.endpoint)
    )
    if should_fetch_renderer_props:
        client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
        client.ping()
        live_props = client.exec_json(build_renderer_props_script(audit_renderer_paths(audit)), no_preflight=True)

    expectations = derive_expectations(args, contract, package, preview)
    renderer_rows = collect_renderer_evidence(audit, live_props)
    findings = build_findings(expectations, audit, renderer_rows, strict_unknown=args.strict_unknown)
    summary = counts(findings)
    gate = {
        "integration_ready": summary["errors"] == 0 and (summary["warnings"] == 0 or not args.fail_on_warning),
        "requires_triage": bool(summary["errors"] or summary["warnings"]),
        "real_system_checked": bool(audit.get("system_path")),
        "material_preview_is_system_proof": False,
    }
    effect = args.effect or contract.get("effect") or package.get("effect") or "NiagaraMaterialIntegration"
    out = Path(args.out) if args.out else default_report_path(ctx, "material-integration-probe", slugify(effect), "niagara-material-integration-probe", ".json")
    report = {
        "tool": "niagara_material_integration_probe",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "system_path": args.system_path or audit.get("system_path") or "",
        "inputs": {
            "niagara_audit": args.niagara_audit or generated_audit_path,
            **expectations.get("source_files", {}),
        },
        "expectations": expectations,
        "renderer_evidence": renderer_rows,
        "findings": findings,
        "summary": summary,
        "gate": gate,
        "next_actions": next_actions(findings),
    }
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    rules = {str(item.get("rule") or "") for item in findings if item.get("severity") in {"error", "warning"}}
    if "material_binding" in rules:
        actions.append("Patch or rebuild the Niagara renderer material binding to the material approved by the material delivery package.")
    if "subuv_missing" in rules or "subuv_grid" in rules:
        actions.append("Verify Sprite Renderer SubImageSize/SubImageIndex binding against the flipbook grid and playback plan.")
    if "particle_color_missing" in rules:
        actions.append("Add or verify Niagara Color/ParticleColor writes before relying on material-side tint controls.")
    if "dynamic_parameter_missing" in rules:
        actions.append("Add or verify Dynamic Material Parameter bindings for the parameters declared in the material contract.")
    if "ribbon_width_missing" in rules:
        actions.append("Add or verify RibbonWidth writes on the ribbon emitter before tuning material opacity/edge response.")
    if "sorting_unproven" in rules:
        actions.append("Record renderer sorting mode or custom sort binding for translucent/additive routes.")
    if "bounds_missing" in rules:
        actions.append("Set and audit FixedBounds before final delivery or platform scalability review.")
    if not actions:
        actions.append("No Niagara/material integration blockers were detected by this probe.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    expectations = report.get("expectations") or {}
    lines = [
        f"# Niagara Material Integration Probe: {report.get('effect')}",
        "",
        f"- System: `{report.get('system_path') or 'unset'}`",
        f"- Expected material: `{expectations.get('material_path') or 'unset'}`",
        f"- Carrier: `{expectations.get('carrier') or 'unset'}`",
        f"- Integration ready: `{gate.get('integration_ready')}`",
        f"- Requires triage: `{gate.get('requires_triage')}`",
        f"- Errors: `{summary.get('errors', 0)}` warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Findings",
        "",
    ]
    for item in report.get("findings") or []:
        lines.append(f"- [{item.get('severity')}] `{item.get('rule')}` {item.get('message')} {item.get('evidence') or ''}".rstrip())
    lines.extend(["", "## Renderer Evidence", ""])
    for row in report.get("renderer_evidence") or []:
        lines.append(
            f"- emitter=`{row.get('emitter')}` renderer=`{row.get('renderer_path') or 'audit-only'}` "
            f"classes=`{', '.join(row.get('classes') or []) or 'none'}` materials=`{', '.join(row.get('materials') or []) or 'none'}`"
        )
    lines.extend(["", "## Next Actions", ""])
    for action in report.get("next_actions") or []:
        lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 1 if args.strict and not (report.get("gate") or {}).get("integration_ready") else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe real Niagara system material integration against material-side contract/delivery evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--system-path", default="", help="Live Niagara System path. When no --niagara-audit is supplied, the tool runs niagara_audit.py first.")
    parser.add_argument("--niagara-audit", default="", help="Existing niagara_audit.py JSON report.")
    parser.add_argument("--material-contract", default="", help="material_contract.py JSON from unreal-material-artist.")
    parser.add_argument("--material-delivery-package", default="", help="delivery_packager.py JSON from unreal-material-artist.")
    parser.add_argument("--preview-report", default="", help="material_preview.py JSON evidence. This is never treated as real-system proof.")
    parser.add_argument("--material-path", default="", help="Expected material or MI asset path override.")
    parser.add_argument("--carrier", default="", choices=("", "sprite", "ribbon", "mesh", "decal", "surface", "unknown"))
    parser.add_argument("--subuv-grid", default="", help="Expected SubUV grid such as 8x8.")
    parser.add_argument("--particle-input", action="append", default=[], help="Expected material particle input, e.g. ParticleColor or DynamicParameter.")
    parser.add_argument("--dynamic-parameter", action="append", default=[], help="Expected DynamicParameter/material parameter binding.")
    parser.add_argument("--require-particle-color", action="store_true")
    parser.add_argument("--require-dynamic-parameter", action="store_true")
    parser.add_argument("--require-subimage-index", action="store_true")
    parser.add_argument("--require-ribbon-width", action="store_true")
    parser.add_argument("--require-sorting", action="store_true")
    parser.add_argument("--no-require-bounds", action="store_true")
    parser.add_argument("--strict-unknown", action="store_true", help="Treat missing binding evidence for expected inputs as errors instead of warnings.")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.system_path or args.niagara_audit):
        parser.error("Provide --system-path or --niagara-audit.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
