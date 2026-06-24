from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .effect_preview_approval import build_context, context_key
from .effect_state import effect_preview_approvals_default, load_effect_record, save_effect_record
from .flipbook_builder import parse_grid
from .promote_naming import (
    PROMOTE_POLICY_CHOICES,
    asset_token,
    derive_formal_promote_root as derive_formal_promote_root_shared,
    resolve_promote_details,
    resolve_promote_root as resolve_promote_root_shared,
)


def package_to_object_ref(package_path: str) -> str:
    leaf = package_path.rsplit("/", 1)[-1]
    return package_path if "." in leaf else f"{package_path}.{leaf}"


def package_path(asset_path: str) -> str:
    clean = str(asset_path or "").strip()
    if "." in clean.rsplit("/", 1)[-1]:
        return clean.rsplit(".", 1)[0]
    return clean


def derive_default_asset_paths(effect: str) -> tuple[str, str]:
    token = asset_token(effect)
    base = f"/Game/CodexTemp/{token}"
    texture_path = f"{base}/Textures/T_{token}_Atlas"
    material_path = f"{base}/Materials/M_{token}_SubUV"
    return texture_path, material_path


def derive_default_niagara_system_path(effect: str) -> str:
    token = asset_token(effect)
    return f"/Game/CodexTemp/{token}/Niagara/NS_{token}_SubUV"


def derive_default_promote_paths(
    *,
    promote_root: str,
    texture_asset_path: str,
    material_asset_path: str,
    niagara_system_path: str | None = None,
) -> dict[str, str]:
    root = promote_root.rstrip("/")
    texture_name = package_path(texture_asset_path).rsplit("/", 1)[-1]
    material_name = package_path(material_asset_path).rsplit("/", 1)[-1]
    paths = {
        "texture": f"{root}/Textures/{texture_name}",
        "material": f"{root}/Materials/{material_name}",
    }
    if niagara_system_path:
        system_name = package_path(niagara_system_path).rsplit("/", 1)[-1]
        paths["niagara"] = f"{root}/Niagara/{system_name}"
    return paths


def derive_formal_promote_root(
    *,
    promote_base: str,
    promote_effect_name: str,
    promote_policy: str = "vfx-effect",
    promote_group: str = "",
    promote_studio: str = "",
    promote_project_name: str = "",
    promote_effect_family: str = "",
) -> str:
    return derive_formal_promote_root_shared(
        promote_base=promote_base,
        promote_policy=promote_policy,
        promote_group=promote_group,
        promote_effect_name=promote_effect_name,
        promote_studio=promote_studio,
        promote_project_name=promote_project_name,
        promote_effect_family=promote_effect_family,
    )


def resolve_promote_root(
    *,
    effect: str,
    explicit_root: str,
    promote_policy: str,
    promote_base: str,
    promote_group: str = "",
    promote_effect_name: str = "",
    promote_studio: str = "",
    promote_project_name: str = "",
    promote_effect_family: str = "",
) -> str:
    return resolve_promote_root_shared(
        effect=effect,
        explicit_root=explicit_root,
        promote_policy=promote_policy,
        promote_base=promote_base,
        promote_group=promote_group,
        promote_effect_name=promote_effect_name,
        promote_studio=promote_studio,
        promote_project_name=promote_project_name,
        promote_effect_family=promote_effect_family,
    )


def adjacent_manifest_path(atlas_file: Path) -> Path | None:
    candidate = atlas_file.with_name("flipbook-manifest.json")
    return candidate if candidate.exists() else None


def load_adjacent_manifest(atlas_file: Path) -> dict[str, Any] | None:
    manifest_path = adjacent_manifest_path(atlas_file)
    if not manifest_path:
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def manifest_playback_seconds(manifest: dict[str, Any] | None) -> float | None:
    if not manifest:
        return None
    clip = manifest.get("clip") or {}
    duration = clip.get("duration_seconds")
    try:
        value = float(duration)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def manifest_grid(manifest: dict[str, Any] | None) -> str | None:
    if not manifest:
        return None
    grid = manifest.get("grid") or {}
    cols = grid.get("columns")
    rows = grid.get("rows")
    try:
        cols_i = int(cols)
        rows_i = int(rows)
    except (TypeError, ValueError):
        return None
    if cols_i <= 0 or rows_i <= 0:
        return None
    return f"{cols_i}x{rows_i}"


def build_import_and_material_script(
    *,
    atlas_file: str,
    texture_package_path: str,
    material_package_path: str,
    parameter_name: str,
) -> str:
    texture_ref = package_to_object_ref(texture_package_path)
    material_ref = package_to_object_ref(material_package_path)
    texture_folder = texture_package_path.rsplit("/", 1)[0]
    texture_name = texture_package_path.rsplit("/", 1)[-1]
    material_folder = material_package_path.rsplit("/", 1)[0]
    material_name = material_package_path.rsplit("/", 1)[-1]
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        ASSET = unreal.UnrealBridgeAssetLibrary
        MAT = unreal.UnrealBridgeMaterialLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary

        ATLAS_FILE = {atlas_file!r}
        TEXTURE_PACKAGE_PATH = {texture_package_path!r}
        TEXTURE_REF = {texture_ref!r}
        TEXTURE_FOLDER = {texture_folder!r}
        TEXTURE_NAME = {texture_name!r}
        MATERIAL_PACKAGE_PATH = {material_package_path!r}
        MATERIAL_REF = {material_ref!r}
        MATERIAL_FOLDER = {material_folder!r}
        MATERIAL_NAME = {material_name!r}
        PARAMETER_NAME = {parameter_name!r}

        def run_tool(name, payload):
            result = TR.execute_qualified_tool(name, json.dumps(payload, ensure_ascii=False), True)
            output = None
            if result.json_output:
                try:
                    output = json.loads(result.json_output)
                except Exception:
                    output = result.json_output
            return {{
                "success": bool(result.success),
                "error": result.error,
                "output": output,
            }}

        import_payload = None
        import_fn = getattr(ASSET, "import_texture2d_from_file", None)
        if import_fn is not None:
            import_row = import_fn(
                ATLAS_FILE,
                TEXTURE_FOLDER,
                TEXTURE_NAME,
                True,
                True,
                True,
            )
            import_payload = {{
                "success": bool(import_row.success),
                "error": str(import_row.error),
                "source_file": str(import_row.source_file),
                "destination_path": str(import_row.destination_path),
                "asset_name": str(import_row.asset_name),
                "imported_asset_path": str(import_row.imported_asset_path),
                "replaced_existing": bool(import_row.replaced_existing),
                "saved": bool(import_row.saved),
                "imported_object_paths": [str(x) for x in list(import_row.imported_object_paths)],
                "route": "bridge-uassetlibrary",
            }}
        else:
            cdo = unreal.load_object(None, '/Script/UnrealBridge.Default__UnrealBridgeAssetLibrary')
            if cdo and hasattr(cdo, 'call_method'):
                import_row = cdo.call_method(
                    'ImportTexture2DFromFile',
                    args=(
                        ATLAS_FILE,
                        TEXTURE_FOLDER,
                        TEXTURE_NAME,
                        True,
                        True,
                        True,
                    ),
                )
                export_text = import_row.export_text() if hasattr(import_row, "export_text") else ""
                def parse_bool(field_name, default=False):
                    import re
                    match = re.search(field_name + r"=(True|False)", export_text)
                    if not match:
                        return default
                    return match.group(1) == "True"
                def parse_string(field_name, default=""):
                    import re
                    match = re.search(field_name + r'="([^"]*)"', export_text)
                    return match.group(1) if match else default
                def parse_int(field_name, default=0):
                    import re
                    match = re.search(field_name + r"=(-?\\d+)", export_text)
                    return int(match.group(1)) if match else default
                imported_paths = []
                import re
                paths_match = re.search(r'ImportedObjectPaths=\\((.*?)\\)', export_text)
                if paths_match:
                    imported_paths = re.findall(r'"([^"]+)"', paths_match.group(1))
                import_payload = {{
                    "success": parse_bool("bSuccess"),
                    "error": parse_string("Error"),
                    "source_file": parse_string("SourceFile"),
                    "destination_path": parse_string("DestinationPath"),
                    "asset_name": parse_string("AssetName"),
                    "imported_asset_path": parse_string("ImportedAssetPath"),
                    "replaced_existing": parse_bool("bReplacedExisting"),
                    "saved": parse_bool("bSaved"),
                    "imported_object_paths": imported_paths,
                    "texture_info": {{
                        "found": parse_bool("bFound"),
                        "asset_path": parse_string("AssetPath"),
                        "width": parse_int("Width"),
                        "height": parse_int("Height"),
                        "num_mips": parse_int("NumMips"),
                        "pixel_format": parse_string("PixelFormat"),
                        "compression_settings": parse_string("CompressionSettings"),
                        "lod_group": parse_string("LODGroup"),
                        "srgb": parse_bool("bSRGB"),
                        "never_stream": parse_bool("bNeverStream"),
                        "resource_size_bytes": parse_int("ResourceSizeBytes"),
                    }},
                    "export_text": export_text,
                    "route": "bridge-uassetlibrary-reflection",
                }}
            else:
                from unreal_bridge_helpers import import_texture2d_from_file as helper_import_texture2d_from_file
                import_payload = helper_import_texture2d_from_file(
                    ATLAS_FILE,
                    TEXTURE_FOLDER,
                    TEXTURE_NAME,
                    True,
                    True,
                    True,
                )
                import_payload["route"] = "plugin-python-helper"

        if not import_payload.get("success"):
            raise RuntimeError(f"Could not import texture to {{TEXTURE_REF}}: {{import_payload.get('error', '')}}")
        texture = unreal.load_asset(import_payload.get("imported_asset_path") or TEXTURE_REF)
        if not texture:
            raise RuntimeError(f"Could not load imported texture {{import_payload.get('imported_asset_path') or TEXTURE_REF}}")

        if not EAL.does_asset_exist(MATERIAL_REF):
            create_row = run_tool(
                "toolset_registry.toolsets.core.material.MaterialTools.create",
                {{
                    "folder_path": MATERIAL_FOLDER,
                    "asset_name": MATERIAL_NAME,
                }},
            )
            if not create_row["success"]:
                raise RuntimeError(f"Could not create material {{MATERIAL_REF}}: {{create_row['error']}}")

        material = unreal.load_asset(MATERIAL_REF)
        if not material:
            raise RuntimeError(f"Could not load material {{MATERIAL_REF}}")

        def resolve_node(mat_ref, class_name, x, y):
            graph = MAT.get_material_graph(mat_ref)
            for node in list(graph.nodes):
                if str(node.class_name) == class_name and int(node.x) == int(x) and int(node.y) == int(y):
                    return node
            return None

        def ensure_node(mat_ref, class_path, x, y):
            class_name = class_path.rsplit(".", 1)[-1].replace("MaterialExpression", "")
            node = resolve_node(mat_ref, class_name, x, y)
            if node:
                return node
            add_result = MAT.add_material_expression(mat_ref, class_path, x, y)
            node = resolve_node(mat_ref, class_name, x, y)
            if not node:
                raise RuntimeError(
                    f"Could not resolve created node {{class_name}} at {{x}},{{y}}; "
                    f"add success={{add_result.success}} error={{add_result.error}}"
                )
            return node

        subuv = ensure_node(MATERIAL_REF, "/Script/Engine.MaterialExpressionTextureSampleParameterSubUV", -600, 0)
        particle_color = ensure_node(MATERIAL_REF, "/Script/Engine.MaterialExpressionParticleColor", -600, 260)
        mul_rgb = ensure_node(MATERIAL_REF, "/Script/Engine.MaterialExpressionMultiply", -250, 40)
        mul_opacity = ensure_node(MATERIAL_REF, "/Script/Engine.MaterialExpressionMultiply", -250, 260)

        MAT.set_material_expression_property(MATERIAL_REF, subuv.guid, "ParameterName", PARAMETER_NAME)
        MAT.set_material_expression_property(MATERIAL_REF, subuv.guid, "Texture", TEXTURE_REF)

        MAT.connect_material_expressions(MATERIAL_REF, subuv.guid, "RGB", mul_rgb.guid, "A")
        MAT.connect_material_expressions(MATERIAL_REF, particle_color.guid, "RGB", mul_rgb.guid, "B")
        MAT.connect_material_expressions(MATERIAL_REF, subuv.guid, "R", mul_opacity.guid, "A")
        MAT.connect_material_expressions(MATERIAL_REF, particle_color.guid, "A", mul_opacity.guid, "B")
        MAT.connect_material_output(MATERIAL_REF, mul_rgb.guid, "", "EmissiveColor")
        MAT.connect_material_output(MATERIAL_REF, mul_opacity.guid, "", "Opacity")

        material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        material.set_editor_property("two_sided", True)
        material.set_editor_property("used_with_particle_sprites", True)
        material.set_editor_property("used_with_niagara_sprites", True)

        MAT.compile_material(MATERIAL_REF, False)
        save_row = run_tool(
            "toolset_registry.toolsets.core.asset.AssetTools.save_assets",
            {{
                "asset_paths": [TEXTURE_REF, MATERIAL_REF],
            }},
        )

        info = MAT.get_material_info(MATERIAL_REF)
        print(
            json.dumps(
                {{
                    "texture_ref": TEXTURE_REF,
                    "texture_import": {{
                        **import_payload,
                    }},
                    "material_ref": MATERIAL_REF,
                    "save": save_row,
                    "material_info": {{
                        "blend_mode": str(info.blend_mode),
                        "material_domain": str(info.material_domain),
                        "usage_flags": [str(x) for x in list(info.usage_flags)],
                        "texture_parameters": [
                            {{
                                "name": str(p.name),
                                "value": str(p.value),
                            }}
                            for p in list(info.texture_parameters)
                        ],
                    }},
                }},
                ensure_ascii=False,
            )
        )
        """
    ).strip()


def build_niagara_hookup_script(
    *,
    target_system_package_path: str,
    template_system_package_path: str,
    emitter_name: str,
    material_package_path: str,
    grid: str,
    playback_seconds: float | None,
    module_insert_after: str,
) -> str:
    target_ref = package_to_object_ref(target_system_package_path)
    template_ref = package_to_object_ref(template_system_package_path)
    material_ref = package_to_object_ref(material_package_path)
    target_folder = target_system_package_path.rsplit("/", 1)[0]
    target_name = target_system_package_path.rsplit("/", 1)[-1]
    cols, rows = parse_grid(grid)
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary
        NIA = unreal.UnrealBridgeNiagaraLibrary

        TARGET_SYSTEM_PACKAGE_PATH = {target_system_package_path!r}
        TARGET_SYSTEM_REF = {target_ref!r}
        TEMPLATE_SYSTEM_REF = {template_ref!r}
        TARGET_FOLDER = {target_folder!r}
        TARGET_NAME = {target_name!r}
        EMITTER_NAME = {emitter_name!r}
        MATERIAL_REF = {material_ref!r}
        GRID_COLS = {cols}
        GRID_ROWS = {rows}
        PLAYBACK_SECONDS = {playback_seconds!r}
        MODULE_INSERT_AFTER = {module_insert_after!r}

        def run_tool(name, payload):
            result = TR.execute_qualified_tool(name, json.dumps(payload, ensure_ascii=False), True)
            output = None
            if result.json_output:
                try:
                    output = json.loads(result.json_output)
                except Exception:
                    output = result.json_output
            return {{
                "success": bool(result.success),
                "error": result.error,
                "output": output,
            }}

        if not EAL.does_asset_exist(TARGET_SYSTEM_REF):
            duplicate_row = run_tool(
                "toolset_registry.toolsets.core.asset.AssetTools.duplicate",
                {{
                    "path": TEMPLATE_SYSTEM_REF,
                    "new_path": TARGET_SYSTEM_REF,
                }},
            )
            if not duplicate_row["success"]:
                raise RuntimeError(f"Could not duplicate Niagara template {{TEMPLATE_SYSTEM_REF}} -> {{TARGET_SYSTEM_REF}}: {{duplicate_row['error']}}")

        system = unreal.load_asset(TARGET_SYSTEM_PACKAGE_PATH)
        if not system:
            raise RuntimeError(f"Could not load Niagara system {{TARGET_SYSTEM_REF}}")

        renderers = list(NIA.list_system_renderers(TARGET_SYSTEM_REF))
        if not renderers:
            raise RuntimeError(f"No renderers found on Niagara system {{TARGET_SYSTEM_REF}}")

        renderer_path = ""
        patched = 0
        for renderer in renderers:
            if renderer.emitter_name != EMITTER_NAME:
                continue
            if "SpriteRendererProperties" not in str(renderer.renderer_class):
                continue
            renderer_obj = unreal.load_object(None, renderer.renderer_path)
            if not renderer_obj:
                continue
            material = unreal.load_asset(MATERIAL_REF)
            if not material:
                raise RuntimeError(f"Could not load material {{MATERIAL_REF}}")
            renderer_obj.set_editor_property("material", material)
            renderer_obj.set_editor_property("sub_image_size", unreal.Vector2D(float(GRID_COLS), float(GRID_ROWS)))
            renderer_path = renderer.renderer_path
            patched += 1
        if patched == 0:
            raise RuntimeError(f"No sprite renderer found for emitter {{EMITTER_NAME}} on {{TARGET_SYSTEM_REF}}")

        module_probe = NIA.get_official_module_topology(TARGET_SYSTEM_REF, EMITTER_NAME, "ParticleUpdateScript", "SubUVAnimation")
        module_added = False
        if not module_probe.success:
            add_row = NIA.add_official_module(
                TARGET_SYSTEM_REF,
                EMITTER_NAME,
                "ParticleUpdateScript",
                MODULE_INSERT_AFTER,
                "/Niagara/Modules/Update/SubUV/V2/SubUVAnimation.SubUVAnimation",
                True,
            )
            if not add_row.success:
                raise RuntimeError(f"Could not add SubUVAnimation module: {{add_row.error}}")
            module_added = True

        def set_stack(script_name, module_name, input_name, struct_path, value_json):
            row = NIA.set_official_stack_input_data(
                TARGET_SYSTEM_REF,
                EMITTER_NAME,
                script_name,
                module_name,
                [input_name],
                struct_path,
                value_json,
                True,
            )
            return {{
                "success": bool(row.success),
                "error": str(row.error),
                "data_json": str(row.data_json),
                "data_struct_path": str(row.data_struct_path),
            }}

        updates = {{
            "Random Start Frame": set_stack("ParticleUpdateScript", "SubUVAnimation", "Random Start Frame", "/Script/Niagara.NiagaraBool", '{{"value":0}}'),
            "Start Frame Offset": set_stack("ParticleUpdateScript", "SubUVAnimation", "Start Frame Offset", "/Script/Niagara.NiagaraInt32", '{{"value":0}}'),
            "SubUV Lookup Index Scale": set_stack("ParticleUpdateScript", "SubUVAnimation", "SubUV Lookup Index Scale", "/Script/Niagara.NiagaraFloat", '{{"value":1.0}}'),
        }}
        if PLAYBACK_SECONDS is not None and PLAYBACK_SECONDS > 0:
            updates["Lifetime Min"] = set_stack("ParticleSpawnScript", "InitializeParticle", "Lifetime Min", "/Script/Niagara.NiagaraFloat", json.dumps({{"value": float(PLAYBACK_SECONDS)}}, ensure_ascii=False))
            updates["Lifetime Max"] = set_stack("ParticleSpawnScript", "InitializeParticle", "Lifetime Max", "/Script/Niagara.NiagaraFloat", json.dumps({{"value": float(PLAYBACK_SECONDS)}}, ensure_ascii=False))

        compile_state = NIA.get_official_system_compile_state_summary(TARGET_SYSTEM_REF)
        save_row = run_tool(
            "toolset_registry.toolsets.core.asset.AssetTools.save_assets",
            {{
                "asset_paths": [TARGET_SYSTEM_REF],
            }},
        )
        print(
            json.dumps(
                {{
                    "target_system_ref": TARGET_SYSTEM_REF,
                    "renderer_path": renderer_path,
                    "module_added": module_added,
                    "stack_updates": updates,
                    "compile_state": {{
                        "success": bool(compile_state.success),
                        "error": str(compile_state.error),
                        "aggregate_status": str(compile_state.aggregate_status),
                        "has_errors": bool(compile_state.has_errors),
                        "has_warnings": bool(compile_state.has_warnings),
                    }},
                    "save": save_row,
                }},
                ensure_ascii=False,
            )
        )
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    texture_import = report["import_result"].get("texture_import", {})
    route = texture_import.get("route", "unknown")
    route_meaning = {
        "bridge-uassetlibrary": "direct bridge API",
        "bridge-uassetlibrary-reflection": "bridge API via reflection fallback",
        "plugin-python-helper": "plugin Python helper fallback",
    }.get(route, "unknown route")
    lines = [
        "# Flipbook UE Pipeline",
        "",
        f"- Effect: `{report['effect']}`",
        f"- Atlas file: `{report['atlas_file']}`",
        f"- Grid: `{report['grid']}`",
        f"- Texture asset: `{report['texture_asset_path']}`",
        f"- Material asset: `{report['material_asset_path']}`",
        f"- Texture import route: `{route}`",
        f"- Texture import route meaning: `{route_meaning}`",
        "",
        "## Outputs",
        "",
        f"- Pipeline report: `{report['report_path']}`",
        f"- Texture fix report: `{report.get('texture_fix_report', '')}`",
        f"- Material audit report: `{report.get('material_audit_report', '')}`",
    ]
    preview = report.get("preview")
    if preview:
        lines.extend(
            [
                f"- Preview report: `{preview.get('report_path', '')}`",
                f"- Preview png: `{preview.get('shaded_png', '')}`",
                f"- Preview cleanup passed: `{preview.get('cleanup_passed')}`",
                f"- Preview passed: `{preview.get('preview_passed')}`",
            ]
        )
        transient = preview.get("transient_preview") or {}
        if transient:
            lines.extend(
                [
                    f"- Preview transient path: `{transient.get('transient_system_path', '')}`",
                    f"- Preview transient reused: `{transient.get('transient_reused')}`",
                    f"- Preview transient key: `{transient.get('key', '')}`",
                ]
            )
    niagara = report.get("niagara")
    if niagara:
        lines.extend(
            [
                f"- Niagara system: `{niagara.get('system_path', '')}`",
                f"- Niagara audit report: `{niagara.get('niagara_audit_report', '')}`",
                f"- Live asset verify report: `{niagara.get('live_asset_verify_report', '')}`",
                f"- Niagara hooked up: `{niagara.get('hookup_passed')}`",
            ]
        )
    effect_preview = report.get("effect_preview")
    if effect_preview:
        lines.extend(
            [
                f"- Effect preview report: `{effect_preview.get('report_path', '')}`",
                f"- Effect preview png: `{effect_preview.get('preview_png', '')}`",
                f"- Effect approval passed: `{effect_preview.get('approval_passed')}`",
            ]
        )
        review = effect_preview.get("review") or {}
        if review:
            lines.append(f"- Effect preview pending review id: `{review.get('review_id', '')}`")
    promote = report.get("promote")
    if promote:
        naming = promote.get("naming") or {}
        segments = naming.get("segments") or []
        segment_text = " / ".join(f"{item.get('label', '')}={item.get('token', '')}" for item in segments if item.get("token"))
        lines.extend(
            [
                f"- Promote requested policy: `{naming.get('requested_policy', promote.get('policy', ''))}`",
                f"- Promote effective policy: `{naming.get('effective_policy', promote.get('policy', ''))}`",
                f"- Promote template: `{naming.get('template', '')}`",
                f"- Promote mode: `{promote.get('mode', '')}`",
                f"- Promote root: `{promote.get('promote_root', '')}`",
                f"- Promote passed: `{promote.get('promote_passed')}`",
                f"- Promote report: `{promote.get('report_path', '')}`",
            ]
        )
        if segment_text:
            lines.append(f"- Promote naming segments: `{segment_text}`")
    lines.extend(["", "## Verification", ""])
    lines.append(f"- Imported texture exists: `{report['import_result'].get('texture_ref') == report['texture_asset_object_ref']}`")
    texture_params = report["import_result"].get("material_info", {}).get("texture_parameters", [])
    if texture_params:
        for item in texture_params:
            lines.append(f"- Material param `{item['name']}` -> `{item['value']}`")
    else:
        lines.append("- Material reported no texture parameters in the immediate create step.")
    return "\n".join(lines).rstrip() + "\n"


def run_python_cli(tool_path: Path, args: list[str], *, timeout: int) -> str:
    command = [sys.executable, str(tool_path), *args]
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"Tool failed: {' '.join(command)}")
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"Tool returned no output: {' '.join(command)}")
    return lines[-1]


def append_optional_arg(args: list[str], name: str, value: str | None) -> list[str]:
    if value:
        args.extend([name, value])
    return args


def material_skill_root(ctx) -> Path:
    return ctx.skill_root.parent / "unreal-material-artist"


def tool_path(ctx, tool_name: str) -> Path:
    return material_skill_root(ctx) / "tools" / tool_name


def run_preview(
    *,
    ctx,
    client: BridgeClient,
    material_asset_path: str,
    effect: str,
    grid: str,
    carrier: str,
    template_system: str,
    emitter_name_hint: str,
    resolution: int,
    sim_time: float,
) -> dict[str, Any]:
    preview_scripts = material_skill_root(ctx) / "scripts"
    if str(preview_scripts) not in sys.path:
        sys.path.insert(0, str(preview_scripts))
    from unreal_material_tools.material_preview import (
        build_delete_temp_niagara_asset_script,
        build_niagara_preview_script,
        transient_preview_registry_path,
        upsert_transient_preview_entry,
    )

    preview_png = default_report_path(ctx, "previews", effect, f"{slugify(material_asset_path)}-{carrier}-shaded", ".png")
    preview_report = default_report_path(ctx, "previews", effect, f"{slugify(material_asset_path)}-{carrier}", ".json")
    raw = client.exec_json(
        build_niagara_preview_script(
            package_to_object_ref(material_asset_path),
            carrier,
            resolution,
            resolution,
            35.0,
            str(preview_png),
            sim_time,
            template_system,
            emitter_name_hint,
            grid,
        )
    )
    temp_system = str(raw.get("temp_system") or "")
    cleanup = raw.get("cleanup") or {}
    content_asset_created = bool(cleanup.get("content_asset_created", temp_system.startswith("/Game/")))
    if temp_system and content_asset_created:
        post_exec_cleanup = client.exec_json(build_delete_temp_niagara_asset_script(temp_system), no_preflight=True)
        raw["post_exec_cleanup"] = post_exec_cleanup
        if post_exec_cleanup.get("success"):
            cleanup["asset_deleted"] = True
            cleanup["asset_delete_error"] = ""
            cleanup["delete_method"] = "AssetTools.delete (post-exec)"
            raw["cleanup"] = cleanup
    cleanup = raw.get("cleanup") or {}
    cleanup_passed = (
        bool(cleanup.get("actor_destroyed"))
        and (
            not bool(cleanup.get("content_asset_created", False))
            or bool(cleanup.get("asset_deleted"))
        )
    )
    report = {
        "tool": "flipbook_ue_pipeline_preview",
        "material_asset_path": material_asset_path,
        "carrier": carrier,
        "grid": grid,
        "template_system": template_system,
        "emitter_name_hint": emitter_name_hint,
        "raw": raw,
        "cleanup_passed": cleanup_passed,
        "report_path": str(preview_report),
        "shaded_png": str(preview_png),
        "preview_passed": bool(raw.get("shaded_ok"))
        and str(raw.get("renderer_material_path") or "").endswith(package_to_object_ref(material_asset_path))
        and str(raw.get("renderer_subuv_grid") or "") == grid,
    }
    report["preview_passed"] = bool(report["preview_passed"]) and cleanup_passed
    if temp_system.startswith("/Engine/Transient."):
        resolved_template_system = str(raw.get("template_system") or template_system or "/Niagara/DefaultAssets/DefaultSystem.DefaultSystem")
        entry = upsert_transient_preview_entry(
            ctx,
            carrier=carrier,
            template_system=resolved_template_system,
            transient_system_path=temp_system,
            material_path=material_asset_path,
            report_path=str(preview_report),
            preview_png=str(preview_png),
            source_tool="flipbook_ue_pipeline.preview",
            live_exists=True,
        )
        report["transient_preview"] = {
            "key": entry.get("key", ""),
            "transient_name": entry.get("transient_name", ""),
            "transient_system_path": temp_system,
            "transient_reused": bool((cleanup or {}).get("transient_reused")),
            "registry_path": str(transient_preview_registry_path(ctx)),
        }
    save_json(preview_report, report)
    return report


def create_effect_preview_review(
    *,
    ctx,
    effect: str,
    preview_path: str,
    system_path: str,
    material_path: str,
    renderer_path: str,
    grid: str,
    playback_seconds: float | None,
    preview_kind: str,
    carrier: str,
    preset: str,
    notes: str,
) -> dict[str, Any]:
    payload = load_effect_record(ctx, "effect-preview-approvals", effect, effect_preview_approvals_default(effect))
    context = build_context(
        system_path=system_path,
        material_path=material_path,
        renderer_path=renderer_path,
        grid=grid,
        playback_seconds=playback_seconds,
        preview_kind=preview_kind,
        carrier=carrier,
    )
    review = {
        "id": __import__("uuid").uuid4().hex[:12],
        "context_key": context_key(context),
        "context": context,
        "preview_path": preview_path,
        "preset": preset,
        "status": "pending",
        "notes": notes,
        "differences": [],
        "historical_reason": "",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    payload["reviews"].append(review)
    record_path = save_effect_record(ctx, "effect-preview-approvals", effect, payload)
    return {
        "record_path": str(record_path),
        "review_id": review["id"],
        "context_key": review["context_key"],
        "status": review["status"],
    }


def find_approved_effect_preview(
    *,
    ctx,
    effect: str,
    system_path: str,
    material_path: str,
    renderer_path: str,
    grid: str,
    playback_seconds: float | None,
    preview_kind: str,
    carrier: str,
) -> dict[str, Any] | None:
    payload = load_effect_record(ctx, "effect-preview-approvals", effect, effect_preview_approvals_default(effect))
    wanted = context_key(
        build_context(
            system_path=system_path,
            material_path=material_path,
            renderer_path=renderer_path,
            grid=grid,
            playback_seconds=playback_seconds,
            preview_kind=preview_kind,
            carrier=carrier,
        )
    )
    for review in payload.get("reviews", []):
        if review.get("status") != "approved":
            continue
        if review.get("context_key") == wanted:
            return review
    return None


def find_pending_effect_preview(
    *,
    ctx,
    effect: str,
    system_path: str,
    material_path: str,
    renderer_path: str,
    grid: str,
    playback_seconds: float | None,
    preview_kind: str,
    carrier: str,
) -> dict[str, Any] | None:
    payload = load_effect_record(ctx, "effect-preview-approvals", effect, effect_preview_approvals_default(effect))
    wanted = context_key(
        build_context(
            system_path=system_path,
            material_path=material_path,
            renderer_path=renderer_path,
            grid=grid,
            playback_seconds=playback_seconds,
            preview_kind=preview_kind,
            carrier=carrier,
        )
    )
    for review in payload.get("reviews", []):
        if review.get("status") != "pending":
            continue
        if review.get("context_key") == wanted:
            return review
    return None


def run_effect_preview_stage(
    *,
    ctx,
    effect: str,
    system_path: str,
    project: str | None,
    endpoint: str | None,
    timeout: int,
    grid: str,
    material_path: str,
    renderer_path: str,
    playback_seconds: float | None,
    carrier: str,
    preset: str,
    sim_time: float,
    create_pending: bool,
    notes: str,
) -> dict[str, Any]:
    preview_png = run_python_cli(
        ctx.skill_root / "tools" / "controlled_preview.py",
        append_optional_arg(
            append_optional_arg(
                [
                    "--root",
                    str(ctx.project_root),
                    "niagara",
                    system_path,
                    "--preset",
                    preset,
                    "--sim-time",
                    str(sim_time),
                ],
                "--project",
                project,
            ),
            "--endpoint",
            endpoint,
        ),
        timeout=timeout,
    )
    preview_report = str(Path(preview_png).with_suffix(".json"))
    preview_json = json.loads(Path(preview_report).read_text(encoding="utf-8"))
    review = None
    if create_pending:
        review = create_effect_preview_review(
            ctx=ctx,
            effect=effect,
            preview_path=preview_png,
            system_path=system_path,
            material_path=material_path,
            renderer_path=renderer_path,
            grid=grid,
            playback_seconds=playback_seconds,
            preview_kind="still",
            carrier=carrier,
            preset=preset,
            notes=notes,
        )
    approved = find_approved_effect_preview(
        ctx=ctx,
        effect=effect,
        system_path=system_path,
        material_path=material_path,
        renderer_path=renderer_path,
        grid=grid,
        playback_seconds=playback_seconds,
        preview_kind="still",
        carrier=carrier,
    )
    pending = find_pending_effect_preview(
        ctx=ctx,
        effect=effect,
        system_path=system_path,
        material_path=material_path,
        renderer_path=renderer_path,
        grid=grid,
        playback_seconds=playback_seconds,
        preview_kind="still",
        carrier=carrier,
    )
    return {
        "report_path": preview_report,
        "preview_png": preview_png,
        "preview_json": preview_json,
        "review": review,
        "approved_review": approved,
        "pending_review": pending,
        "approval_passed": approved is not None,
    }


def run_niagara_stage(
    *,
    ctx,
    client: BridgeClient,
    effect: str,
    texture_asset_path: str,
    material_asset_path: str,
    atlas_file: Path,
    grid: str,
    system_path: str,
    template_system: str,
    emitter_name: str,
    playback_seconds: float | None,
    module_insert_after: str,
    project: str | None,
    endpoint: str | None,
    timeout: int,
) -> dict[str, Any]:
    hookup = client.exec_json(
        build_niagara_hookup_script(
            target_system_package_path=system_path,
            template_system_package_path=template_system,
            emitter_name=emitter_name,
            material_package_path=material_asset_path,
            grid=grid,
            playback_seconds=playback_seconds,
            module_insert_after=module_insert_after,
        )
    )

    live_asset_verify_report = run_python_cli(
        ctx.skill_root / "tools" / "live_asset_verify.py",
        append_optional_arg(
            append_optional_arg(
                [
            "--root",
            str(ctx.project_root),
            "--effect",
            effect,
            "--local-file",
            str(atlas_file),
            "--source-policy",
            "generated",
            "--texture-asset-path",
            texture_asset_path,
            "--material-path",
            material_asset_path,
            "--renderer-path",
            str(hookup.get("renderer_path") or ""),
                ],
                "--project",
                project,
            ),
            "--endpoint",
            endpoint,
        ),
        timeout=timeout,
    )

    niagara_audit_report = run_python_cli(
        ctx.skill_root / "tools" / "niagara_audit.py",
        append_optional_arg(
            append_optional_arg(
                [
            "--root",
            str(ctx.project_root),
            system_path,
                ],
                "--project",
                project,
            ),
            "--endpoint",
            endpoint,
        ),
        timeout=timeout,
    )

    live_verify_json = json.loads(Path(live_asset_verify_report).read_text(encoding="utf-8"))
    niagara_audit_json = json.loads(Path(niagara_audit_report).read_text(encoding="utf-8"))
    emitter_summary = next((item for item in niagara_audit_json.get("emitters", []) if item.get("name") == emitter_name), {})
    module_names = emitter_summary.get("parsed", {}).get("function_names", []) or []
    hookup_passed = (
        bool(live_verify_json.get("verification_passed"))
        and "SubUVAnimation" in module_names
        and not hookup.get("compile_state", {}).get("has_errors")
    )
    return {
        "system_path": system_path,
        "template_system": template_system,
        "emitter_name": emitter_name,
        "renderer_path": hookup.get("renderer_path", ""),
        "hookup": hookup,
        "live_asset_verify_report": live_asset_verify_report,
        "niagara_audit_report": niagara_audit_report,
        "hookup_passed": hookup_passed,
    }


def build_promote_script(
    *,
    texture_asset_path: str,
    material_asset_path: str,
    niagara_system_path: str,
    target_texture_path: str,
    target_material_path: str,
    target_niagara_path: str,
    parameter_name: str,
    emitter_name: str,
    grid: str,
    mode: str,
    save_assets: bool,
) -> str:
    texture_src_ref = package_to_object_ref(texture_asset_path)
    material_src_ref = package_to_object_ref(material_asset_path)
    niagara_src_ref = package_to_object_ref(niagara_system_path) if niagara_system_path else ""
    texture_dst_ref = package_to_object_ref(target_texture_path)
    material_dst_ref = package_to_object_ref(target_material_path)
    niagara_dst_ref = package_to_object_ref(target_niagara_path) if target_niagara_path else ""
    cols, rows = parse_grid(grid)
    return textwrap.dedent(
        f"""
        import json
        import unreal

        EAL = unreal.EditorAssetLibrary
        TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
        MAT = unreal.UnrealBridgeMaterialLibrary
        NIA = unreal.UnrealBridgeNiagaraLibrary
        TR = unreal.UnrealBridgeToolsetRegistryLibrary

        TEXTURE_SRC_REF = {texture_src_ref!r}
        MATERIAL_SRC_REF = {material_src_ref!r}
        NIAGARA_SRC_REF = {niagara_src_ref!r}
        TEXTURE_DST_REF = {texture_dst_ref!r}
        MATERIAL_DST_REF = {material_dst_ref!r}
        NIAGARA_DST_REF = {niagara_dst_ref!r}
        PARAMETER_NAME = {parameter_name!r}
        EMITTER_NAME = {emitter_name!r}
        GRID_COLS = {cols}
        GRID_ROWS = {rows}
        MODE = {mode!r}
        SAVE_ASSETS = {save_assets!r}

        def package_path(path):
            path = (path or "").split(".", 1)[0]
            return path

        def split_target(path):
            pkg = package_path(path)
            folder, name = pkg.rsplit("/", 1)
            return folder, name

        def run_tool(name, payload):
            result = TR.execute_qualified_tool(name, json.dumps(payload, ensure_ascii=False), True)
            output = None
            if result.json_output:
                try:
                    output = json.loads(result.json_output)
                except Exception:
                    output = result.json_output
            return {{
                "success": bool(result.success),
                "error": result.error,
                "output": output,
            }}

        def move_or_duplicate(source_ref, target_ref):
            row = {{
                "source": source_ref,
                "target": target_ref,
                "mode": MODE,
                "success": False,
                "error": "",
            }}
            if not source_ref or not target_ref:
                row["error"] = "missing source or target"
                return row
            try:
                if not EAL.does_asset_exist(source_ref):
                    row["error"] = "source asset missing"
                    return row
                if EAL.does_asset_exist(target_ref):
                    row["error"] = "target asset already exists"
                    return row
                if MODE == "duplicate":
                    folder, name = split_target(target_ref)
                    source_asset = unreal.load_asset(source_ref)
                    created = TOOLS.duplicate_asset(name, folder, source_asset)
                    row["success"] = created is not None
                else:
                    row["success"] = bool(EAL.rename_asset(source_ref, target_ref))
                if row["success"] and SAVE_ASSETS:
                    EAL.save_asset(target_ref, False)
            except Exception as exc:
                row["error"] = str(exc)
            return row

        def patch_material_texture(mat_ref, texture_ref):
            graph = MAT.get_material_graph(mat_ref)
            for node in list(graph.nodes):
                if str(node.class_name) not in ["TextureSampleParameterSubUV", "TextureSampleParameter2D"]:
                    continue
                if f"ParameterName={{PARAMETER_NAME}}" in str(node.key_properties):
                    ok = MAT.set_material_expression_property(mat_ref, node.guid, "Texture", texture_ref)
                    return {{
                        "success": bool(ok),
                        "error": "" if ok else "set_material_expression_property returned false",
                    }}
            return {{
                "success": False,
                "error": f"Texture parameter node `{{PARAMETER_NAME}}` not found",
            }}

        def patch_niagara_system(system_ref, material_ref):
            renderers = list(NIA.list_system_renderers(system_ref))
            patched = 0
            renderer_path = ""
            material = unreal.load_asset(material_ref)
            for renderer in renderers:
                if renderer.emitter_name != EMITTER_NAME:
                    continue
                if "SpriteRendererProperties" not in str(renderer.renderer_class):
                    continue
                renderer_obj = unreal.load_object(None, renderer.renderer_path)
                if not renderer_obj:
                    continue
                renderer_obj.set_editor_property("material", material)
                renderer_obj.set_editor_property("sub_image_size", unreal.Vector2D(float(GRID_COLS), float(GRID_ROWS)))
                renderer_path = renderer.renderer_path
                patched += 1
            if patched == 0:
                return {{
                    "success": False,
                    "error": f"No sprite renderer found for emitter `{{EMITTER_NAME}}`",
                    "renderer_path": "",
                }}
            return {{
                "success": True,
                "error": "",
                "renderer_path": renderer_path,
            }}

        texture_row = move_or_duplicate(TEXTURE_SRC_REF, TEXTURE_DST_REF)
        material_row = move_or_duplicate(MATERIAL_SRC_REF, MATERIAL_DST_REF)
        niagara_row = {{
            "source": NIAGARA_SRC_REF,
            "target": NIAGARA_DST_REF,
            "mode": MODE,
            "success": True,
            "error": "",
        }}
        if NIAGARA_SRC_REF and NIAGARA_DST_REF:
            niagara_row = move_or_duplicate(NIAGARA_SRC_REF, NIAGARA_DST_REF)

        actual_texture_ref = TEXTURE_DST_REF if texture_row["success"] else TEXTURE_SRC_REF
        actual_material_ref = MATERIAL_DST_REF if material_row["success"] else MATERIAL_SRC_REF
        actual_niagara_ref = NIAGARA_DST_REF if (NIAGARA_SRC_REF and niagara_row["success"]) else NIAGARA_SRC_REF

        material_patch = patch_material_texture(actual_material_ref, actual_texture_ref)
        niagara_patch = {{"success": False, "error": "no niagara system", "renderer_path": ""}}
        if actual_niagara_ref:
            niagara_patch = patch_niagara_system(actual_niagara_ref, actual_material_ref)

        compile_state = None
        if actual_niagara_ref:
            state = NIA.get_official_system_compile_state_summary(actual_niagara_ref)
            compile_state = {{
                "success": bool(state.success),
                "error": str(state.error),
                "aggregate_status": str(state.aggregate_status),
                "has_errors": bool(state.has_errors),
                "has_warnings": bool(state.has_warnings),
            }}

        save_targets = [actual_texture_ref, actual_material_ref]
        if actual_niagara_ref:
            save_targets.append(actual_niagara_ref)
        save_row = run_tool(
            "toolset_registry.toolsets.core.asset.AssetTools.save_assets",
            {{
                "asset_paths": save_targets,
            }},
        )

        print(
            json.dumps(
                {{
                    "mode": MODE,
                    "texture": texture_row,
                    "material": material_row,
                    "niagara": niagara_row,
                    "material_patch": material_patch,
                    "niagara_patch": niagara_patch,
                    "actual_texture_ref": actual_texture_ref,
                    "actual_material_ref": actual_material_ref,
                    "actual_niagara_ref": actual_niagara_ref,
                    "compile_state": compile_state,
                    "save": save_row,
                }},
                ensure_ascii=False,
            )
        )
        """
    ).strip()


def run_promote_stage(
    *,
    ctx,
    client: BridgeClient,
    effect: str,
    texture_asset_path: str,
    material_asset_path: str,
    niagara_system_path: str | None,
    grid: str,
    parameter_name: str,
    emitter_name: str,
    promote_details: dict[str, Any],
    promote_root: str,
    promote_mode: str,
    promote_dry_run: bool,
    save_assets: bool,
    project: str | None,
    endpoint: str | None,
    timeout: int,
) -> dict[str, Any]:
    paths = derive_default_promote_paths(
        promote_root=promote_root,
        texture_asset_path=texture_asset_path,
        material_asset_path=material_asset_path,
        niagara_system_path=niagara_system_path,
    )
    report_path = default_report_path(ctx, "promoted-assets", effect, "flipbook-ue-promote", ".json")
    if promote_dry_run:
        report = {
            "tool": "flipbook_ue_pipeline_promote",
            "policy": promote_details.get("effective_policy", ""),
            "mode": promote_mode,
            "dry_run": True,
            "promote_root": promote_root,
            "naming": promote_details,
            "source_texture_asset_path": texture_asset_path,
            "source_material_asset_path": material_asset_path,
            "source_niagara_system_path": niagara_system_path or "",
            "target_texture_asset_path": paths["texture"],
            "target_material_asset_path": paths["material"],
            "target_niagara_system_path": paths.get("niagara", ""),
            "report_path": str(report_path),
            "promote_passed": True,
        }
        save_json(report_path, report)
        return report

    raw = client.exec_json(
        build_promote_script(
            texture_asset_path=texture_asset_path,
            material_asset_path=material_asset_path,
            niagara_system_path=niagara_system_path or "",
            target_texture_path=paths["texture"],
            target_material_path=paths["material"],
            target_niagara_path=paths.get("niagara", ""),
            parameter_name=parameter_name,
            emitter_name=emitter_name,
            grid=grid,
            mode=promote_mode,
            save_assets=save_assets,
        )
    )

    actual_texture_asset_path = package_path(raw.get("actual_texture_ref") or texture_asset_path)
    actual_material_asset_path = package_path(raw.get("actual_material_ref") or material_asset_path)
    actual_niagara_system_path = package_path(raw.get("actual_niagara_ref") or (niagara_system_path or ""))
    promote_passed = (
        raw.get("texture", {}).get("success")
        and raw.get("material", {}).get("success")
        and raw.get("material_patch", {}).get("success")
        and (not niagara_system_path or raw.get("niagara_patch", {}).get("success"))
        and not (raw.get("compile_state") or {}).get("has_errors", False)
    )

    live_asset_verify_report = ""
    niagara_audit_report = ""
    if actual_niagara_system_path:
        live_asset_verify_report = run_python_cli(
            ctx.skill_root / "tools" / "live_asset_verify.py",
            append_optional_arg(
                append_optional_arg(
                    [
                        "--root",
                        str(ctx.project_root),
                        "--effect",
                        effect,
                        "--source-policy",
                        "ue-only",
                        "--texture-asset-path",
                        actual_texture_asset_path,
                        "--material-path",
                        actual_material_asset_path,
                        "--renderer-path",
                        str(raw.get("niagara_patch", {}).get("renderer_path") or ""),
                    ],
                    "--project",
                    project,
                ),
                "--endpoint",
                endpoint,
            ),
            timeout=timeout,
        )
        niagara_audit_report = run_python_cli(
            ctx.skill_root / "tools" / "niagara_audit.py",
            append_optional_arg(
                append_optional_arg(
                    [
                        "--root",
                        str(ctx.project_root),
                        actual_niagara_system_path,
                    ],
                    "--project",
                    project,
                ),
                "--endpoint",
                endpoint,
            ),
            timeout=timeout,
        )
        live_verify_json = json.loads(Path(live_asset_verify_report).read_text(encoding="utf-8"))
        promote_passed = promote_passed and bool(live_verify_json.get("verification_passed"))

    report = {
        "tool": "flipbook_ue_pipeline_promote",
        "policy": promote_details.get("effective_policy", ""),
        "mode": promote_mode,
        "dry_run": False,
        "promote_root": promote_root,
        "naming": promote_details,
        "source_texture_asset_path": texture_asset_path,
        "source_material_asset_path": material_asset_path,
        "source_niagara_system_path": niagara_system_path or "",
        "target_texture_asset_path": paths["texture"],
        "target_material_asset_path": paths["material"],
        "target_niagara_system_path": paths.get("niagara", ""),
        "actual_texture_asset_path": actual_texture_asset_path,
        "actual_material_asset_path": actual_material_asset_path,
        "actual_niagara_system_path": actual_niagara_system_path,
        "raw": raw,
        "live_asset_verify_report": live_asset_verify_report,
        "niagara_audit_report": niagara_audit_report,
        "promote_passed": promote_passed,
        "report_path": str(report_path),
    }
    save_json(report_path, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-click local atlas -> UE texture -> SubUV material pipeline.")
    parser.add_argument("atlas_file")
    parser.add_argument("--grid", required=True, help="SubUV grid, e.g. 8x8 or 16x16.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect", default="")
    parser.add_argument("--texture-asset-path", default="")
    parser.add_argument("--material-asset-path", default="")
    parser.add_argument("--parameter-name", default="FlipbookTexture")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--preview-carrier", default="sprite", choices=["sprite", "ribbon"])
    parser.add_argument("--preview-template-system", default="/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke")
    parser.add_argument("--preview-emitter", default="Smoke")
    parser.add_argument("--preview-resolution", type=int, default=768)
    parser.add_argument("--preview-sim-time", type=float, default=1.0)
    parser.add_argument("--effect-preview", action="store_true")
    parser.add_argument("--effect-preview-preset", default="niagara-sandbox")
    parser.add_argument("--effect-preview-sim-time", type=float, default=1.25)
    parser.add_argument("--approval-create-pending", action="store_true")
    parser.add_argument("--approval-notes", default="")
    parser.add_argument("--niagara-hookup", action="store_true")
    parser.add_argument("--niagara-system-path", default="")
    parser.add_argument("--niagara-template-system", default="/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke")
    parser.add_argument("--niagara-emitter", default="Smoke")
    parser.add_argument("--niagara-playback-seconds", type=float)
    parser.add_argument("--niagara-module-insert-after", default="ScaleColor")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--promote-root", default="")
    parser.add_argument("--promote-policy", choices=PROMOTE_POLICY_CHOICES, default="vfx-effect")
    parser.add_argument("--promote-base", default="/Game/VFX")
    parser.add_argument("--promote-group", default="Codex")
    parser.add_argument("--promote-studio", default="Studio")
    parser.add_argument("--promote-project-name", default="Project")
    parser.add_argument("--promote-effect-family", default="Shared")
    parser.add_argument("--promote-effect-name", default="")
    parser.add_argument("--promote-mode", choices=["move", "duplicate"], default="duplicate")
    parser.add_argument("--promote-dry-run", action="store_true")
    parser.add_argument("--promote-save-assets", action="store_true")
    parser.add_argument("--allow-promote-without-approved-preview", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    parse_grid(args.grid)
    ctx = resolve_root_context(args.root)
    atlas_file = Path(args.atlas_file).expanduser().resolve()
    if not atlas_file.exists():
        raise SystemExit(f"Atlas file does not exist: {atlas_file}")

    effect = args.effect or atlas_file.stem
    manifest = load_adjacent_manifest(atlas_file)
    texture_asset_path, material_asset_path = (
        (args.texture_asset_path, args.material_asset_path)
        if args.texture_asset_path and args.material_asset_path
        else derive_default_asset_paths(effect)
    )
    texture_asset_object_ref = package_to_object_ref(texture_asset_path)
    material_asset_object_ref = package_to_object_ref(material_asset_path)

    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    import_result = client.exec_json(
        build_import_and_material_script(
            atlas_file=str(atlas_file),
            texture_package_path=texture_asset_path,
            material_package_path=material_asset_path,
            parameter_name=args.parameter_name,
        )
    )

    texture_fix_report = run_python_cli(
        tool_path(ctx, "texture_import_fix.py"),
        append_optional_arg(
            append_optional_arg(
                [
            texture_asset_path,
            "--root",
            str(ctx.project_root),
            "--role",
            "atlas",
            "--flavor",
            "color",
            "--grid",
            args.grid,
            "--apply",
                ],
                "--project",
                args.project,
            ),
            "--endpoint",
            args.endpoint,
        ),
        timeout=args.timeout,
    )

    material_audit_report = run_python_cli(
        tool_path(ctx, "material_audit.py"),
        append_optional_arg(
            append_optional_arg(
                [
            material_asset_path,
            "--root",
            str(ctx.project_root),
                ],
                "--project",
                args.project,
            ),
            "--endpoint",
            args.endpoint,
        ),
        timeout=args.timeout,
    )

    preview_report = None
    if args.preview:
        preview_report = run_preview(
            ctx=ctx,
            client=client,
            material_asset_path=material_asset_path,
            effect=effect,
            grid=args.grid,
            carrier=args.preview_carrier,
            template_system=args.preview_template_system,
            emitter_name_hint=args.preview_emitter,
            resolution=args.preview_resolution,
            sim_time=args.preview_sim_time,
        )

    niagara_report = None
    if args.niagara_hookup:
        playback_seconds = args.niagara_playback_seconds
        if playback_seconds is None:
            playback_seconds = manifest_playback_seconds(manifest)
        system_path = args.niagara_system_path or derive_default_niagara_system_path(effect)
        niagara_report = run_niagara_stage(
            ctx=ctx,
            client=client,
            effect=effect,
            texture_asset_path=texture_asset_path,
            material_asset_path=material_asset_path,
            atlas_file=atlas_file,
            grid=args.grid,
            system_path=system_path,
            template_system=args.niagara_template_system,
            emitter_name=args.niagara_emitter,
            playback_seconds=playback_seconds,
            module_insert_after=args.niagara_module_insert_after,
            project=args.project,
            endpoint=args.endpoint,
            timeout=args.timeout,
        )

    effect_preview_report = None
    active_system_path = (niagara_report or {}).get("system_path") or args.niagara_system_path or ""
    active_renderer_path = (niagara_report or {}).get("renderer_path") or ""
    active_playback_seconds = args.niagara_playback_seconds
    if active_playback_seconds is None:
        active_playback_seconds = manifest_playback_seconds(manifest)
    if args.effect_preview:
        if not active_system_path:
            raise SystemExit("--effect-preview requires an active Niagara system path; use --niagara-hookup or --niagara-system-path.")
        effect_preview_report = run_effect_preview_stage(
            ctx=ctx,
            effect=effect,
            system_path=active_system_path,
            project=args.project,
            endpoint=args.endpoint,
            timeout=args.timeout,
            grid=args.grid,
            material_path=material_asset_path,
            renderer_path=active_renderer_path,
            playback_seconds=active_playback_seconds,
            carrier="sprite",
            preset=args.effect_preview_preset,
            sim_time=args.effect_preview_sim_time,
            create_pending=args.approval_create_pending,
            notes=args.approval_notes,
        )

    promote_report = None
    if args.promote:
        promote_details = resolve_promote_details(
            effect=effect,
            explicit_root=args.promote_root,
            promote_policy=args.promote_policy,
            promote_base=args.promote_base,
            promote_group=args.promote_group,
            promote_effect_name=args.promote_effect_name,
            promote_studio=args.promote_studio,
            promote_project_name=args.promote_project_name,
            promote_effect_family=args.promote_effect_family,
        )
        resolved_promote_root = str(promote_details.get("promote_root") or "")
        if not resolved_promote_root:
            raise SystemExit("--promote requires either --promote-root or a promotable policy.")
        if not resolved_promote_root.startswith("/Game/VFX/") and resolved_promote_root != "/Game/VFX":
            raise SystemExit(f"Promote root must stay under /Game/VFX for formal production promotion. Got: {resolved_promote_root}")
        if not args.promote_dry_run and not args.allow_promote_without_approved_preview:
            approved = find_approved_effect_preview(
                ctx=ctx,
                effect=effect,
                system_path=active_system_path,
                material_path=material_asset_path,
                renderer_path=active_renderer_path,
                grid=args.grid,
                playback_seconds=active_playback_seconds,
                preview_kind="still",
                carrier="sprite",
            )
            if approved is None:
                pending = find_pending_effect_preview(
                    ctx=ctx,
                    effect=effect,
                    system_path=active_system_path,
                    material_path=material_asset_path,
                    renderer_path=active_renderer_path,
                    grid=args.grid,
                    playback_seconds=active_playback_seconds,
                    preview_kind="still",
                    carrier="sprite",
                )
                pending_text = f" Pending review id: {pending.get('id')}" if pending else ""
                raise SystemExit(
                    "Promote gate failed: no approved effect preview for the current system/material/grid context."
                    f"{pending_text} Use tools\\effect_preview_approval.py decide --effect {effect} --review-id <id> --status approved after visual review."
                )
        promote_report = run_promote_stage(
            ctx=ctx,
            client=client,
            effect=effect,
            texture_asset_path=texture_asset_path,
            material_asset_path=material_asset_path,
            niagara_system_path=(niagara_report or {}).get("system_path") or args.niagara_system_path or "",
            grid=args.grid,
            parameter_name=args.parameter_name,
            emitter_name=args.niagara_emitter,
            promote_details=promote_details,
            promote_root=resolved_promote_root,
            promote_mode=args.promote_mode,
            promote_dry_run=args.promote_dry_run,
            save_assets=args.promote_save_assets,
            project=args.project,
            endpoint=args.endpoint,
            timeout=args.timeout,
        )
        promote_report["policy"] = str(promote_details.get("effective_policy") or args.promote_policy)
        promote_report["naming"] = promote_details
        promote_report["promote_root"] = resolved_promote_root

    report_path = default_report_path(ctx, "flipbook-ue-pipeline", effect, "flipbook-ue-pipeline", ".json")
    report = {
        "tool": "flipbook_ue_pipeline",
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "atlas_file": str(atlas_file),
        "adjacent_manifest_path": str(adjacent_manifest_path(atlas_file) or ""),
        "adjacent_manifest_grid": manifest_grid(manifest) or "",
        "adjacent_manifest_playback_seconds": manifest_playback_seconds(manifest),
        "grid": args.grid,
        "texture_asset_path": texture_asset_path,
        "texture_asset_object_ref": texture_asset_object_ref,
        "material_asset_path": material_asset_path,
        "material_asset_object_ref": material_asset_object_ref,
        "parameter_name": args.parameter_name,
        "import_result": import_result,
        "texture_fix_report": texture_fix_report,
        "material_audit_report": material_audit_report,
        "preview": preview_report,
        "niagara": niagara_report,
        "effect_preview": effect_preview_report,
        "promote": promote_report,
        "report_path": str(report_path),
    }
    save_json(report_path, report)
    if args.markdown:
        write_text(report_path.with_suffix(".md"), render_markdown(report))
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
