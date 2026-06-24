from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
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


def build_ue_script(payload: dict[str, Any]) -> str:
    payload_text = json.dumps(payload, ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import json
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary
        PAYLOAD = json.loads({payload_text!r})

        def guid_text(value):
            try:
                return value.to_string()
            except Exception:
                try:
                    return str(value)
                except Exception:
                    return ""

        def package_path(path):
            return str(path or "").split(".", 1)[0]

        def asset_ref(path):
            pkg = package_path(path)
            if not pkg:
                return ""
            return pkg + "." + pkg.rsplit("/", 1)[-1]

        def run_tool(name, payload):
            result = TR.execute_qualified_tool(name, json.dumps(payload, ensure_ascii=False), True)
            output = None
            if result.json_output:
                try:
                    output = json.loads(result.json_output)
                except Exception:
                    output = result.json_output
            return {{"success": bool(result.success), "error": result.error, "output": output}}

        def enum_value(enum_cls, names):
            for name in names:
                if hasattr(enum_cls, name):
                    return getattr(enum_cls, name)
            return None

        def domain_enum(value):
            key = str(value or "").replace(" ", "").lower()
            mapping = {{
                "surface": ["MD_SURFACE"],
                "deferreddecal": ["MD_DEFERRED_DECAL"],
                "postprocess": ["MD_POST_PROCESS"],
                "ui": ["MD_UI"],
                "lightfunction": ["MD_LIGHT_FUNCTION"],
                "volume": ["MD_VOLUME"],
                "runtimevirtualtexture": ["MD_RUNTIME_VIRTUAL_TEXTURE"],
                "virtualtexture": ["MD_VIRTUAL_TEXTURE"],
            }}
            return enum_value(unreal.MaterialDomain, mapping.get(key, [str(value or "")]))

        def blend_enum(value):
            key = str(value or "").replace(" ", "").replace("_", "").lower()
            mapping = {{
                "opaque": ["BLEND_OPAQUE"],
                "masked": ["BLEND_MASKED"],
                "translucent": ["BLEND_TRANSLUCENT"],
                "additive": ["BLEND_ADDITIVE"],
                "modulate": ["BLEND_MODULATE"],
                "alphacomposite": ["BLEND_ALPHA_COMPOSITE"],
                "alphaholdout": ["BLEND_ALPHA_HOLDOUT"],
            }}
            return enum_value(unreal.BlendMode, mapping.get(key, [str(value or "")]))

        def shading_enum(value):
            key = str(value or "").replace(" ", "").replace("_", "").lower()
            mapping = {{
                "defaultlit": ["MSM_DEFAULT_LIT"],
                "unlit": ["MSM_UNLIT"],
                "subsurface": ["MSM_SUBSURFACE"],
                "preintegratedskin": ["MSM_PREINTEGRATED_SKIN"],
                "clearcoat": ["MSM_CLEAR_COAT"],
                "subsurfaceprofile": ["MSM_SUBSURFACE_PROFILE"],
                "twosidedfoliage": ["MSM_TWOSIDED_FOLIAGE"],
                "hair": ["MSM_HAIR"],
                "cloth": ["MSM_CLOTH"],
                "eye": ["MSM_EYE"],
                "singlelayerwater": ["MSM_SINGLELAYERWATER"],
                "thintranslucent": ["MSM_THIN_TRANSLUCENT"],
            }}
            return enum_value(unreal.MaterialShadingModel, mapping.get(key, [str(value or "")]))

        def set_prop(material, prop, value, row):
            try:
                material.set_editor_property(prop, value)
                row["changes"].append({{"property": prop, "success": True, "value": str(value)}})
                return True
            except Exception as exc:
                row["changes"].append({{"property": prop, "success": False, "value": str(value), "error": str(exc)}})
                return False

        def graph_output(material_ref, property_name):
            graph = MAT.get_material_graph(material_ref)
            for output in list(graph.output_connections):
                if str(output.dst_property_name or "") == property_name:
                    return output
            return None

        def node_guid_by_text(material_ref, text):
            graph = MAT.get_material_graph(material_ref)
            needle = str(text or "")
            for node in list(graph.nodes):
                if guid_text(node.guid) == needle:
                    return node.guid
            return None

        def add_expr(material_ref, class_path, x, y, props=None):
            added = MAT.add_material_expression(material_ref, class_path, int(x), int(y))
            row = {{
                "class": class_path,
                "success": bool(added.success),
                "error": added.error,
                "guid": guid_text(getattr(added, "guid", "")),
            }}
            if added.success and props:
                prop_rows = []
                for name, value in props:
                    ok = MAT.set_material_expression_property(material_ref, added.guid, name, str(value))
                    prop_rows.append({{"name": name, "value": str(value), "success": bool(ok)}})
                row["properties"] = prop_rows
            return added, row

        def apply_usage_flags(material_ref, usage_flags):
            material = unreal.EditorAssetLibrary.load_asset(package_path(material_ref))
            rows = []
            if material is None:
                return [{{"success": False, "error": "candidate material could not be loaded"}}]
            setter = getattr(unreal.MaterialEditingLibrary, "set_base_material_usage", None)
            legacy_setter = getattr(unreal.MaterialEditingLibrary, "set_material_usage", None)
            usage_map = {{
                "niagarasprites": "MATUSAGE_NIAGARA_SPRITES",
                "niagararibbons": "MATUSAGE_NIAGARA_RIBBONS",
                "staticmesh": "MATUSAGE_STATIC_MESH",
                "particlesprites": "MATUSAGE_PARTICLE_SPRITES",
                "meshparticles": "MATUSAGE_MESH_PARTICLES",
                "niagarameshparticles": "MATUSAGE_NIAGARA_MESH_PARTICLES",
                "splinemesh": "MATUSAGE_SPLINE_MESH",
                "water": "MATUSAGE_WATER",
            }}
            for raw in usage_flags or []:
                compact = "".join(ch for ch in str(raw or "") if ch.isalnum()).lower()
                for prefix in ("busedwith", "usedwith", "matusage"):
                    if compact.startswith(prefix):
                        compact = compact[len(prefix):]
                        break
                enum_name = usage_map.get(compact)
                row = {{"requested": raw, "enum": enum_name, "success": False, "before": None, "after": None, "error": ""}}
                usage = getattr(unreal.MaterialUsage, enum_name, None) if enum_name else None
                if usage is None:
                    row["error"] = "unsupported usage flag"
                    rows.append(row)
                    continue
                try:
                    before = bool(unreal.MaterialEditingLibrary.has_material_usage(material, usage))
                    if not before:
                        if setter is not None:
                            setter(material, usage, True)
                        elif legacy_setter is not None:
                            legacy_setter(material, usage)
                        else:
                            raise RuntimeError("no safe usage setter")
                    after = bool(unreal.MaterialEditingLibrary.has_material_usage(material, usage))
                    row.update({{"success": after, "before": before, "after": after}})
                except Exception as exc:
                    row["error"] = str(exc)
                rows.append(row)
            return rows

        def apply_route_restore(material_ref, route):
            row = {{"operation": "restore_route_contract", "success": False, "changes": [], "usage_flags": []}}
            if not route:
                row["error"] = "missing route_restore payload"
                return row
            material = unreal.EditorAssetLibrary.load_asset(package_path(material_ref))
            if material is None:
                row["error"] = "candidate material could not be loaded"
                return row
            ok = True
            domain = domain_enum(route.get("domain"))
            if domain is not None:
                ok = set_prop(material, "material_domain", domain, row) and ok
            blend = blend_enum(route.get("blend_mode"))
            if blend is not None:
                ok = set_prop(material, "blend_mode", blend, row) and ok
            shading = shading_enum(route.get("shading_model"))
            if shading is not None:
                ok = set_prop(material, "shading_model", shading, row) and ok
            ok = set_prop(material, "two_sided", bool(route.get("two_sided")), row) and ok
            ok = set_prop(material, "use_material_attributes", bool(route.get("use_material_attributes")), row) and ok
            row["usage_flags"] = apply_usage_flags(material_ref, route.get("usage_flags") or [])
            try:
                material.post_edit_change()
                material.mark_package_dirty()
            except Exception:
                pass
            row["success"] = bool(ok and all(item.get("success") for item in row["usage_flags"] or [{{"success": True}}]))
            return row

        def apply_fresnel(material_ref):
            row = {{"operation": "add_fresnel_layer", "success": False, "nodes": [], "connections": []}}
            existing = graph_output(material_ref, "EmissiveColor")
            fresnel, fresnel_row = add_expr(material_ref, "/Script/Engine.MaterialExpressionFresnel", -520, -260)
            intensity, intensity_row = add_expr(
                material_ref,
                "/Script/Engine.MaterialExpressionScalarParameter",
                -520,
                -80,
                [("ParameterName", "S_RefactorFresnelIntensity"), ("DefaultValue", "0.0")],
            )
            color, color_row = add_expr(
                material_ref,
                "/Script/Engine.MaterialExpressionVectorParameter",
                -520,
                80,
                [("ParameterName", "V_RefactorFresnelColor"), ("DefaultValue", "(R=1.0,G=1.0,B=1.0,A=1.0)")],
            )
            mul_a, mul_a_row = add_expr(material_ref, "/Script/Engine.MaterialExpressionMultiply", -240, -170)
            mul_b, mul_b_row = add_expr(material_ref, "/Script/Engine.MaterialExpressionMultiply", 20, -130)
            add_node = None
            add_row = {{"class": "/Script/Engine.MaterialExpressionAdd", "success": True}}
            if existing is not None:
                add_node, add_row = add_expr(material_ref, "/Script/Engine.MaterialExpressionAdd", 270, -80)
            row["nodes"] = [fresnel_row, intensity_row, color_row, mul_a_row, mul_b_row, add_row]
            if not all(item.get("success") for item in row["nodes"]):
                row["error"] = "node creation failed"
                return row
            links = [
                ("fresnel_to_intensity", MAT.connect_material_expressions(material_ref, fresnel.guid, "", mul_a.guid, "A")),
                ("intensity_to_multiply", MAT.connect_material_expressions(material_ref, intensity.guid, "", mul_a.guid, "B")),
                ("scaled_to_color", MAT.connect_material_expressions(material_ref, mul_a.guid, "", mul_b.guid, "A")),
                ("color_to_rim", MAT.connect_material_expressions(material_ref, color.guid, "", mul_b.guid, "B")),
            ]
            if existing is not None and add_node is not None:
                MAT.disconnect_material_output(material_ref, "EmissiveColor")
                links.extend(
                    [
                        ("old_emissive_to_add", MAT.connect_material_expressions(material_ref, existing.src_guid, str(existing.src_output_name or ""), add_node.guid, "A")),
                        ("rim_to_add", MAT.connect_material_expressions(material_ref, mul_b.guid, "", add_node.guid, "B")),
                        ("add_to_emissive", MAT.connect_material_output(material_ref, add_node.guid, "", "EmissiveColor")),
                    ]
                )
            else:
                links.append(("rim_to_emissive", MAT.connect_material_output(material_ref, mul_b.guid, "", "EmissiveColor")))
            row["connections"] = [{{"name": name, "success": bool(ok)}} for name, ok in links]
            row["success"] = all(item["success"] for item in row["connections"])
            return row

        def apply_depth_fade(material_ref):
            row = {{"operation": "add_depth_fade", "success": False, "nodes": [], "connections": []}}
            existing = graph_output(material_ref, "Opacity")
            if existing is None:
                row["error"] = "Opacity output is not connected; DepthFade needs an opacity chain to soften."
                return row
            fade, fade_row = add_expr(material_ref, "/Script/Engine.MaterialExpressionDepthFade", -40, 280)
            distance, distance_row = add_expr(
                material_ref,
                "/Script/Engine.MaterialExpressionScalarParameter",
                -320,
                360,
                [("ParameterName", "S_RefactorDepthFadeDistance"), ("DefaultValue", "64.0")],
            )
            row["nodes"] = [fade_row, distance_row]
            if not all(item.get("success") for item in row["nodes"]):
                row["error"] = "node creation failed"
                return row
            MAT.disconnect_material_output(material_ref, "Opacity")
            links = [
                ("old_opacity_to_depthfade", MAT.connect_material_expressions(material_ref, existing.src_guid, str(existing.src_output_name or ""), fade.guid, "Opacity")),
                ("distance_to_depthfade", MAT.connect_material_expressions(material_ref, distance.guid, "", fade.guid, "FadeDistance")),
                ("depthfade_to_opacity", MAT.connect_material_output(material_ref, fade.guid, "", "Opacity")),
            ]
            row["connections"] = [{{"name": name, "success": bool(ok)}} for name, ok in links]
            row["success"] = all(item["success"] for item in row["connections"])
            return row

        def apply_output_repair(material_ref, before_outputs):
            row = {{"operation": "repair_output_chain", "success": False, "repairs": [], "blocked": []}}
            for output in before_outputs or []:
                prop = str(output.get("dst_property_name") or "")
                if not prop:
                    continue
                src_guid = node_guid_by_text(material_ref, output.get("src_guid"))
                if src_guid is None:
                    row["blocked"].append({{"property": prop, "reason": "before source guid is not present in candidate graph", "src_guid": output.get("src_guid")}})
                    continue
                MAT.disconnect_material_output(material_ref, prop)
                ok = MAT.connect_material_output(material_ref, src_guid, str(output.get("src_output_name") or ""), prop)
                row["repairs"].append({{"property": prop, "success": bool(ok), "src_guid": output.get("src_guid"), "src_output_name": output.get("src_output_name")}})
            row["success"] = bool(row["repairs"]) and all(item.get("success") for item in row["repairs"]) and not row["blocked"]
            if not row["repairs"] and not row["blocked"]:
                row["error"] = "no before output rows were provided"
            return row

        target_ref = asset_ref(PAYLOAD["target_material"])
        backup_ref = asset_ref(PAYLOAD["backup_path"])
        candidate_ref = asset_ref(PAYLOAD["candidate_path"])
        report = {{
            "tool": "graph_refactor_apply_ue",
            "target_material": PAYLOAD["target_material"],
            "backup_path": package_path(PAYLOAD["backup_path"]),
            "backup_ref": backup_ref,
            "candidate_path": package_path(PAYLOAD["candidate_path"]),
            "candidate_ref": candidate_ref,
            "duplicates": [],
            "operations": [],
            "compile": None,
            "save": None,
            "transaction": {{"name": "Codex graph refactor apply candidate", "used": False}},
        }}

        source_asset = unreal.EditorAssetLibrary.load_asset(package_path(PAYLOAD["target_material"]))
        if source_asset is None:
            raise RuntimeError("Could not load target material: " + str(PAYLOAD["target_material"]))

        for label, new_ref in (("backup", backup_ref), ("candidate", candidate_ref)):
            result = run_tool("toolset_registry.toolsets.core.asset.AssetTools.duplicate", {{"path": target_ref, "new_path": new_ref}})
            report["duplicates"].append({{"role": label, "target": new_ref, **result}})
            if not result["success"]:
                raise RuntimeError(f"Could not duplicate {{label}} material: {{result['error']}}")

        transaction = None
        try:
            transaction = unreal.ScopedEditorTransaction("Codex graph refactor apply candidate")
            report["transaction"]["used"] = True
        except Exception as exc:
            report["transaction"]["error"] = str(exc)

        def run_operations():
            for op in PAYLOAD.get("operations") or []:
                name = op.get("operation")
                if not op.get("executable"):
                    report["operations"].append({{"operation": name, "success": False, "skipped": True, "reason": op.get("blocked_reason") or "not executable"}})
                    continue
                if name == "restore_route_contract":
                    report["operations"].append(apply_route_restore(candidate_ref, PAYLOAD.get("route_restore") or {{}}))
                elif name == "repair_output_chain":
                    report["operations"].append(apply_output_repair(candidate_ref, PAYLOAD.get("before_output_connections") or []))
                elif name == "add_fresnel_layer":
                    report["operations"].append(apply_fresnel(candidate_ref))
                elif name == "add_depth_fade":
                    report["operations"].append(apply_depth_fade(candidate_ref))
                else:
                    report["operations"].append({{"operation": name, "success": False, "skipped": True, "reason": "unsupported operation"}})

        if transaction is not None:
            with transaction:
                run_operations()
        else:
            run_operations()

        compile_ok = MAT.compile_material(candidate_ref, False)
        report["compile"] = {{"success": bool(compile_ok)}}
        report["save"] = run_tool("toolset_registry.toolsets.core.asset.AssetTools.save_assets", {{"asset_paths": [backup_ref, candidate_ref]}})
        print(json.dumps(report, ensure_ascii=False))
        """
    ).strip()


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
        if args.endpoint:
            items.extend(["--endpoint", args.endpoint])
        items.extend(["--timeout", str(args.timeout)])
        return items

    before_audit = [sys.executable, str(tool_root / "material_audit.py"), target, "--include-raw-graph", "--markdown", *ue_args()]
    before_domain = [sys.executable, str(tool_root / "material_domain_audit.py"), target, "--markdown", *ue_args()]
    after_audit = [sys.executable, str(tool_root / "material_audit.py"), candidate, "--include-raw-graph", "--markdown", *ue_args()]
    after_domain = [sys.executable, str(tool_root / "material_domain_audit.py"), candidate, "--markdown", *ue_args()]
    preview = [
        sys.executable,
        str(tool_root / "material_preview.py"),
        "render",
        candidate,
        "--carrier",
        args.carrier,
        "--with-complexity",
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
        "execute": bool(args.execute),
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

    if not args.execute:
        report["validation_plan"] = validation_commands(args, ctx, resolved["target_material"], object_ref(resolved["candidate_path"]))
        report["gate"] = {"ready_for_acceptance": False, "reason": "dry_run_only"}
        return report, out

    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    before_commands = validation_commands(args, ctx, resolved["target_material"], object_ref(resolved["candidate_path"]))
    report["validation"]["before_audit"] = run_command(before_commands["before_audit"], ctx.project_root)  # type: ignore[arg-type]
    report["validation"]["before_domain_audit"] = run_command(before_commands["before_domain_audit"], ctx.project_root)  # type: ignore[arg-type]

    ue_report = client.exec_json(build_ue_script(payload), no_preflight=True)
    report["ue_apply"] = ue_report
    candidate_ref = ue_report.get("candidate_ref") or object_ref(resolved["candidate_path"])

    after_commands = validation_commands(args, ctx, resolved["target_material"], candidate_ref)
    report["validation"]["after_audit"] = run_command(after_commands["after_audit"], ctx.project_root)  # type: ignore[arg-type]
    report["validation"]["after_domain_audit"] = run_command(after_commands["after_domain_audit"], ctx.project_root)  # type: ignore[arg-type]
    report["validation"]["preview"] = run_command(after_commands["preview"], ctx.project_root)  # type: ignore[arg-type]
    preview_report = report["validation"]["preview"].get("report_path") or ""
    regression_commands = validation_commands(args, ctx, resolved["target_material"], candidate_ref, preview_report)
    regression_command = regression_commands.get("regression")
    if regression_command:
        report["validation"]["regression"] = run_command(regression_command, ctx.project_root)
    else:
        report["validation"]["regression"] = {
            "skipped": True,
            "reason": "No regression baseline was found. Create one with material_regression.py baseline or pass --baseline.",
        }
    report["gate"] = evaluate_gate(report)
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
    parser.add_argument("--execute", action="store_true", help="Actually duplicate/apply in UE. Without this, only writes a review plan.")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
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
