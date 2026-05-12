from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .material_audit import build_ue_script as build_material_audit_script
from .niagara_contract_audit import build_ue_script as build_niagara_contract_script, summarize as summarize_niagara_contract


VFX_CARRIERS = {"sprite", "ribbon", "sprite_card", "ribbon_card", "decal", "post_process"}


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


def audit_material_snapshot(
    client: BridgeClient,
    material_path: str,
) -> dict[str, Any]:
    raw = client.exec_json(build_material_audit_script(material_path, 0, 0))
    return {
        "material_info": raw["material_info"],
        "graph": raw["graph"],
        "analysis": raw["analysis"],
    }


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


def build_renderer_contract_scan(raw_preview: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    contract = preset.get("renderer_contract") or {}
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if raw_preview.get("preview_route") != "niagara":
        return {"renderer_contract": contract, "findings": findings, "mode": "not_applicable"}

    expected_classes = [item.lower() for item in contract.get("renderer_class_contains") or []]
    actual_class = str(raw_preview.get("renderer_class") or "").lower()
    if expected_classes and not any(token in actual_class for token in expected_classes):
        add("warning", "renderer_class", f"Preset expects renderer class tokens {expected_classes}, but preview used `{raw_preview.get('renderer_class')}`.")

    if contract.get("material_binding_required"):
        bound = str(raw_preview.get("renderer_material_path") or "")
        if not bound:
            add("warning", "renderer_material_binding", "Preview route did not report a bound renderer material path.")
        elif str(raw_preview.get("material_path") or "") not in bound:
            add("warning", "renderer_material_binding", f"Renderer material path `{bound}` does not match preview material `{raw_preview.get('material_path')}`.")

    if contract.get("subuv_required"):
        expected = str(preset.get("subuv_grid") or "")
        actual = str(raw_preview.get("renderer_subuv_grid") or "")
        if not actual:
            add("warning", "renderer_subuv", "Preset expects SubUV but preview route did not report renderer sub-image size.")
        elif expected and actual != expected:
            add("warning", "renderer_subuv", f"Preview renderer SubUV grid `{actual}` does not match preset `{expected}`.")

    return {
        "renderer_contract": contract,
        "findings": findings,
        "mode": "niagara_preview_route",
        "actual_renderer_class": raw_preview.get("renderer_class"),
        "actual_renderer_material_path": raw_preview.get("renderer_material_path"),
        "actual_renderer_subuv_grid": raw_preview.get("renderer_subuv_grid"),
    }


def build_real_system_contract_scan(real_system_report: dict[str, Any], preset: dict[str, Any], material_path: str) -> dict[str, Any]:
    contract = preset.get("system_contract") or {}
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not contract.get("verify_real_system"):
        return {"system_contract": contract, "findings": findings, "mode": "disabled"}

    emitters = real_system_report.get("emitters") or []
    if not emitters:
        add("warning", "system_missing", "Real Niagara system report returned no emitters.")
        return {"system_contract": contract, "findings": findings, "mode": "empty"}

    hint = str(contract.get("expected_emitter_name_hint") or "").lower()
    matching = []
    for emitter in emitters:
        name_blob = str(emitter.get("name") or "").lower()
        if hint and hint not in name_blob:
            continue
        matching.append(emitter)
    if not matching:
        matching = emitters

    expected_renderer = [item.lower() for item in contract.get("expected_renderer_classes") or []]
    expected_functions = [item.lower() for item in contract.get("expected_functions_any") or []]
    expected_dis = [item.lower() for item in contract.get("expected_data_interfaces_any") or []]
    expected_bindings = [item.lower() for item in contract.get("expected_dynamic_bindings_any") or []]
    expected_renderer_bindings = [item.lower() for item in contract.get("expected_renderer_bindings_any") or []]
    expected_renderer_binding_text = [item.lower() for item in contract.get("expected_renderer_binding_text_any") or []]
    semantic_contract = preset.get("semantic_bindings") or {}

    renderer_hits = []
    material_hits = []
    function_hits = []
    di_hits = []
    binding_hints = []
    renderer_binding_hits = []
    semantic_binding_hits: dict[str, list[dict[str, Any]]] = {}
    semantic_binding_sections: dict[str, list[dict[str, Any]]] = {}
    semantic_checks = {
        "particle_color": {"status": "unknown", "details": []},
        "dynamic_parameter": {"status": "unknown", "details": []},
        "sub_image_index": {"status": "unknown", "details": []},
        "ribbon_width": {"status": "unknown", "details": []},
    }

    for emitter in matching:
        renderer_classes = [str(item).lower() for item in emitter.get("renderer_classes") or []]
        renderer_materials = [str(item) for item in emitter.get("renderer_materials") or []]
        function_names = [str(item).lower() for item in emitter.get("function_names") or []]
        data_interfaces = [str(item).lower() for item in emitter.get("data_interface_classes") or []]
        input_titles = [str(item).lower() for item in emitter.get("input_titles") or []]
        input_signatures = [str(item).lower() for item in emitter.get("input_signatures") or []]

        renderer_hits.append(
            {
                "emitter": emitter.get("name"),
                "matches": any(token in " ".join(renderer_classes) for token in expected_renderer) if expected_renderer else True,
                "renderer_classes": emitter.get("renderer_classes") or [],
            }
        )
        material_hits.append(
            {
                "emitter": emitter.get("name"),
                "matches": any(material_path in item for item in renderer_materials),
                "renderer_materials": renderer_materials,
            }
        )
        function_hits.append(
            {
                "emitter": emitter.get("name"),
                "matches": any(any(token in fn for fn in function_names) for token in expected_functions) if expected_functions else True,
                "function_names": emitter.get("function_names") or [],
            }
        )
        di_hits.append(
            {
                "emitter": emitter.get("name"),
                "matches": any(any(token in di for di in data_interfaces) for token in expected_dis) if expected_dis else True,
                "data_interface_classes": emitter.get("data_interface_classes") or [],
            }
        )
        binding_hints.append(
            {
                "emitter": emitter.get("name"),
                "matches": any(token in " ".join(function_names + data_interfaces + input_titles + input_signatures) for token in expected_bindings) if expected_bindings else True,
                "binding_terms": expected_bindings,
            }
        )
        renderer_probe_blob = " ".join(
            " ".join(f"{k}:{v}" for k, v in probe.items())
            for probe in emitter.get("renderer_binding_probe") or []
            if isinstance(probe, dict)
        ).lower()
        renderer_binding_hits.append(
            {
                "emitter": emitter.get("name"),
                "matches": (
                    all(term in renderer_probe_blob for term in expected_renderer_binding_text)
                    if expected_renderer_binding_text
                    else any(term in renderer_probe_blob for term in expected_renderer_bindings) if expected_renderer_bindings else True
                ),
                "renderer_probe_blob": renderer_probe_blob,
            }
        )

        binding_exports = emitter.get("renderer_binding_exports") or []
        flat_binding_exports = {}
        for export in binding_exports:
            if isinstance(export, dict):
                flat_binding_exports.update(export)
        binding_export_blob = " ".join(f"{k}:{v}" for k, v in flat_binding_exports.items()).lower()
        for logical_name, spec in semantic_contract.items():
            spec = spec or {}
            renderer_binding_name = str(spec.get("renderer_binding_name") or "").lower()
            expected_attribute = str(spec.get("expected_attribute") or "").lower()
            matched = False
            evidence = []
            if renderer_binding_name and renderer_binding_name in binding_export_blob:
                matched = True
                evidence.append(f"{emitter.get('name')}: binding export mentions {renderer_binding_name}")
            if expected_attribute and expected_attribute in binding_export_blob:
                matched = True
                evidence.append(f"{emitter.get('name')}: binding export mentions {expected_attribute}")
            semantic_binding_hits.setdefault(logical_name, []).append(
                {
                    "emitter": emitter.get("name"),
                    "renderer_binding_name": spec.get("renderer_binding_name"),
                    "expected_attribute": spec.get("expected_attribute"),
                    "matches": matched,
                    "evidence": evidence,
                    "binding_export_blob": binding_export_blob,
                }
            )
            semantic_binding_sections.setdefault(logical_name, []).append(
                {
                    "emitter": emitter.get("name"),
                    "renderer_binding_name": spec.get("renderer_binding_name"),
                    "expected_attribute": spec.get("expected_attribute"),
                    "binding_export_text": flat_binding_exports.get(spec.get("renderer_binding_name"), ""),
                    "matches": matched,
                    "evidence": evidence,
                }
            )
        if "particles.color" in renderer_probe_blob:
            semantic_checks["particle_color"]["status"] = "present"
            semantic_checks["particle_color"]["details"].append(f"{emitter.get('name')}: renderer binding mentions Particles.Color")
        if "particles.dynamicmaterialparameter" in renderer_probe_blob:
            semantic_checks["dynamic_parameter"]["status"] = "present"
            semantic_checks["dynamic_parameter"]["details"].append(f"{emitter.get('name')}: renderer binding mentions Particles.DynamicMaterialParameter")
        if "particles.subimageindex" in renderer_probe_blob:
            semantic_checks["sub_image_index"]["status"] = "present"
            semantic_checks["sub_image_index"]["details"].append(f"{emitter.get('name')}: renderer binding mentions Particles.SubImageIndex")
        if "particles.ribbonwidth" in renderer_probe_blob:
            semantic_checks["ribbon_width"]["status"] = "present"
            semantic_checks["ribbon_width"]["details"].append(f"{emitter.get('name')}: renderer binding mentions Particles.RibbonWidth")

        joined = " ".join(function_names + data_interfaces + input_titles + input_signatures)
        if "particlecolor" in joined or "particles.color" in joined:
            if semantic_checks["particle_color"]["status"] == "unknown":
                semantic_checks["particle_color"]["status"] = "hint"
            semantic_checks["particle_color"]["details"].append(f"{emitter.get('name')}: graph hints mention ParticleColor-related terms")
        if "dynamicmaterialparameter" in joined or "dynamicparameter" in joined:
            if semantic_checks["dynamic_parameter"]["status"] == "unknown":
                semantic_checks["dynamic_parameter"]["status"] = "hint"
            semantic_checks["dynamic_parameter"]["details"].append(f"{emitter.get('name')}: graph hints mention DynamicParameter-related terms")
        if "subimageindex" in joined:
            if semantic_checks["sub_image_index"]["status"] == "unknown":
                semantic_checks["sub_image_index"]["status"] = "hint"
            semantic_checks["sub_image_index"]["details"].append(f"{emitter.get('name')}: graph hints mention SubImageIndex")
        if "ribbonwidth" in joined:
            if semantic_checks["ribbon_width"]["status"] == "unknown":
                semantic_checks["ribbon_width"]["status"] = "hint"
            semantic_checks["ribbon_width"]["details"].append(f"{emitter.get('name')}: graph hints mention RibbonWidth")

    if expected_renderer and not any(item["matches"] for item in renderer_hits):
        add("warning", "system_renderer_class", f"Real system did not expose expected renderer classes {contract.get('expected_renderer_classes')}.")
    if contract.get("expected_material_binding_required") and not any(item["matches"] for item in material_hits):
        add("warning", "system_material_binding", "Real system did not expose the preview material on matching renderer materials.")
    if expected_functions and not any(item["matches"] for item in function_hits):
        add("warning", "system_functions", f"Real system did not expose expected functions {contract.get('expected_functions_any')}.")
    if expected_dis and not any(item["matches"] for item in di_hits):
        add("warning", "system_data_interfaces", f"Real system did not expose expected data interfaces {contract.get('expected_data_interfaces_any')}.")
    if expected_bindings and not any(item["matches"] for item in binding_hints):
        add("info", "system_binding_hints", f"Real system did not expose strong binding hints for {contract.get('expected_dynamic_bindings_any')}.")
    if expected_renderer_bindings and not any(item["matches"] for item in renderer_binding_hits):
        add("info", "system_renderer_binding_probe", f"Real system renderer probe did not expose strong binding evidence for {contract.get('expected_renderer_bindings_any')}.")

    for logical_name, spec in semantic_contract.items():
        hits = semantic_binding_hits.get(logical_name) or []
        if hits and not any(item["matches"] for item in hits):
            add("info", f"semantic_{logical_name.lower()}", f"No strong semantic evidence was found for {logical_name} plumbing in the real system.")
        elif not hits:
            add("info", f"semantic_{logical_name.lower()}", f"Preset expects {logical_name} plumbing, but no semantic binding evidence was recorded.")

    return {
        "system_contract": contract,
        "mode": "real_system",
        "findings": findings,
        "renderer_hits": renderer_hits,
        "material_hits": material_hits,
        "function_hits": function_hits,
        "data_interface_hits": di_hits,
        "binding_hints": binding_hints,
        "renderer_binding_hits": renderer_binding_hits,
        "semantic_checks": semantic_checks,
        "semantic_binding_hits": semantic_binding_hits,
        "semantic_binding_sections": semantic_binding_sections,
    }


def build_render_script(
    material_path: str,
    mesh: str,
    lighting: str,
    resolution: int,
    yaw: float,
    pitch: float,
    distance: float,
    shaded_out: str,
    complexity_out: str | None,
) -> str:
    complexity_line = (
        f"complexity_ok = MAT.preview_material_complexity({material_path!r}, {mesh!r}, {lighting!r}, {resolution}, {yaw}, {pitch}, {distance}, {complexity_out!r})"
        if complexity_out
        else "complexity_ok = None"
    )
    return textwrap.dedent(
        f"""
        import json
        import os
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary
        os.makedirs(os.path.dirname({shaded_out!r}) or ".", exist_ok=True)
        shaded_ok = MAT.preview_material({material_path!r}, {mesh!r}, {lighting!r}, {resolution}, {yaw}, {pitch}, {distance}, {shaded_out!r})
        {f"os.makedirs(os.path.dirname({complexity_out!r}) or '.', exist_ok=True)" if complexity_out else ""}
        {complexity_line}
        print(json.dumps({{
            "material_path": {material_path!r},
            "shaded_ok": shaded_ok,
            "complexity_ok": complexity_ok,
        }}, ensure_ascii=False))
        """
    ).strip()


def build_vfx_carrier_script(
    material_path: str,
    carrier: str,
    width: int,
    height: int,
    fov: float,
    out_png: str,
) -> str:
    return textwrap.dedent(
        f"""
        import json
        import math
        import os
        import unreal

        MATERIAL_PATH = {material_path!r}
        CARRIER = {carrier!r}
        WIDTH = {width}
        HEIGHT = {height}
        FOV = {fov}
        OUT_PNG = {out_png!r}

        os.makedirs(os.path.dirname(OUT_PNG) or ".", exist_ok=True)

        L = unreal.UnrealBridgeLevelLibrary
        M = unreal.UnrealBridgeMaterialLibrary
        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor_sub.get_editor_world()
        mat = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
        if not mat:
            raise RuntimeError(f"Could not load material: {{MATERIAL_PATH}}")

        base = unreal.Vector(500000.0, 500000.0, 500000.0)
        spawned = []
        post_process_volume = None

        def spawn_static_mesh(mesh_path, location, rotation, scale, label):
            actor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, location)
            actor.set_actor_label(label)
            actor.set_actor_rotation(rotation, False)
            actor.set_actor_scale3d(scale)
            smc = actor.get_editor_property('static_mesh_component')
            mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
            smc.set_editor_property('static_mesh', mesh)
            spawned.append(actor)
            return actor, smc

        def destroy_spawned():
            for actor in reversed(spawned):
                try:
                    actor_sub.destroy_actor(actor)
                except Exception:
                    pass

        shaded_ok = False
        view_location = unreal.Vector(base.x + 260.0, base.y, base.z)
        view_rotation = unreal.Rotator(0.0, 180.0, 0.0)

        try:
            if CARRIER == 'sprite_card':
                plane_actor, plane = spawn_static_mesh(
                    '/Engine/BasicShapes/Plane.Plane',
                    base,
                    unreal.Rotator(-90.0, 0.0, 0.0),
                    unreal.Vector(2.5, 2.5, 1.0),
                    'CodexPreview_Sprite'
                )
                plane.set_material(0, mat)
            elif CARRIER == 'ribbon_card':
                plane_actor, plane = spawn_static_mesh(
                    '/Engine/BasicShapes/Plane.Plane',
                    base,
                    unreal.Rotator(-90.0, 0.0, 0.0),
                    unreal.Vector(7.0, 0.45, 1.0),
                    'CodexPreview_Ribbon'
                )
                plane.set_material(0, mat)
                view_location = unreal.Vector(base.x + 340.0, base.y, base.z)
            elif CARRIER == 'decal':
                wall_actor, wall = spawn_static_mesh(
                    '/Engine/BasicShapes/Plane.Plane',
                    base,
                    unreal.Rotator(-90.0, 0.0, 0.0),
                    unreal.Vector(5.0, 5.0, 1.0),
                    'CodexPreview_DecalWall'
                )
                decal = actor_sub.spawn_actor_from_class(unreal.DecalActor, unreal.Vector(base.x - 5.0, base.y, base.z))
                decal.set_actor_label('CodexPreview_Decal')
                decal.set_actor_rotation(unreal.Rotator(0.0, 0.0, 0.0), False)
                decal.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
                decal.set_decal_material(mat)
                decal_comp = decal.get_editor_property('decal')
                decal_comp.set_editor_property('decal_size', unreal.Vector(128.0, 128.0, 128.0))
                spawned.append(decal)
            elif CARRIER == 'post_process':
                floor_actor, floor = spawn_static_mesh(
                    '/Engine/BasicShapes/Plane.Plane',
                    unreal.Vector(base.x, base.y, base.z - 60.0),
                    unreal.Rotator(0.0, 0.0, 0.0),
                    unreal.Vector(8.0, 8.0, 1.0),
                    'CodexPreview_Floor'
                )
                cube_actor, cube = spawn_static_mesh(
                    '/Engine/BasicShapes/Cube.Cube',
                    unreal.Vector(base.x, base.y, base.z),
                    unreal.Rotator(0.0, 30.0, 0.0),
                    unreal.Vector(1.2, 1.2, 1.2),
                    'CodexPreview_Cube'
                )
                sphere_actor, sphere = spawn_static_mesh(
                    '/Engine/BasicShapes/Sphere.Sphere',
                    unreal.Vector(base.x - 70.0, base.y + 80.0, base.z - 10.0),
                    unreal.Rotator(0.0, 0.0, 0.0),
                    unreal.Vector(1.0, 1.0, 1.0),
                    'CodexPreview_Sphere'
                )
                post_process_volume = actor_sub.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(base.x, base.y, base.z))
                post_process_volume.set_actor_label('CodexPreview_PPV')
                post_process_volume.set_editor_property('priority', 1000.0)
                post_process_volume.set_editor_property('blend_weight', 1.0)
                post_process_volume.set_editor_property('unbound', True)
                spawned.append(post_process_volume)
                if not M.apply_post_process_material('CodexPreview_PPV', MATERIAL_PATH, 1.0):
                    raise RuntimeError('Failed to apply post-process material to preview volume.')
                view_location = unreal.Vector(base.x + 260.0, base.y - 140.0, base.z + 80.0)
                view_rotation = unreal.Rotator(-8.0, 155.0, 0.0)
            else:
                raise RuntimeError(f"Unsupported carrier: {{CARRIER}}")

            shaded_ok = L.capture_from_pose(view_location, view_rotation, FOV, WIDTH, HEIGHT, OUT_PNG)
        finally:
            if post_process_volume is not None:
                try:
                    M.remove_post_process_material('CodexPreview_PPV', MATERIAL_PATH)
                except Exception:
                    pass
            destroy_spawned()

        print(json.dumps({{
            "material_path": MATERIAL_PATH,
            "carrier": CARRIER,
            "shaded_ok": bool(shaded_ok),
            "camera": {{
                "location": [view_location.x, view_location.y, view_location.z],
                "rotation": [view_rotation.pitch, view_rotation.yaw, view_rotation.roll],
                "fov": FOV,
                "width": WIDTH,
                "height": HEIGHT
            }}
        }}, ensure_ascii=False))
        """
    ).strip()


def build_niagara_preview_script(
    material_path: str,
    carrier: str,
    width: int,
    height: int,
    fov: float,
    out_png: str,
    sim_time: float,
    template_system: str | None,
    emitter_name_hint: str | None,
    subuv_grid: str | None,
) -> str:
    template = template_system or "/Niagara/DefaultAssets/DefaultSystem.DefaultSystem"
    subuv_grid_payload = json.dumps(subuv_grid or "", ensure_ascii=False)
    emitter_hint_payload = json.dumps(emitter_name_hint or "", ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import json
        import math
        import os
        import uuid
        import unreal

        MATERIAL_PATH = {material_path!r}
        CARRIER = {carrier!r}
        TEMPLATE_SYSTEM = {template!r}
        WIDTH = {width}
        HEIGHT = {height}
        FOV = {fov}
        SIM_TIME = {sim_time}
        OUT_PNG = {out_png!r}
        EMITTER_HINT = json.loads({emitter_hint_payload!r})
        SUBUV_GRID = json.loads({subuv_grid_payload!r})

        os.makedirs(os.path.dirname(OUT_PNG) or ".", exist_ok=True)

        LV = unreal.UnrealBridgeLevelLibrary
        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        system_asset = unreal.EditorAssetLibrary.load_asset(TEMPLATE_SYSTEM)
        if not system_asset:
            raise RuntimeError(f"Could not load Niagara template system: {{TEMPLATE_SYSTEM}}")
        material = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
        if not material:
            raise RuntimeError(f"Could not load material: {{MATERIAL_PATH}}")

        temp_pkg = f"/Game/CodexTemp/MaterialPreview/NS_CodexPreview_{{CARRIER}}_{{uuid.uuid4().hex[:8]}}"
        if not unreal.EditorAssetLibrary.duplicate_asset(TEMPLATE_SYSTEM.split('.', 1)[0], temp_pkg):
            raise RuntimeError(f"Could not duplicate Niagara template into {{temp_pkg}}")
        temp_object_path = temp_pkg + "." + temp_pkg.rsplit("/", 1)[-1]
        duplicated_system = unreal.EditorAssetLibrary.load_asset(temp_pkg)
        if not duplicated_system:
            raise RuntimeError(f"Could not load duplicated Niagara system: {{temp_pkg}}")

        renderers = list(unreal.UnrealBridgeNiagaraLibrary.list_system_renderers(temp_object_path))
        if not renderers:
            raise RuntimeError("Duplicated Niagara template has no renderers to patch.")

        def parse_grid(text):
            if not text:
                return None
            normalized = str(text).lower().replace(" ", "")
            if "x" not in normalized:
                return None
            left, right = normalized.split("x", 1)
            return float(int(left)), float(int(right))

        if CARRIER == 'sprite':
            bound_material_path = ""
            actual_renderer_class = ""
            actual_subuv_grid = ""
            patched = 0
            for renderer in renderers:
                if 'SpriteRendererProperties' not in renderer.renderer_class:
                    continue
                if EMITTER_HINT and renderer.emitter_name != EMITTER_HINT:
                    continue
                renderer_obj = unreal.load_object(None, renderer.renderer_path)
                if renderer_obj:
                    renderer_obj.set_editor_property('material', material)
                    grid = parse_grid(SUBUV_GRID)
                    if grid:
                        renderer_obj.set_editor_property('sub_image_size', unreal.Vector2D(grid[0], grid[1]))
                        actual_subuv_grid = f"{{int(grid[0])}}x{{int(grid[1])}}"
                    else:
                        try:
                            sub = renderer_obj.get_editor_property('sub_image_size')
                            actual_subuv_grid = f"{{int(sub.x)}}x{{int(sub.y)}}"
                        except Exception:
                            actual_subuv_grid = ""
                    try:
                        bound_material_path = renderer_obj.get_editor_property('material').get_path_name()
                    except Exception:
                        bound_material_path = MATERIAL_PATH
                    actual_renderer_class = renderer.renderer_class
                    patched += 1
            if patched == 0:
                raise RuntimeError("No sprite renderer found on duplicated Niagara template.")
        elif CARRIER == 'ribbon':
            emitter_name = EMITTER_HINT or renderers[0].emitter_name
            result = unreal.UnrealBridgeNiagaraLibrary.add_ribbon_renderer_to_emitter(
                temp_object_path,
                emitter_name,
                MATERIAL_PATH,
                "CodexPreviewRibbonRenderer",
                "Screen",
                1,
                0.0,
                True,
                True,
            )
            if not result.success:
                raise RuntimeError(f"Failed to add ribbon renderer: {{result.error}}")
            bound_material_path = result.material_path
            actual_renderer_class = "/Script/Niagara.NiagaraRibbonRendererProperties"
            actual_subuv_grid = ""
        else:
            raise RuntimeError(f"Unsupported Niagara preview carrier: {{CARRIER}}")

        unreal.EditorAssetLibrary.save_asset(temp_pkg, False)

        center = unreal.Vector(500000.0, 500000.0, 500000.0)
        actor_name = LV.spawn_actor("/Script/Niagara.NiagaraActor", center, unreal.Rotator(0, 0, 0))
        editor_actor = None
        for actor in actor_sub.get_all_level_actors():
            if actor.get_name() == actor_name or actor.get_actor_label() == actor_name:
                editor_actor = actor
                break
        if editor_actor is None:
            raise RuntimeError(f"Could not resolve spawned Niagara preview actor: {{actor_name}}")
        niagara_components = list(editor_actor.get_components_by_class(unreal.NiagaraComponent))
        niagara_component = niagara_components[-1] if niagara_components else None
        if niagara_component is None:
            raise RuntimeError("Could not find NiagaraComponent on preview actor.")

        niagara_component.set_asset(duplicated_system)
        niagara_component.set_world_location(center, False, False)
        niagara_component.set_bounds_scale(12.0)
        niagara_component.set_can_render_while_seeking(True)
        niagara_component.set_rendering_enabled(True)
        niagara_component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.DESIRED_AGE)
        niagara_component.set_seek_delta(1.0 / 60.0)
        niagara_component.set_desired_age(SIM_TIME)
        niagara_component.activate(True)
        niagara_component.seek_to_desired_age(SIM_TIME)

        yaw = 35.0 if CARRIER == 'sprite' else 28.0
        pitch = 10.0 if CARRIER == 'sprite' else 12.0
        distance = 420.0 if CARRIER == 'sprite' else 520.0
        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch)
        camera = unreal.Vector(
            center.x + math.cos(pitch_rad) * math.cos(yaw_rad) * distance,
            center.y + math.cos(pitch_rad) * math.sin(yaw_rad) * distance,
            center.z + math.sin(pitch_rad) * distance,
        )
        rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)

        shaded_ok = False
        try:
            shaded_ok = LV.capture_from_pose(camera, rotation, FOV, WIDTH, HEIGHT, OUT_PNG)
        finally:
            try:
                actor_sub.destroy_actor(editor_actor)
            except Exception:
                pass
            unreal.EditorAssetLibrary.delete_asset(temp_pkg)

        print(json.dumps({{
            "material_path": MATERIAL_PATH,
            "carrier": CARRIER,
            "preview_route": "niagara",
            "template_system": TEMPLATE_SYSTEM,
            "temp_system": temp_object_path,
            "emitter_name_hint": EMITTER_HINT,
            "subuv_grid": SUBUV_GRID,
            "renderer_class": actual_renderer_class,
            "renderer_material_path": bound_material_path,
            "renderer_subuv_grid": actual_subuv_grid,
            "shaded_ok": bool(shaded_ok),
            "camera": {{
                "location": [camera.x, camera.y, camera.z],
                "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
                "fov": FOV,
                "width": WIDTH,
                "height": HEIGHT
            }}
        }}, ensure_ascii=False))
        """
    ).strip()


def build_sweep_script(
    material_instance_path: str,
    param_name: str,
    values: list[str],
    mesh: str,
    lighting: str,
    resolution: int,
    yaw: float,
    pitch: float,
    distance: float,
    grid_cols: int,
    out_grid_path: str,
) -> str:
    values_payload = json.dumps(values, ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import json
        import os
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary
        values = json.loads({values_payload!r})
        os.makedirs(os.path.dirname({out_grid_path!r}) or ".", exist_ok=True)
        paths = MAT.sweep_mi_params(
            {material_instance_path!r},
            {param_name!r},
            values,
            {mesh!r},
            {lighting!r},
            {resolution},
            {yaw},
            {pitch},
            {distance},
            {grid_cols},
            {out_grid_path!r},
        )
        print(json.dumps({{
            "material_instance_path": {material_instance_path!r},
            "param_name": {param_name!r},
            "paths": list(paths),
        }}, ensure_ascii=False))
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Material Preview: {report.get('material_path') or report.get('material_instance_path')}", ""]
    if report["mode"] == "render":
        lines.extend(
            [
                f"- Carrier: `{report['options'].get('carrier', 'mesh')}`",
                f"- Preview route: `{report['options'].get('preview_route', 'mesh')}`",
                f"- Preset: `{report['options'].get('preset_name') or 'none'}`",
                f"- Mesh: `{report['options']['mesh']}`",
                f"- Lighting: `{report['options']['lighting']}`",
                f"- Resolution: `{report['options']['resolution']}`",
                f"- Shaded output: `{report['outputs']['shaded_png']}`",
                f"- Shaded ok: `{report['outputs']['shaded_ok']}`",
            ]
        )
        preset_contract = report['options'].get('preset_contract') or {}
        if preset_contract:
            lines.append(f"- Usage flags: `{', '.join(preset_contract.get('usage_flags_required') or []) or 'none'}`")
            lines.append(f"- SubUV grid: `{preset_contract.get('subuv_grid') or 'none'}`")
            lines.append(f"- Ribbon UV: `{preset_contract.get('ribbon_uv_mode') or 'none'}`")
            lines.append(f"- Dynamic parameters: `{', '.join(preset_contract.get('dynamic_parameters') or []) or 'none'}`")
        contract_scan = report.get("contract_scan") or {}
        if contract_scan.get("findings"):
            lines.extend(["", "Contract Scan:"])
            for finding in contract_scan["findings"]:
                lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
        renderer_scan = contract_scan.get("renderer_scan") or {}
        if renderer_scan.get("findings"):
            lines.extend(["", "Renderer Scan:"])
            for finding in renderer_scan["findings"]:
                lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
        system_scan = contract_scan.get("system_scan") or {}
        if system_scan.get("findings"):
            lines.extend(["", "Real System Scan:"])
            for finding in system_scan["findings"]:
                lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
        semantic_binding_hits = system_scan.get("semantic_binding_hits") or {}
        if semantic_binding_hits:
            lines.extend(["", "Semantic Bindings:"])
            for logical_name, hits in semantic_binding_hits.items():
                lines.append(f"- `{logical_name}`")
                for hit in hits:
                    status = "match" if hit.get("matches") else "miss"
                    exp = hit.get("expected_attribute") or "unset"
                    rbn = hit.get("renderer_binding_name") or "unset"
                    lines.append(f"  - [{status}] renderer=`{rbn}` attribute=`{exp}` emitter=`{hit.get('emitter')}`")
                    for evidence in hit.get("evidence") or []:
                        lines.append(f"    - {evidence}")
        semantic_binding_sections = system_scan.get("semantic_binding_sections") or {}
        if semantic_binding_sections:
            lines.extend(["", "Semantic Channels:"])
            for logical_name, hits in semantic_binding_sections.items():
                lines.append(f"- `{logical_name}`")
                for hit in hits:
                    status = "match" if hit.get("matches") else "miss"
                    lines.append(
                        f"  - [{status}] emitter=`{hit.get('emitter')}` renderer_binding=`{hit.get('renderer_binding_name')}` attribute=`{hit.get('expected_attribute')}`"
                    )
                    if hit.get("binding_export_text"):
                        lines.append(f"    - export={hit.get('binding_export_text')}")
                    for evidence in hit.get("evidence") or []:
                        lines.append(f"    - {evidence}")
        if report["outputs"].get("complexity_png"):
            lines.append(f"- Complexity output: `{report['outputs']['complexity_png']}`")
            lines.append(f"- Complexity ok: `{report['outputs']['complexity_ok']}`")
    else:
        lines.extend(
            [
                f"- Parameter: `{report['param_name']}`",
                f"- Values: {', '.join(report['values'])}",
                f"- Grid output: `{report['outputs']['grid_png']}`",
                f"- Cell count: `{len(report['outputs']['cell_pngs'])}`",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def command_render(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    preset_name, preset = resolve_preview_preset(args.carrier, args.preset)
    contract_scan = {}
    if preset:
        snapshot = audit_material_snapshot(client, args.material_path)
        contract_scan = build_preview_contract_scan(snapshot, preset)

    effect = slugify(args.effect or args.material_path)
    base_dir = default_report_path(ctx, "previews", effect, slugify(args.material_path), "")
    shaded_out = str(Path(args.out) if args.out else base_dir.with_name(f"preview-{slugify(args.carrier)}-shaded.png"))
    complexity_out = None
    if args.carrier == "mesh":
        if args.with_complexity:
            complexity_out = str(Path(args.complexity_out) if args.complexity_out else base_dir.with_name("preview-complexity.png"))
        raw = client.exec_json(
            build_render_script(
                args.material_path,
                args.mesh,
                args.lighting,
                args.resolution,
                args.yaw,
                args.pitch,
                args.distance,
                shaded_out,
                complexity_out,
            )
        )
    elif args.carrier in {"sprite", "ribbon"}:
        raw = client.exec_json(
            build_niagara_preview_script(
                args.material_path,
                args.carrier,
                args.width or preset.get("width") or args.resolution,
                args.height or preset.get("height") or args.resolution,
                args.fov if args.fov != 35.0 else float(preset.get("fov") or args.fov),
                shaded_out,
                args.sim_time if args.sim_time != 1.0 else float(preset.get("sim_time") or args.sim_time),
                args.template_system or preset.get("template_system"),
                preset.get("emitter_name_hint"),
                preset.get("subuv_grid"),
            ),
            no_preflight=True,
        )
        if preset:
            contract_scan["renderer_scan"] = build_renderer_contract_scan(raw, preset)
            verify_system_path = args.verify_system_path or preset.get("verify_system_path")
            if verify_system_path:
                real_raw = client.exec_json(build_niagara_contract_script(verify_system_path), no_preflight=True)
                real_report = summarize_niagara_contract(real_raw)
                contract_scan["system_scan"] = build_real_system_contract_scan(real_report, preset, args.material_path)
    else:
        raw = client.exec_json(
            build_vfx_carrier_script(
                args.material_path,
                args.carrier,
                args.width or args.resolution,
                args.height or args.resolution,
                args.fov,
                shaded_out,
            )
        )
    report = {
        "tool": "material_preview",
        "mode": "render",
        "material_path": args.material_path,
        "options": {
            "carrier": args.carrier,
            "mesh": args.mesh,
            "lighting": args.lighting,
            "resolution": args.resolution,
            "yaw": args.yaw,
            "pitch": args.pitch,
            "distance": args.distance,
            "width": args.width or args.resolution,
            "height": args.height or args.resolution,
            "fov": args.fov,
            "template_system": args.template_system,
            "sim_time": args.sim_time,
            "preset_name": preset_name,
            "preset_contract": preset,
            "preview_route": raw.get("preview_route") or ("niagara" if args.carrier in {"sprite", "ribbon"} else "world_harness" if args.carrier in {"sprite_card", "ribbon_card", "decal", "post_process"} else "mesh"),
        },
        "outputs": {
            "shaded_png": shaded_out,
            "shaded_ok": raw["shaded_ok"],
            "complexity_png": complexity_out,
            "complexity_ok": raw.get("complexity_ok"),
        },
        "contract_scan": contract_scan,
    }
    if "camera" in raw:
        report["camera"] = raw["camera"]
    report_path = default_report_path(ctx, "previews", effect, f"{slugify(args.material_path)}-preview", ".json")
    save_json(report_path, report)
    if args.markdown:
        write_text(report_path.with_suffix(".md"), render_markdown(report))
    print(report_path)
    return 0


def command_sweep(args: argparse.Namespace) -> int:
    if not args.value:
        raise SystemExit("Provide at least one --value for the parameter sweep.")
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    effect = slugify(args.effect or args.material_instance_path)
    grid_out = str(Path(args.out) if args.out else default_report_path(ctx, "previews", effect, f"{slugify(args.material_instance_path)}-{slugify(args.param_name)}-sweep", ".png"))
    raw = client.exec_json(
        build_sweep_script(
            args.material_instance_path,
            args.param_name,
            args.value,
            args.mesh,
            args.lighting,
            args.resolution,
            args.yaw,
            args.pitch,
            args.distance,
            args.grid_cols,
            grid_out,
        )
    )
    cell_paths = list(raw.get("paths") or [])
    report = {
        "tool": "material_preview",
        "mode": "sweep",
        "material_instance_path": args.material_instance_path,
        "param_name": args.param_name,
        "values": args.value,
        "options": {
            "mesh": args.mesh,
            "lighting": args.lighting,
            "resolution": args.resolution,
            "yaw": args.yaw,
            "pitch": args.pitch,
            "distance": args.distance,
            "grid_cols": args.grid_cols,
        },
        "outputs": {
            "grid_png": cell_paths[0] if cell_paths else grid_out,
            "cell_pngs": cell_paths[1:] if len(cell_paths) > 1 else [],
        },
    }
    report_path = default_report_path(ctx, "previews", effect, f"{slugify(args.material_instance_path)}-{slugify(args.param_name)}-sweep", ".json")
    save_json(report_path, report)
    if args.markdown:
        write_text(report_path.with_suffix(".md"), render_markdown(report))
    print(report_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render controlled previews for Unreal materials and material instances.")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="Render a preview of a material or MI.")
    render.add_argument("material_path")
    render.add_argument("--root", default="auto")
    render.add_argument("--project")
    render.add_argument("--endpoint")
    render.add_argument("--timeout", type=int, default=180)
    render.add_argument("--effect")
    render.add_argument("--mesh", default="shaderball")
    render.add_argument("--carrier", default="mesh", choices=["mesh", "sprite", "ribbon", "sprite_card", "ribbon_card", "decal", "post_process"])
    render.add_argument("--preset")
    render.add_argument("--template-system")
    render.add_argument("--verify-system-path")
    render.add_argument("--lighting", default="hdri")
    render.add_argument("--resolution", type=int, default=512)
    render.add_argument("--width", type=int)
    render.add_argument("--height", type=int)
    render.add_argument("--yaw", type=float, default=30.0)
    render.add_argument("--pitch", type=float, default=15.0)
    render.add_argument("--distance", type=float, default=0.0)
    render.add_argument("--fov", type=float, default=35.0)
    render.add_argument("--sim-time", type=float, default=1.0)
    render.add_argument("--with-complexity", action="store_true")
    render.add_argument("--out")
    render.add_argument("--complexity-out")
    render.add_argument("--markdown", action="store_true")
    render.set_defaults(func=command_render)

    sweep = sub.add_parser("sweep", help="Sweep a single MI parameter and render a comparison grid.")
    sweep.add_argument("material_instance_path")
    sweep.add_argument("--param-name", required=True)
    sweep.add_argument("--value", action="append")
    sweep.add_argument("--root", default="auto")
    sweep.add_argument("--project")
    sweep.add_argument("--endpoint")
    sweep.add_argument("--timeout", type=int, default=180)
    sweep.add_argument("--effect")
    sweep.add_argument("--mesh", default="shaderball")
    sweep.add_argument("--lighting", default="hdri")
    sweep.add_argument("--resolution", type=int, default=320)
    sweep.add_argument("--yaw", type=float, default=30.0)
    sweep.add_argument("--pitch", type=float, default=15.0)
    sweep.add_argument("--distance", type=float, default=0.0)
    sweep.add_argument("--grid-cols", type=int, default=0)
    sweep.add_argument("--out")
    sweep.add_argument("--markdown", action="store_true")
    sweep.set_defaults(func=command_sweep)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
