from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, normalize_cli_global_args, resolve_root_context, save_json, slugify, write_text
from .delivery_package import check_delivery_payload, find_latest_delivery_index, load_delivery_payload
from . import delivery_package as delivery_package_module
from . import niagara_audit as niagara_audit_module
from .effect_state import acceptance_default, asset_plan_default, load_effect_record


PLAN_VERSION = 1
SUPPORTED_OPS = {
    "duplicate_asset",
    "create_material_instance",
    "add_emitter_to_system_from_asset",
    "duplicate_emitter_in_system",
    "remove_emitter_from_system",
    "set_emitter_enabled_in_system",
    "toolset_get_system_info",
    "toolset_get_system_topology",
    "toolset_get_emitter_topology",
    "toolset_get_module_topology",
    "toolset_get_stack_input_data",
    "toolset_set_stack_input_data",
    "toolset_add_module",
    "toolset_remove_module",
    "toolset_set_module_enabled",
    "toolset_get_system_compile_state",
    "toolset_get_stack_issues",
    "toolset_apply_stack_issue_fix",
    "add_ribbon_renderer",
    "set_mi_params",
    "set_niagara_system_props",
    "patch_renderer_material",
    "set_u_property_export",
    "save_assets",
}

SEMANTIC_ENABLED_OPS = {
    "set_emitter_enabled_in_system",
    "toolset_set_module_enabled",
}


def full_object_path(path: str) -> str:
    clean = path.strip()
    match = re.search(r"'([^']+)'", clean)
    if match:
        clean = match.group(1)
    if not clean:
        return clean
    last = clean.rsplit("/", 1)[-1]
    if "." in last:
        return clean
    return f"{clean}.{last}"


def package_path(path: str) -> str:
    return full_object_path(path).split(".", 1)[0]


def asset_folder_from_path(path: str) -> str:
    return package_path(path).rsplit("/", 1)[0]


def asset_token(text: str) -> str:
    token = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_")
    return token or "Layer"


def plan_path(ctx, effect: str, stem: str = "mutation-plan") -> Path:
    return default_report_path(ctx, "ue-mutation-plans", effect, stem, ".json")


def script_path(ctx, effect: str, stem: str = "apply-niagara-plan") -> Path:
    return default_report_path(ctx, "ue-mutation-plans", effect, stem, ".py")


def result_path(ctx, effect: str, stem: str = "apply-result") -> Path:
    return default_report_path(ctx, "ue-mutation-plans", effect, stem, ".json")


def load_plan(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_plan(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    save_json(target, payload)
    return target


def make_plan(effect: str, mode: str, target_system: str, project: str = "", notes: str = "") -> dict[str, Any]:
    return {
        "version": PLAN_VERSION,
        "tool": "niagara_asset_assistant",
        "effect_name": effect,
        "mode": mode,
        "project": project,
        "target_system": target_system,
        "notes": notes,
        "safety": {
            "dry_run_default": True,
            "requires_apply_flag": True,
            "delete_ops_allowed": False,
            "template_first": True,
        },
        "operations": [],
        "warnings": [],
    }


def renderer_parent_map(items: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        mapping[key.strip().lower()] = value.strip()
    return mapping


def pick_parent_for_renderers(renderers: list[str], default_parent: str, mapping: dict[str, str]) -> str:
    for renderer in renderers:
        hit = mapping.get(str(renderer).strip().lower())
        if hit:
            return hit
    return default_parent


def parse_param_set(items: list[str]) -> list[dict[str, str]]:
    params: list[dict[str, str]] = []
    for item in items:
        parts = item.split("=", 2)
        if len(parts) != 3:
            raise ValueError(f"Param must be name=type=value: {item}")
        params.append({"name": parts[0], "type": parts[1], "value": parts[2]})
    return params


def op_summary(op: dict[str, Any]) -> str:
    kind = op.get("op", "")
    if kind == "duplicate_asset":
        return f"duplicate `{op.get('source')}` -> `{op.get('target')}`"
    if kind == "create_material_instance":
        return f"create MI `{op.get('target')}` parent=`{op.get('parent')}`"
    if kind == "add_emitter_to_system_from_asset":
        return f"add emitter asset `{op.get('emitter_asset_path')}` to system `{op.get('system_path')}` as `{op.get('new_emitter_name') or 'auto'}`"
    if kind == "duplicate_emitter_in_system":
        return f"duplicate emitter `{op.get('source_emitter_name')}` in `{op.get('system_path')}` as `{op.get('new_emitter_name') or 'auto'}`"
    if kind == "remove_emitter_from_system":
        return f"remove emitter `{op.get('emitter_name')}` from `{op.get('system_path')}`"
    if kind == "set_emitter_enabled_in_system":
        return f"set emitter `{op.get('emitter_name')}` enabled=`{op.get('enabled')}` in `{op.get('system_path')}`"
    if kind == "toolset_get_system_info":
        return f"official get system info `{op.get('system_path')}`"
    if kind == "toolset_get_system_topology":
        return f"official get system topology `{op.get('system_path')}`"
    if kind == "toolset_get_emitter_topology":
        return f"official get emitter topology `{op.get('emitter_name')}`"
    if kind == "toolset_get_module_topology":
        return f"official get module topology `{op.get('module_name')}` in `{op.get('script_name')}`"
    if kind == "toolset_get_stack_input_data":
        return f"official get stack input `{op.get('input_name_stack') or op.get('input_name')}` in `{op.get('module_name')}`"
    if kind == "toolset_set_stack_input_data":
        return f"official set stack input `{op.get('input_name_stack') or op.get('input_name')}` in `{op.get('module_name')}`"
    if kind == "toolset_add_module":
        return f"official add module asset `{op.get('module_asset_path')}` into `{op.get('script_name')}`"
    if kind == "toolset_remove_module":
        return f"official remove module `{op.get('module_name')}` from `{op.get('script_name')}`"
    if kind == "toolset_set_module_enabled":
        return f"official set module `{op.get('module_name')}` enabled=`{op.get('enabled')}`"
    if kind == "toolset_get_system_compile_state":
        return f"official get compile state `{op.get('system_path')}`"
    if kind == "toolset_get_stack_issues":
        return f"official get stack issues `{op.get('system_path')}`"
    if kind == "toolset_apply_stack_issue_fix":
        return f"official apply stack issue fix `{op.get('issue_id')}` / `{op.get('fix_id')}`"
    if kind == "add_ribbon_renderer":
        return f"add Ribbon Renderer to `{op.get('emitter_path') or op.get('emitter_name_contains')}` material=`{op.get('material_path')}`"
    if kind == "set_mi_params":
        return f"set {len(op.get('params', []))} MI params on `{op.get('material_instance')}`"
    if kind == "set_niagara_system_props":
        return f"set Niagara system props on `{op.get('system_path')}`"
    if kind == "patch_renderer_material":
        return f"patch renderer material to `{op.get('material_path')}`"
    if kind == "set_u_property_export":
        return f"set UPROPERTY `{op.get('property_path')}` on `{op.get('object_path')}`"
    if kind == "save_assets":
        return f"save {len(op.get('asset_paths', []))} assets"
    return kind or "unknown"


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# Niagara Asset Mutation Plan: {plan.get('effect_name', '')}",
        "",
        f"- Mode: `{plan.get('mode', '')}`",
        f"- Target system: `{plan.get('target_system', '')}`",
        f"- Project: `{plan.get('project', '') or 'default bridge project'}`",
        f"- Dry-run default: `{plan.get('safety', {}).get('dry_run_default', True)}`",
        "",
        "## Operations",
        "",
    ]
    for index, op in enumerate(plan.get("operations", []), start=1):
        enabled = op.get("enabled", True)
        lines.append(f"{index}. [{'enabled' if enabled else 'disabled'}] `{op.get('op')}` {op_summary(op)}")
    if not plan.get("operations"):
        lines.append("- No operations.")
    warnings = plan.get("warnings", [])
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("- No plan warnings.")
    return "\n".join(lines).rstrip() + "\n"


def build_apply_script(plan: dict[str, Any], verify: bool) -> str:
    plan_json = json.dumps(plan, ensure_ascii=False)
    semantic_enabled_ops_json = json.dumps(sorted(SEMANTIC_ENABLED_OPS), ensure_ascii=False)
    return textwrap.dedent(
        f"""
        import hashlib
        import json
        import re
        import unreal

        PLAN = json.loads({plan_json!r})
        SEMANTIC_ENABLED_OPS = set(json.loads({semantic_enabled_ops_json!r}))
        PROP = unreal.UnrealBridgePropertyLibrary
        MAT = unreal.UnrealBridgeMaterialLibrary

        def full_object_path(path):
            path = (path or "").strip()
            match = re.search(r"'([^']+)'", path)
            if match:
                path = match.group(1)
            if not path:
                return path
            last = path.rsplit("/", 1)[-1]
            if "." in last:
                return path
            return path + "." + last

        def package_path(path):
            return full_object_path(path).split(".", 1)[0]

        def split_target(path):
            pkg = package_path(path)
            folder, name = pkg.rsplit("/", 1)
            return folder, name

        def asset_exists(path):
            return bool(unreal.EditorAssetLibrary.does_asset_exist(package_path(path)))

        def read_export(path, prop_name):
            text, ok = PROP.get_u_property_as_export_text(path, prop_name)
            return text or "", bool(ok)

        def material_paths(text):
            return sorted(set(re.findall(r"/(?:Game|Engine)/[^'\\\",)]+", text or "")))

        def parse_renderer_objects(renderer_text):
            objects = []
            for class_path, object_path in re.findall(r"(/Script/[^']+)'([^']+)'", renderer_text or ""):
                material_text, material_ok = read_export(object_path, "Material")
                objects.append({{
                    "class_path": class_path,
                    "class_name": class_path.rsplit(".", 1)[-1],
                    "object_path": object_path,
                    "material": {{"success": material_ok, "text": material_text}},
                }})
            return objects

        def versioned_renderers(system_path):
            if not hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                return []
            rows = []
            for item in unreal.UnrealBridgeNiagaraLibrary.list_system_renderers(system_path):
                rows.append({{
                    "emitter_name": item.emitter_name,
                    "emitter_path": item.emitter_path,
                    "emitter_version": item.emitter_version,
                    "class_path": item.renderer_class,
                    "class_name": item.renderer_class.rsplit(".", 1)[-1],
                    "object_path": item.renderer_path,
                    "material_path": item.material_path,
                    "source": "versioned-emitter-data",
                }})
            return rows

        def digest(text):
            return hashlib.sha1((text or "").encode("utf-8", errors="ignore")).hexdigest()[:12]

        def as_list(value):
            if value is None or value == "":
                return []
            if isinstance(value, list):
                return [str(item) for item in value if str(item)]
            return [str(value)]

        def make_mi_param(item):
            param = unreal.BridgeMIParamSet()
            param.name = str(item.get("name", ""))
            param.type = str(item.get("type", ""))
            param.value = str(item.get("value", ""))
            return param

        def parse_json_text(text):
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return None

        def execute_toolset_qualified(qualified_tool_name, payload):
            lib = getattr(unreal, "UnrealBridgeToolsetRegistryLibrary", None)
            if lib is None:
                return {{
                    "success": False,
                    "error": "UnrealBridgeToolsetRegistryLibrary not available",
                    "qualified_tool_name": qualified_tool_name,
                }}
            json_input = json.dumps(payload, ensure_ascii=False)
            result = lib.execute_qualified_tool(qualified_tool_name, json_input, True)
            return {{
                "success": bool(result.success),
                "resolved_by_alias": bool(result.resolved_by_alias),
                "requested_toolset_name": result.requested_toolset_name,
                "resolved_toolset_name": result.resolved_toolset_name,
                "tool_name": result.tool_name,
                "qualified_tool_name": result.qualified_tool_name or qualified_tool_name,
                "json_input": result.json_input,
                "json_output": result.json_output,
                "parsed_output": parse_json_text(result.json_output),
                "error": result.error,
            }}

        def compact_official_result(result, *, include_full_output=False):
            compact = {{
                "success": bool(result.get("success")),
                "route": "official-toolset",
                "requested_toolset_name": result.get("requested_toolset_name", ""),
                "resolved_toolset_name": result.get("resolved_toolset_name", ""),
                "tool_name": result.get("tool_name", ""),
                "qualified_tool_name": result.get("qualified_tool_name", ""),
                "error": result.get("error", ""),
            }}
            parsed = result.get("parsed_output")
            if include_full_output:
                compact["official_result"] = result
            elif parsed is not None:
                compact["parsed_output"] = parsed
            return compact

        def find_emitter_snapshot(snapshot, emitter_name):
            if not snapshot:
                return None
            target = (emitter_name or "").lower()
            for emitter in snapshot.get("emitters", []):
                if str(emitter.get("name", "")).lower() == target or str(emitter.get("id_name", "")).lower() == target:
                    return emitter
            return None

        def make_toolset_system_ref(system_path):
            return {{"refPath": full_object_path(system_path)}}

        def _string_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return [str(item) for item in value]
            if value == "":
                return []
            return [str(value)]

        def make_toolset_stack_ref(op, field_name="stack_item_ref"):
            if isinstance(op.get(field_name), dict):
                ref = dict(op.get(field_name))
            else:
                system_path = op.get("system_path") or PLAN.get("target_system", "")
                ref = {{
                    "system": make_toolset_system_ref(system_path),
                    "emitterName": str(op.get("emitter_name", "")),
                    "scriptName": str(op.get("script_name", "")),
                    "moduleName": str(op.get("module_name", "")),
                    "rendererIndex": int(op.get("renderer_index", -1)),
                    "inputNameStack": _string_list(op.get("input_name_stack") or op.get("input_name")),
                }}
            system_ref = ref.get("system")
            if isinstance(system_ref, str):
                ref["system"] = make_toolset_system_ref(system_ref)
            elif isinstance(system_ref, dict) and "refPath" not in system_ref and "system_path" in system_ref:
                ref["system"] = make_toolset_system_ref(system_ref.get("system_path", ""))
            return ref

        def inspect_niagara_system(system_path):
            system_props = {{}}
            for name in ["EmitterHandles", "EffectType", "FixedBounds", "WarmupTickCount", "WarmupTickDelta", "SystemScalabilityOverrides"]:
                text, ok = read_export(system_path, name)
                system_props[name] = {{"success": ok, "text": text}}
            handle_text = system_props["EmitterHandles"]["text"]
            names = re.findall(r'(?<!Id)Name="([^"]+)"', handle_text)
            id_names = re.findall(r'IdName="([^"]*)"', handle_text)
            enabled = re.findall(r'bIsEnabled=(True|False)', handle_text)
            emitter_paths = re.findall(r'Emitter="([^"]+)"', handle_text)
            live_renderers = versioned_renderers(system_path)
            emitters = []
            for index, emitter_path in enumerate(emitter_paths):
                props = {{}}
                for prop in ["SimTarget", "FixedBounds", "RendererProperties", "EventHandlerScriptProps"]:
                    text, ok = read_export(emitter_path, prop)
                    props[prop] = {{"success": ok, "text": text, "digest": digest(text)}}
                renderer_text = props["RendererProperties"]["text"]
                renderer_objects = parse_renderer_objects(renderer_text)
                emitter_name = names[index] if index < len(names) else ""
                normalized_emitter_path = emitter_path
                match = re.search(r"'([^']+)'", normalized_emitter_path)
                if match:
                    normalized_emitter_path = match.group(1)
                versioned_for_emitter = [
                    item for item in live_renderers
                    if item.get("emitter_name") == emitter_name or item.get("emitter_path") == normalized_emitter_path
                ]
                all_renderer_objects = renderer_objects + versioned_for_emitter
                renderers = sorted(set(
                    re.findall(r"Niagara([A-Za-z0-9_]+RendererProperties)", renderer_text)
                    + [
                        (item.get("class_name", "")[len("Niagara"):] if item.get("class_name", "").startswith("Niagara") else item.get("class_name", ""))
                        for item in all_renderer_objects
                        if item.get("class_name")
                    ]
                ))
                materials = sorted(set(
                    [path for item in renderer_objects for path in material_paths(item.get("material", {{}}).get("text", ""))]
                    + [item.get("material_path", "") for item in versioned_for_emitter if item.get("material_path")]
                ))
                emitters.append({{
                    "index": index,
                    "name": emitter_name,
                    "id_name": id_names[index] if index < len(id_names) else "",
                    "enabled": enabled[index] if index < len(enabled) else "",
                    "emitter_path": emitter_path,
                    "renderer_classes": renderers,
                    "renderer_materials": materials,
                    "renderer_objects": renderer_objects,
                    "versioned_renderer_objects": versioned_for_emitter,
                    "properties": props,
                }})
            return {{"system_path": system_path, "system_properties": system_props, "versioned_renderers": live_renderers, "emitters": emitters}}

        def match_emitter(emitter, op):
            name_blob = (emitter.get("name", "") + " " + emitter.get("id_name", "") + " " + emitter.get("emitter_path", "")).lower()
            name_tokens = [item.lower() for item in as_list(op.get("emitter_name_contains"))]
            if name_tokens and not any(token in name_blob for token in name_tokens):
                return False
            renderer_blob = (
                emitter.get("properties", {{}}).get("RendererProperties", {{}}).get("text", "")
                + " "
                + " ".join(emitter.get("renderer_classes", []))
            ).lower()
            renderer_tokens = [item.lower() for item in as_list(op.get("renderer_class_contains"))]
            if renderer_tokens and not any(token in renderer_blob for token in renderer_tokens):
                return False
            return True

        def patch_material_text(text, material_path, replace_all=False, material_regex=""):
            target = "Material=MaterialInterface'\\\"" + full_object_path(material_path) + "\\\"'"
            count = 0 if replace_all else 1
            if material_regex:
                new_text, hits = re.subn(material_regex, target, text, count=count)
                return new_text, hits
            patterns = [
                r"Material=MaterialInterface'\\\"[^\\\"]*\\\"'",
                r"Material=Material'\\\"[^\\\"]*\\\"'",
                r"Material=Object'\\\"[^\\\"]*\\\"'",
                r"Material=\\\"[^\\\"]*\\\"",
                r"Material=None",
            ]
            for pattern in patterns:
                new_text, hits = re.subn(pattern, target, text, count=count)
                if hits:
                    return new_text, hits
            return text, 0

        def duplicate_asset(op):
            source = op.get("source", "")
            target = op.get("target", "")
            if asset_exists(target):
                if op.get("reuse_if_exists", True):
                    return {{"success": True, "status": "exists", "target": target}}
                return {{"success": False, "error": "target already exists", "target": target}}
            source_asset = unreal.load_asset(source)
            if source_asset is None:
                return {{"success": False, "error": "source asset not found", "source": source}}
            folder, name = split_target(target)
            created = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, folder, source_asset)
            if created is None:
                return {{"success": False, "error": "duplicate_asset returned None", "target": target}}
            unreal.EditorAssetLibrary.save_asset(package_path(target), False)
            return {{"success": True, "status": "created", "target": full_object_path(target)}}

        def create_material_instance(op):
            parent = op.get("parent", "")
            target = op.get("target", "")
            if asset_exists(target):
                if not op.get("reuse_if_exists", True):
                    return {{"success": False, "error": "target already exists", "target": target}}
                status = "exists"
            else:
                result = MAT.create_material_instance(parent, target)
                if not result.success:
                    return {{"success": False, "error": result.error, "target": target, "parent": parent}}
                status = "created"
            params = op.get("params", [])
            param_result = None
            if params:
                param_result = MAT.set_mi_params(target, [make_mi_param(item) for item in params])
            unreal.EditorAssetLibrary.save_asset(package_path(target), False)
            return {{
                "success": True if param_result is None else bool(param_result.success),
                "status": status,
                "target": full_object_path(target),
                "param_result": None if param_result is None else {{"success": param_result.success, "applied": param_result.applied, "skipped": list(param_result.skipped)}},
            }}

        def add_emitter_to_system_from_asset(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            emitter_asset_path = op.get("emitter_asset_path", "")
            if not system_path or not emitter_asset_path:
                return {{"success": False, "error": "system_path and emitter_asset_path are required"}}
            official = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.AddEmitter",
                {{
                    "system": {{"refPath": full_object_path(system_path)}},
                    "templateEmitter": {{"refPath": full_object_path(emitter_asset_path)}},
                    "emitterName": op.get("new_emitter_name", ""),
                }},
            )
            if official.get("success"):
                snapshot = inspect_niagara_system(system_path)
                parsed = official.get("parsed_output") or {{}}
                emitter_name = (
                    parsed.get("returnValue", {{}}).get("emitterName")
                    or op.get("new_emitter_name", "")
                )
                emitter = find_emitter_snapshot(snapshot, emitter_name) or {{}}
                return {{
                    "success": True,
                    "route": "official-toolset",
                    "official_result": official,
                    "system_path": system_path,
                    "emitter_name": emitter_name,
                    "emitter_path": emitter.get("emitter_path", ""),
                    "renderer_classes": emitter.get("renderer_classes", []),
                    "renderer_materials": emitter.get("renderer_materials", []),
                }}
            result = unreal.UnrealBridgeNiagaraLibrary.add_emitter_to_system_from_asset(
                system_path,
                emitter_asset_path,
                op.get("new_emitter_name", ""),
                bool(op.get("create_copy", True)),
                bool(op.get("save_asset", True)),
            )
            return {{
                "success": bool(result.success),
                "route": "bridge-fallback",
                "official_result": official,
                "error": result.error,
                "system_path": result.system_path,
                "emitter_name": result.emitter_name,
                "emitter_path": result.emitter_path,
                "renderers": [r.export_text() for r in result.renderers],
                "emitter_graphs": [g.export_text() for g in result.emitter_graphs],
            }}

        def duplicate_emitter_in_system(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            source_emitter_name = op.get("source_emitter_name", "")
            if not system_path or not source_emitter_name:
                return {{"success": False, "error": "system_path and source_emitter_name are required"}}
            result = unreal.UnrealBridgeNiagaraLibrary.duplicate_emitter_in_system(
                system_path,
                source_emitter_name,
                op.get("new_emitter_name", ""),
                bool(op.get("save_asset", True)),
            )
            return {{
                "success": bool(result.success),
                "error": result.error,
                "system_path": result.system_path,
                "emitter_name": result.emitter_name,
                "emitter_path": result.emitter_path,
                "renderers": [r.export_text() for r in result.renderers],
                "emitter_graphs": [g.export_text() for g in result.emitter_graphs],
            }}

        def remove_emitter_from_system(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            emitter_name = op.get("emitter_name", "")
            if not system_path or not emitter_name:
                return {{"success": False, "error": "system_path and emitter_name are required"}}
            official = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.RemoveEmitter",
                {{
                    "emitterToRemove": {{
                        "system": {{"refPath": full_object_path(system_path)}},
                        "emitterName": emitter_name,
                        "scriptName": "",
                        "moduleName": "",
                        "rendererIndex": -1,
                        "inputNameStack": [],
                    }}
                }},
            )
            if official.get("success"):
                snapshot = inspect_niagara_system(system_path)
                still_exists = find_emitter_snapshot(snapshot, emitter_name) is not None
                return {{
                    "success": not still_exists,
                    "route": "official-toolset",
                    "official_result": official,
                    "system_path": system_path,
                    "emitter_name": emitter_name,
                    "still_exists": still_exists,
                    "error": "" if not still_exists else "Emitter still present after official remove route",
                }}
            result = unreal.UnrealBridgeNiagaraLibrary.remove_emitter_from_system(
                system_path,
                emitter_name,
                bool(op.get("save_asset", True)),
            )
            return {{
                "success": bool(result.success),
                "route": "bridge-fallback",
                "official_result": official,
                "error": result.error,
                "system_path": result.system_path,
                "emitter_name": result.emitter_name,
                "emitter_path": result.emitter_path,
                "renderers": [r.export_text() for r in result.renderers],
                "emitter_graphs": [g.export_text() for g in result.emitter_graphs],
            }}

        def set_emitter_enabled_in_system(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            emitter_name = op.get("emitter_name", "")
            if not system_path or not emitter_name or "enabled" not in op:
                return {{"success": False, "error": "system_path, emitter_name, and enabled are required"}}
            result = unreal.UnrealBridgeNiagaraLibrary.set_emitter_enabled_in_system(
                system_path,
                emitter_name,
                bool(op.get("enabled")),
                bool(op.get("save_asset", True)),
            )
            return {{
                "success": bool(result.success),
                "error": result.error,
                "system_path": result.system_path,
                "emitter_name": result.emitter_name,
                "emitter_path": result.emitter_path,
                "old_default_value": result.old_default_value,
                "new_default_value": result.new_default_value,
                "renderers": [r.export_text() for r in result.renderers],
                "emitter_graphs": [g.export_text() for g in result.emitter_graphs],
            }}

        def toolset_get_system_info(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            if not system_path:
                return {{"success": False, "error": "system_path is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_system_info_summary(system_path)
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "used_renderer_count": int(result.used_renderer_count),
                        "used_data_interface_count": int(result.used_data_interface_count),
                        "used_module_count": int(result.used_module_count),
                        "used_dynamic_input_count": int(result.used_dynamic_input_count),
                        "used_renderer_classes": [str(item) for item in result.used_renderer_classes],
                        "used_data_interface_classes": [str(item) for item in result.used_data_interface_classes],
                        "used_module_paths": [str(item) for item in result.used_module_paths],
                        "used_dynamic_input_paths": [str(item) for item in result.used_dynamic_input_paths],
                        "emitter_names": [str(item) for item in result.emitter_names],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetSystemInfo",
                {{"system": make_toolset_system_ref(system_path)}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            parsed = result.get("parsed_output") or {{}}
            info = parsed.get("returnValue", {{}})
            compact["system_path"] = system_path
            compact["used_renderer_count"] = len(info.get("usedRenderers", []) or [])
            compact["used_module_count"] = len(info.get("usedModules", []) or [])
            compact["used_dynamic_input_count"] = len(info.get("usedDynamicInputs", []) or [])
            compact["used_data_interface_count"] = len(info.get("usedDataInterfaces", []) or [])
            return compact

        def toolset_get_system_topology(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            if not system_path:
                return {{"success": False, "error": "system_path is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_system_topology_summary(system_path)
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "system_scripts": [
                            {{
                                "script_name": item.script_name,
                                "module_names": [str(name) for name in item.module_names],
                            }}
                            for item in result.system_scripts
                        ],
                        "emitters": [
                            {{
                                "emitter_name": item.emitter_name,
                                "scripts": [
                                    {{
                                        "script_name": script.script_name,
                                        "module_names": [str(name) for name in script.module_names],
                                    }}
                                    for script in item.scripts
                                ],
                                "renderer_classes": [str(name) for name in item.renderer_classes],
                            }}
                            for item in result.emitters
                        ],
                        "user_variable_names": [str(name) for name in result.user_variable_names],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetSystemTopology",
                {{"system": make_toolset_system_ref(system_path)}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            parsed = result.get("parsed_output") or {{}}
            topo = parsed.get("returnValue", {{}})
            emitters = topo.get("emitters", []) or []
            compact["system_path"] = system_path
            compact["emitter_count"] = len(emitters)
            compact["emitter_names"] = [item.get("emitterName", "") for item in emitters]
            return compact

        def toolset_get_emitter_topology(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            emitter_name = op.get("emitter_name", "")
            if not system_path or not emitter_name:
                return {{"success": False, "error": "system_path and emitter_name are required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_emitter_topology_summary(system_path, emitter_name)
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "scripts": [
                            {{
                                "script_name": item.script_name,
                                "module_names": [str(name) for name in item.module_names],
                            }}
                            for item in result.scripts
                        ],
                        "renderer_classes": [str(name) for name in result.renderer_classes],
                    }}
            stack_ref = {{
                "system": make_toolset_system_ref(system_path),
                "emitterName": emitter_name,
                "scriptName": "",
                "moduleName": "",
                "rendererIndex": -1,
                "inputNameStack": [],
            }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetEmitterTopology",
                {{"emitterRef": stack_ref}},
            )
            return compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))

        def toolset_get_module_topology(op):
            stack_ref = make_toolset_stack_ref(op, "module_ref")
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_module_topology(
                    stack_ref["system"]["refPath"],
                    stack_ref.get("emitterName", ""),
                    stack_ref.get("scriptName", ""),
                    stack_ref.get("moduleName", ""),
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "script_name": result.script_name,
                        "module_name": result.module_name,
                        "enabled": bool(result.enabled),
                        "is_set_parameters_module": bool(result.is_set_parameters_module),
                        "module_script_path": result.module_script_path,
                        "input_names": [str(item) for item in result.input_names],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetModuleTopology",
                {{"moduleRef": stack_ref}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            parsed = result.get("parsed_output") or {{}}
            topo = parsed.get("returnValue", {{}})
            compact["module_name"] = topo.get("moduleName", stack_ref.get("moduleName", ""))
            compact["enabled"] = topo.get("enabled")
            compact["input_names"] = [item.get("name", "") for item in topo.get("inputs", []) or []]
            return compact

        def toolset_get_stack_input_data(op):
            stack_ref = make_toolset_stack_ref(op, "stack_input_ref")
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_stack_input_data_summary(
                    stack_ref["system"]["refPath"],
                    stack_ref.get("emitterName", ""),
                    stack_ref.get("scriptName", ""),
                    stack_ref.get("moduleName", ""),
                    [str(item) for item in stack_ref.get("inputNameStack", [])],
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "script_name": result.script_name,
                        "module_name": result.module_name,
                        "input_name_stack": [str(name) for name in result.input_name_stack],
                        "is_visible": bool(result.is_visible),
                        "is_editable": bool(result.is_editable),
                        "type_name": result.type_name,
                        "type_path": result.type_path,
                        "data_struct_path": result.data_struct_path,
                        "data_json": result.data_json,
                        "dynamic_input_count": int(result.dynamic_input_count),
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetStackInputData",
                {{"stackInputRef": stack_ref}},
            )
            return compact_official_result(result, include_full_output=bool(op.get("include_full_output", True)))

        def toolset_set_stack_input_data(op):
            stack_ref = make_toolset_stack_ref(op, "stack_input_ref")
            input_data = op.get("input_data")
            if not isinstance(input_data, dict):
                return {{"success": False, "error": "input_data dict is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                struct_ref = str(input_data.get("struct", {{}}).get("refPath", "") or "")
                value_payload = input_data.get("value")
                if not struct_ref or value_payload is None:
                    return {{"success": False, "error": "input_data.struct.refPath and input_data.value are required for direct official stack input write"}}
                result = unreal.UnrealBridgeNiagaraLibrary.set_official_stack_input_data(
                    stack_ref["system"]["refPath"],
                    stack_ref.get("emitterName", ""),
                    stack_ref.get("scriptName", ""),
                    stack_ref.get("moduleName", ""),
                    [str(item) for item in stack_ref.get("inputNameStack", [])],
                    struct_ref,
                    json.dumps(value_payload, ensure_ascii=False),
                    bool(op.get("save_asset", True)),
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "script_name": result.script_name,
                        "module_name": result.module_name,
                        "input_name_stack": [str(name) for name in result.input_name_stack],
                        "is_visible": bool(result.is_visible),
                        "is_editable": bool(result.is_editable),
                        "type_name": result.type_name,
                        "type_path": result.type_path,
                        "data_struct_path": result.data_struct_path,
                        "data_json": result.data_json,
                        "dynamic_input_count": int(result.dynamic_input_count),
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.SetStackInputData",
                {{"stackInputRef": stack_ref, "inputData": input_data}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            compact["module_name"] = stack_ref.get("moduleName", "")
            compact["input_name_stack"] = stack_ref.get("inputNameStack", [])
            return compact

        def toolset_add_module(op):
            module_location_ref = make_toolset_stack_ref(op, "module_location_ref")
            module_asset_path = op.get("module_asset_path", "")
            if not module_asset_path:
                return {{"success": False, "error": "module_asset_path is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.add_official_module(
                    module_location_ref["system"]["refPath"],
                    module_location_ref.get("emitterName", ""),
                    module_location_ref.get("scriptName", ""),
                    module_location_ref.get("moduleName", ""),
                    module_asset_path,
                    bool(op.get("save_asset", True)),
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "script_name": result.script_name,
                        "module_name": result.module_name,
                        "enabled": bool(result.enabled),
                        "is_set_parameters_module": bool(result.is_set_parameters_module),
                        "module_script_path": result.module_script_path,
                        "input_names": [str(item) for item in result.input_names],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.AddModule",
                {{
                    "moduleLocationRef": module_location_ref,
                    "moduleAsset": {{"refPath": full_object_path(module_asset_path)}},
                }},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            parsed = result.get("parsed_output") or {{}}
            topo = parsed.get("returnValue", {{}})
            compact["module_name"] = topo.get("moduleName", "")
            compact["enabled"] = topo.get("enabled")
            compact["input_names"] = [item.get("name", "") for item in topo.get("inputs", []) or []]
            return compact

        def toolset_remove_module(op):
            module_ref = make_toolset_stack_ref(op, "module_ref")
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.remove_official_module(
                    module_ref["system"]["refPath"],
                    module_ref.get("emitterName", ""),
                    module_ref.get("scriptName", ""),
                    module_ref.get("moduleName", ""),
                    bool(op.get("save_asset", True)),
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "script_name": result.script_name,
                        "module_name": result.module_name,
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.RemoveModule",
                {{"moduleToRemove": module_ref}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            compact["module_name"] = module_ref.get("moduleName", "")
            return compact

        def toolset_set_module_enabled(op):
            module_ref = make_toolset_stack_ref(op, "module_ref")
            if "enabled" not in op:
                return {{"success": False, "error": "enabled is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.set_official_module_enabled(
                    module_ref["system"]["refPath"],
                    module_ref.get("emitterName", ""),
                    module_ref.get("scriptName", ""),
                    module_ref.get("moduleName", ""),
                    bool(op.get("enabled")),
                    bool(op.get("save_asset", True)),
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "emitter_name": result.emitter_name,
                        "script_name": result.script_name,
                        "module_name": result.module_name,
                        "enabled": bool(result.enabled),
                        "is_set_parameters_module": bool(result.is_set_parameters_module),
                        "module_script_path": result.module_script_path,
                        "input_names": [str(item) for item in result.input_names],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.SetModuleEnabled",
                {{"moduleRef": module_ref, "bEnabled": bool(op.get("enabled"))}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            compact["module_name"] = module_ref.get("moduleName", "")
            compact["enabled"] = bool(op.get("enabled"))
            return compact

        def toolset_get_system_compile_state(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            if not system_path:
                return {{"success": False, "error": "system_path is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_system_compile_state_summary(system_path)
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "aggregate_status": result.aggregate_status,
                        "is_compiling": bool(result.is_compiling),
                        "is_stale": bool(result.is_stale),
                        "has_errors": bool(result.has_errors),
                        "has_warnings": bool(result.has_warnings),
                        "scripts": [
                            {{
                                "emitter_name": item.emitter_name,
                                "script_name": item.script_name,
                                "last_compile_status": item.last_compile_status,
                                "error_summary": item.error_summary,
                                "compile_event_count": int(item.compile_event_count),
                                "error_event_count": int(item.error_event_count),
                                "warning_event_count": int(item.warning_event_count),
                            }}
                            for item in result.scripts
                        ],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetSystemCompileState",
                {{"system": make_toolset_system_ref(system_path)}},
            )
            return compact_official_result(result, include_full_output=bool(op.get("include_full_output", True)))

        def toolset_get_stack_issues(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            if not system_path:
                return {{"success": False, "error": "system_path is required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.get_official_stack_issues_summary(system_path)
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "num_errors": int(result.num_errors),
                        "num_warnings": int(result.num_warnings),
                        "num_infos": int(result.num_infos),
                        "issues": [
                            {{
                                "issue_id": item.issue_id,
                                "severity": item.severity,
                                "short_description": item.short_description,
                                "long_description": item.long_description,
                                "stack_display_path": item.stack_display_path,
                                "location_emitter_name": item.location_emitter_name,
                                "location_script_name": item.location_script_name,
                                "location_module_name": item.location_module_name,
                                "location_input_name_stack": [str(name) for name in item.location_input_name_stack],
                                "can_be_dismissed": bool(item.can_be_dismissed),
                                "is_dismissed": bool(item.is_dismissed),
                                "fixes": [
                                    {{
                                        "fix_id": fix.fix_id,
                                        "description": fix.description,
                                        "style": fix.style,
                                    }}
                                    for fix in item.fixes
                                ],
                            }}
                            for item in result.issues
                        ],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.GetStackIssues",
                {{"system": make_toolset_system_ref(system_path)}},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            parsed = result.get("parsed_output") or {{}}
            issues = parsed.get("returnValue", {{}})
            compact["num_errors"] = issues.get("numErrors", 0)
            compact["num_warnings"] = issues.get("numWarnings", 0)
            compact["num_infos"] = issues.get("numInfos", 0)
            compact["issue_ids"] = [item.get("issueId", "") for item in issues.get("issues", []) or []]
            return compact

        def toolset_apply_stack_issue_fix(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            issue_id = op.get("issue_id", "")
            fix_id = op.get("fix_id", "")
            if not system_path or not issue_id or not fix_id:
                return {{"success": False, "error": "system_path, issue_id, and fix_id are required"}}
            if hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                result = unreal.UnrealBridgeNiagaraLibrary.apply_official_stack_issue_fix(
                    system_path,
                    issue_id,
                    fix_id,
                    bool(op.get("save_asset", True)),
                )
                if result.success:
                    return {{
                        "success": True,
                        "route": "official-bridge-direct",
                        "system_path": result.system_path,
                        "issue_id": result.issue_id,
                        "fix_id": result.fix_id,
                        "applied": bool(result.applied),
                        "applied_fix_description": result.applied_fix_description,
                        "post_fix_issues_ready": bool(result.post_fix_issues_ready),
                        "post_fix_num_errors": int(result.post_fix_num_errors),
                        "post_fix_num_warnings": int(result.post_fix_num_warnings),
                        "post_fix_num_infos": int(result.post_fix_num_infos),
                        "post_fix_issue_ids": [str(item) for item in result.post_fix_issue_ids],
                    }}
            result = execute_toolset_qualified(
                "NiagaraToolsets.NiagaraToolset_System.ApplyStackIssueFix",
                {{
                    "system": make_toolset_system_ref(system_path),
                    "issueId": issue_id,
                    "fixId": fix_id,
                }},
            )
            compact = compact_official_result(result, include_full_output=bool(op.get("include_full_output", False)))
            parsed = result.get("parsed_output") or {{}}
            payload = parsed.get("returnValue", {{}})
            apply_result = payload.get("applyResult", {{}})
            post_fix = payload.get("postFixIssues", {{}})
            compact["applied"] = apply_result.get("bApplied")
            compact["applied_fix_description"] = apply_result.get("appliedFixDescription", "")
            compact["post_fix_num_errors"] = post_fix.get("numErrors", 0)
            compact["post_fix_num_warnings"] = post_fix.get("numWarnings", 0)
            return compact

        def set_mi_params(op):
            mi_path = op.get("material_instance", "")
            params = [make_mi_param(item) for item in op.get("params", [])]
            result = MAT.set_mi_params(mi_path, params)
            unreal.EditorAssetLibrary.save_asset(package_path(mi_path), False)
            return {{"success": bool(result.success), "applied": result.applied, "skipped": list(result.skipped), "target": mi_path}}

        def set_niagara_system_props(op):
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            system = unreal.load_asset(system_path)
            if system is None:
                return {{"success": False, "error": "system not found", "system_path": system_path}}
            results = {{}}
            effect_type_path = op.get("effect_type_path", "")
            if effect_type_path:
                effect_type = unreal.load_asset(effect_type_path)
                if effect_type is None:
                    results["EffectType"] = {{"success": False, "error": "effect type not found"}}
                else:
                    try:
                        system.set_editor_property("effect_type", effect_type)
                        results["EffectType"] = {{"success": True}}
                    except Exception as exc:
                        results["EffectType"] = {{"success": False, "error": str(exc)}}
            prop_map = {{
                "fixed_bounds": "FixedBounds",
                "warmup_tick_count": "WarmupTickCount",
                "warmup_tick_delta": "WarmupTickDelta",
                "system_scalability_overrides": "SystemScalabilityOverrides",
            }}
            for key, prop_name in prop_map.items():
                if key in op and op[key] not in (None, ""):
                    ok = PROP.set_u_property_from_export_text(system_path, prop_name, str(op[key]), True)
                    results[prop_name] = {{"success": bool(ok), "value": str(op[key])}}
            unreal.EditorAssetLibrary.save_asset(package_path(system_path), False)
            return {{"success": all(item.get("success", False) for item in results.values()) if results else True, "results": results, "system_path": system_path}}

        def patch_renderer_material(op):
            material_path = op.get("material_path", "")
            if not material_path:
                return {{"success": False, "error": "material_path is required"}}
            emitter_paths = as_list(op.get("emitter_path"))
            matched = []
            if not emitter_paths:
                snapshot = inspect_niagara_system(op.get("system_path") or PLAN.get("target_system", ""))
                for emitter in snapshot.get("emitters", []):
                    if match_emitter(emitter, op):
                        emitter_paths.append(emitter["emitter_path"])
                        matched.append({{"name": emitter.get("name", ""), "emitter_path": emitter["emitter_path"]}})
            changed = []
            failed = []
            for emitter_path in emitter_paths:
                renderer_text, ok = read_export(emitter_path, "RendererProperties")
                if not ok or not renderer_text:
                    failed.append({{"emitter_path": emitter_path, "error": "RendererProperties not readable"}})
                    continue
                new_text, hits = patch_material_text(renderer_text, material_path, bool(op.get("replace_all", False)), op.get("material_regex", ""))
                if not hits:
                    if op.get("allow_noop", False):
                        changed.append({{"emitter_path": emitter_path, "status": "no material slot found", "hits": 0}})
                    else:
                        failed.append({{"emitter_path": emitter_path, "error": "no material slot found", "renderer_digest": digest(renderer_text)}})
                    continue
                ok = PROP.set_u_property_from_export_text(emitter_path, "RendererProperties", new_text, True)
                if ok:
                    unreal.EditorAssetLibrary.save_asset(package_path(emitter_path), False)
                    changed.append({{"emitter_path": emitter_path, "hits": hits, "material": full_object_path(material_path)}})
                else:
                    failed.append({{"emitter_path": emitter_path, "error": "RendererProperties write failed"}})
            return {{"success": bool(changed) and not failed, "matched": matched, "changed": changed, "failed": failed}}

        def add_ribbon_renderer(op):
            material_path = op.get("material_path", "")
            if not material_path:
                return {{"success": False, "error": "material_path is required"}}
            material = unreal.load_asset(material_path)
            if material is None:
                return {{"success": False, "error": "material not found", "material_path": material_path}}
            ribbon_cls = unreal.load_class(None, "/Script/Niagara.NiagaraRibbonRendererProperties")
            if ribbon_cls is None:
                return {{"success": False, "error": "NiagaraRibbonRendererProperties class not found"}}
            emitter_paths = as_list(op.get("emitter_path"))
            matched = []
            if not emitter_paths:
                snapshot = inspect_niagara_system(op.get("system_path") or PLAN.get("target_system", ""))
                for emitter in snapshot.get("emitters", []):
                    if match_emitter(emitter, op):
                        emitter_paths.append(emitter["emitter_path"])
                        matched.append({{"name": emitter.get("name", ""), "emitter_path": emitter["emitter_path"]}})
            system_path = op.get("system_path") or PLAN.get("target_system", "")
            snapshot_for_names = inspect_niagara_system(system_path) if system_path else {{"emitters": []}}
            name_by_path = {{
                item.get("emitter_path", ""): item.get("name", "")
                for item in snapshot_for_names.get("emitters", [])
            }}
            changed = []
            failed = []
            for emitter_path in emitter_paths:
                emitter_name = op.get("emitter_name") or name_by_path.get(emitter_path, "")
                if hasattr(unreal, "UnrealBridgeNiagaraLibrary") and system_path and emitter_name:
                    result = unreal.UnrealBridgeNiagaraLibrary.add_ribbon_renderer_to_emitter(
                        system_path,
                        emitter_name,
                        material_path,
                        op.get("renderer_name") or "CodexRibbonRenderer",
                        op.get("facing_mode") or "Screen",
                        int(op.get("width_segmentation_count") or 1),
                        float(op.get("curve_tension") or 0.0),
                        True,
                        bool(op.get("allow_existing", False)),
                    )
                    if result.success:
                        changed.append({{
                            "emitter_path": result.emitter_path,
                            "emitter_name": result.emitter_name,
                            "renderer_path": result.renderer_path,
                            "material": result.material_path,
                            "route": "versioned-emitter-data",
                        }})
                    else:
                        failed.append({{
                            "emitter_path": emitter_path,
                            "emitter_name": emitter_name,
                            "error": result.error,
                            "route": "versioned-emitter-data",
                        }})
                    continue
                emitter_obj_path = full_object_path(emitter_path)
                emitter = unreal.load_object(None, emitter_obj_path)
                if emitter is None:
                    failed.append({{"emitter_path": emitter_path, "error": "emitter not found"}})
                    continue
                existing_text, existing_ok = read_export(emitter_path, "RendererProperties")
                if existing_ok and existing_text.strip() and not op.get("allow_existing", False):
                    failed.append({{"emitter_path": emitter_path, "error": "RendererProperties already contains renderer data", "renderer_digest": digest(existing_text)}})
                    continue
                renderer_name = op.get("renderer_name") or "CodexRibbonRenderer"
                renderer = unreal.new_object(ribbon_cls, outer=emitter, name=renderer_name)
                if renderer is None:
                    failed.append({{"emitter_path": emitter_path, "error": "new_object returned None"}})
                    continue
                renderer.set_editor_property("material", material)
                renderer_path = renderer.get_path_name()
                prop_values = {{
                    "FacingMode": op.get("facing_mode", ""),
                    "MaxNumRibbons": op.get("max_num_ribbons", ""),
                    "WidthSegmentationCount": op.get("width_segmentation_count", ""),
                    "CurveTension": op.get("curve_tension", ""),
                }}
                prop_results = {{}}
                for prop_name, value in prop_values.items():
                    if value not in (None, ""):
                        prop_results[prop_name] = bool(PROP.set_u_property_from_export_text(renderer_path, prop_name, str(value), True))
                ok = PROP.array_append_u_property(emitter_path, "RendererProperties", renderer_path, True)
                if ok:
                    unreal.EditorAssetLibrary.save_asset(package_path(emitter_path), False)
                    changed.append({{"emitter_path": emitter_path, "renderer_path": renderer_path, "material": full_object_path(material_path), "prop_results": prop_results, "route": "deprecated-renderer-properties"}})
                else:
                    failed.append({{"emitter_path": emitter_path, "renderer_path": renderer_path, "error": "RendererProperties append failed", "prop_results": prop_results}})
            return {{"success": bool(changed) and not failed, "matched": matched, "changed": changed, "failed": failed}}

        def set_u_property_export(op):
            target = op.get("object_path", "")
            prop = op.get("property_path", "")
            value = str(op.get("export_text", ""))
            ok = PROP.set_u_property_from_export_text(target, prop, value, bool(op.get("fire_change_notify", True)))
            if ok and op.get("save", True):
                unreal.EditorAssetLibrary.save_asset(package_path(target), False)
            return {{"success": bool(ok), "object_path": target, "property_path": prop}}

        def save_assets(op):
            results = {{}}
            for path in op.get("asset_paths", []):
                results[path] = bool(unreal.EditorAssetLibrary.save_asset(package_path(path), False))
            return {{"success": all(results.values()) if results else True, "results": results}}

        HANDLERS = {{
            "duplicate_asset": duplicate_asset,
            "create_material_instance": create_material_instance,
            "add_emitter_to_system_from_asset": add_emitter_to_system_from_asset,
            "duplicate_emitter_in_system": duplicate_emitter_in_system,
            "remove_emitter_from_system": remove_emitter_from_system,
            "set_emitter_enabled_in_system": set_emitter_enabled_in_system,
            "toolset_get_system_info": toolset_get_system_info,
            "toolset_get_system_topology": toolset_get_system_topology,
            "toolset_get_emitter_topology": toolset_get_emitter_topology,
            "toolset_get_module_topology": toolset_get_module_topology,
            "toolset_get_stack_input_data": toolset_get_stack_input_data,
            "toolset_set_stack_input_data": toolset_set_stack_input_data,
            "toolset_add_module": toolset_add_module,
            "toolset_remove_module": toolset_remove_module,
            "toolset_set_module_enabled": toolset_set_module_enabled,
            "toolset_get_system_compile_state": toolset_get_system_compile_state,
            "toolset_get_stack_issues": toolset_get_stack_issues,
            "toolset_apply_stack_issue_fix": toolset_apply_stack_issue_fix,
            "add_ribbon_renderer": add_ribbon_renderer,
            "set_mi_params": set_mi_params,
            "set_niagara_system_props": set_niagara_system_props,
            "patch_renderer_material": patch_renderer_material,
            "set_u_property_export": set_u_property_export,
            "save_assets": save_assets,
        }}

        operation_results = []
        for index, op in enumerate(PLAN.get("operations", [])):
            kind = op.get("op")
            operation_enabled = op.get("operation_enabled")
            if operation_enabled is None and kind not in SEMANTIC_ENABLED_OPS:
                operation_enabled = op.get("enabled", True)
            if operation_enabled is False:
                operation_results.append({{"index": index, "op": op.get("op"), "success": True, "status": "disabled"}})
                continue
            handler = HANDLERS.get(kind)
            if handler is None:
                operation_results.append({{"index": index, "op": kind, "success": False, "error": "unsupported operation"}})
                continue
            try:
                result = handler(op)
                result["index"] = index
                result["op"] = kind
                operation_results.append(result)
            except Exception as exc:
                operation_results.append({{"index": index, "op": kind, "success": False, "error": str(exc)}})

        verification = None
        if {str(bool(verify))}:
            target_system = PLAN.get("target_system", "")
            if target_system:
                try:
                    verification = inspect_niagara_system(target_system)
                except Exception as exc:
                    verification = {{"success": False, "error": str(exc)}}

        payload = {{
            "success": all(item.get("success", False) for item in operation_results),
            "plan_effect": PLAN.get("effect_name", ""),
            "target_system": PLAN.get("target_system", ""),
            "operation_results": operation_results,
            "verification": verification,
        }}
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


def append_template_layer_ops(
    plan: dict[str, Any],
    layers: list[dict[str, Any]],
    folder_root: str,
    default_parent: str,
    parent_map: dict[str, str],
    default_params: list[dict[str, str]],
) -> None:
    material_paths: list[str] = []
    for layer in layers:
        renderers = [str(item) for item in layer.get("renderers", [])]
        parent = pick_parent_for_renderers(renderers, default_parent, parent_map)
        if not parent:
            plan["warnings"].append(f"No material parent supplied for layer `{layer.get('layer_name', '')}`.")
            continue
        layer_name = str(layer.get("layer_name", "Layer"))
        layer_emitters = [str(item) for item in layer.get("emitters", [])]
        materials = layer.get("materials", []) or [{"instance": f"MI_{asset_token(plan['effect_name'])}_{asset_token(layer_name)}"}]
        for material in materials:
            instance_name = str(material.get("instance") or material.get("name") or f"MI_{asset_token(plan['effect_name'])}_{asset_token(layer_name)}")
            mi_path = f"{folder_root.rstrip('/')}/Materials/{instance_name}"
            material_paths.append(mi_path)
            plan["operations"].append(
                {
                    "op": "create_material_instance",
                    "parent": parent,
                    "target": mi_path,
                    "reuse_if_exists": True,
                    "params": default_params,
                    "reason": f"Create tunable material instance for layer {layer_name}.",
                }
            )
            plan["operations"].append(
                {
                    "op": "patch_renderer_material",
                    "system_path": plan["target_system"],
                    "emitter_name_contains": [layer_name, asset_token(layer_name), *layer_emitters],
                    "renderer_class_contains": renderers,
                    "material_path": mi_path,
                    "replace_all": False,
                    "allow_noop": False,
                    "reason": f"Bind layer material to matching Niagara renderer for {layer_name}.",
                }
            )
    if material_paths:
        plan["operations"].append({"op": "save_assets", "asset_paths": [plan["target_system"], *material_paths]})


def plan_template_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    asset_plan = load_effect_record(ctx, "asset-plans", args.effect, asset_plan_default(args.effect))
    target_system = args.target_system or f"{asset_plan.get('naming', {}).get('folder_root', '/Game/VFX').rstrip('/')}/{asset_plan.get('naming', {}).get('system_name', 'NS_' + asset_token(args.effect))}"
    folder_root = args.folder_root or asset_plan.get("naming", {}).get("folder_root") or asset_folder_from_path(target_system)
    plan = make_plan(args.effect, "create-from-template", target_system, args.project or "", args.notes)
    if args.template_system:
        plan["operations"].append(
            {
                "op": "duplicate_asset",
                "source": args.template_system,
                "target": target_system,
                "reuse_if_exists": args.reuse_existing,
                "reason": "Template-first Niagara creation keeps emitter graphs and renderer setup valid.",
            }
        )
    if args.fixed_bounds or args.warmup_tick_count is not None or args.warmup_tick_delta is not None or args.effect_type_path:
        op: dict[str, Any] = {"op": "set_niagara_system_props", "system_path": target_system}
        if args.effect_type_path:
            op["effect_type_path"] = args.effect_type_path
        if args.fixed_bounds:
            op["fixed_bounds"] = args.fixed_bounds
        if args.warmup_tick_count is not None:
            op["warmup_tick_count"] = args.warmup_tick_count
        if args.warmup_tick_delta is not None:
            op["warmup_tick_delta"] = args.warmup_tick_delta
        plan["operations"].append(op)
    layers = asset_plan.get("assets", {}).get("layers", [])
    append_template_layer_ops(
        plan,
        layers,
        folder_root,
        args.material_parent,
        renderer_parent_map(args.material_parent_by_renderer),
        parse_param_set(args.mi_param),
    )
    if not layers:
        plan["warnings"].append("No asset-plan layers found; generated only template/system operations.")
    out = Path(args.out) if args.out else plan_path(ctx, args.effect)
    save_plan(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_plan_markdown(plan))
    print(out)
    return 0


def repair_plan_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    target_system = args.target_system or audit.get("system_path", "")
    effect = args.effect or slugify(target_system)
    plan = make_plan(effect, "repair-existing", target_system, args.project or "", args.notes)
    if args.fixed_bounds and any("FixedBounds" in item for item in audit.get("warnings", [])):
        plan["operations"].append({"op": "set_niagara_system_props", "system_path": target_system, "fixed_bounds": args.fixed_bounds})
    parent_map = renderer_parent_map(args.material_by_renderer)
    for emitter in audit.get("emitters", []):
        parsed = emitter.get("parsed", {})
        renderers = parsed.get("renderer_classes", [])
        materials = parsed.get("renderer_materials", [])
        if materials:
            continue
        renderer_text = emitter.get("properties", {}).get("RendererProperties", {}).get("text", "")
        has_any_renderer = bool(renderers or renderer_text.strip())
        if not has_any_renderer:
            role = str(emitter.get("role", "")).lower()
            if role in {"receiver", "trail-receiver"}:
                material = args.default_material or pick_parent_for_renderers(renderers, "", parent_map)
                if material:
                    plan["operations"].append(
                        {
                            "op": "add_ribbon_renderer",
                            "system_path": target_system,
                            "emitter_name": emitter.get("name", ""),
                            "emitter_path": emitter.get("emitter_path", ""),
                            "material_path": material,
                            "renderer_name": args.renderer_name,
                            "facing_mode": args.facing_mode,
                            "max_num_ribbons": args.max_num_ribbons,
                            "width_segmentation_count": args.width_segmentation_count,
                            "curve_tension": args.curve_tension,
                            "reason": f"Create missing Ribbon Renderer on receiver emitter {emitter.get('name', '')}.",
                        }
                    )
                    continue
                plan["warnings"].append(
                    f"Skipped receiver `{emitter.get('name', '')}` with empty RendererProperties because no material was supplied."
                )
                continue
            plan["warnings"].append(
                f"Skipped emitter `{emitter.get('name', '')}` because RendererProperties is empty; material binding repair needs an existing renderer slot."
            )
            continue
        if not renderer_text.strip() and renderers:
            plan["warnings"].append(
                f"Emitter `{emitter.get('name', '')}` has versioned renderers `{', '.join(renderers)}`; material patching for existing versioned renderer slots is not automatic yet."
            )
            continue
        material = pick_parent_for_renderers(renderers, args.default_material, parent_map)
        if not material:
            plan["warnings"].append(
                f"Skipped emitter `{emitter.get('name', '')}` because no default material was supplied for renderers `{', '.join(renderers) or 'unknown'}`."
            )
            continue
        plan["operations"].append(
            {
                "op": "patch_renderer_material",
                "system_path": target_system,
                "emitter_path": emitter.get("emitter_path", ""),
                "renderer_class_contains": renderers,
                "material_path": material,
                "replace_all": False,
                "allow_noop": False,
                "reason": f"Repair missing renderer material on emitter {emitter.get('name', '')}.",
            }
        )
    if not plan["operations"]:
        plan["warnings"].append("No automatic repairs were inferred from the audit and supplied defaults.")
    out = Path(args.out) if args.out else plan_path(ctx, effect, "repair-plan")
    save_plan(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_plan_markdown(plan))
    print(out)
    return 0


def new_plan_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = make_plan(args.effect, args.mode, args.target_system, args.project or "", args.notes)
    for op_json in args.op_json:
        op = json.loads(op_json)
        if op.get("op") not in SUPPORTED_OPS:
            raise ValueError(f"Unsupported operation: {op.get('op')}")
        plan["operations"].append(op)
    out = Path(args.out) if args.out else plan_path(ctx, args.effect)
    save_plan(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_plan_markdown(plan))
    print(out)
    return 0


def render_script_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = load_plan(args.plan)
    target = Path(args.out) if args.out else script_path(ctx, plan.get("effect_name", "effect"))
    write_text(target, build_apply_script(plan, args.verify))
    print(target)
    return 0


def resolve_apply_delivery_payload(ctx, args: argparse.Namespace, plan: dict[str, Any]) -> tuple[dict[str, Any] | None, Path | None]:
    if args.delivery_index and args.delivery_manifest:
        raise SystemExit("Provide only one of --delivery-index or --delivery-manifest.")
    if args.delivery_index or args.delivery_manifest:
        payload_path = Path(args.delivery_index or args.delivery_manifest)
        return load_delivery_payload(payload_path), payload_path
    effect_name = str(args.delivery_effect or plan.get("effect_name", "") or "")
    if args.require_delivery_ready:
        if not effect_name:
            raise SystemExit("--require-delivery-ready needs --delivery-effect or a plan effect_name.")
        payload_path = find_latest_delivery_index(ctx, effect_name)
        if payload_path is None:
            raise SystemExit(f"No delivery-index.json found for effect `{effect_name}`.")
        return load_delivery_payload(payload_path), payload_path
    if args.delivery_effect:
        payload_path = find_latest_delivery_index(ctx, effect_name)
        if payload_path is None:
            raise SystemExit(f"No delivery-index.json found for effect `{effect_name}`.")
        return load_delivery_payload(payload_path), payload_path
    return None, None


def auto_package_final_systems(args: argparse.Namespace, plan: dict[str, Any]) -> list[str]:
    systems = list(args.final_system or [])
    target_system = str(plan.get("target_system", "") or "")
    if not systems and target_system:
        systems.append(target_system)
    return systems


def run_post_apply_delivery_pipeline(ctx, args: argparse.Namespace, plan: dict[str, Any]) -> tuple[int, Path | None]:
    effect_name = str(args.package_effect or args.delivery_effect or plan.get("effect_name", "") or "")
    if not effect_name:
        raise SystemExit("--auto-delivery-package needs --package-effect, --delivery-effect, or a plan effect_name.")
    final_systems = auto_package_final_systems(args, plan)
    if not final_systems:
        raise SystemExit("--auto-delivery-package needs at least one --final-system or a plan target_system.")
    project = args.project or plan.get("project") or None
    for system_path in final_systems:
        niagara_audit_module.command(
            argparse.Namespace(
                system_path=system_path,
                root=args.root,
                project=project,
                endpoint=args.endpoint,
                timeout=args.timeout,
                out="",
                markdown=True,
            )
        )
    package_args = argparse.Namespace(
        root=args.root,
        effect=effect_name,
        asset=list(args.asset or []),
        final_system=final_systems,
        final_material=list(args.final_material or []),
        effect_type_contract=args.effect_type_contract,
        require_niagara_renderer=list(args.require_niagara_renderer or []),
        require_niagara_material=list(args.require_niagara_material or []),
        require_attribute_reader_data_flow=args.require_attribute_reader_data_flow,
        require_niagara_bounds=args.require_niagara_bounds,
        forbid_test_emitter=args.forbid_test_emitter,
        require_visual_qa=args.require_visual_qa,
        max_visual_mean_diff=args.max_visual_mean_diff,
        max_visual_edge_mean_diff=args.max_visual_edge_mean_diff,
        max_visual_mask_delta=args.max_visual_mask_delta,
        low_end_note=args.low_end_note,
        risk=list(args.risk or []),
        notes=args.package_notes or "Auto-generated after niagara_asset_assistant apply-plan.",
        require_ready=args.require_ready_after_package,
    )
    code = delivery_package_module.package_command(package_args)
    index_path = find_latest_delivery_index(ctx, effect_name)
    if args.require_ready_after_package and index_path:
        payload = load_delivery_payload(index_path)
        gate_code = check_delivery_payload(payload, require_ready=True)
        code = code or gate_code
    return code, index_path


def apply_plan_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = load_plan(args.plan)
    effect_name = str(plan.get("effect_name", "") or "")
    if effect_name:
        anchor_lock = load_effect_record(ctx, "reference-acceptance", effect_name, acceptance_default(effect_name)).get("anchor_lock", {})
        if not str(anchor_lock.get("entry_id", "") or "").strip():
            raise SystemExit("Reference gate failed before apply-plan: no locked anchor.")
        if not bool(anchor_lock.get("scope_confirmed", False)):
            raise SystemExit("Reference gate failed before apply-plan: scope not confirmed.")
        if not str(anchor_lock.get("implementation_scope", "") or "").strip():
            raise SystemExit("Reference gate failed before apply-plan: implementation scope missing.")
        if not str(anchor_lock.get("cached_path", "") or "").strip():
            raise SystemExit("Reference gate failed before apply-plan: cached anchor path missing.")
    delivery_payload, delivery_payload_path = resolve_apply_delivery_payload(ctx, args, plan)
    effective_verify = bool(args.verify or args.apply)
    script_text = build_apply_script(plan, effective_verify)
    script_out = Path(args.script_out) if args.script_out else script_path(ctx, plan.get("effect_name", "effect"))
    write_text(script_out, script_text)
    if args.markdown:
        write_text(Path(args.plan).with_suffix(".md"), render_plan_markdown(plan))
    if not args.apply:
        print(json.dumps({
            "dry_run": True,
            "script": str(script_out),
            "operations": len(plan.get("operations", [])),
            "verify": effective_verify,
            "delivery_ready_gate": {
                "enabled": bool(delivery_payload),
                "payload": str(delivery_payload_path or ""),
                "enforced_on_apply": bool(delivery_payload),
            },
        }, ensure_ascii=False))
        return 0
    client = BridgeClient(ctx.skill_root, project=args.project or plan.get("project") or None, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    result = client.exec_json(script_text, no_preflight=True)
    out = Path(args.out) if args.out else result_path(ctx, plan.get("effect_name", "effect"))
    save_json(out, result)
    print(out)
    if not bool(result.get("success", False)):
        print(f"Niagara apply-plan failed verification/operation success; result saved to {out}")
        return 1
    if delivery_payload:
        code = check_delivery_payload(delivery_payload, require_ready=True)
        if code != 0:
            return code
        print(f"Delivery ready gate passed: {delivery_payload_path}")
    if args.auto_delivery_package:
        code, index_path = run_post_apply_delivery_pipeline(ctx, args, plan)
        if index_path:
            print(f"Auto delivery package index: {index_path}")
        if code != 0:
            return code
    return 0


def inspect_system_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = make_plan(args.effect or slugify(args.system_path), "inspect-only", args.system_path, args.project or "", "")
    script_text = build_apply_script(plan, verify=True)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    result = client.exec_json(script_text, no_preflight=True)
    out = Path(args.out) if args.out else default_report_path(ctx, "ue-inspect", slugify(args.system_path), "niagara-system-inspect", ".json")
    save_json(out, result.get("verification") or result)
    print(out)
    return 0


def export_md_command(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan)
    out = Path(args.out) if args.out else Path(args.plan).with_suffix(".md")
    write_text(out, render_plan_markdown(plan))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, repair, dry-run, and apply safe Niagara asset mutation plans.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_template = subparsers.add_parser("plan-template")
    plan_template.add_argument("--effect", required=True)
    plan_template.add_argument("--template-system", default="")
    plan_template.add_argument("--target-system", default="")
    plan_template.add_argument("--folder-root", default="")
    plan_template.add_argument("--material-parent", default="")
    plan_template.add_argument("--material-parent-by-renderer", action="append", default=[], help="Renderer=/Game/Path/M_Master")
    plan_template.add_argument("--mi-param", action="append", default=[], help="Name=Type=Value, for example Intensity=Scalar=1.0")
    plan_template.add_argument("--effect-type-path", default="")
    plan_template.add_argument("--fixed-bounds", default="")
    plan_template.add_argument("--warmup-tick-count", type=int)
    plan_template.add_argument("--warmup-tick-delta", type=float)
    plan_template.add_argument("--reuse-existing", action="store_true")
    plan_template.add_argument("--project", default="")
    plan_template.add_argument("--notes", default="")
    plan_template.add_argument("--out")
    plan_template.add_argument("--markdown", action="store_true")
    plan_template.set_defaults(func=plan_template_command)

    repair = subparsers.add_parser("repair-plan")
    repair.add_argument("--audit", required=True)
    repair.add_argument("--effect", default="")
    repair.add_argument("--target-system", default="")
    repair.add_argument("--default-material", default="")
    repair.add_argument("--material-by-renderer", action="append", default=[], help="Renderer=/Game/Path/MI_Fix")
    repair.add_argument("--fixed-bounds", default="")
    repair.add_argument("--renderer-name", default="CodexRibbonRenderer")
    repair.add_argument("--facing-mode", default="Screen")
    repair.add_argument("--max-num-ribbons", default="")
    repair.add_argument("--width-segmentation-count", default="1")
    repair.add_argument("--curve-tension", default="0.0")
    repair.add_argument("--project", default="")
    repair.add_argument("--notes", default="")
    repair.add_argument("--out")
    repair.add_argument("--markdown", action="store_true")
    repair.set_defaults(func=repair_plan_command)

    new_plan = subparsers.add_parser("new-plan")
    new_plan.add_argument("--effect", required=True)
    new_plan.add_argument("--mode", default="manual")
    new_plan.add_argument("--target-system", required=True)
    new_plan.add_argument("--project", default="")
    new_plan.add_argument("--notes", default="")
    new_plan.add_argument("--op-json", action="append", default=[])
    new_plan.add_argument("--out")
    new_plan.add_argument("--markdown", action="store_true")
    new_plan.set_defaults(func=new_plan_command)

    render = subparsers.add_parser("render-script")
    render.add_argument("--plan", required=True)
    render.add_argument("--out")
    render.add_argument("--verify", action="store_true")
    render.set_defaults(func=render_script_command)

    apply_plan = subparsers.add_parser("apply-plan")
    apply_plan.add_argument("--plan", required=True)
    apply_plan.add_argument("--project", default="")
    apply_plan.add_argument("--endpoint")
    apply_plan.add_argument("--timeout", type=int, default=240)
    apply_plan.add_argument("--script-out")
    apply_plan.add_argument("--out")
    apply_plan.add_argument("--verify", action="store_true")
    apply_plan.add_argument("--markdown", action="store_true")
    apply_plan.add_argument("--delivery-index", default="", help="Existing delivery-index.json that must be ready after apply.")
    apply_plan.add_argument("--delivery-manifest", default="", help="Existing delivery manifest.json that must be ready after apply.")
    apply_plan.add_argument("--delivery-effect", default="", help="Find the latest delivery-index.json for this effect and require it to be ready.")
    apply_plan.add_argument("--require-delivery-ready", action="store_true", help="Use the plan effect_name or --delivery-effect to require a ready delivery index.")
    apply_plan.add_argument("--auto-delivery-package", action="store_true", help="After apply, rerun Niagara audit, rebuild delivery package, and optionally require ready.")
    apply_plan.add_argument("--package-effect", default="", help="Effect name for --auto-delivery-package; defaults to delivery-effect or plan effect_name.")
    apply_plan.add_argument("--final-system", action="append", default=[], help="Final Niagara system to audit/package after apply. Defaults to plan target_system.")
    apply_plan.add_argument("--final-material", action="append", default=[], help="Final material path to include in delivery package.")
    apply_plan.add_argument("--asset", action="append", default=[], help="Active texture/source asset to include in delivery package.")
    apply_plan.add_argument("--effect-type-contract", default="", choices=delivery_package_module.effect_type_names())
    apply_plan.add_argument("--require-niagara-renderer", action="append", default=[])
    apply_plan.add_argument("--require-niagara-material", action="append", default=[])
    apply_plan.add_argument("--require-attribute-reader-data-flow", action="store_true")
    apply_plan.add_argument("--require-niagara-bounds", action="store_true")
    apply_plan.add_argument("--forbid-test-emitter", action="store_true")
    apply_plan.add_argument("--require-visual-qa", action="store_true")
    apply_plan.add_argument("--max-visual-mean-diff", type=float, default=64.0)
    apply_plan.add_argument("--max-visual-edge-mean-diff", type=float, default=48.0)
    apply_plan.add_argument("--max-visual-mask-delta", type=float, default=0.35)
    apply_plan.add_argument("--low-end-note", default="")
    apply_plan.add_argument("--risk", action="append", default=[])
    apply_plan.add_argument("--package-notes", default="")
    apply_plan.add_argument("--require-ready-after-package", action="store_true")
    apply_plan.add_argument("--apply", action="store_true", help="Actually execute the generated script through unreal-bridge.")
    apply_plan.set_defaults(func=apply_plan_command)

    inspect = subparsers.add_parser("inspect-system")
    inspect.add_argument("system_path")
    inspect.add_argument("--effect", default="")
    inspect.add_argument("--project")
    inspect.add_argument("--endpoint")
    inspect.add_argument("--timeout", type=int, default=180)
    inspect.add_argument("--out")
    inspect.set_defaults(func=inspect_system_command)

    export_md = subparsers.add_parser("export-md")
    export_md.add_argument("--plan", required=True)
    export_md.add_argument("--out")
    export_md.set_defaults(func=export_md_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(
        argv,
        known_subcommands={"plan-template", "repair-plan", "new-plan", "render-script", "apply-plan", "inspect-system", "export-md"},
        global_opts_with_value={"--root"},
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
